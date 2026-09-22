import os
from fastapi import FastAPI
import psycopg

app = FastAPI(title="Jarvis API", version="0.1.0")
DATABASE_URL = os.getenv("DATABASE_URL")

@app.get("/")
def root():
    return {"name": "Jarvis", "version": "0.1.0", "status": "running"}

@app.get("/health")
def health():
    db = "unknown"
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
    if not DATABASE_URL:
        return {"businesses": 0, "opportunities": 0, "proposals": 0, "clients": 0, "projects": 0}
    queries = {
        "businesses": "SELECT count(*) FROM businesses",
        "opportunities": "SELECT count(*) FROM opportunities",
        "proposals": "SELECT count(*) FROM proposals",
        "clients": "SELECT count(*) FROM clients",
        "projects": "SELECT count(*) FROM projects",
    }
    try:
        with psycopg.connect(DATABASE_URL, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                return {k: cur.execute(q) or cur.fetchone()[0] for k,q in queries.items()}
    except Exception:
        return {k: 0 for k in queries}
