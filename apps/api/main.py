import os
import json
import csv
import io
from datetime import date
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
import psycopg

from db import get_conn, ensure_delivery_schema
from qualification import score_opportunity, map_to_service_opportunities
from website_analyzer import analyze_website
from delivery import generate_project, validate_project, package_project, deploy_static, check_live_url
from project_options import option_definitions, validate_options, option_summary
from requirements import compile_requirements
from revenue import revenue_summary, service_performance
from workflows import workflow_definition, next_step
from integrations import providers
from security import authorized
from portal import create_token, hash_token

app = FastAPI(title="Luma API", version="0.7.0")


@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    if request.url.path in {"/", "/health"}:
        return await call_next(request)
    if not authorized(request.headers.get("X-Luma-Key")):
        return JSONResponse(status_code=401, content={"detail": "Authentication required"})
    return await call_next(request)
DATABASE_URL = os.getenv("DATABASE_URL")


@app.on_event("startup")
def startup():
    if DATABASE_URL:
        try:
            ensure_delivery_schema()
        except Exception as exc:
            print(f"[luma] delivery schema check failed: {type(exc).__name__}: {exc}", flush=True)



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
    options: dict = {}



@app.get("/")
def root():
    return {"name": "Luma", "version": "0.6.0", "status": "running"}


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
            missing = validate_options(service, selected)\n            return {"project_id": project_id, "service": service, "options": definitions, "definitions": definitions, "selected": selected,\n                    "validation": {"missing": missing, "complete": not missing}, "summary": option_summary(service, selected)}

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
            return {"project_id": project_id, "service": service, "options": definitions, "selected": selected,
                    "validation": {"missing": missing, "complete": not missing},
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
            status = payload.get("status") or ("completed" if step is None else "running")
            cur.execute(
                """UPDATE workflow_runs
                   SET current_step=%s, status=%s, output=%s::jsonb,
                       completed_at=CASE WHEN %s='completed' THEN now() ELSE completed_at END
                   WHERE id=%s RETURNING *""",
                (step, status, json.dumps(payload.get("output") or {}), status, run_id),
            )
            return cur.fetchone()


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
            cur.execute(
                "UPDATE billing_records SET status='paid', paid_at=now() WHERE id=%s RETURNING *",
                (billing_id,),
            )
            record = cur.fetchone()
            if not record:
                raise HTTPException(status_code=404, detail="Billing record not found")
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
                    cur.execute(
                        """INSERT INTO opportunities
                           (business_id,research_report_id,title,description,problem_evidence,score,
                            confidence,rationale,factors,estimated_value_min,estimated_value_max,status,next_action,service_id)
                           SELECT %s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb,price_min,price_max,
                                  'new','Review evidence and approve outreach',id
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
            cur.execute(
                """INSERT INTO proposals
                   (opportunity_id, offer_id, title, status, total_amount,
                    recurring_amount, content, expires_at)
                   VALUES (%s, %s, %s, 'draft', %s, %s, %s, CURRENT_DATE + 14)
                   RETURNING *""",
                (
                    opportunity_id, offer_id, offer["name"], offer["setup_price"],
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
    requirements: dict = {}


class DeliveryApproval(BaseModel):
    approved: bool


class LaunchSettingsUpdate(BaseModel):
    settings: dict = {}



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


@app.post("/projects/{project_id}/validate")
def validate_project_delivery(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            project, implementation = _delivery_project(cur, project_id)
            project["requirements"] = implementation.get("requirements") or project.get("requirements") or {}
    result = validate_project(project)
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
def deploy_project_delivery(project_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            project, implementation = _delivery_project(cur, project_id)
            if implementation["status"] != "approved":
                raise HTTPException(status_code=409, detail="Project must be approved before deployment")
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
                return {"project": project, "implementation": implementation, "deployment": cur.fetchone() if False else result}
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
