import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
import psycopg

from db import get_conn
from qualification import score_opportunity
from website_analyzer import analyze_website

app = FastAPI(title="Jarvis API", version="0.2.0")
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


@app.get("/")
def root():
    return {"name": "Jarvis", "version": "0.2.0", "status": "running"}


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
    queries = {
        "businesses": "SELECT count(*) FROM businesses",
        "opportunities": "SELECT count(*) FROM opportunities",
        "proposals": "SELECT count(*) FROM proposals",
        "clients": "SELECT count(*) FROM clients",
        "projects": "SELECT count(*) FROM projects",
    }
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                result = {}
                for key, query in queries.items():
                    cur.execute(query)
                    result[key] = cur.fetchone()["count"]
                return result
    except Exception:
        return {key: 0 for key in queries}


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


@app.post("/qualify")
def qualify(payload: dict):
    analysis = payload.get("analysis")
    if not isinstance(analysis, dict):
        raise HTTPException(status_code=400, detail="analysis object is required")
    return score_opportunity(analysis, payload.get("service_name"))
