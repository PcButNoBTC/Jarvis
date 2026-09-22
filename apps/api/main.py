import os
import json
from datetime import date
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import psycopg

from db import get_conn
from qualification import score_opportunity
from website_analyzer import analyze_website

app = FastAPI(title="Luma API", version="0.2.0")
DATABASE_URL = os.getenv("DATABASE_URL")


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


@app.get("/")
def root():
    return {"name": "Luma", "version": "0.2.0", "status": "running"}


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
                           b.name AS business_name
                    FROM projects p
                    JOIN clients c ON c.id = p.client_id
                    JOIN businesses b ON b.id = c.business_id
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
        analysis=analyze_website(business["website_url"])
        qualification=score_opportunity(analysis,"AI Website")
        evidence=qualification["factors"]
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO websites
                    (business_id,url,http_status,https_enabled,mobile_friendly,load_time_ms,cms,technology_stack,last_checked_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,'[]'::jsonb,now()) RETURNING id""",
                    (business["id"],analysis["url"],analysis["http_status"],analysis["https"],
                     analysis["has_mobile_viewport"],analysis["response_time_ms"],analysis["cms"]))
                website_id=cur.fetchone()["id"]
                cur.execute("""INSERT INTO research_reports
                    (business_id,summary,observed_problems,opportunities,evidence,model,prompt_version)
                    VALUES (%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s) RETURNING id""",
                    (business["id"],"Automated website research based only on observed technical signals.",
                     json.dumps(evidence),json.dumps([{"service":"AI Website","score":qualification["score"]}]),
                     json.dumps(analysis),"heuristic","website-analysis-v1"))
                report_id=cur.fetchone()["id"]
                cur.execute("""INSERT INTO opportunities
                    (business_id,research_report_id,title,description,problem_evidence,score,
                     estimated_value_min,estimated_value_max,status,next_action,service_id)
                    SELECT %s,%s,%s,%s,%s::jsonb,%s,price_min,price_max,
                           'new','Review evidence and approve outreach',id
                    FROM services WHERE name='AI Website' RETURNING id""",
                    (business["id"],report_id,"Website improvement opportunity",
                     "Observed website signals that may justify a website improvement conversation.",
                     json.dumps(evidence),qualification["score"]))
                opportunity=cur.fetchone()
                cur.execute("""UPDATE research_jobs SET status='completed',completed_at=now(),
                               locked_at=NULL,last_error=NULL,updated_at=now() WHERE id=%s""",(job_id,))
                return {"job_id":job_id,"business_id":business["id"],"website_id":website_id,
                        "research_report_id":report_id,"opportunity_id":opportunity["id"] if opportunity else None,
                        "qualification":qualification}
    except Exception as exc:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""UPDATE research_jobs SET status='failed',last_error=%s,
                               locked_at=NULL,updated_at=now() WHERE id=%s""",
                            (f"{type(exc).__name__}: {exc}",job_id))
        raise HTTPException(status_code=500, detail="Research job failed")


@app.post("/outreach/drafts")
def create_outreach_draft(opportunity_id: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT o.*,b.name AS business_name,b.email AS business_email
                           FROM opportunities o JOIN businesses b ON b.id=o.business_id WHERE o.id=%s""",(opportunity_id,))
            opportunity=cur.fetchone()
            if not opportunity: raise HTTPException(status_code=404,detail="Opportunity not found")
            if not opportunity["business_email"]: raise HTTPException(status_code=400,detail="Business has no email")
            evidence=opportunity["problem_evidence"] or []
            evidence_text=", ".join(item.get("factor","observed issue") for item in evidence[:3])
            subject="A quick idea for "+opportunity["business_name"]
            body=(f"Hi,\n\nI reviewed {opportunity['business_name']}'s website and noticed "
                  f"{evidence_text or 'a few areas worth reviewing'}. "
                  "I can share a short, specific improvement plan if useful.\n\nBest,\nLuma")
            cur.execute("""INSERT INTO messages
                (business_id,opportunity_id,channel,direction,subject,body,status)
                VALUES (%s,%s,'email','outbound',%s,%s,'draft') RETURNING *""",
                (opportunity["business_id"],opportunity_id,subject,body))
            cur.execute("""UPDATE opportunities SET next_action='Human review of outreach draft',updated_at=now()
                           WHERE id=%s""",(opportunity_id,))
            return cur.fetchone()


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
    qualification = score_opportunity(analysis, "AI Website")
    evidence = qualification["factors"]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO websites
                   (business_id, url, http_status, https_enabled, mobile_friendly,
                    load_time_ms, cms, technology_stack, last_checked_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, '[]'::jsonb, now())
                   RETURNING id""",
                (
                    business_id, analysis["url"], analysis["http_status"],
                    analysis["https"], analysis["has_mobile_viewport"],
                    analysis["response_time_ms"], analysis["cms"],
                ),
            )
            website_id = cur.fetchone()["id"]

            cur.execute(
                """INSERT INTO research_reports
                   (business_id, summary, observed_problems, opportunities, evidence,
                    model, prompt_version)
                   VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s)
                   RETURNING id""",
                (
                    business_id,
                    "Automated website research based only on observed technical signals.",
                    json.dumps(evidence),
                    json.dumps([{"service": "AI Website", "score": qualification["score"]}]),
                    json.dumps(analysis),
                    "heuristic",
                    "website-analysis-v1",
                ),
            )
            report_id = cur.fetchone()["id"]

            cur.execute(
                """INSERT INTO opportunities
                   (business_id, research_report_id, title, description,
                    problem_evidence, score, estimated_value_min,
                    estimated_value_max, status, next_action)
                   SELECT %s, %s, %s, %s, %s::jsonb, %s, price_min, price_max,
                          'new', 'Review evidence and approve outreach'
                   FROM services WHERE name = 'AI Website'
                   RETURNING id""",
                (
                    business_id, report_id,
                    "Website improvement opportunity",
                    "Observed website signals that may justify a website improvement conversation.",
                    json.dumps(evidence),
                    qualification["score"],
                ),
            )
            opportunity = cur.fetchone()

    return {
        "business_id": business_id,
        "website_id": website_id,
        "research_report_id": report_id,
        "opportunity_id": opportunity["id"] if opportunity else None,
        "analysis": analysis,
        "qualification": qualification,
    }


@app.post("/qualify")
def qualify(payload: dict):
    analysis = payload.get("analysis")
    if not isinstance(analysis, dict):
        raise HTTPException(status_code=400, detail="analysis object is required")
    return score_opportunity(analysis, payload.get("service_name"))


from sales import build_call_prep, build_proposal_content


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

            setup_price = payload.get("setup_price")
            if setup_price is None:
                setup_price = float(service["price_min"] or 0)
            recurring_price = payload.get("recurring_price")
            name = payload.get("name") or "{} — {}".format(service["name"], opportunity["business_name"])
            deliverables = [
                "Discovery and requirements confirmation for " + service["name"],
                "Configured implementation of the agreed scope",
                "Basic testing and handoff",
            ]
            assumptions = [
                "Client provides required access, content, and approvals.",
                "Scope remains within the agreed deliverables.",
            ]
            exclusions = [
                "Unscoped third-party licenses or usage fees.",
                "Material scope changes after approval.",
            ]
            cur.execute(
                """INSERT INTO offers
                   (opportunity_id, service_id, name, description, setup_price,
                    recurring_price, deliverables, assumptions, exclusions)
                   VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
                   RETURNING *""",
                (
                    opportunity_id, service["id"], name, service["description"],
                    setup_price, recurring_price, json.dumps(deliverables),
                    json.dumps(assumptions), json.dumps(exclusions),
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
                ("Build first release", "Implement the agreed scope and document material decisions.", "high"),
                ("Test and review", "Run functional checks and client review before handoff.", "normal"),
                ("Handoff", "Deliver access, documentation, and operating instructions.", "normal"),
            ]
            for title, description, priority in tasks:
                cur.execute(
                    """INSERT INTO tasks (project_id, title, description, priority)
                       VALUES (%s, %s, %s, %s)""",
                    (project_id, title, description, priority),
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
