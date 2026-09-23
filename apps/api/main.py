import os
import json
import csv
import io
from datetime import date
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.responses import Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, HttpUrl
import psycopg

from db import get_conn, ensure_delivery_schema
from qualification import score_opportunity, map_to_service_opportunities
from website_analyzer import analyze_website
from delivery import generate_project, validate_project, package_project, deploy_static, check_live_url
from project_options import option_definitions, validate_options, option_summary
from requirements import compile_requirements
from revenue import revenue_summary, service_performance
from workflows import workflow_definition, next_step
from integrations import providers, suggestions_for_service, provider_setup
from security import authenticate, can, PUBLIC_PATHS
from portal import create_token, hash_token
from auth import hash_password, verify_password, issue_token
from scheduler import next_run
from oauth import authorization_url, verify_state, token_request
from client_trust import assess_opportunity, outreach_disposition, should_expand
from secret_backend import backend as secret_backend
from provider_adapters import get_adapter
from evidence_engine import build_claim, evidence_strength
from policy_engine import evaluate_action, normalize_policy
from economics import unit_economics
from service_blueprints import blueprint, instantiate
from action_receipts import make_receipt
from checkpoints import checkpoint_state
from agent_gateway import catalog as agent_tool_catalog, resolve as resolve_agent_tool
from provider_runtime import execute_integration, provider_status
from blueprint_optimizer import propose
from voice import voice_capabilities, disclosure_text, twilio_gather_twiml, twilio_stream_twiml, validate_twilio_signature, realtime_bridge, VOICE_MODES

app = FastAPI(title="Luma API", version="0.8.0")


@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    path=request.url.path
    if path in PUBLIC_PATHS and path not in {"/auth/login","/integrations/oauth"}:
        return await call_next(request)

    api_key=request.headers.get("X-Luma-Key")
    authorization=request.headers.get("Authorization","")
    bearer=authorization[7:] if authorization.lower().startswith("bearer ") else None
    principal=authenticate(api_key,bearer)
    if not principal and path not in {"/auth/login"} and not path.startswith("/integrations/oauth/"):
        return JSONResponse(status_code=401, content={"detail":"Authentication required"})

    # PostgreSQL-backed fixed windows are shared by every API replica.
    # The limiter is route-aware for public auth/OAuth endpoints and identity-aware
    # after authentication. Forwarded headers are intentionally ignored here.
    if DATABASE_URL and path != "/health":
        import time
        from datetime import datetime, timezone, timedelta
        is_auth=path=="/auth/login"
        is_oauth=path.startswith("/integrations/oauth/")
        limit=int(os.getenv("LUMA_RATE_LIMIT_AUTH_PER_MINUTE" if is_auth else "LUMA_RATE_LIMIT_OAUTH_PER_MINUTE" if is_oauth else "LUMA_RATE_LIMIT_PER_MINUTE","10" if is_auth else "30" if is_oauth else "120"))
        identity=(principal or {}).get("sub") or (request.client.host if request.client else "unknown")
        bucket_key=f"{path.split('/')[1]}:{identity}:{request.client.host if request.client else 'unknown'}"
        bucket_start=datetime.fromtimestamp(int(time.time())//60*60,tz=timezone.utc)
        try:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""INSERT INTO security_rate_limits(bucket_key,window_start,request_count)
                                   VALUES (%s,%s,1)
                                   ON CONFLICT (bucket_key,window_start)
                                   DO UPDATE SET request_count=security_rate_limits.request_count+1
                                   RETURNING request_count""",(bucket_key,bucket_start))
                    count=cur.fetchone()["request_count"]
                    cur.execute("DELETE FROM security_rate_limits WHERE window_start < %s",
                                (bucket_start-timedelta(minutes=10),))
                    if count > limit:
                        return JSONResponse(status_code=429,content={"detail":"Rate limit exceeded","retry_after_seconds":60})
        except Exception:
            if os.getenv("LUMA_RATE_LIMIT_FAIL_CLOSED","true").lower()=="true":
                return JSONResponse(status_code=503,content={"detail":"Rate limiter unavailable"})
    if principal:
        request.state.principal=principal
    return await call_next(request)

DATABASE_URL = os.getenv("DATABASE_URL")


def bootstrap_service_blueprints():
    from service_blueprints import blueprint
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,name FROM services WHERE active=true")
            for service in cur.fetchall():
                try:
                    data=blueprint(service["name"])
                except ValueError:
                    continue
                cur.execute(
                    """INSERT INTO service_blueprint_versions(service_id,version,blueprint,active)
                       VALUES (%s,1,%s::jsonb,true)
                       ON CONFLICT (service_id,version) DO NOTHING""",
                    (service["id"], json.dumps(data)),
                )

def bootstrap_agent_policies():
    from agent_layer import AGENTS
    with get_conn() as conn:
        with conn.cursor() as cur:
            for name, definition in AGENTS.items():
                cur.execute(
                    """INSERT INTO agent_policies(agent_name,budget_usd,tools,approval_required)
                       VALUES (%s,%s,%s::jsonb,%s)
                       ON CONFLICT (agent_name) DO NOTHING""",
                    (name, definition["default_budget"], json.dumps(definition["tools"]), definition["approval_required"]),
                )

def bootstrap_owner():
    email=os.getenv("LUMA_ADMIN_EMAIL")
    password_hash=os.getenv("LUMA_ADMIN_PASSWORD_HASH")
    if not email or not password_hash:
        return
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO users(email,password_hash,role) VALUES (%s,%s,'owner')
                   ON CONFLICT (email) DO NOTHING""",
                (email.strip().lower(),password_hash),
            )


@app.on_event("startup")
def startup():
    if DATABASE_URL:
        try:
            ensure_delivery_schema()
            bootstrap_owner()
            bootstrap_agent_policies()
            bootstrap_service_blueprints()
        except Exception as exc:
            print(f"[luma] startup initialization failed: {type(exc).__name__}: {exc}", flush=True)



class BusinessCreate(BaseModel):
    name: str
    website_url: HttpUrl | None = None
    industry: str | None = None
    phone: str | None = None
    email: str | None = None
    source: str = "manual"


class WebsiteAnalyzeRequest(BaseModel):
    url: HttpUrl


class ProspectIngest(BaseModel):
    name: str
    website_url: HttpUrl | None = None
    industry: str | None = None
    phone: str | None = None
    email: str | None = None
    source: str = "manual"
    source_url: str | None = None
    source_external_id: str | None = None
    notes: str | None = None


class ResearchEnqueue(BaseModel):
    priority: int = 50


class ProspectCSVImport(BaseModel):
    csv_text: str
    source: str = "csv"
    source_url: str | None = None


class OutreachDraftUpdate(BaseModel):
    subject: str | None = None
    body: str | None = None
    status: str | None = None


class ProjectOptionUpdate(BaseModel):
    options: dict = Field(default_factory=dict)



@app.get("/")
def root():
    return {"name": "Luma", "version": "0.8.0", "status": "running"}


@app.get("/health")
def health():
    db = "not_configured" if not DATABASE_URL else "error"
    if DATABASE_URL:
        try:
            with psycopg.connect(DATABASE_URL, connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    db = "ok" if cur.fetchone() == (1,) else "error"
        except Exception as exc:
            db = f"error: {type(exc).__name__}"
    return {"status": "ok", "database": db}


@app.get("/projects/{project_id}/options")
def get_project_options(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            project, _ = _delivery_project(cur, project_id)
            service = project.get("service_name")
            definitions = option_definitions(service)
            cur.execute("SELECT options FROM project_options WHERE project_id=%s", (project_id,))
            row = cur.fetchone()
            selected = row["options"] if row else {}
            missing = validate_options(service, selected)
            return {"project_id": project_id, "service": service, "options": definitions, "definitions": definitions, "selected": selected,
                    "validation": {"missing": missing, "complete": not missing}, "summary": option_summary(service, selected)}

@app.post("/projects/{project_id}/options")
def save_project_options(project_id: str, payload: ProjectOptionUpdate):
    with get_conn() as conn:
        with conn.cursor() as cur:
            project, _ = _delivery_project(cur, project_id)
            service = project.get("service_name")
            definitions = option_definitions(service)
            allowed = {x["key"] for x in definitions}
            options = {str(k): v for k, v in payload.options.items() if k in allowed}
            cur.execute("SELECT options FROM project_options WHERE project_id=%s", (project_id,))
            row = cur.fetchone()
            current = row["options"] if row else {}
            current.update(options)
            cur.execute("""INSERT INTO project_options (project_id, options, updated_at)
                           VALUES (%s, %s::jsonb, now())
                           ON CONFLICT (project_id) DO UPDATE SET options=EXCLUDED.options, updated_at=now()
                           RETURNING options""", (project_id, json.dumps(current)))
            selected = cur.fetchone()["options"]
            missing = validate_options(service, selected)
            compiled = None
            if not missing:
                try:
                    compiled = compile_requirements(service, selected)
                    cur.execute(
                        """UPDATE implementations
                           SET requirements=%s::jsonb,
                               status=CASE WHEN status IN ('deployed','complete') THEN status ELSE 'requirements' END,
                               updated_at=now()
                           WHERE project_id=%s""",
                        (json.dumps(compiled), project_id),
                    )
                    cur.execute(
                        "UPDATE projects SET requirements=%s::jsonb WHERE id=%s",
                        (json.dumps(compiled), project_id),
                    )
                except ValueError:
                    compiled = None
            return {"project_id": project_id, "service": service, "options": definitions, "selected": selected,
                    "validation": {"missing": missing, "complete": not missing},
                    "compiled_requirements": compiled,
                    "summary": option_summary(service, selected)}

@app.get("/projects/{project_id}/configuration")
def get_project_configuration(project_id: str):
    return get_project_options(project_id)

@app.post("/projects/{project_id}/configuration")
def save_project_configuration(project_id: str, payload: ProjectOptionUpdate):
    return save_project_options(project_id, payload)

@app.get("/analytics/revenue")
def analytics_revenue():
    with get_conn() as conn:
        with conn.cursor() as cur:
            return {
                "summary": revenue_summary(cur),
                "services": service_performance(cur),
            }


@app.post("/analytics/revenue")
def record_revenue(payload: dict):
    required = {"amount"}
    if not required.issubset(payload):
        raise HTTPException(status_code=400, detail="amount is required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO revenue_transactions
                   (client_id, project_id, proposal_id, transaction_type, status,
                    amount, recurring_amount, currency, external_id, metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                   RETURNING *""",
                (
                    payload.get("client_id"), payload.get("project_id"), payload.get("proposal_id"),
                    payload.get("transaction_type", "sale"), payload.get("status", "paid"),
                    payload.get("amount", 0), payload.get("recurring_amount", 0),
                    payload.get("currency", "USD"), payload.get("external_id"),
                    json.dumps(payload.get("metadata") or {}),
                ),
            )
            return cur.fetchone()


@app.post("/analytics/costs")
def record_cost(payload: dict):
    if payload.get("amount") is None or not payload.get("category"):
        raise HTTPException(status_code=400, detail="amount and category are required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO cost_records
                   (project_id, agent_run_id, category, amount, currency, description, metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)
                   RETURNING *""",
                (
                    payload.get("project_id"), payload.get("agent_run_id"), payload["category"],
                    payload["amount"], payload.get("currency", "USD"), payload.get("description"),
                    json.dumps(payload.get("metadata") or {}),
                ),
            )
            return cur.fetchone()


@app.get("/analytics/costs")
def list_costs(limit: int = 100):
    limit = max(1, min(limit, 500))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM cost_records ORDER BY occurred_at DESC LIMIT %s", (limit,))
            return cur.fetchall()


@app.get("/automation/workflows")
def list_workflows():
    return [
        {"name": name, **definition}
        for name, definition in {
            "proposal_follow_up": workflow_definition("proposal_follow_up"),
            "project_delivery": workflow_definition("project_delivery"),
            "research": workflow_definition("research"),
        }.items()
    ]


@app.get("/automation/workflows/{workflow_name}")
def get_workflow(workflow_name: str, current_step: str | None = None):
    try:
        definition = workflow_definition(workflow_name)
        return {
            **definition,
            "next_step": next_step(workflow_name, current_step),
            "requires_human_approval": definition["external_action"] is not None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.post("/automation/runs")
def create_workflow_run(payload: dict):
    name = payload.get("workflow_name")
    if not name:
        raise HTTPException(status_code=400, detail="workflow_name is required")
    try:
        definition = workflow_definition(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO workflow_runs
                   (workflow_name, trigger_type, entity_type, entity_id, status, current_step, input)
                   VALUES (%s,%s,%s,%s,'pending',%s,%s::jsonb)
                   RETURNING *""",
                (
                    name, payload.get("trigger_type", "manual"), payload.get("entity_type"),
                    payload.get("entity_id"), definition["steps"][0],
                    json.dumps(payload.get("input") or {}),
                ),
            )
            return cur.fetchone()


@app.patch("/automation/runs/{run_id}")
def advance_workflow_run(run_id: str, payload: dict):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM workflow_runs WHERE id=%s", (run_id,))
            run = cur.fetchone()
            if not run:
                raise HTTPException(status_code=404, detail="Workflow run not found")
            try:
                step = next_step(run["workflow_name"], run["current_step"])
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc))
            from workflows import is_approval_step
            waiting = bool(step and is_approval_step(run["workflow_name"], step) and payload.get("approved") is not True)
            if waiting:
                status = "awaiting_approval"
            else:
                status = payload.get("status") or ("completed" if step is None else "running")
            cur.execute(
                """UPDATE workflow_runs
                   SET current_step=%s, status=%s, waiting_for_approval=%s, output=%s::jsonb,
                       completed_at=CASE WHEN %s='completed' THEN now() ELSE completed_at END
                   WHERE id=%s RETURNING *""",
                (step, status, waiting, json.dumps(payload.get("output") or {}), status, run_id),
            )
            return cur.fetchone()


@app.get("/integrations/suggestions/{service_name}")
def integration_suggestions(service_name: str):
    suggestions = suggestions_for_service(service_name)
    return {"service": service_name, "suggestions": [{**item, "providers": providers(item["category"])} for item in suggestions], "note": "Suggestions are optional. Connections become active only after configuration and verification."}


@app.get("/integrations/setup/{provider}")
def integration_setup(provider: str):
    for category, items in providers().items():
        if any(item["provider"] == provider for item in items):
            setup = provider_setup(provider)
            return {"provider": provider, "category": category, "capabilities": next(item["capabilities"] for item in items if item["provider"] == provider), "setup": setup}
    raise HTTPException(status_code=404, detail="Unknown integration provider")


@app.get("/integrations/providers")
def integration_providers(category: str | None = None):
    return {"category": category, "providers": providers(category)}


@app.get("/integrations")
def list_integrations(project_id: str | None = None, client_id: str | None = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if project_id:
                cur.execute("SELECT * FROM integration_connections WHERE project_id=%s ORDER BY created_at DESC", (project_id,))
            elif client_id:
                cur.execute("SELECT * FROM integration_connections WHERE client_id=%s ORDER BY created_at DESC", (client_id,))
            else:
                cur.execute("SELECT * FROM integration_connections ORDER BY created_at DESC LIMIT 200")
            return cur.fetchall()


@app.post("/integrations")
def create_integration(payload: dict):
    if not payload.get("provider") or not payload.get("category"):
        raise HTTPException(status_code=400, detail="provider and category are required")
    allowed = {item["provider"] for item in providers(payload["category"])}
    if payload["provider"] not in allowed:
        raise HTTPException(status_code=400, detail="Unknown provider for integration category")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO integration_connections
                   (client_id, project_id, provider, category, status, capabilities, secret_ref, metadata)
                   VALUES (%s,%s,%s,%s,'pending',%s::jsonb,%s,%s::jsonb)
                   RETURNING *""",
                (
                    payload.get("client_id"), payload.get("project_id"), payload["provider"], payload["category"],
                    json.dumps(next(item["capabilities"] for item in providers(payload["category"]) if item["provider"] == payload["provider"])),
                    payload.get("secret_ref"), json.dumps(payload.get("metadata") or {}),
                ),
            )
            return cur.fetchone()


@app.post("/portal/access")
def create_portal_access(payload: dict):
    if not payload.get("client_id"):
        raise HTTPException(status_code=400, detail="client_id is required")
    raw, token_hash = create_token()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO client_portal_access (client_id, project_id, token_hash, expires_at)
                   VALUES (%s,%s,%s,%s) RETURNING id, client_id, project_id, status, expires_at, created_at""",
                (payload["client_id"], payload.get("project_id"), token_hash, payload.get("expires_at")),
            )
            access = cur.fetchone()
    return {"access": access, "token": raw}


@app.get("/portal/project/{project_id}")
def portal_project(project_id: str, token: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT a.id, a.client_id
                   FROM client_portal_access a
                   WHERE a.project_id=%s AND a.token_hash=%s AND a.status='active'
                     AND (a.expires_at IS NULL OR a.expires_at > now())""",
                (project_id, hash_token(token)),
            )
            access = cur.fetchone()
            if not access:
                raise HTTPException(status_code=401, detail="Invalid or expired portal token")
            cur.execute(
                """SELECT p.id, p.name, p.status, p.agreed_price, p.recurring_price,
                          p.start_date, p.target_date, b.name AS business_name,
                          s.name AS service_name
                   FROM projects p
                   JOIN clients c ON c.id=p.client_id
                   JOIN businesses b ON b.id=c.business_id
                   LEFT JOIN services s ON s.id=p.service_id
                   WHERE p.id=%s AND p.client_id=%s""",
                (project_id, access["client_id"]),
            )
            project = cur.fetchone()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            cur.execute("SELECT * FROM project_milestones WHERE project_id=%s ORDER BY sequence", (project_id,))
            milestones = cur.fetchall()
            cur.execute(
                "UPDATE client_portal_access SET last_used_at=now() WHERE id=%s",
                (access["id"],),
            )
            return {"project": project, "milestones": milestones}


@app.get("/billing")
def list_billing(status: str | None = None, limit: int = 100):
    limit = max(1, min(limit, 500))
    with get_conn() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute("SELECT * FROM billing_records WHERE status=%s ORDER BY created_at DESC LIMIT %s", (status, limit))
            else:
                cur.execute("SELECT * FROM billing_records ORDER BY created_at DESC LIMIT %s", (limit,))
            return cur.fetchall()


@app.post("/billing")
def create_billing(payload: dict):
    if payload.get("amount") is None:
        raise HTTPException(status_code=400, detail="amount is required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO billing_records
                   (client_id, project_id, proposal_id, external_invoice_id, status,
                    amount, currency, due_at, metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)
                   RETURNING *""",
                (
                    payload.get("client_id"), payload.get("project_id"), payload.get("proposal_id"),
                    payload.get("external_invoice_id"), payload.get("status", "draft"),
                    payload["amount"], payload.get("currency", "USD"), payload.get("due_at"),
                    json.dumps(payload.get("metadata") or {}),
                ),
            )
            return cur.fetchone()


@app.post("/billing/{billing_id}/paid")
def mark_billing_paid(billing_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM billing_records WHERE id=%s", (billing_id,))
            record = cur.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Billing record not found")
            if record["status"] == "paid":
                return {"billing": record, "revenue": None, "note": "Payment was already reconciled"}
            cur.execute(
                "UPDATE billing_records SET status='paid', paid_at=now() WHERE id=%s RETURNING *",
                (billing_id,),
            )
            record = cur.fetchone()
            cur.execute(
                """INSERT INTO revenue_transactions
                   (client_id, project_id, amount, status, transaction_type, metadata)
                   VALUES (%s,%s,%s,'paid','payment',%s::jsonb)
                   RETURNING *""",
                (record["client_id"], record["project_id"], record["amount"],
                 json.dumps({"billing_id": str(billing_id)})),
            )
            return {"billing": record, "revenue": cur.fetchone()}


@app.get("/dashboard")
def dashboard():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                counts = {}
                for key, query in {
                    "businesses": "SELECT count(*) FROM businesses",
                    "opportunities": "SELECT count(*) FROM opportunities",
                    "proposals": "SELECT count(*) FROM proposals",
                    "clients": "SELECT count(*) FROM clients",
                    "projects": "SELECT count(*) FROM projects",
                    "open_tasks": "SELECT count(*) FROM tasks WHERE status NOT IN ('done', 'completed')",
                }.items():
                    cur.execute(query)
                    counts[key] = cur.fetchone()["count"]

                cur.execute("""
                    SELECT COALESCE(SUM(estimated_value_max), 0) AS pipeline_value
                    FROM opportunities
                    WHERE status NOT IN ('won', 'lost', 'rejected')
                """)
                counts["pipeline_value"] = float(cur.fetchone()["pipeline_value"] or 0)

                cur.execute("""
                    SELECT COALESCE(SUM(total_amount), 0) AS won_revenue
                    FROM proposals
                    WHERE status = 'accepted'
                """)
                counts["won_revenue"] = float(cur.fetchone()["won_revenue"] or 0)

                cur.execute("""
                    SELECT o.id, o.title, o.status, o.score, o.estimated_value_min,
                           o.estimated_value_max, o.next_action, b.name AS business_name,
                           s.name AS service_name
                    FROM opportunities o
                    JOIN businesses b ON b.id = o.business_id
                    LEFT JOIN services s ON s.id = o.service_id
                    WHERE o.status NOT IN ('won', 'lost', 'rejected')
                    ORDER BY o.score DESC NULLS LAST, o.created_at DESC
                    LIMIT 10
                """)
                counts["opportunities_queue"] = cur.fetchall()

                cur.execute("""
                    SELECT p.id, p.name, p.status, p.agreed_price, p.recurring_price,
                           p.start_date, p.target_date,
                           b.name AS business_name,
                           s.name AS service_name,
                           i.status AS implementation_status,
                           i.validated_at, i.approved_at,
                           h.status AS handoff_status
                    FROM projects p
                    JOIN clients c ON c.id = p.client_id
                    JOIN businesses b ON b.id = c.business_id
                    LEFT JOIN services s ON s.id = p.service_id
                    LEFT JOIN implementations i ON i.project_id = p.id
                    LEFT JOIN handoffs h ON h.project_id = p.id
                    WHERE p.status NOT IN ('completed', 'cancelled')
                    ORDER BY p.created_at DESC
                    LIMIT 10
                """)
                counts["active_projects"] = cur.fetchall()

                cur.execute("""
                    SELECT t.id, t.title, t.description, t.status, t.priority, t.due_at,
                           p.name AS project_name, b.name AS business_name
                    FROM tasks t
                    JOIN projects p ON p.id = t.project_id
                    JOIN clients c ON c.id = p.client_id
                    JOIN businesses b ON b.id = c.business_id
                    WHERE t.status NOT IN ('done', 'completed')
                    ORDER BY CASE t.priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,
                             t.due_at NULLS LAST, t.created_at
                    LIMIT 12
                """)
                counts["tasks"] = cur.fetchall()

                cur.execute("""SELECT r.id, r.priority, r.scheduled_at, b.name AS business_name, b.website_url
                               FROM research_jobs r JOIN businesses b ON b.id=r.business_id
                               WHERE r.status='pending'
                               ORDER BY r.priority DESC, r.scheduled_at, r.created_at LIMIT 10""")
                counts["research_queue"] = cur.fetchall()

                cur.execute("""SELECT m.id, m.subject, m.created_at, b.name AS business_name, b.email
                               FROM messages m JOIN businesses b ON b.id=m.business_id
                               WHERE m.status='draft' AND m.direction='outbound'
                               ORDER BY m.created_at DESC LIMIT 10""")
                counts["outreach_drafts"] = cur.fetchall()
                return counts
    except Exception:
        return {
            "businesses": 0, "opportunities": 0, "proposals": 0, "clients": 0,
            "projects": 0, "open_tasks": 0, "pipeline_value": 0,
            "won_revenue": 0, "opportunities_queue": [], "active_projects": [], "tasks": [],
            "research_queue": [], "outreach_drafts": []
        }


@app.post("/businesses")
def create_business(payload: BusinessCreate):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO businesses
                      (name, website_url, industry, phone, email, source)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (
                        payload.name,
                        str(payload.website_url) if payload.website_url else None,
                        payload.industry,
                        payload.phone,
                        payload.email,
                        payload.source,
                    ),
                )
                return cur.fetchone()
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail="Business already exists")


@app.post("/prospects/ingest")
def ingest_prospect(payload: ProspectIngest):
    website = str(payload.website_url) if payload.website_url else None
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM businesses
                   WHERE (%s IS NOT NULL AND source = %s AND source_external_id = %s)
                      OR (%s IS NOT NULL AND lower(regexp_replace(website_url, '^https?://(www\\.)?', '')) =
                          lower(regexp_replace(%s, '^https?://(www\\.)?', '')))
                      OR (%s IS NOT NULL AND lower(email) = lower(%s))
                   LIMIT 1""",
                (payload.source_external_id, payload.source, payload.source_external_id,
                 website, website, payload.email, payload.email),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    """UPDATE businesses SET
                       name=COALESCE(%s,name), industry=COALESCE(%s,industry),
                       phone=COALESCE(%s,phone), email=COALESCE(%s,email),
                       website_url=COALESCE(%s,website_url),
                       source_url=COALESCE(%s,source_url),
                       source_external_id=COALESCE(%s,source_external_id),
                       notes=COALESCE(%s,notes), updated_at=now()
                       WHERE id=%s RETURNING *""",
                    (payload.name,payload.industry,payload.phone,payload.email,website,
                     payload.source_url,payload.source_external_id,payload.notes,existing["id"]),
                )
                return {"action":"updated","business":cur.fetchone()}
            cur.execute(
                """INSERT INTO businesses
                   (name,website_url,industry,phone,email,source,source_url,source_external_id,notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (payload.name,website,payload.industry,payload.phone,payload.email,payload.source,
                 payload.source_url,payload.source_external_id,payload.notes),
            )
            return {"action":"created","business":cur.fetchone()}








@app.post("/prospects/import-csv")
def import_prospects_csv(payload: ProspectCSVImport):
    if len(payload.csv_text.encode("utf-8")) > 2_000_000:
        raise HTTPException(status_code=400, detail="CSV payload is too large")
    reader = csv.DictReader(io.StringIO(payload.csv_text))
    required = {"name"}
    headers = {h.strip().lower() for h in (reader.fieldnames or []) if h}
    if not required.issubset(headers):
        raise HTTPException(status_code=400, detail="CSV must include a name column")
    rows = []
    for row in reader:
        normalized = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        if not normalized.get("name"):
            continue
        rows.append(ProspectIngest(
            name=normalized["name"],
            website_url=normalized.get("website_url") or normalized.get("website"),
            industry=normalized.get("industry"),
            phone=normalized.get("phone"),
            email=normalized.get("email"),
            source=payload.source,
            source_url=payload.source_url,
            source_external_id=normalized.get("source_external_id") or normalized.get("id"),
            notes=normalized.get("notes"),
        ))
        if len(rows) > 100:
            raise HTTPException(status_code=400, detail="Maximum batch size is 100")
    return ingest_prospects_batch(rows)


@app.post("/prospects/ingest-batch")
def ingest_prospects_batch(payload: list[ProspectIngest]):
    if not payload:
        raise HTTPException(status_code=400, detail="Prospect batch is empty")
    if len(payload) > 100:
        raise HTTPException(status_code=400, detail="Maximum batch size is 100")
    results = []
    for prospect in payload:
        result = ingest_prospect(prospect)
        business = result["business"]
        queued = None
        if business.get("website_url"):
            queued = enqueue_research(str(business["id"]), ResearchEnqueue(priority=50))
        results.append({
            "action": result["action"],
            "business_id": business["id"],
            "research_job_id": queued["id"] if queued else None,
        })
    return {"count": len(results), "results": results}


@app.post("/businesses/{business_id}/research")
def enqueue_research(business_id: str, payload: ResearchEnqueue | None = None):
    priority = max(0, min((payload or ResearchEnqueue()).priority, 100))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, website_url FROM businesses WHERE id=%s",(business_id,))
            business=cur.fetchone()
            if not business: raise HTTPException(status_code=404, detail="Business not found")
            if not business["website_url"]: raise HTTPException(status_code=400, detail="Business has no website URL")
            cur.execute("""INSERT INTO research_jobs (business_id,priority) VALUES (%s,%s)
                           ON CONFLICT DO NOTHING RETURNING *""",(business_id,priority))
            job=cur.fetchone()
            if job: return job
            cur.execute("""SELECT * FROM research_jobs WHERE business_id=%s
                           AND status IN ('pending','running') ORDER BY created_at DESC LIMIT 1""",(business_id,))
            return cur.fetchone()


@app.get("/research/jobs")
def list_research_jobs(status: str="pending", limit: int=20):
    if status not in {"pending","running","completed","failed"}:
        raise HTTPException(status_code=400, detail="Invalid research job status")
    limit=max(1,min(limit,100))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE research_jobs
                           SET status='pending', locked_at=NULL, updated_at=now()
                           WHERE status='running'
                             AND locked_at < now() - interval '15 minutes'""")
            cur.execute("""SELECT r.*,b.name AS business_name,b.website_url
                           FROM research_jobs r JOIN businesses b ON b.id=r.business_id
                           WHERE r.status=%s ORDER BY r.priority DESC,r.scheduled_at,r.created_at LIMIT %s""",
                        (status,limit))
            return cur.fetchall()


@app.post("/research/jobs/{job_id}/run")
def run_research_job(job_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE research_jobs SET status='running',attempts=attempts+1,
                           locked_at=now(),updated_at=now()
                           WHERE id=%s AND status='pending' RETURNING *""",(job_id,))
            job=cur.fetchone()
            if not job: raise HTTPException(status_code=409, detail="Research job is not pending")
            cur.execute("SELECT * FROM businesses WHERE id=%s",(job["business_id"],))
            business=cur.fetchone()
    try:
        analysis = analyze_website(business["website_url"])
        service_opps = map_to_service_opportunities(
            analysis, industry=business.get("industry")
        )
        all_factors = []
        for o in service_opps:
            for f in o["factors"]:
                if f not in all_factors:
                    all_factors.append(f)
        # Backward-compatible aggregate for callers that still expect a single qualification
        qualification = score_opportunity(analysis)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO websites
                       (business_id,url,http_status,https_enabled,mobile_friendly,load_time_ms,cms,technology_stack,last_checked_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,'[]'::jsonb,now()) RETURNING id""",
                    (
                        business["id"],
                        analysis["url"],
                        analysis["http_status"],
                        analysis["https"],
                        analysis["has_mobile_viewport"],
                        analysis["response_time_ms"],
                        analysis["cms"],
                    ),
                )
                website_id = cur.fetchone()["id"]

                opp_summaries = [
                    {"service": o["service"], "score": o["score"]} for o in service_opps
                ]
                cur.execute(
                    """INSERT INTO research_reports
                       (business_id,summary,observed_problems,opportunities,evidence,model,prompt_version)
                       VALUES (%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s) RETURNING id""",
                    (
                        business["id"],
                        "Automated website research based only on observed technical signals.",
                        json.dumps(all_factors),
                        json.dumps(opp_summaries),
                        json.dumps(analysis),
                        "heuristic",
                        "website-analysis-v2",
                    ),
                )
                report_id = cur.fetchone()["id"]

                opportunity_ids = []
                for o in service_opps:
                    fit = assess_opportunity(
                        evidence_count=min(100, len(o.get("factors") or []) * 20),
                        evidence_confidence=o.get("confidence") or 0,
                        impact_confidence=min(100, float(o.get("score") or 0)),
                        solution_fit=min(100, float(o.get("score") or 0)),
                        intrusiveness_risk=20,
                        problem_proven=bool(o.get("factors")),
                    )
                    cur.execute(
                        """INSERT INTO opportunities
                           (business_id,research_report_id,title,description,problem_evidence,score,
                            confidence,rationale,factors,estimated_value_min,estimated_value_max,status,next_action,service_id,
                            fit_score,fit_disposition,why_this,why_not,alternatives)
                           SELECT %s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb,price_min,price_max,
                                  'new','Review evidence and approve outreach',id,%s,%s,%s,%s::jsonb,%s::jsonb
                           FROM services WHERE name=%s RETURNING id""",
                        (
                            business["id"],
                            report_id,
                            o["title"],
                            o["description"],
                            json.dumps(o["factors"]),
                            o["score"],
                            o.get("confidence"),
                            o["description"],
                            json.dumps(o["factors"]),
                            fit["score"],
                            fit["disposition"],
                            "Observed signals indicate a possible fit; human review should confirm business impact.",
                            json.dumps([]),
                            json.dumps([]),
                            o["service"],
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        opportunity_ids.append(row["id"])
                        for factor in o["factors"]:
                            cur.execute(
                                """INSERT INTO evidence_items
                                   (business_id,research_report_id,opportunity_id,evidence_type,observation,
                                    source_url,confidence,metadata)
                                   VALUES (%s,%s,%s,'website_observation',%s,%s,%s,%s::jsonb)""",
                                (
                                    business["id"], report_id, row["id"],
                                    factor.get("factor", "observed signal"), analysis.get("url"),
                                    o.get("confidence"),
                                    json.dumps({"points": factor.get("points", 0), "source": "website_analyzer"}),
                                ),
                            )

                cur.execute(
                    """UPDATE research_jobs SET status='completed',completed_at=now(),
                       locked_at=NULL,last_error=NULL,updated_at=now() WHERE id=%s""",
                    (job_id,),
                )
                return {
                    "job_id": job_id,
                    "business_id": business["id"],
                    "website_id": website_id,
                    "research_report_id": report_id,
                    "opportunity_ids": opportunity_ids,
                    "opportunities": service_opps,
                    "qualification": qualification,
                }
    except Exception as exc:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT attempts FROM research_jobs WHERE id=%s""", (job_id,))
                current = cur.fetchone()
                attempts = current["attempts"] if current else 3
                next_status = "pending" if attempts < 3 else "failed"
                cur.execute(
                    """UPDATE research_jobs SET status=%s,last_error=%s,
                       locked_at=NULL,updated_at=now() WHERE id=%s""",
                    (next_status, f"{type(exc).__name__}: {exc}", job_id),
                )
        raise HTTPException(status_code=500, detail="Research job failed")


@app.post("/outreach/drafts")
def create_outreach_draft(opportunity_id: str):
    """
    Create a full Day 1 / 3 / 7 email sequence as draft messages.
    Nothing is sent until a human approves each draft.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT o.*, b.name AS business_name, b.email AS business_email,
                          b.industry, s.name AS service_name
                   FROM opportunities o
                   JOIN businesses b ON b.id = o.business_id
                   LEFT JOIN services s ON s.id = o.service_id
                   WHERE o.id = %s""",
                (opportunity_id,),
            )
            opportunity = cur.fetchone()
            if not opportunity:
                raise HTTPException(status_code=404, detail="Opportunity not found")
            if not opportunity["business_email"]:
                raise HTTPException(
                    status_code=400,
                    detail="Business has no email — add an email before drafting outreach",
                )

            cur.execute(
                """SELECT status, contact_count FROM outreach_preferences WHERE business_id=%s""",
                (opportunity["business_id"],),
            )
            preference = cur.fetchone() or {"status": "normal", "contact_count": 0}
            eligibility = outreach_disposition(preference["status"], preference["contact_count"])
            if eligibility != "allow":
                raise HTTPException(
                    status_code=409,
                    detail={
                        "message": "Outreach is paused for this business.",
                        "reason": preference["status"],
                        "eligibility": eligibility,
                    },
                )
            if opportunity.get("fit_disposition") == "suppress":
                raise HTTPException(
                    status_code=409,
                    detail="This opportunity is suppressed by the client-respect policy. Gather new evidence before outreach.",
                )
            if opportunity.get("fit_disposition") != "allow":
                raise HTTPException(
                    status_code=409,
                    detail="This opportunity needs human fit review before outreach.",
                )

            sequence = build_outreach_sequence(opportunity)
            created = []
            for touch in sequence["touches"]:
                meta_note = f"[Day {touch['day']}] "
                cur.execute(
                    """INSERT INTO messages
                       (business_id, opportunity_id, channel, direction, subject, body, status)
                       VALUES (%s, %s, %s, 'outbound', %s, %s, 'draft')
                       RETURNING *""",
                    (
                        opportunity["business_id"],
                        opportunity_id,
                        touch["channel"],
                        touch["subject"],
                        meta_note + touch["body"],
                    ),
                )
                created.append(cur.fetchone())

            cur.execute(
                """UPDATE opportunities
                   SET next_action = 'Human review of outreach sequence (Day 1/3/7 drafts)',
                       updated_at = now()
                   WHERE id = %s""",
                (opportunity_id,),
            )
            return {
                "opportunity_id": opportunity_id,
                "service": sequence["service"],
                "observations": sequence["observations"],
                "drafts": created,
                "note": "All messages are drafts. Approve individually before any send.",
            }


@app.patch("/outreach/drafts/{message_id}")
def update_outreach_draft(message_id: str, payload: OutreachDraftUpdate):
    allowed = {"draft", "approved", "rejected"}
    if payload.status is not None and payload.status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid outreach draft status")
    if payload.subject is not None and not payload.subject.strip():
        raise HTTPException(status_code=400, detail="Subject cannot be empty")
    if payload.body is not None and not payload.body.strip():
        raise HTTPException(status_code=400, detail="Body cannot be empty")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE messages
                   SET subject=COALESCE(%s,subject),
                       body=COALESCE(%s,body),
                       status=COALESCE(%s,status)
                   WHERE id=%s AND direction='outbound'
                   RETURNING *""",
                (payload.subject, payload.body, payload.status, message_id),
            )
            message = cur.fetchone()
            if not message:
                raise HTTPException(status_code=404, detail="Outreach draft not found")
            cur.execute(
                """INSERT INTO activities
                   (business_id, opportunity_id, type, subject, content, metadata)
                   SELECT business_id, opportunity_id, 'outreach_review', %s, %s, %s::jsonb
                   FROM messages WHERE id=%s""",
                (
                    "Outreach draft reviewed",
                    "Draft was edited or its approval status changed.",
                    json.dumps({"message_id": str(message_id), "status": message["status"]}),
                    message_id,
                ),
            )
            return message


@app.get("/outreach/drafts")
def list_outreach_drafts(limit: int=50):
    limit=max(1,min(limit,200))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT m.*,b.name AS business_name,b.email AS business_email,o.title AS opportunity_title
                           FROM messages m JOIN businesses b ON b.id=m.business_id
                           LEFT JOIN opportunities o ON o.id=m.opportunity_id
                           WHERE m.status='draft' AND m.direction='outbound'
                           ORDER BY m.created_at DESC LIMIT %s""",(limit,))
            return cur.fetchall()


@app.get("/businesses")
def list_businesses(limit: int = 50):
    limit = max(1, min(limit, 200))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM businesses ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            return cur.fetchall()


@app.post("/analyze-website")
def analyze(payload: WebsiteAnalyzeRequest):
    return analyze_website(str(payload.url))



@app.post("/businesses/{business_id}/analyze")
def analyze_business(business_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM businesses WHERE id = %s", (business_id,))
            business = cur.fetchone()
            if not business:
                raise HTTPException(status_code=404, detail="Business not found")
            if not business["website_url"]:
                raise HTTPException(status_code=400, detail="Business has no website URL")

    analysis = analyze_website(business["website_url"])
    service_opps = map_to_service_opportunities(
        analysis, industry=business.get("industry")
    )
    all_factors = []
    for o in service_opps:
        for f in o["factors"]:
            if f not in all_factors:
                all_factors.append(f)
    qualification = score_opportunity(analysis)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO websites
                   (business_id, url, http_status, https_enabled, mobile_friendly,
                    load_time_ms, cms, technology_stack, last_checked_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, '[]'::jsonb, now())
                   RETURNING id""",
                (
                    business_id,
                    analysis["url"],
                    analysis["http_status"],
                    analysis["https"],
                    analysis["has_mobile_viewport"],
                    analysis["response_time_ms"],
                    analysis["cms"],
                ),
            )
            website_id = cur.fetchone()["id"]

            opp_summaries = [{"service": o["service"], "score": o["score"]} for o in service_opps]
            cur.execute(
                """INSERT INTO research_reports
                   (business_id, summary, observed_problems, opportunities, evidence,
                    model, prompt_version)
                   VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s)
                   RETURNING id""",
                (
                    business_id,
                    "Automated website research based only on observed technical signals.",
                    json.dumps(all_factors),
                    json.dumps(opp_summaries),
                    json.dumps(analysis),
                    "heuristic",
                    "website-analysis-v2",
                ),
            )
            report_id = cur.fetchone()["id"]

            opportunity_ids = []
            for o in service_opps:
                cur.execute(
                    """INSERT INTO opportunities
                       (business_id, research_report_id, title, description,
                        problem_evidence, score, estimated_value_min,
                        estimated_value_max, status, next_action, service_id)
                       SELECT %s, %s, %s, %s, %s::jsonb, %s, price_min, price_max,
                              'new', 'Review evidence and approve outreach', id
                       FROM services WHERE name = %s
                       RETURNING id""",
                    (
                        business_id,
                        report_id,
                        o["title"],
                        o["description"],
                        json.dumps(o["factors"]),
                        o["score"],
                        o.get("confidence"),
                        o["description"],
                        json.dumps(o["factors"]),
                        o["service"],
                    ),
                )
                row = cur.fetchone()
                if row:
                    opportunity_ids.append(row["id"])
                    for factor in o["factors"]:
                        cur.execute(
                            """INSERT INTO evidence_items
                               (business_id, research_report_id, opportunity_id, evidence_type,
                                observation, source_url, confidence, metadata)
                               VALUES (%s,%s,%s,'website_observation',%s,%s,%s,%s::jsonb)""",
                            (
                                business_id, report_id, row["id"],
                                factor.get("factor", "observed signal"),
                                analysis.get("url"),
                                o.get("confidence"),
                                json.dumps({"points": factor.get("points", 0), "source": "website_analyzer"}),
                            ),
                        )

    return {
        "business_id": business_id,
        "website_id": website_id,
        "research_report_id": report_id,
        "opportunity_ids": opportunity_ids,
        "opportunities": service_opps,
        "analysis": analysis,
        "qualification": qualification,
    }


@app.post("/qualify")
def qualify(payload: dict):
    """
    Score an analysis. If service_name is provided, return a single service-weighted score.
    Otherwise return the full list of service-specific opportunities (optionally
    industry-biased via payload.industry).
    """
    analysis = payload.get("analysis")
    if not isinstance(analysis, dict):
        raise HTTPException(status_code=400, detail="analysis object is required")
    service_name = payload.get("service_name")
    if service_name:
        return score_opportunity(analysis, service_name)
    industry = payload.get("industry")
    return {
        "opportunities": map_to_service_opportunities(analysis, industry=industry),
        "aggregate": score_opportunity(analysis),
    }


from sales import (
    build_call_prep,
    build_proposal_content,
    build_outreach_sequence,
    default_offer_scope,
    build_client_brief,
)


def _get_opportunity(cur, opportunity_id: str):
    cur.execute(
        """SELECT o.*, b.name AS business_name, b.website_url, b.industry,
                  s.name AS service_name, s.description AS service_description,
                  s.price_min, s.price_max, s.delivery_days
           FROM opportunities o
           JOIN businesses b ON b.id = o.business_id
           LEFT JOIN services s ON s.id = o.service_id
           WHERE o.id = %s""",
        (opportunity_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return row


@app.patch("/opportunities/{opportunity_id}/lifecycle")
def update_opportunity_lifecycle(opportunity_id: str, payload: dict):
    allowed = {"new", "qualified", "contact_pending", "contacted", "discovery", "proposal", "won", "lost", "rejected"}
    status = payload.get("status")
    if status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid opportunity status")
    with get_conn() as conn:
        with conn.cursor() as cur:
            opportunity = _get_opportunity(cur, opportunity_id)
            cur.execute(
                """UPDATE opportunities
                   SET status=%s, next_action=%s, next_action_at=%s, updated_at=now()
                   WHERE id=%s RETURNING *""",
                (status, payload.get("next_action"), payload.get("next_action_at"), opportunity_id),
            )
            updated = cur.fetchone()
            cur.execute(
                """INSERT INTO activities
                   (business_id, opportunity_id, type, subject, content, metadata)
                   VALUES (%s,%s,'opportunity_status','Opportunity status changed',%s,%s::jsonb)""",
                (
                    opportunity["business_id"], opportunity_id, status,
                    json.dumps({"from": opportunity["status"], "to": status}),
                ),
            )
            return updated


@app.get("/opportunities")
def list_opportunities(status: str | None = None, limit: int = 50):
    limit = max(1, min(limit, 200))
    with get_conn() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    """SELECT o.*, b.name AS business_name, s.name AS service_name
                       FROM opportunities o
                       JOIN businesses b ON b.id = o.business_id
                       LEFT JOIN services s ON s.id = o.service_id
                       WHERE o.status = %s
                       ORDER BY o.score DESC NULLS LAST, o.created_at DESC LIMIT %s""",
                    (status, limit),
                )
            else:
                cur.execute(
                    """SELECT o.*, b.name AS business_name, s.name AS service_name
                       FROM opportunities o
                       JOIN businesses b ON b.id = o.business_id
                       LEFT JOIN services s ON s.id = o.service_id
                       ORDER BY o.score DESC NULLS LAST, o.created_at DESC LIMIT %s""",
                    (limit,),
                )
            return cur.fetchall()


@app.get("/opportunities/{opportunity_id}")
def get_opportunity(opportunity_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            opportunity = _get_opportunity(cur, opportunity_id)
            cur.execute(
                "SELECT * FROM activities WHERE opportunity_id = %s ORDER BY created_at DESC LIMIT 50",
                (opportunity_id,),
            )
            opportunity["activities"] = cur.fetchall()
            return opportunity


@app.post("/opportunities/{opportunity_id}/prepare-call")
def prepare_call(opportunity_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            opportunity = _get_opportunity(cur, opportunity_id)
            prep = build_call_prep(opportunity)
            cur.execute(
                """INSERT INTO activities
                   (business_id, opportunity_id, type, subject, content, metadata)
                   VALUES (%s, %s, 'call_prep', %s, %s, %s::jsonb)
                   RETURNING id""",
                (
                    opportunity["business_id"], opportunity_id,
                    "Sales call preparation", json.dumps(prep),
                    json.dumps({"generated_by": "deterministic-template", "version": "sales-cockpit-v1"}),
                ),
            )
            activity_id = cur.fetchone()["id"]
            cur.execute(
                """UPDATE opportunities
                   SET status = CASE WHEN status = 'qualified' THEN 'contact_pending' ELSE status END,
                       next_action = 'Review call prep and approve outreach', updated_at = now()
                   WHERE id = %s""",
                (opportunity_id,),
            )
            return {"opportunity_id": opportunity_id, "activity_id": activity_id, "call_prep": prep}


@app.post("/opportunities/{opportunity_id}/client-brief")
def client_brief(opportunity_id: str):
    """
    Generate a one-page, client-friendly brief you can share with the prospect.
    Plain language. What we noticed, why it matters, recommendation, price range.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            opportunity = _get_opportunity(cur, opportunity_id)
            brief = build_client_brief(opportunity)
            cur.execute(
                """INSERT INTO activities
                   (business_id, opportunity_id, type, subject, content, metadata)
                   VALUES (%s, %s, 'client_brief', %s, %s, %s::jsonb)
                   RETURNING id""",
                (
                    opportunity["business_id"],
                    opportunity_id,
                    brief["title"],
                    brief["markdown"],
                    json.dumps(
                        {
                            "generated_by": "client-brief-v1",
                            "service": brief["service"],
                        }
                    ),
                ),
            )
            activity_id = cur.fetchone()["id"]
            cur.execute(
                """UPDATE opportunities
                   SET next_action = 'Share client brief or book discovery call',
                       updated_at = now()
                   WHERE id = %s""",
                (opportunity_id,),
            )
            return {
                "opportunity_id": opportunity_id,
                "activity_id": activity_id,
                "brief": brief,
            }


@app.post("/opportunities/{opportunity_id}/create-offer")
def create_offer(opportunity_id: str, payload: dict | None = None):
    payload = payload or {}
    with get_conn() as conn:
        with conn.cursor() as cur:
            opportunity = _get_opportunity(cur, opportunity_id)
            service_name = payload.get("service_name") or opportunity.get("service_name") or "Custom Automation"
            cur.execute("SELECT * FROM services WHERE name = %s AND active = true", (service_name,))
            service = cur.fetchone()
            if not service:
                raise HTTPException(status_code=400, detail="Active service not found: " + service_name)

            scope = default_offer_scope(service_name, opportunity["business_name"])
            setup_price = payload.get("setup_price")
            if setup_price is None:
                setup_price = float(service["price_min"] or 0)
            recurring_price = payload.get("recurring_price")
            name = payload.get("name") or scope["name"]
            deliverables = payload.get("deliverables") or scope["deliverables"]
            assumptions = payload.get("assumptions") or scope["assumptions"]
            exclusions = payload.get("exclusions") or scope["exclusions"]
            description = payload.get("description") or scope["description"] or service["description"]
            cur.execute(
                """INSERT INTO offers
                   (opportunity_id, service_id, name, description, setup_price,
                    recurring_price, deliverables, assumptions, exclusions)
                   VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
                   RETURNING *""",
                (
                    opportunity_id,
                    service["id"],
                    name,
                    description,
                    setup_price,
                    recurring_price,
                    json.dumps(deliverables),
                    json.dumps(assumptions),
                    json.dumps(exclusions),
                ),
            )
            offer = cur.fetchone()
            cur.execute(
                """UPDATE opportunities
                   SET status = 'proposal', next_action = 'Review offer and approve proposal draft',
                       updated_at = now()
                   WHERE id = %s""",
                (opportunity_id,),
            )
            return offer


@app.post("/proposals")
def create_proposal(payload: dict):
    opportunity_id = payload.get("opportunity_id")
    offer_id = payload.get("offer_id")
    if not opportunity_id or not offer_id:
        raise HTTPException(status_code=400, detail="opportunity_id and offer_id are required")

    with get_conn() as conn:
        with conn.cursor() as cur:
            opportunity = _get_opportunity(cur, opportunity_id)
            cur.execute(
                """SELECT o.*, s.delivery_days
                   FROM offers o LEFT JOIN services s ON s.id = o.service_id
                   WHERE o.id = %s AND o.opportunity_id = %s""",
                (offer_id, opportunity_id),
            )
            offer = cur.fetchone()
            if not offer:
                raise HTTPException(status_code=404, detail="Offer not found for opportunity")

            content = build_proposal_content(opportunity["business_name"], offer, opportunity)
            cur.execute("SELECT COALESCE(MAX(version), 0) + 1 AS version FROM proposals WHERE opportunity_id=%s", (opportunity_id,))
            version = cur.fetchone()["version"]
            cur.execute(
                """INSERT INTO proposals
                   (opportunity_id, offer_id, title, version, status, total_amount,
                    recurring_amount, content, expires_at)
                   VALUES (%s, %s, %s, %s, 'draft', %s, %s, %s, CURRENT_DATE + 14)
                   RETURNING *""",
                (
                    opportunity_id, offer_id, offer["name"], version, offer["setup_price"],
                    offer["recurring_price"], content,
                ),
            )
            proposal = cur.fetchone()
            cur.execute(
                """INSERT INTO activities
                   (business_id, opportunity_id, type, subject, content, metadata)
                   VALUES (%s, %s, 'proposal_draft', %s, %s, %s::jsonb)""",
                (
                    opportunity["business_id"], opportunity_id,
                    "Proposal draft created", content,
                    json.dumps({"proposal_id": str(proposal["id"]), "version": "proposal-v1"}),
                ),
            )
            return proposal


@app.get("/proposals")
def list_proposals(status: str | None = None, limit: int = 50):
    limit = max(1, min(limit, 200))
    with get_conn() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute(
                    """SELECT p.*, b.name AS business_name
                       FROM proposals p
                       LEFT JOIN opportunities o ON o.id = p.opportunity_id
                       LEFT JOIN businesses b ON b.id = o.business_id
                       WHERE p.status = %s ORDER BY p.created_at DESC LIMIT %s""",
                    (status, limit),
                )
            else:
                cur.execute(
                    """SELECT p.*, b.name AS business_name
                       FROM proposals p
                       LEFT JOIN opportunities o ON o.id = p.opportunity_id
                       LEFT JOIN businesses b ON b.id = o.business_id
                       ORDER BY p.created_at DESC LIMIT %s""",
                    (limit,),
                )
            return cur.fetchall()


class ProposalStatusUpdate(BaseModel):
    status: str


class ProjectStartRequest(BaseModel):
    start_date: date | None = None
    target_date: date | None = None


class ProjectRequirements(BaseModel):
    requirements: dict = Field(default_factory=dict)


class DeliveryApproval(BaseModel):
    approved: bool


class LaunchSettingsUpdate(BaseModel):
    settings: dict = Field(default_factory=dict)



@app.patch("/proposals/{proposal_id}/status")
def update_proposal_status(proposal_id: str, payload: ProposalStatusUpdate):
    allowed = {"draft", "sent", "accepted", "rejected", "expired"}
    if payload.status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid proposal status")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT p.*, o.business_id, o.service_id, o.title AS opportunity_title
                   FROM proposals p
                   JOIN opportunities o ON o.id = p.opportunity_id
                   WHERE p.id = %s""",
                (proposal_id,),
            )
            proposal = cur.fetchone()
            if not proposal:
                raise HTTPException(status_code=404, detail="Proposal not found")
            if proposal["status"] == "accepted" and payload.status == "accepted":
                raise HTTPException(status_code=409, detail="Proposal is already accepted")
            if proposal["status"] in {"rejected", "expired"} and payload.status == "accepted":
                raise HTTPException(status_code=409, detail="A rejected or expired proposal cannot be accepted")
            if payload.status == "accepted":
                cur.execute("SELECT id FROM projects WHERE opportunity_id = %s LIMIT 1", (proposal["opportunity_id"],))
                if cur.fetchone():
                    raise HTTPException(status_code=409, detail="A project already exists for this opportunity")

            if payload.status == "accepted":
                cur.execute(
                    """UPDATE proposals SET status = %s, accepted_at = now()
                       WHERE id = %s RETURNING *""",
                    (payload.status, proposal_id),
                )
            else:
                cur.execute(
                    """UPDATE proposals
                       SET status = %s,
                           sent_at = CASE WHEN %s = 'sent' THEN COALESCE(sent_at, now()) ELSE sent_at END
                       WHERE id = %s RETURNING *""",
                    (payload.status, payload.status, proposal_id),
                )
            updated = cur.fetchone()

            if payload.status != "accepted":
                return {"proposal": updated}

            cur.execute(
                """INSERT INTO clients (business_id, status, customer_since)
                   VALUES (%s, 'active', CURRENT_DATE)
                   ON CONFLICT (business_id) DO UPDATE SET status = 'active'
                   RETURNING id""",
                (proposal["business_id"],),
            )
            client_id = cur.fetchone()["id"]

            cur.execute(
                """INSERT INTO projects
                   (client_id, opportunity_id, service_id, name, status,
                    agreed_price, recurring_price)
                   VALUES (%s, %s, %s, %s, 'planning', %s, %s)
                   RETURNING id""",
                (
                    client_id, proposal["opportunity_id"], proposal["service_id"],
                    proposal["opportunity_title"], proposal["total_amount"],
                    proposal["recurring_amount"],
                ),
            )
            project_id = cur.fetchone()["id"]

            tasks = [
                ("Confirm requirements", "Collect required access, content, integrations, and acceptance criteria.", "high"),
                ("Generate implementation", "Generate the actual project package from approved requirements.", "high"),
                ("Run automated QA", "Validate generated artifacts against service acceptance criteria.", "high"),
                ("Client review", "Share preview/package and record approval before production activation.", "high"),
                ("Deploy or activate", "Launch the approved implementation when credentials and target are configured.", "high"),
                ("Handoff", "Deliver access, documentation, package, and operating instructions.", "normal"),
            ]
            for title, description, priority in tasks:
                cur.execute(
                    """INSERT INTO tasks (project_id, title, description, priority)
                       VALUES (%s, %s, %s, %s)""",
                    (project_id, title, description, priority),
                )
            cur.execute(
                """INSERT INTO implementations (project_id, status, requirements)
                   VALUES (%s, 'requirements', '{}'::jsonb)
                   ON CONFLICT (project_id) DO NOTHING""",
                (project_id,),
            )

            cur.execute(
                """INSERT INTO revenue_transactions
                   (client_id, project_id, proposal_id, transaction_type, status, amount, recurring_amount, metadata)
                   VALUES (%s,%s,%s,'sale','pending',%s,%s,%s::jsonb)""",
                (
                    client_id, project_id, proposal_id,
                    proposal["total_amount"] or 0, proposal["recurring_amount"] or 0,
                    json.dumps({"source": "proposal_acceptance"}),
                ),
            )
            milestones = [
                ("Planning", "in_progress"),
                ("Build", "pending"),
                ("QA", "pending"),
                ("Client Review", "pending"),
                ("Launch / Activation", "pending"),
                ("Handoff", "pending"),
            ]
            for sequence, (name, status) in enumerate(milestones):
                cur.execute(
                    """INSERT INTO project_milestones (project_id, name, status, sequence)
                       VALUES (%s,%s,%s,%s)""",
                    (project_id, name, status, sequence),
                )

            cur.execute(
                """UPDATE opportunities
                   SET status = 'won', next_action = 'Deliver project', updated_at = now()
                   WHERE id = %s""",
                (proposal["opportunity_id"],),
            )
            cur.execute(
                """INSERT INTO activities
                   (business_id, opportunity_id, project_id, type, subject, content, metadata)
                   VALUES (%s, %s, %s, 'deal_won', %s, %s, %s::jsonb)""",
                (
                    proposal["business_id"], proposal["opportunity_id"], project_id,
                    "Deal accepted and project created",
                    "Accepted proposal automatically created a client project and delivery checklist.",
                    json.dumps({"proposal_id": str(proposal_id), "project_id": str(project_id)}),
                ),
            )
            return {
                "proposal": updated,
                "client_id": client_id,
                "project_id": project_id,
                "created_tasks": len(tasks),
            }


class TaskStatusUpdate(BaseModel):
    status: str


@app.post("/projects/{project_id}/requirements")
def save_project_requirements(project_id: str, payload: ProjectRequirements):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT p.id, p.status, b.name AS business_name, b.website_url,
                          s.name AS service_name
                   FROM projects p
                   JOIN clients c ON c.id = p.client_id
                   JOIN businesses b ON b.id = c.business_id
                   LEFT JOIN services s ON s.id = p.service_id
                   WHERE p.id = %s""",
                (project_id,),
            )
            project = cur.fetchone()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            cur.execute(
                """INSERT INTO implementations (project_id, requirements, status, updated_at)
                   VALUES (%s, %s::jsonb, 'requirements', now())
                   ON CONFLICT (project_id) DO UPDATE
                   SET requirements = EXCLUDED.requirements,
                       status = CASE WHEN implementations.status IN ('deployed', 'complete')
                                     THEN implementations.status ELSE 'requirements' END,
                       updated_at = now()
                   RETURNING *""",
                (project_id, json.dumps(payload.requirements)),
            )
            implementation = cur.fetchone()
            cur.execute(
                "UPDATE projects SET requirements = %s::jsonb WHERE id = %s RETURNING *",
                (json.dumps(payload.requirements), project_id),
            )
            project = cur.fetchone()
            return {"project": project, "implementation": implementation}


def _delivery_project(cur, project_id: str):
    cur.execute(
        """SELECT p.*, c.business_id, b.name AS business_name, b.website_url,
                  s.name AS service_name
           FROM projects p
           JOIN clients c ON c.id = p.client_id
           JOIN businesses b ON b.id = c.business_id
           LEFT JOIN services s ON s.id = p.service_id
           WHERE p.id = %s""",
        (project_id,),
    )
    project = cur.fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    cur.execute("SELECT * FROM implementations WHERE project_id = %s", (project_id,))
    implementation = cur.fetchone()
    if not implementation:
        cur.execute(
            """INSERT INTO implementations (project_id, requirements, status)
               VALUES (%s, %s::jsonb, 'requirements') RETURNING *""",
            (project_id, json.dumps(project.get("requirements") or {})),
        )
        implementation = cur.fetchone()
    return project, implementation


@app.post("/projects/{project_id}/generate")
def generate_project_delivery(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            project, implementation = _delivery_project(cur, project_id)
            if implementation["status"] == "approved":
                raise HTTPException(status_code=409, detail="Approved implementation cannot be regenerated")
            service = project.get("service_name")
            cur.execute("SELECT options FROM project_options WHERE project_id=%s", (project_id,))
            option_row = cur.fetchone()
            selected = option_row["options"] if option_row else {}
            missing = validate_options(service, selected)
            if missing:
                raise HTTPException(
                    status_code=409,
                    detail={"message": "Complete project configuration before build", "missing_options": missing},
                )
            try:
                compiled = compile_requirements(service, selected, implementation.get("requirements") or {})
            except ValueError as exc:
                raise HTTPException(
                    status_code=409,
                    detail={"message": str(exc), "missing_options": validate_options(service, selected)},
                ) from exc
            cur.execute(
                "UPDATE implementations SET requirements=%s::jsonb, updated_at=now() WHERE project_id=%s RETURNING *",
                (json.dumps(compiled), project_id),
            )
            implementation = cur.fetchone()
            project["requirements"] = compiled
    result = generate_project(project)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE implementations
                   SET status='generated', generated_at=now(), validation='{}'::jsonb, updated_at=now()
                   WHERE project_id=%s RETURNING *""",
                (project_id,),
            )
            implementation = cur.fetchone()
            cur.execute("DELETE FROM delivery_artifacts WHERE project_id=%s", (project_id,))
            for name in result["files"]:
                cur.execute(
                    """INSERT INTO delivery_artifacts
                       (project_id, implementation_id, kind, name, path, metadata)
                       VALUES (%s,%s,'generated_file',%s,%s,%s::jsonb)""",
                    (project_id, implementation["id"], name, str(result["workspace"]), json.dumps({"version": "delivery-v1"})),
                )
            cur.execute(
                """UPDATE projects SET status='build' WHERE id=%s AND status NOT IN ('completed','cancelled')
                   RETURNING id""",
                (project_id,),
            )
            return {"project_id": project_id, "implementation": implementation, "generated": result}


@app.get("/projects/{project_id}/qa-plan")
def project_qa_plan(project_id: str):
    project, implementation = _delivery_project(project_id)
    plan = build_plan(project.get("service_name"), implementation.get("requirements") or {})
    return {"project_id": project_id, "service": project.get("service_name"), "checks": plan["qa_checks"]}


@app.post("/projects/{project_id}/validate")
def validate_project_delivery(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            project, implementation = _delivery_project(cur, project_id)
            project["requirements"] = implementation.get("requirements") or project.get("requirements") or {}
    result = validate_project(project)
    plan = build_plan(project.get("service_name"), project.get("requirements") or {})
    result["qa_plan"] = plan["qa_checks"]
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE implementations
                   SET status=%s, validated_at=CASE WHEN %s THEN now() ELSE validated_at END,
                       validation=%s::jsonb, updated_at=now()
                   WHERE project_id=%s RETURNING *""",
                ("validated" if result["passed"] else "failed", result["passed"], json.dumps(result), project_id),
            )
            implementation = cur.fetchone()
            return {"project_id": project_id, "implementation": implementation, "validation": result}


@app.post("/projects/{project_id}/approval")
def approve_project_delivery(project_id: str, payload: DeliveryApproval):
    with get_conn() as conn:
        with conn.cursor() as cur:
            project, implementation = _delivery_project(cur, project_id)
            if not payload.approved:
                cur.execute(
                    "UPDATE implementations SET status='changes_requested', approved_at=NULL, updated_at=now() WHERE project_id=%s RETURNING *",
                    (project_id,),
                )
                return cur.fetchone()
            if implementation["status"] != "validated" or not (implementation.get("validation") or {}).get("passed"):
                raise HTTPException(status_code=409, detail="Project must pass validation before approval")
            cur.execute(
                """UPDATE implementations SET status='approved', approved_at=now(), updated_at=now()
                   WHERE project_id=%s RETURNING *""",
                (project_id,),
            )
            return cur.fetchone()


LAUNCH_OPTIONS = [
    {"key": "client_hosting", "name": "Use client's existing hosting", "category": "Hosting", "description": "Deploy to the client's current web host after access and DNS are confirmed."},
    {"key": "cloudflare_pages", "name": "Cloudflare Pages", "category": "Hosting", "description": "Suggested managed static hosting option for generated websites."},
    {"key": "vercel", "name": "Vercel", "category": "Hosting", "description": "Suggested managed hosting option for web projects that fit its deployment model."},
    {"key": "netlify", "name": "Netlify", "category": "Hosting", "description": "Suggested managed static hosting option with optional form handling."},
    {"key": "self_hosted", "name": "Self-hosted", "category": "Hosting", "description": "Use the client's VPS/server and configure its web root, DNS, and HTTPS."},
    {"key": "custom", "name": "Other / custom", "category": "Hosting", "description": "Record a custom provider or deployment target."},
]

LAUNCH_RESOURCES = [
    {"category": "Hosting", "name": "Cloudflare Pages", "url": "https://pages.cloudflare.com/", "reason": "Managed hosting option for generated static sites."},
    {"category": "Hosting", "name": "Vercel", "url": "https://vercel.com/", "reason": "Managed deployment option for supported web projects."},
    {"category": "Hosting", "name": "Netlify", "url": "https://www.netlify.com/", "reason": "Static hosting with optional form handling."},
    {"category": "DNS", "name": "Cloudflare DNS", "url": "https://www.cloudflare.com/dns/", "reason": "Useful when the client needs DNS and domain routing."},
    {"category": "Forms", "name": "Netlify Forms", "url": "https://docs.netlify.com/manage/forms/setup/", "reason": "Optional form handling for compatible static sites."},
    {"category": "Analytics", "name": "Plausible Analytics", "url": "https://plausible.io/", "reason": "Optional lightweight website analytics."},
]

def _launch_checklist(project: dict, settings: dict):
    service = project.get("service_name") or "Project"
    launch_mode = settings.get("launch_mode", "prepare_and_client_launch")
    hosting = settings.get("hosting_option")
    checks = []

    if service == "AI Website":
        checks = [
            ("content_approved", "Production content/assets approved", bool(settings.get("content_approved")), True, "Client-approved copy, branding, images, and contact details."),
            ("domain", "Production domain", bool(settings.get("domain")), True, "The client's domain or an approved production subdomain."),
            ("hosting_option", "Hosting option selected", bool(hosting), True, "Choose an existing host, managed host, self-hosting, or custom target."),
        ]
        if launch_mode == "luma_deploy":
            checks += [
                ("hosting_access", "Hosting access confirmed", bool(settings.get("hosting_access")), True, "Deployment access or a configured server target is required."),
                ("dns_access", "DNS access confirmed", bool(settings.get("dns_access")), True, "Someone must be able to route the domain to the approved host."),
                ("ssl_ready", "HTTPS / SSL confirmed", bool(settings.get("ssl_ready")), True, "HTTPS must be configured before declaring the site live."),
                ("production_url", "Production URL", bool(settings.get("production_url")), True, "Final URL used for monitoring."),
            ]
    elif service in {"Appointment Automation", "AI Receptionist", "Lead Capture System", "Review Automation", "Custom Automation"}:
        checks = [
            ("requirements_approved", "Workflow requirements approved", bool(settings.get("requirements_approved")), True, "Client confirms workflow, triggers, destinations, and acceptance criteria."),
            ("provider_selected", "Automation/provider option selected", bool(settings.get("provider_selected")), True, "Select the client's existing platform or an approved implementation option."),
            ("credentials_ready", "Required credentials/access confirmed", bool(settings.get("credentials_ready")), True, "Credentials or delegated access must be supplied by the client."),
            ("test_approved", "Production test approved", bool(settings.get("test_approved")), True, "Client confirms the production test behaved as expected."),
        ]
    elif service == "Video Walkthrough":
        checks = [
            ("content_approved", "Script/assets approved", bool(settings.get("content_approved")), True, "Client approves the script, branding, and supplied assets."),
            ("delivery_destination", "Delivery destination selected", bool(settings.get("delivery_destination")), True, "Choose the client's site, storage, video platform, or handoff package."),
        ]
    else:
        checks = [
            ("requirements_approved", "Requirements approved", bool(settings.get("requirements_approved")), True, "Client confirms the scope and acceptance criteria."),
            ("delivery_destination", "Delivery destination selected", bool(settings.get("delivery_destination")), True, "Choose deployment, activation, or handoff destination."),
        ]

    return [
        {"key": key, "label": label, "required": required, "complete": complete, "help": help_text}
        for key, label, complete, required, help_text in checks
    ]

def _launch_response(project: dict, settings: dict):
    checklist = _launch_checklist(project, settings)
    ready = all(item["complete"] for item in checklist if item["required"])
    return {
        "project_id": str(project["id"]),
        "business_name": project.get("business_name"),
        "service": project.get("service_name"),
        "ready": ready,
        "launch_options": LAUNCH_OPTIONS,
        "checklist": checklist,
        "settings": settings,
        "suggestions": LAUNCH_RESOURCES,
        "note": "Options and suggestions are configurable. Luma does not create third-party accounts or fabricate credentials.",
    }

@app.get("/launch/options")
def launch_options():
    return {"options": LAUNCH_OPTIONS}

@app.get("/launch/resources")
def launch_resources():
    return {"resources": LAUNCH_RESOURCES}

@app.get("/projects/{project_id}/launch-readiness")
def get_launch_readiness(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            project, _ = _delivery_project(cur, project_id)
            cur.execute("SELECT settings FROM launch_settings WHERE project_id=%s", (project_id,))
            row = cur.fetchone()
            settings = row["settings"] if row else {}
            return _launch_response(project, settings)

@app.post("/projects/{project_id}/launch-settings")
def save_launch_settings(project_id: str, payload: LaunchSettingsUpdate):
    allowed = {
        "domain", "hosting_provider", "hosting_option", "launch_mode", "hosting_access", "dns_access",
        "ssl_ready", "contact_email", "phone", "production_url", "content_approved", "privacy_url",
        "terms_url", "analytics", "requirements_approved", "provider_selected", "credentials_ready",
        "test_approved", "delivery_destination"
    }
    settings = {str(k): v for k, v in payload.settings.items() if k in allowed}
    with get_conn() as conn:
        with conn.cursor() as cur:
            project, _ = _delivery_project(cur, project_id)
            cur.execute(
                """INSERT INTO launch_settings (project_id, settings, ready, updated_at)
                   VALUES (%s, %s::jsonb, false, now())
                   ON CONFLICT (project_id) DO UPDATE
                   SET settings=EXCLUDED.settings, updated_at=now()
                   RETURNING settings""",
                (project_id, json.dumps(settings)),
            )
            saved = cur.fetchone()["settings"]
            result = _launch_response(project, saved)
            cur.execute("UPDATE launch_settings SET ready=%s, updated_at=now() WHERE project_id=%s", (result["ready"], project_id))
            return result

@app.post("/projects/{project_id}/deploy")
def deploy_project_delivery(project_id: str, request: Request):
    with get_conn() as conn:
        with conn.cursor() as cur:
            project, implementation = _delivery_project(cur, project_id)
            if implementation["status"] != "approved":
                raise HTTPException(status_code=409, detail="Project must be approved before deployment")
            principal=request.state.principal
            decision=evaluate_action("deploy",tools=["deploy"],approval_required=True,approved=True)
            if decision.decision!="allow":
                raise HTTPException(status_code=403,detail=decision.reason)
            cur.execute("SELECT settings FROM launch_settings WHERE project_id=%s", (project_id,))
            launch_row = cur.fetchone()
            launch_settings = launch_row["settings"] if launch_row else {}
            readiness = _launch_response(project, launch_settings)
            if not readiness["ready"]:
                missing = [item["label"] for item in readiness["checklist"] if item["required"] and not item["complete"]]
                raise HTTPException(status_code=409, detail={"message": "Complete the client launch checklist before deployment", "missing": missing})
            cur.execute(
                """INSERT INTO deployment_runs
                   (project_id, implementation_id, status, target, approved_at, started_at)
                   VALUES (%s,%s,'running',%s,now(),now()) RETURNING *""",
                (project_id, implementation["id"], os.getenv("LUMA_DEPLOY_ROOT")),
            )
            run = cur.fetchone()
    project["requirements"] = implementation.get("requirements") or project.get("requirements") or {}
    try:
        result = deploy_static(project)
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE deployment_runs SET status='completed', completed_at=now(), output=%s::jsonb
                       WHERE id=%s RETURNING *""",
                    (json.dumps(result), run["id"]),
                )
                cur.execute(
                    "UPDATE implementations SET status='deployed', updated_at=now() WHERE project_id=%s RETURNING *",
                    (project_id,),
                )
                implementation = cur.fetchone()
                cur.execute(
                    "UPDATE projects SET status='active' WHERE id=%s RETURNING *",
                    (project_id,),
                )
                project = cur.fetchone()
                return {"project": project, "implementation": implementation, "deployment": result,"governance":decision.__dict__}
    except Exception as exc:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE deployment_runs SET status='failed', completed_at=now(), error=%s
                       WHERE id=%s""",
                    (f"{type(exc).__name__}: {exc}", run["id"]),
                )
        raise HTTPException(status_code=500, detail=f"Deployment failed: {type(exc).__name__}: {exc}")


@app.post("/projects/{project_id}/monitor")
def monitor_project(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            project, implementation = _delivery_project(cur, project_id)
            url = (implementation.get("requirements") or {}).get("production_url") or project.get("website_url")
            if not url:
                raise HTTPException(status_code=400, detail="No production URL configured")
    try:
        result = check_live_url(url)
    except Exception as exc:
        result = {"url": url, "healthy": False, "error": f"{type(exc).__name__}: {exc}"}
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO activities (business_id, project_id, type, subject, content, metadata)
                   VALUES (%s,%s,'deployment_check','Production deployment check',%s,%s::jsonb)""",
                (project["business_id"], project_id, json.dumps(result), json.dumps(result)),
            )
    return result


@app.get("/projects/{project_id}/artifacts")
def list_project_artifacts(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM projects WHERE id=%s", (project_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Project not found")
            cur.execute("SELECT * FROM delivery_artifacts WHERE project_id=%s ORDER BY created_at", (project_id,))
            return cur.fetchall()


@app.get("/projects/{project_id}/download")
def download_project_delivery(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            project, implementation = _delivery_project(cur, project_id)
            project["requirements"] = implementation.get("requirements") or project.get("requirements") or {}
    archive = package_project(project)
    return FileResponse(archive, filename=archive.name, media_type="application/zip")


@app.post("/projects/{project_id}/handoff")
def create_project_handoff(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            project, implementation = _delivery_project(cur, project_id)
            if implementation["status"] not in {"approved", "deployed"}:
                raise HTTPException(status_code=409, detail="Project must be validated and approved before handoff")
            project["requirements"] = implementation.get("requirements") or project.get("requirements") or {}
    archive = package_project(project)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO handoffs (project_id, package_path, status, completed_at)
                   VALUES (%s,%s,'ready',now())
                   ON CONFLICT (project_id) DO UPDATE
                   SET package_path=EXCLUDED.package_path, status='ready', completed_at=now()
                   RETURNING *""",
                (project_id, str(archive)),
            )
            handoff = cur.fetchone()
            cur.execute(
                """INSERT INTO activities (business_id, project_id, type, subject, content, metadata)
                   VALUES (%s,%s,'handoff_ready','Delivery handoff ready',%s,%s::jsonb)""",
                (project["business_id"], project_id, "Client delivery package is ready.", json.dumps({"package": str(archive)})),
            )
            return {"handoff": handoff, "download": f"/projects/{project_id}/download"}


@app.get("/projects/{project_id}/milestones")
def list_project_milestones(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM projects WHERE id=%s", (project_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Project not found")
            cur.execute("SELECT * FROM project_milestones WHERE project_id=%s ORDER BY sequence", (project_id,))
            return cur.fetchall()


@app.patch("/projects/{project_id}/milestones/{milestone_id}")
def update_project_milestone(project_id: str, milestone_id: str, payload: dict):
    allowed = {"pending", "in_progress", "blocked", "completed"}
    if payload.get("status") not in allowed:
        raise HTTPException(status_code=400, detail="Invalid milestone status")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE project_milestones
                   SET status=%s, completed_at=CASE WHEN %s='completed' THEN now() ELSE completed_at END
                   WHERE id=%s AND project_id=%s RETURNING *""",
                (payload["status"], payload["status"], milestone_id, project_id),
            )
            milestone = cur.fetchone()
            if not milestone:
                raise HTTPException(status_code=404, detail="Milestone not found")
            return milestone


@app.patch("/tasks/{task_id}/status")
def update_task_status(task_id: str, payload: TaskStatusUpdate):
    allowed = {"todo", "in_progress", "blocked", "done", "completed"}
    if payload.status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid task status")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tasks SET status = %s WHERE id = %s RETURNING *",
                (payload.status, task_id),
            )
            task = cur.fetchone()
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            return task


@app.post("/projects/{project_id}/start")
def start_project(project_id: str, payload: ProjectStartRequest | None = None):
    payload = payload or ProjectStartRequest()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Project not found")
            cur.execute(
                """UPDATE projects
                   SET status = 'active',
                       start_date = COALESCE(%s, start_date, CURRENT_DATE),
                       target_date = COALESCE(%s, target_date)
                   WHERE id = %s RETURNING *""",
                (payload.start_date, payload.target_date, project_id),
            )
            return cur.fetchone()


@app.get("/projects/{project_id}")
def get_project(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
            project = cur.fetchone()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            cur.execute(
                "SELECT * FROM tasks WHERE project_id = %s ORDER BY priority DESC, created_at",
                (project_id,),
            )
            project["tasks"] = cur.fetchall()
            return project


# --- Strong MVP completion APIs ------------------------------------------------

@app.get("/control/agents")
def list_agents():
    from agent_layer import AGENTS
    return [{"name": name, **definition} for name, definition in AGENTS.items()]

@app.get("/control/agents/{agent_name}")
def get_agent(agent_name: str):
    from agent_layer import agent_policy
    try:
        return agent_policy(agent_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@app.post("/control/agents/evaluations")
def evaluate_agent(payload: dict):
    if not payload.get("agent_name"):
        raise HTTPException(status_code=400, detail="agent_name is required")
    score = payload.get("score")
    if score is not None and not 0 <= float(score) <= 100:
        raise HTTPException(status_code=400, detail="score must be between 0 and 100")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO agent_evaluations
                   (agent_run_id, agent_name, evaluator, score, passed, feedback)
                   VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
                (payload.get("agent_run_id"), payload["agent_name"], payload.get("evaluator", "human"),
                 score, payload.get("passed"), payload.get("feedback")),
            )
            return cur.fetchone()

@app.get("/projects/{project_id}/dependencies")
def list_project_dependencies(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM project_dependencies WHERE project_id=%s ORDER BY created_at", (project_id,))
            items = cur.fetchall()
            blockers = [x for x in items if x["required"] and x["status"] not in ("complete", "approved")]
            return {"dependencies": items, "blocked": bool(blockers), "blockers": blockers}

@app.post("/projects/{project_id}/dependencies")
def create_project_dependency(project_id: str, payload: dict):
    if not payload.get("name"):
        raise HTTPException(status_code=400, detail="name is required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO project_dependencies
                   (project_id, depends_on_project_id, dependency_type, name, status, required, metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING *""",
                (project_id, payload.get("depends_on_project_id"), payload.get("dependency_type", "external"),
                 payload["name"], payload.get("status", "pending"), payload.get("required", True),
                 json.dumps(payload.get("metadata") or {})),
            )
            return cur.fetchone()

@app.patch("/projects/{project_id}/dependencies/{dependency_id}")
def update_project_dependency(project_id: str, dependency_id: str, payload: dict):
    status = payload.get("status")
    allowed = {"pending", "in_progress", "complete", "approved", "blocked"}
    if status and status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid dependency status")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE project_dependencies
                   SET status=COALESCE(%s,status),
                       metadata=COALESCE(%s::jsonb,metadata),
                       completed_at=CASE WHEN %s IN ('complete','approved') THEN now() ELSE completed_at END
                   WHERE id=%s AND project_id=%s RETURNING *""",
                (status, json.dumps(payload.get("metadata")) if payload.get("metadata") is not None else None,
                 status, dependency_id, project_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Dependency not found")
            return row

@app.post("/projects/{project_id}/approvals")
def record_project_approval(project_id: str, payload: dict):
    approval_type = payload.get("approval_type")
    decision = payload.get("decision")
    if approval_type not in {"requirements", "build", "qa", "launch", "handoff"}:
        raise HTTPException(status_code=400, detail="Invalid approval type")
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="Decision must be approved or rejected")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO approval_history
                   (project_id, entity_type, entity_id, approval_type, decision, actor_type, actor_id, notes, metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING *""",
                (project_id, payload.get("entity_type", "project"), payload.get("entity_id", project_id),
                 approval_type, decision, payload.get("actor_type", "human"), payload.get("actor_id"),
                 payload.get("notes"), json.dumps(payload.get("metadata") or {})),
            )
            return cur.fetchone()

@app.get("/projects/{project_id}/approvals")
def list_project_approvals(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM approval_history WHERE project_id=%s ORDER BY created_at DESC", (project_id,))
            return cur.fetchall()

@app.post("/projects/{project_id}/revisions")
def create_revision(project_id: str, payload: dict):
    if not payload.get("summary"):
        raise HTTPException(status_code=400, detail="summary is required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO revision_requests
                   (project_id, implementation_id, requested_by, summary, details, priority)
                   VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
                (project_id, payload.get("implementation_id"), payload.get("requested_by", "client"),
                 payload["summary"], payload.get("details"), payload.get("priority", "normal")),
            )
            cur.execute(
                """INSERT INTO activities (project_id, type, subject, content, metadata)
                   VALUES (%s,'revision_requested','Client revision request',%s,%s::jsonb)""",
                (project_id, payload["summary"], json.dumps({"priority": payload.get("priority", "normal")})),
            )
            return cur.fetchone()

@app.patch("/projects/{project_id}/revisions/{revision_id}")
def update_revision(project_id: str, revision_id: str, payload: dict):
    status = payload.get("status")
    if status and status not in {"requested", "accepted", "rejected", "completed"}:
        raise HTTPException(status_code=400, detail="Invalid revision status")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE revision_requests SET status=COALESCE(%s,status),
                   resolved_at=CASE WHEN %s IN ('completed','rejected') THEN now() ELSE resolved_at END
                   WHERE id=%s AND project_id=%s RETURNING *""",
                (status, status, revision_id, project_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Revision request not found")
            return row

@app.get("/projects/{project_id}/revisions")
def list_revisions(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM revision_requests WHERE project_id=%s ORDER BY created_at DESC", (project_id,))
            return cur.fetchall()

@app.get("/projects/{project_id}/qa-contract")
def project_qa_contract(project_id: str):
    from service_adapters import build_plan
    with get_conn() as conn:
        with conn.cursor() as cur:
            project, implementation = _delivery_project(cur, project_id)
            requirements = (implementation or {}).get("requirements") or project.get("requirements") or {}
            return build_plan(project.get("service_name"), requirements)

@app.get("/integrations/{integration_id}/health")
def integration_health(integration_id: str):
    from integration_runtime import runtime
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM integration_connections WHERE id=%s", (integration_id,))
            connection = cur.fetchone()
            if not connection:
                raise HTTPException(status_code=404, detail="Integration not found")
            result = runtime.adapter(connection["provider"]).health_check()
            new_status = "verified" if result.status == "ok" else connection["status"]
            cur.execute(
                "UPDATE integration_connections SET status=%s, connected_at=CASE WHEN %s='verified' THEN COALESCE(connected_at,now()) ELSE connected_at END WHERE id=%s RETURNING *",
                (new_status, new_status, integration_id),
            )
            return {"connection": cur.fetchone(), "health": result.__dict__}

@app.post("/integrations/{integration_id}/execute")
def integration_execute(integration_id: str, payload: dict):
    from integration_runtime import runtime
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM integration_connections WHERE id=%s", (integration_id,))
            connection = cur.fetchone()
            if not connection:
                raise HTTPException(status_code=404, detail="Integration not found")
            if connection["status"] != "verified":
                raise HTTPException(status_code=409, detail="Integration must be verified before execution")
            result = runtime.adapter(connection["provider"]).execute(payload.get("capability", "unknown"), payload.get("payload"))
            return {"connection_id": integration_id, "result": result.__dict__}

@app.post("/secrets/references")
def create_secret_reference(payload: dict):
    if not payload.get("provider") or not payload.get("reference") or not payload.get("owner_type"):
        raise HTTPException(status_code=400, detail="provider, reference, and owner_type are required")
    # Only a reference is accepted. Raw credentials are intentionally rejected.
    forbidden = {"secret", "password", "token", "api_key", "auth_token", "client_secret"}
    if any(k in payload for k in forbidden):
        raise HTTPException(status_code=400, detail="Raw credentials are not accepted; store them in a secret manager and submit a reference")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO secret_references (owner_type, owner_id, provider, reference, metadata)
                   VALUES (%s,%s,%s,%s,%s::jsonb) RETURNING *""",
                (payload["owner_type"], payload.get("owner_id"), payload["provider"], payload["reference"],
                 json.dumps(payload.get("metadata") or {})),
            )
            return cur.fetchone()

@app.post("/secrets/references/{reference_id}/revoke")
def revoke_secret_reference(reference_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE secret_references SET status='revoked', revoked_at=now() WHERE id=%s RETURNING *", (reference_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Secret reference not found")
            return row

@app.get("/recurring-revenue")
def list_recurring_revenue(status: str | None = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute("SELECT * FROM recurring_revenue WHERE status=%s ORDER BY next_billing_at NULLS LAST", (status,))
            else:
                cur.execute("SELECT * FROM recurring_revenue ORDER BY next_billing_at NULLS LAST")
            return cur.fetchall()

@app.post("/recurring-revenue")
def create_recurring_revenue(payload: dict):
    if payload.get("amount") is None:
        raise HTTPException(status_code=400, detail="amount is required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO recurring_revenue
                   (client_id, project_id, billing_record_id, amount, currency, interval, next_billing_at, metadata)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING *""",
                (payload.get("client_id"), payload.get("project_id"), payload.get("billing_record_id"),
                 payload["amount"], payload.get("currency", "USD"), payload.get("interval", "month"),
                 payload.get("next_billing_at"), json.dumps(payload.get("metadata") or {})),
            )
            return cur.fetchone()

@app.patch("/recurring-revenue/{revenue_id}")
def update_recurring_revenue(revenue_id: str, payload: dict):
    status = payload.get("status")
    if status and status not in {"active", "paused", "cancelled"}:
        raise HTTPException(status_code=400, detail="Invalid recurring revenue status")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE recurring_revenue SET amount=COALESCE(%s,amount), status=COALESCE(%s,status),
                   next_billing_at=COALESCE(%s,next_billing_at),
                   cancelled_at=CASE WHEN %s='cancelled' THEN now() ELSE cancelled_at END
                   WHERE id=%s RETURNING *""",
                (payload.get("amount"), status, payload.get("next_billing_at"), status, revenue_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Recurring revenue record not found")
            return row

@app.get("/automation/schedules")
def list_automation_schedules():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM automation_schedules ORDER BY next_run_at NULLS LAST")
            return cur.fetchall()

@app.post("/automation/schedules")
def create_automation_schedule(payload: dict):
    if not payload.get("workflow_name") or not payload.get("cron_expression"):
        raise HTTPException(status_code=400, detail="workflow_name and cron_expression are required")
    try:
        workflow_definition(payload["workflow_name"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    with get_conn() as conn:
        with conn.cursor() as cur:
            expression=payload["cron_expression"]
            try:
                scheduled_for=payload.get("next_run_at") or next_run(expression)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))
            cur.execute(
                """INSERT INTO automation_schedules (workflow_name, cron_expression, input, next_run_at)
                   VALUES (%s,%s,%s::jsonb,%s) RETURNING *""",
                (payload["workflow_name"], expression, json.dumps(payload.get("input") or {}), scheduled_for),
            )
            return cur.fetchone()

@app.patch("/automation/schedules/{schedule_id}")
def update_automation_schedule(schedule_id: str, payload: dict):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE automation_schedules SET enabled=COALESCE(%s,enabled), cron_expression=COALESCE(%s,cron_expression),
                   next_run_at=COALESCE(%s,next_run_at), input=COALESCE(%s::jsonb,input)
                   WHERE id=%s RETURNING *""",
                (payload.get("enabled"), payload.get("cron_expression"), payload.get("next_run_at"),
                 json.dumps(payload.get("input")) if payload.get("input") is not None else None, schedule_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Schedule not found")
            return row


@app.post("/portal/project/{project_id}/approve")
def portal_approve(project_id: str, token: str, payload: dict | None = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, client_id FROM client_portal_access
                   WHERE project_id=%s AND token_hash=%s AND status='active'
                     AND (expires_at IS NULL OR expires_at > now())""",
                (project_id, hash_token(token)),
            )
            access = cur.fetchone()
            if not access:
                raise HTTPException(status_code=401, detail="Invalid or expired portal token")
            cur.execute(
                """INSERT INTO approval_history
                   (project_id, entity_type, entity_id, approval_type, decision, actor_type, notes)
                   VALUES (%s,'project',%s,'launch','approved','client',%s) RETURNING *""",
                (project_id, project_id, (payload or {}).get("notes")),
            )
            approval = cur.fetchone()
            cur.execute("UPDATE client_portal_access SET last_used_at=now() WHERE id=%s", (access["id"],))
            return {"approval": approval, "message": "Client approval recorded. Production actions remain subject to Luma launch gates."}

@app.post("/portal/project/{project_id}/revision")
def portal_revision(project_id: str, token: str, payload: dict):
    if not payload.get("summary"):
        raise HTTPException(status_code=400, detail="summary is required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id, client_id FROM client_portal_access
                   WHERE project_id=%s AND token_hash=%s AND status='active'
                     AND (expires_at IS NULL OR expires_at > now())""",
                (project_id, hash_token(token)),
            )
            access = cur.fetchone()
            if not access:
                raise HTTPException(status_code=401, detail="Invalid or expired portal token")
            cur.execute(
                """INSERT INTO revision_requests
                   (project_id, implementation_id, requested_by, summary, details, priority)
                   VALUES (%s,%s,'client',%s,%s,%s) RETURNING *""",
                (project_id, payload.get("implementation_id"), payload["summary"],
                 payload.get("details"), payload.get("priority", "normal")),
            )
            revision = cur.fetchone()
            cur.execute("UPDATE client_portal_access SET last_used_at=now() WHERE id=%s", (access["id"],))
            return revision


@app.post("/integrations/{integration_id}/execute")
def execute_provider_action(integration_id: str, payload: dict, request: Request):
    capability=payload.get("capability")
    if not capability: raise HTTPException(status_code=400,detail="capability is required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM integration_connections WHERE id=%s",(integration_id,))
            integration=cur.fetchone()
    if not integration: raise HTTPException(status_code=404,detail="Integration not found")
    action_map={"health_check":"read","list_calendars":"read","read_availability":"read","list_contacts":"read",
                "list_event_types":"read","booking_link":"draft","create_contact":"write_crm","create_deal":"write_crm",
                "create_event":"create_event","send_message":"send_message","create_invoice":"charge_payment"}
    action=action_map.get(capability,"write_crm")
    principal=request.state.principal
    import uuid
    actor_id=principal.get("sub")
    try: uuid.UUID(str(actor_id))
    except Exception: actor_id=None
    if principal.get("role") in {"owner","admin","operator"}:
        allowed_scopes=["read","draft","write_crm","create_event","send_message","charge_payment","deploy"]
    elif principal.get("role")=="client":
        allowed_scopes=["read"]
    else:
        from agent_layer import agent_policy
        try: allowed_scopes=agent_policy(payload.get("agent_name","research"))["agent"]["tools"]
        except ValueError: allowed_scopes=["read"]
    decision=evaluate_action(action,tools=allowed_scopes,
                             approval_required=action in {"create_event","send_message","charge_payment","deploy"},
                             approved=payload.get("approved") is True,
                             estimated_cost=float(payload.get("estimated_cost") or 0),
                             spent=float(payload.get("spent_usd") or 0),
                             budget=float(payload.get("budget_usd") or 0))
    if decision.decision!="allow": return {"executed":False,"decision":decision.__dict__}
    try:
        result=execute_integration(integration,capability,payload.get("input") or {})
    except Exception as exc:
        result={"status":"error","provider":integration["provider"],"error":type(exc).__name__}
    result_status=result.status if hasattr(result,"status") else result.get("status","unknown")
    if result_status=="error":
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE integration_connections SET status='error', metadata=metadata || %s::jsonb WHERE id=%s",
                            (json.dumps({"last_provider_error":result.error if hasattr(result,"error") else result.get("error")}),integration_id))
    with get_conn() as conn:
        with conn.cursor() as cur:
            status=result.status if hasattr(result,"status") else result.get("status","unknown")
            cur.execute("""INSERT INTO audit_log(actor_type,actor_id,action,entity_type,entity_id,metadata)
                           VALUES (%s,%s,'provider_action','integration_connection',%s,%s::jsonb)""",
                        (principal.get("role","agent"),actor_id,integration_id,
                         json.dumps({"capability":capability,"status":status})))
            cur.execute("SELECT receipt_hash FROM agent_action_receipts ORDER BY created_at DESC LIMIT 1")
            previous=cur.fetchone()
            receipt=make_receipt(action=action,decision=decision.decision,actor=principal.get("sub","unknown"),
                                  entity_type="integration_connection",entity_id=integration_id,
                                  previous_hash=previous["receipt_hash"] if previous else None,
                                  metadata={"capability":capability,"status":status})
            cur.execute("""INSERT INTO agent_action_receipts
              (actor_type,actor_id,action,decision,risk,reason,previous_hash,receipt_hash,entity_type,entity_id,metadata)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
              (principal.get("role","agent"),actor_id,action,decision.decision,decision.risk,decision.reason,
               receipt["previous_hash"],receipt["hash"],"integration_connection",integration_id,json.dumps(receipt["metadata"])))
    return {"executed":True,"decision":decision.__dict__,"receipt_hash":receipt["hash"],
            "result":result.__dict__ if hasattr(result,"__dict__") else result}

@app.post("/integrations/{integration_id}/verify")
def verify_integration(integration_id: str, payload: dict):
    if payload.get("approved") is not True:
        raise HTTPException(status_code=400, detail="Explicit approved=true is required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM integration_connections WHERE id=%s",(integration_id,))
            row=cur.fetchone()
            if not row: raise HTTPException(status_code=404,detail="Integration not found")
    health=provider_status(row) if row.get("secret_ref") else {"status":"handoff_required","error":"No secret reference"}
    if health["status"]!="ok" and not payload.get("allow_handoff"):
        raise HTTPException(status_code=409,detail={"message":"Provider health check failed","health":health})
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE integration_connections
                   SET status='verified', connected_at=COALESCE(connected_at,now()),
                       last_health_check_at=now(), metadata=metadata || %s::jsonb
                   WHERE id=%s RETURNING *""",
                (json.dumps({"verified_by": payload.get("verified_by", "human"), "verification_note": payload.get("note"),"health":health}), integration_id),
            )
            row = cur.fetchone()
            if not row: raise HTTPException(status_code=404, detail="Integration not found")
            cur.execute(
                """INSERT INTO audit_log (actor_type, action, entity_type, entity_id, metadata)
                   VALUES ('human','integration_verified','integration_connection',%s,%s::jsonb)""",
                (integration_id, json.dumps({"provider": row["provider"], "category": row["category"]})),
            )
            return row


@app.post("/auth/login")
def login(payload: dict):
    email=(payload.get("email") or "").strip().lower()
    password=payload.get("password") or ""
    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password are required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE lower(email)=lower(%s) AND active=true", (email,))
            user=cur.fetchone()
            if not user or not verify_password(password,user["password_hash"]):
                raise HTTPException(status_code=401, detail="Invalid credentials")
            cur.execute("UPDATE users SET last_login_at=now() WHERE id=%s", (user["id"],))
            token=issue_token(user["id"],user["role"],user["email"])
            return {"access_token":token,"token_type":"bearer","expires_in":int(os.getenv("LUMA_AUTH_TOKEN_TTL_SECONDS","3600")),"role":user["role"]}

@app.post("/auth/users")
def create_user(payload: dict, request: Request):
    principal=request.state.principal
    if not can(principal["role"],"owner"):
        raise HTTPException(status_code=403, detail="Owner role required")
    email=(payload.get("email") or "").strip().lower()
    password=payload.get("password") or ""
    role=payload.get("role","operator")
    if not email or len(password)<12:
        raise HTTPException(status_code=400, detail="email and password (12+ characters) are required")
    if role not in {"owner","admin","operator","client"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    with get_conn() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("INSERT INTO users(email,password_hash,role) VALUES (%s,%s,%s) RETURNING id,email,role,active,created_at",(email,hash_password(password),role))
            except psycopg.errors.UniqueViolation:
                raise HTTPException(status_code=409, detail="User already exists")
            return cur.fetchone()

@app.get("/auth/me")
def auth_me(request: Request):
    return request.state.principal


@app.post("/automation/schedules/claim")
def claim_due_schedule():
    from datetime import datetime, timezone
    now=datetime.now(timezone.utc)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM automation_schedules
                   WHERE enabled=true AND next_run_at IS NOT NULL AND next_run_at <= now()
                   ORDER BY next_run_at LIMIT 1 FOR UPDATE SKIP LOCKED"""
            )
            row=cur.fetchone()
            if not row:
                return {"claimed":False}
            try:
                following=next_run(row["cron_expression"], now)
            except ValueError as exc:
                cur.execute("UPDATE automation_schedules SET enabled=false WHERE id=%s",(row["id"],))
                raise HTTPException(status_code=400, detail=str(exc))
            cur.execute(
                """UPDATE automation_schedules SET last_run_at=%s,next_run_at=%s
                   WHERE id=%s RETURNING *""",(now,following,row["id"])
            )
            return {"claimed":True,"schedule":cur.fetchone()}


@app.get("/analytics/model-costs")
def analytics_model_costs():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT agent_name, COUNT(*) AS runs,
                          COALESCE(SUM(input_tokens),0) AS input_tokens,
                          COALESCE(SUM(output_tokens),0) AS output_tokens,
                          COALESCE(SUM(estimated_cost),0) AS estimated_cost
                   FROM agent_runs GROUP BY agent_name ORDER BY estimated_cost DESC"""
            )
            return cur.fetchall()

@app.get("/analytics/margins")
def analytics_margins():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT p.id AS project_id, p.name, b.name AS business_name,
                          COALESCE(SUM(CASE WHEN rt.status='paid' THEN rt.amount ELSE 0 END),0) AS revenue,
                          COALESCE((SELECT SUM(cr.amount) FROM cost_records cr WHERE cr.project_id=p.id),0) AS direct_costs,
                          COALESCE((SELECT SUM(ar.estimated_cost) FROM agent_runs ar WHERE ar.entity_type='project' AND ar.entity_id=p.id),0) AS model_costs
                   FROM projects p
                   JOIN clients c ON c.id=p.client_id
                   JOIN businesses b ON b.id=c.business_id
                   LEFT JOIN revenue_transactions rt ON rt.project_id=p.id
                   GROUP BY p.id,p.name,b.name ORDER BY revenue DESC"""
            )
            rows=cur.fetchall()
            return [
                {**row,
                 "total_cost": float(row["direct_costs"] or 0)+float(row["model_costs"] or 0),
                 "contribution": float(row["revenue"] or 0)-float(row["direct_costs"] or 0)-float(row["model_costs"] or 0)}
                for row in rows
            ]


@app.get("/integrations/oauth/{provider}/start")
def oauth_start(provider: str, project_id: str, request: Request):
    if provider not in {"google_calendar","microsoft_outlook","hubspot","calendly"}:
        raise HTTPException(status_code=400, detail="Unsupported OAuth provider")
    redirect_uri = str(request.base_url).rstrip("/") + f"/integrations/oauth/{provider}/callback"
    try:
        return {"authorization_url": authorization_url(provider, project_id, redirect_uri)}
    except (RuntimeError, KeyError) as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/integrations/oauth/{provider}/callback")
def oauth_callback(provider: str, code: str, state: str, request: Request):
    claims = verify_state(state)
    if not claims or claims.get("provider") != provider:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM oauth_state_nonces WHERE expires_at < now()")
            try:
                cur.execute("""INSERT INTO oauth_state_nonces(nonce,provider,project_id,expires_at)
                               VALUES (%s,%s,%s,to_timestamp(%s))
                               ON CONFLICT DO NOTHING RETURNING nonce""",
                            (claims["nonce"],provider,claims["project_id"],claims["exp"]))
                if not cur.fetchone():
                    raise HTTPException(status_code=400,detail="OAuth state has already been consumed")
                cur.execute("UPDATE oauth_state_nonces SET consumed_at=now() WHERE nonce=%s",(claims["nonce"],))
            except HTTPException:
                raise
    redirect_uri = str(request.base_url).rstrip("/") + f"/integrations/oauth/{provider}/callback"
    try:
        tokens = token_request(provider, code, redirect_uri, claims.get("code_verifier"))
        secret_ref = f"oauth/{provider}/{claims['project_id']}"
        if tokens.get("expires_in"):
            from time import time
            tokens["expires_at"]=time()+float(tokens["expires_in"])
        secret_backend().put(secret_ref, json.dumps(tokens))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OAuth connection failed: {type(exc).__name__}")

    category = "crm" if provider == "hubspot" else "calendar"
    capabilities = next((item["capabilities"] for item in providers(category) if item["provider"] == provider), [])
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE integration_connections
                   SET status='connected', secret_ref=%s, scopes=%s::jsonb, metadata=metadata || %s::jsonb
                   WHERE project_id=%s AND provider=%s
                   RETURNING *""",
                (
                    secret_ref,
                    json.dumps((tokens.get("scope") or "").split() if isinstance(tokens.get("scope"), str) else []),
                    json.dumps({"oauth": True, "capabilities": capabilities}),
                    claims["project_id"], provider,
                ),
            )
            integration = cur.fetchone()
            if not integration:
                cur.execute(
                    """INSERT INTO integration_connections
                       (project_id, provider, category, status, capabilities, secret_ref, scopes, metadata)
                       VALUES (%s,%s,%s,'connected',%s::jsonb,%s,%s::jsonb,%s::jsonb)
                       RETURNING *""",
                    (
                        claims["project_id"], provider, category, json.dumps(capabilities), secret_ref,
                        json.dumps((tokens.get("scope") or "").split() if isinstance(tokens.get("scope"), str) else []),
                        json.dumps({"oauth": True}),
                    ),
                )
                integration = cur.fetchone()
    return {"status": "connected", "provider": provider, "project_id": claims["project_id"], "integration": integration, "token_storage": "secret_manager"}


# Client trust, outcome, and regional-growth controls.
@app.post("/opportunities/{opportunity_id}/fit")
def evaluate_opportunity_fit(opportunity_id: str, payload: dict):
    result = assess_opportunity(
        evidence_count=payload.get("evidence_count", 0),
        evidence_confidence=payload.get("evidence_confidence", 0),
        impact_confidence=payload.get("impact_confidence", 0),
        solution_fit=payload.get("solution_fit", 0),
        intrusiveness_risk=payload.get("intrusiveness_risk", 0),
        problem_proven=payload.get("problem_proven", True),
    )
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE opportunities
                   SET fit_score=%s, fit_disposition=%s, why_this=%s,
                       why_not=%s::jsonb, alternatives=%s::jsonb
                   WHERE id=%s RETURNING *""",
                (
                    result["score"], result["disposition"],
                    payload.get("why_this"),
                    json.dumps(payload.get("why_not") or []),
                    json.dumps(payload.get("alternatives") or []),
                    opportunity_id,
                ),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Opportunity not found")
            return {"opportunity": row, "assessment": result}

@app.get("/businesses/{business_id}/outreach-preferences")
def get_outreach_preferences(business_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM outreach_preferences WHERE business_id=%s", (business_id,))
            return cur.fetchone() or {
                "business_id": business_id, "status": "normal",
                "contact_count": 0, "reason": None,
            }

@app.patch("/businesses/{business_id}/outreach-preferences")
def update_outreach_preferences(business_id: str, payload: dict):
    status = (payload.get("status") or "normal").lower()
    if status not in {"normal", "maybe_later", "do_not_contact", "not_interested", "complaint"}:
        raise HTTPException(status_code=400, detail="Invalid outreach preference")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO outreach_preferences
                   (business_id,status,reason,source,contact_count)
                   VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (business_id) DO UPDATE SET
                     status=EXCLUDED.status, reason=EXCLUDED.reason, source=EXCLUDED.source,
                     contact_count=EXCLUDED.contact_count, updated_at=now()
                   RETURNING *""",
                (business_id, status, payload.get("reason"), payload.get("source", "operator"),
                 int(payload.get("contact_count", 0))),
            )
            return cur.fetchone()

@app.post("/outreach/check")
def check_outreach_eligibility(payload: dict):
    preference = payload.get("preference", "normal")
    count = int(payload.get("prior_contact_count", 0))
    return outreach_disposition(preference, count)

@app.post("/clients/{client_id}/outcomes")
def record_client_outcome(client_id: str, payload: dict):
    if not payload.get("outcome_type"):
        raise HTTPException(status_code=400, detail="outcome_type is required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO client_outcomes
                   (client_id,project_id,outcome_type,baseline,current_value,status,client_confirmed,notes)
                   VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s) RETURNING *""",
                (
                    client_id, payload.get("project_id"), payload["outcome_type"],
                    json.dumps(payload.get("baseline") or {}),
                    json.dumps(payload.get("current_value") or {}),
                    payload.get("status", "tracking"),
                    bool(payload.get("client_confirmed", False)),
                    payload.get("notes"),
                ),
            )
            return cur.fetchone()

@app.get("/clients/{client_id}/outcomes")
def list_client_outcomes(client_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM client_outcomes WHERE client_id=%s ORDER BY measured_at DESC",
                (client_id,),
            )
            return cur.fetchall()

@app.post("/clients/{client_id}/expansion-check")
def expansion_check(client_id: str, payload: dict):
    result = should_expand(
        payload.get("existing_outcome", "tracking"),
        bool(payload.get("client_approved", False)),
        bool(payload.get("new_problem_evidence", False)),
    )
    return {
        "eligible": result,
        "rule": "Expansion requires demonstrated value, client approval, and separately evidenced need.",
    }

@app.get("/clients/{client_id}/preferences")
def get_client_preferences(client_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM client_preferences WHERE client_id=%s", (client_id,))
            return cur.fetchone() or {
                "client_id": client_id,
                "ai_disclosure": True,
                "data_ownership_note": "Client retains ownership of business data and deliverables, subject to the engagement agreement.",
                "preferred_contact_channel": "email",
                "communication_frequency": "normal",
            }

@app.patch("/clients/{client_id}/preferences")
def update_client_preferences(client_id: str, payload: dict):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO client_preferences
                   (client_id,ai_disclosure,data_ownership_note,preferred_contact_channel,communication_frequency,notes)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (client_id) DO UPDATE SET
                     ai_disclosure=EXCLUDED.ai_disclosure,
                     data_ownership_note=EXCLUDED.data_ownership_note,
                     preferred_contact_channel=EXCLUDED.preferred_contact_channel,
                     communication_frequency=EXCLUDED.communication_frequency,
                     notes=EXCLUDED.notes, updated_at=now()
                   RETURNING *""",
                (
                    client_id, bool(payload.get("ai_disclosure", True)),
                    payload.get("data_ownership_note",
                                "Client retains ownership of business data and deliverables, subject to the engagement agreement."),
                    payload.get("preferred_contact_channel", "email"),
                    payload.get("communication_frequency", "normal"),
                    payload.get("notes"),
                ),
            )
            return cur.fetchone()

@app.get("/regional-playbooks")
def list_regional_playbooks():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM regional_playbooks ORDER BY display_name")
            return cur.fetchall()

@app.post("/regional-playbooks")
def create_regional_playbook(payload: dict):
    if not payload.get("region_key") or not payload.get("display_name"):
        raise HTTPException(status_code=400, detail="region_key and display_name are required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO regional_playbooks
                   (region_key,display_name,status,notes,proven_offers,industry_patterns,outreach_metrics,client_success_metrics)
                   VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb)
                   ON CONFLICT (region_key) DO UPDATE SET
                     display_name=EXCLUDED.display_name, status=EXCLUDED.status, notes=EXCLUDED.notes,
                     proven_offers=EXCLUDED.proven_offers, industry_patterns=EXCLUDED.industry_patterns,
                     outreach_metrics=EXCLUDED.outreach_metrics, client_success_metrics=EXCLUDED.client_success_metrics,
                     updated_at=now()
                   RETURNING *""",
                (
                    payload["region_key"], payload["display_name"], payload.get("status", "pilot"),
                    payload.get("notes"),
                    json.dumps(payload.get("proven_offers") or []),
                    json.dumps(payload.get("industry_patterns") or []),
                    json.dumps(payload.get("outreach_metrics") or {}),
                    json.dumps(payload.get("client_success_metrics") or {}),
                ),
            )
            return cur.fetchone()


# --- Control & Intelligence Core ---

@app.get("/governance/agents/{agent_name}")
def governance_agent(agent_name: str):
    from agent_layer import agent_definition
    try:
        definition=agent_definition(agent_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM agent_policies WHERE agent_name=%s",(agent_name,))
            row=cur.fetchone()
    return {"agent":normalize_policy(agent_name,row), "definition":definition}

@app.post("/governance/evaluate")
def governance_evaluate(payload: dict):
    agent=payload.get("agent_name")
    action=payload.get("action")
    if not agent or not action:
        raise HTTPException(status_code=400,detail="agent_name and action are required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM agent_policies WHERE agent_name=%s",(agent,))
            row=cur.fetchone()
            if row:
                policy=normalize_policy(agent,row)
            else:
                from agent_layer import agent_policy
                policy=agent_policy(agent)
            cur.execute("SELECT COALESCE(SUM(amount),0) AS spent FROM agent_budget_ledger WHERE agent_name=%s AND occurred_at >= date_trunc('month',now())",(agent,))
            spent=float(cur.fetchone()["spent"] or 0)
    decision=evaluate_action(action,tools=policy["tools"],approval_required=policy["approval_required"],
                             approved=bool(payload.get("approved")),spent=spent,budget=policy["budget_usd"],
                             estimated_cost=float(payload.get("estimated_cost") or 0))
    return {"decision":decision.__dict__,"policy":policy,"spent_usd":spent}

@app.post("/governance/receipts")
def governance_receipt(payload: dict):
    receipt=make_receipt(action=payload.get("action","unknown"),decision=payload.get("decision","unknown"),
                         actor=payload.get("actor","agent"),entity_type=payload.get("entity_type"),
                         entity_id=payload.get("entity_id"),cost=payload.get("cost",0),
                         previous_hash=payload.get("previous_hash"),metadata=payload.get("metadata"))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO agent_action_receipts
              (agent_run_id,actor_type,action,decision,risk,reason,estimated_cost,previous_hash,receipt_hash,entity_type,entity_id,metadata)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING *""",
              (payload.get("agent_run_id"),payload.get("actor_type","agent"),receipt["action"],receipt["decision"],
               payload.get("risk","unknown"),payload.get("reason",""),receipt["cost"],receipt["previous_hash"],
               receipt["hash"],receipt["entity_type"],receipt["entity_id"],json.dumps(receipt["metadata"])))
            return cur.fetchone()

@app.post("/evidence/claims")
def create_evidence_claim(payload: dict):
    claim=payload.get("claim")
    evidence=payload.get("evidence") or []
    if not claim or not evidence:
        raise HTTPException(status_code=400,detail="claim and evidence are required")
    built=build_claim(claim,evidence,alternatives=payload.get("alternatives"))
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO evidence_claims
              (business_id,research_report_id,opportunity_id,claim,evidence_strength,alternatives,verified_at)
              VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s) RETURNING *""",
              (payload.get("business_id"),payload.get("research_report_id"),payload.get("opportunity_id"),
               claim,built["evidence_strength"],json.dumps(built["alternatives"]),built["verified_at"]))
            row=cur.fetchone()
            for item in evidence:
                eid=item.get("id")
                if eid:
                    cur.execute("INSERT INTO claim_evidence(claim_id,evidence_id,relation) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
                                (row["id"],eid,item.get("relation","supports")))
            return {**row,"evidence_strength":built["evidence_strength"]}

@app.get("/evidence/claims/{opportunity_id}")
def list_evidence_claims(opportunity_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT c.*, COALESCE(jsonb_agg(jsonb_build_object(
              'id',e.id,'observation',e.observation,'source_url',e.source_url,'confidence',e.confidence,'relation',ce.relation))
              FILTER (WHERE e.id IS NOT NULL),'[]') AS evidence
              FROM evidence_claims c LEFT JOIN claim_evidence ce ON ce.claim_id=c.id
              LEFT JOIN evidence_items e ON e.id=ce.evidence_id
              WHERE c.opportunity_id=%s GROUP BY c.id ORDER BY c.verified_at DESC""",(opportunity_id,))
            return cur.fetchall()

@app.get("/services/{service_name}/blueprint")
def service_blueprint(service_name: str):
    try: return blueprint(service_name)
    except ValueError as exc: raise HTTPException(status_code=404,detail=str(exc))

@app.post("/projects/{project_id}/blueprint")
def project_blueprint(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            project,_=_delivery_project(cur,project_id)
            service=project.get("service_name")
            cur.execute("SELECT options FROM project_options WHERE project_id=%s",(project_id,))
            row=cur.fetchone()
            selected=row["options"] if row else {}
            try:
                return instantiate(service,selected,project.get("requirements") or {})
            except ValueError as exc:
                raise HTTPException(status_code=404,detail=str(exc))

@app.post("/automation/runs/{run_id}/checkpoint")
def save_workflow_checkpoint(run_id: str, payload: dict):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM workflow_runs WHERE id=%s",(run_id,))
            run=cur.fetchone()
            if not run: raise HTTPException(status_code=404,detail="Workflow run not found")
            state=checkpoint_state(run,step=payload.get("step"),state=payload.get("state"))
            cur.execute("""INSERT INTO workflow_checkpoints(workflow_run_id,step,state)
                           VALUES (%s,%s,%s::jsonb) RETURNING *""",
                        (run_id,state["step"],json.dumps(state["state"])))
            cur.execute("UPDATE workflow_runs SET checkpoint_version=checkpoint_version+1, output=%s::jsonb WHERE id=%s",
                        (json.dumps(state["state"]),run_id))
            return cur.fetchone()

@app.get("/automation/runs/{run_id}/checkpoints")
def list_workflow_checkpoints(run_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM workflow_checkpoints WHERE workflow_run_id=%s ORDER BY created_at DESC",(run_id,))
            return cur.fetchall()

@app.post("/analytics/blueprint-optimizations")
def create_blueprint_optimization(payload: dict):
    metric=payload.get("metric_name")
    if not metric or payload.get("before_value") is None or payload.get("after_value") is None:
        raise HTTPException(status_code=400,detail="metric_name, before_value and after_value are required")
    recommendation=propose(metric,payload["before_value"],payload["after_value"],payload.get("target"),
                            payload.get("service"),payload.get("blueprint_version",1))
    with get_conn() as conn:
        with conn.cursor() as cur:
            service_id=None
            if payload.get("service"):
                cur.execute("SELECT id FROM services WHERE name=%s",(payload["service"],))
                row=cur.fetchone(); service_id=row["id"] if row else None
            cur.execute("""INSERT INTO blueprint_optimization_proposals
              (service_id,project_id,source_metric,before_value,after_value,delta,recommendation)
              VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING *""",
              (service_id,payload.get("project_id"),metric,payload["before_value"],payload["after_value"],
               recommendation["delta"],json.dumps(recommendation)))
            return cur.fetchone()

@app.post("/analytics/blueprint-optimizations/scan")
def scan_blueprint_optimizations(payload: dict):
    project_id=payload.get("project_id")
    service=payload.get("service")
    limit=max(1,min(int(payload.get("limit",100)),500))
    with get_conn() as conn:
        with conn.cursor() as cur:
            sql="""SELECT metric_name, MIN(value) AS before_value, MAX(value) AS after_value,
                          MIN(source) AS source
                   FROM client_metric_snapshots
                   WHERE (%s IS NULL OR project_id=%s)
                     AND captured_at >= now() - interval '90 days'
                   GROUP BY metric_name
                   HAVING COUNT(*) >= 2
                   ORDER BY metric_name LIMIT %s"""
            cur.execute(sql,(project_id,project_id,limit))
            rows=cur.fetchall()
            created=[]
            for row in rows:
                recommendation=propose(row["metric_name"],row["before_value"],row["after_value"],None,service,1)
                cur.execute("""INSERT INTO blueprint_optimization_proposals
                  (project_id,source_metric,before_value,after_value,delta,recommendation)
                  VALUES (%s,%s,%s,%s,%s,%s::jsonb) RETURNING *""",
                  (project_id,row["metric_name"],row["before_value"],row["after_value"],
                   recommendation["delta"],json.dumps(recommendation)))
                created.append(cur.fetchone())
            return {"created":created,"count":len(created),"automation":"proposal_only_until_approval"}

@app.post("/analytics/blueprint-optimizations/{proposal_id}/approve")
def approve_blueprint_optimization(proposal_id: str, payload: dict, request: Request):
    if payload.get("approved") is not True:
        raise HTTPException(status_code=400,detail="Explicit approved=true is required")
    principal=request.state.principal
    if principal.get("role") not in {"owner","admin","operator"}:
        raise HTTPException(status_code=403,detail="Operator approval required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM blueprint_optimization_proposals WHERE id=%s",(proposal_id,))
            proposal=cur.fetchone()
            if not proposal: raise HTTPException(status_code=404,detail="Optimization proposal not found")
            cur.execute("""UPDATE blueprint_optimization_proposals
                           SET status='approved',approved_at=now(),approved_by=%s WHERE id=%s RETURNING *""",
                        (principal.get("sub"),proposal_id))
            return cur.fetchone()

@app.post("/analytics/blueprint-optimizations/{proposal_id}/publish")
def publish_blueprint_optimization(proposal_id: str, payload: dict, request: Request):
    if payload.get("approved") is not True:
        raise HTTPException(status_code=400,detail="Explicit approved=true is required")
    principal=request.state.principal
    if principal.get("role") not in {"owner","admin"}:
        raise HTTPException(status_code=403,detail="Owner/admin approval required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT p.*,s.name AS service_name
                          FROM blueprint_optimization_proposals p
                          LEFT JOIN services s ON s.id=p.service_id WHERE p.id=%s""",(proposal_id,))
            proposal=cur.fetchone()
            if not proposal: raise HTTPException(status_code=404,detail="Optimization proposal not found")
            if proposal["status"]!="approved": raise HTTPException(status_code=409,detail="Proposal must be approved before publish")
            if not proposal["service_id"]: raise HTTPException(status_code=409,detail="Proposal has no service")
            cur.execute("SELECT COALESCE(MAX(version),0)+1 AS next_version FROM service_blueprint_versions WHERE service_id=%s",(proposal["service_id"],))
            version=cur.fetchone()["next_version"]
            recommendation=proposal["recommendation"] or {}
            cur.execute("UPDATE service_blueprint_versions SET active=false WHERE service_id=%s",(proposal["service_id"],))
            cur.execute("""INSERT INTO service_blueprint_versions(service_id,version,blueprint,active)
                           SELECT %s,%s,blueprint || %s::jsonb,true
                           FROM service_blueprint_versions WHERE service_id=%s
                           ORDER BY version DESC LIMIT 1 RETURNING *""",
                        (proposal["service_id"],version,json.dumps({"optimization":recommendation}),proposal["service_id"]))
            created=cur.fetchone()
            cur.execute("UPDATE blueprint_optimization_proposals SET status='published' WHERE id=%s",(proposal_id,))
            return {"proposal":proposal,"published_blueprint":created}

@app.get("/analytics/blueprint-optimizations")
def list_blueprint_optimizations(status: str|None=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if status:
                cur.execute("SELECT * FROM blueprint_optimization_proposals WHERE status=%s ORDER BY created_at DESC",(status,))
            else:
                cur.execute("SELECT * FROM blueprint_optimization_proposals ORDER BY created_at DESC LIMIT 200")
            return cur.fetchall()

@app.get("/analytics/unit-economics")
def analytics_unit_economics(project_id: str|None=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if project_id:
                cur.execute("SELECT COALESCE(SUM(amount),0) AS revenue FROM revenue_transactions WHERE project_id=%s AND status IN ('paid','completed')",(project_id,))
                revenue=float(cur.fetchone()["revenue"] or 0)
                cur.execute("SELECT COALESCE(SUM(amount),0) AS cost FROM cost_records WHERE project_id=%s",(project_id,))
                cost=float(cur.fetchone()["cost"] or 0)
            else:
                cur.execute("SELECT COALESCE(SUM(amount),0) AS revenue FROM revenue_transactions WHERE status IN ('paid','completed')")
                revenue=float(cur.fetchone()["revenue"] or 0)
                cur.execute("SELECT COALESCE(SUM(amount),0) AS cost FROM cost_records")
                cost=float(cur.fetchone()["cost"] or 0)
            return unit_economics(revenue,cost)

@app.post("/analytics/client-metrics")
def record_client_metric(payload: dict):
    if not payload.get("metric_name"): raise HTTPException(status_code=400,detail="metric_name is required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO client_metric_snapshots
              (client_id,project_id,metric_name,value,unit,source,client_confirmed)
              VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
              (payload.get("client_id"),payload.get("project_id"),payload["metric_name"],payload.get("value"),
               payload.get("unit"),payload.get("source","operator"),bool(payload.get("client_confirmed"))))
            return cur.fetchone()

@app.get("/analytics/client-metrics/{project_id}")
def list_client_metrics(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM client_metric_snapshots WHERE project_id=%s ORDER BY captured_at DESC",(project_id,))
            return cur.fetchall()


@app.get("/agent-gateway/tools")
def agent_gateway_tools():
    return {"tools":agent_tool_catalog(),"policy":"All writes and external actions must pass /governance/evaluate."}

@app.post("/agent-gateway/authorize")
def agent_gateway_authorize(payload: dict):
    name=payload.get("tool")
    if not name: raise HTTPException(status_code=400,detail="tool is required")
    try: tool=resolve_agent_tool(name)
    except KeyError: raise HTTPException(status_code=404,detail="Unknown agent tool")
    allowed=payload.get("allowed_scopes")
    if not allowed and payload.get("agent_name"):
        from agent_layer import agent_policy
        try: allowed=agent_policy(payload["agent_name"])["agent"]["tools"]
        except ValueError: allowed=[]
    allowed=allowed or []
    decision=evaluate_action(tool["scope"],tools=allowed,
                             approval_required=bool(payload.get("approval_required",True)),
                             approved=bool(payload.get("approved")),
                             spent=float(payload.get("spent_usd") or 0),
                             budget=float(payload.get("budget_usd") or 0),
                             estimated_cost=float(payload.get("estimated_cost") or 0))
    return {"tool":name,"risk":tool["risk"],"decision":decision.__dict__}

@app.post("/agent-evaluations/trajectory")
def record_agent_trajectory(payload: dict):
    if not payload.get("agent_run_id") or payload.get("sequence") is None or not payload.get("event_type"):
        raise HTTPException(status_code=400,detail="agent_run_id, sequence and event_type are required")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO agent_trajectory_events
              (agent_run_id,sequence,event_type,action,input,output,decision,latency_ms,cost_usd)
              VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s) RETURNING *""",
              (payload["agent_run_id"],payload["sequence"],payload["event_type"],payload.get("action"),
               json.dumps(payload.get("input") or {}),json.dumps(payload.get("output") or {}),
               payload.get("decision"),payload.get("latency_ms"),payload.get("cost_usd",0)))
            return cur.fetchone()

@app.get("/agent-evaluations/trajectory/{agent_run_id}")
def get_agent_trajectory(agent_run_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM agent_trajectory_events WHERE agent_run_id=%s ORDER BY sequence,created_at",(agent_run_id,))
            return cur.fetchall()

@app.post("/agent-governance/charge")
def charge_agent_budget(payload: dict):
    if not payload.get("agent_name") or payload.get("amount") is None:
        raise HTTPException(status_code=400,detail="agent_name and amount are required")
    amount=float(payload["amount"])
    if amount < 0: raise HTTPException(status_code=400,detail="amount must be non-negative")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(amount),0) AS spent FROM agent_budget_ledger WHERE agent_name=%s AND occurred_at >= date_trunc('month',now())",(payload["agent_name"],))
            spent=float(cur.fetchone()["spent"] or 0)
            cur.execute("SELECT * FROM agent_policies WHERE agent_name=%s",(payload["agent_name"],))
            row=cur.fetchone()
            if row:
                budget=float(row["budget_usd"] or 0)
            else:
                from agent_layer import agent_policy
                budget=float(agent_policy(payload["agent_name"])["budget_usd"])
            if spent+amount>budget:
                raise HTTPException(status_code=409,detail={"message":"Agent budget exceeded","spent_usd":spent,"budget_usd":budget})
            cur.execute("""INSERT INTO agent_budget_ledger
              (agent_name,project_id,workflow_run_id,agent_run_id,amount,category)
              VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
              (payload["agent_name"],payload.get("project_id"),payload.get("workflow_run_id"),
               payload.get("agent_run_id"),amount,payload.get("category","model")))
            return {"charge":cur.fetchone(),"spent_usd":spent+amount,"budget_usd":budget}


@app.websocket("/voice/stream")
async def voice_stream(websocket: WebSocket):
    signature=websocket.headers.get("X-Twilio-Signature")
    if not validate_twilio_signature(str(websocket.url), {}, signature):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    try:
        await realtime_bridge(websocket, os.getenv("LUMA_VOICE_PUBLIC_URL"))
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close(code=1011)
        except Exception:
            pass


@app.post("/voice/test-call")
def voice_test_call(payload: dict, request: Request):
    """Place a single operator-approved test call to any E.164 destination."""
    principal=request.state.principal
    if principal.get("role") not in {"owner","admin","operator"}:
        raise HTTPException(status_code=403,detail="Operator approval required")
    to=(payload.get("to") or "").strip()
    if not to:
        raise HTTPException(status_code=400,detail="to is required in E.164 format")
    if payload.get("approved") is not True:
        raise HTTPException(status_code=400,detail="Explicit approved=true is required")
    decision=evaluate_action(
        "place_call",
        tools=["voice"],
        approval_required=True,
        approved=True,
        spent=0,
        budget=0,
        estimated_cost=float(payload.get("estimated_cost") or 0),
    )
    if not decision.allowed:
        raise HTTPException(status_code=403,detail=decision.reason)
    integration={
        "provider":"twilio",
        "secret_ref":payload.get("secret_ref") or os.getenv("LUMA_TWILIO_SECRET_REF"),
    }
    if not integration["secret_ref"]:
        raise HTTPException(status_code=503,detail="Twilio secret reference is not configured")
    try:
        result=execute_integration(
            integration,
            "place_call",
            {"to":to,"from":payload.get("from") or os.getenv("TWILIO_FROM_NUMBER"),
             "url":payload.get("url") or os.getenv("LUMA_VOICE_TWIML_URL")}
        )
    except Exception as exc:
        raise HTTPException(status_code=502,detail=f"Voice provider error: {type(exc).__name__}")
    return {"provider_result":result.__dict__,"governance":decision.__dict__}



# --- Optional Voice ---

@app.get("/voice/capabilities")
def get_voice_capabilities():
    return voice_capabilities()


@app.post("/voice/sessions")
def create_voice_session(payload: dict, request: Request):
    mode=payload.get("mode","receptionist")
    if mode not in VOICE_MODES:
        raise HTTPException(status_code=400, detail="Unknown voice mode")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO voice_sessions
                   (business_id,project_id,caller,mode,status,disclosed)
                   VALUES (%s,%s,%s,%s,'active',false) RETURNING *""",
                (payload.get("business_id"),payload.get("project_id"),payload.get("caller"),mode),
            )
            return cur.fetchone()


@app.get("/voice/sessions/{session_id}")
def get_voice_session(session_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM voice_sessions WHERE id=%s",(session_id,))
            session=cur.fetchone()
            if not session: raise HTTPException(status_code=404,detail="Voice session not found")
            cur.execute("SELECT * FROM voice_turns WHERE session_id=%s ORDER BY sequence",(session_id,))
            return {**session,"turns":cur.fetchall()}


@app.post("/voice/sessions/{session_id}/turn")
def record_voice_turn(session_id: str, payload: dict):
    transcript=(payload.get("transcript") or "").strip()
    speaker=payload.get("speaker","caller")
    if not transcript: raise HTTPException(status_code=400,detail="transcript is required")
    if speaker not in {"caller","assistant","system"}:
        raise HTTPException(status_code=400,detail="invalid speaker")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,status FROM voice_sessions WHERE id=%s",(session_id,))
            session=cur.fetchone()
            if not session: raise HTTPException(status_code=404,detail="Voice session not found")
            if session["status"]!="active": raise HTTPException(status_code=409,detail="Voice session is not active")
            cur.execute("SELECT COALESCE(MAX(sequence),0)+1 AS sequence FROM voice_turns WHERE session_id=%s",(session_id,))
            sequence=cur.fetchone()["sequence"]
            cur.execute(
                """INSERT INTO voice_turns(session_id,speaker,transcript,sequence,metadata)
                   VALUES (%s,%s,%s,%s,%s::jsonb) RETURNING *""",
                (session_id,speaker,transcript,sequence,json.dumps(payload.get("metadata") or {})),
            )
            return cur.fetchone()


@app.post("/voice/sessions/{session_id}/disclose")
def disclose_voice_session(session_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE voice_sessions SET disclosed=true WHERE id=%s RETURNING id,disclosed",
                (session_id,),
            )
            row=cur.fetchone()
            if not row: raise HTTPException(status_code=404,detail="Voice session not found")
            return {"session_id":row["id"],"disclosed":row["disclosed"],"text":disclosure_text()}


@app.post("/voice/sessions/{session_id}/end")
def end_voice_session(session_id: str, payload: dict):
    reason=payload.get("reason","completed")
    allowed={"user_requested","escalated","completed","provider_error","policy_blocked"}
    if reason not in allowed: raise HTTPException(status_code=400,detail="invalid end reason")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE voice_sessions SET status=%s, escalation_reason=%s,
                          ended_at=now() WHERE id=%s RETURNING *""",
                (reason, payload.get("escalation_reason"), session_id),
            )
            row=cur.fetchone()
            if not row: raise HTTPException(status_code=404,detail="Voice session not found")
            return row


@app.post("/voice/twilio/incoming")
async def twilio_incoming(request: Request):
    from urllib.parse import parse_qs
    body=(await request.body()).decode("utf-8","replace")
    form={k:v[-1] for k,v in parse_qs(body).items()}
    call_sid=form.get("CallSid") or request.query_params.get("CallSid") or request.headers.get("X-Twilio-CallSid")
    if not validate_twilio_signature(str(request.url), form, request.headers.get("X-Twilio-Signature")):
        raise HTTPException(status_code=403, detail="Invalid Twilio webhook signature")
    if DATABASE_URL and call_sid:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO voice_sessions(caller,mode,status,disclosed)
                       VALUES (%s,'receptionist','active',false)""",
                    (call_sid,),
                )
    stream_url=os.getenv("LUMA_VOICE_STREAM_URL")
    if stream_url:
        xml=twilio_stream_twiml(stream_url)
    else:
        action_url=str(request.base_url).rstrip("/")+"/voice/twilio/gather"
        xml=twilio_gather_twiml(action_url, disclosure_text())
    return Response(content=xml, media_type="application/xml")


@app.post("/voice/twilio/gather")
async def twilio_gather(request: Request):
    from urllib.parse import parse_qs
    body=(await request.body()).decode("utf-8","replace")
    form={k:v[-1] for k,v in parse_qs(body).items()}
    transcript=(form.get("SpeechResult") or "").strip()
    call_sid=form.get("CallSid")
    if not validate_twilio_signature(str(request.url), form, request.headers.get("X-Twilio-Signature")):
        raise HTTPException(status_code=403, detail="Invalid Twilio webhook signature")
    if transcript and DATABASE_URL:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM voice_sessions WHERE caller=%s AND status='active' ORDER BY started_at DESC LIMIT 1",
                    (call_sid,),
                )
                session=cur.fetchone()
                if session:
                    cur.execute("SELECT COALESCE(MAX(sequence),0)+1 AS sequence FROM voice_turns WHERE session_id=%s",(session["id"],))
                    seq=cur.fetchone()["sequence"]
                    cur.execute(
                        """INSERT INTO voice_turns(session_id,speaker,transcript,sequence,metadata)
                           VALUES (%s,'caller',%s,%s,%s::jsonb)""",
                        (session["id"],transcript,seq,json.dumps({"call_sid":call_sid})),
                    )
    action_url=str(request.base_url).rstrip("/")+"/voice/twilio/gather"
    return Response(content=twilio_gather_twiml(action_url,"Thanks. I heard you. I can continue by email, or the voice system can continue this conversation."),media_type="application/xml")



