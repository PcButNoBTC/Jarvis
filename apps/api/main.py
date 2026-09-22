import os
import json
import csv
import io
from datetime import date
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import psycopg

from db import get_conn
from qualification import score_opportunity, map_to_service_opportunities
from website_analyzer import analyze_website

app = FastAPI(title="Luma API", version="0.3.0")
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


class ProspectCSVImport(BaseModel):
    csv_text: str
    source: str = "csv"
    source_url: str | None = None


class OutreachDraftUpdate(BaseModel):
    subject: str | None = None
    body: str | None = None
    status: str | None = None


@app.get("/")
def root():
    return {"name": "Luma", "version": "0.3.0", "status": "running"}


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
                            estimated_value_min,estimated_value_max,status,next_action,service_id)
                           SELECT %s,%s,%s,%s,%s::jsonb,%s,price_min,price_max,
                                  'new','Review evidence and approve outreach',id
                           FROM services WHERE name=%s RETURNING id""",
                        (
                            business["id"],
                            report_id,
                            o["title"],
                            o["description"],
                            json.dumps(o["factors"]),
                            o["score"],
                            o["service"],
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        opportunity_ids.append(row["id"])

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
                        o["service"],
                    ),
                )
                row = cur.fetchone()
                if row:
                    opportunity_ids.append(row["id"])

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
