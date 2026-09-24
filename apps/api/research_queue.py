"""Research queue reliability helpers.

Backoff, claim safety, and adapter result normalization for website research jobs.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

MAX_ATTEMPTS = 5
BASE_BACKOFF_SECONDS = 60


def next_retry_at(attempts: int, now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    exp = min(max(attempts, 1), 8)
    seconds = min(BASE_BACKOFF_SECONDS * (2 ** (exp - 1)), 3600)
    return now + timedelta(seconds=seconds)


def should_fail(attempts: int, max_attempts: int = MAX_ATTEMPTS) -> bool:
    return attempts >= max_attempts


def normalize_analysis(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(raw or {})
    return {
        "http_status": raw.get("http_status") or raw.get("status_code"),
        "https": bool(raw.get("https")),
        "has_mobile_viewport": bool(raw.get("has_mobile_viewport")),
        "has_contact_form": bool(raw.get("has_contact_form")),
        "has_phone_link": bool(raw.get("has_phone_link")),
        "has_email_link": bool(raw.get("has_email_link")),
        "has_cta": bool(raw.get("has_cta")),
        "response_time_ms": raw.get("response_time_ms"),
        "cms": raw.get("cms"),
        "technology_stack": raw.get("technology_stack") or [],
        "url": raw.get("url") or raw.get("final_url"),
        "error": raw.get("error"),
        "adapter": raw.get("adapter") or "default",
        "fetched_at": raw.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
    }


def claim_sql() -> str:
    return """
        UPDATE research_jobs
        SET status='running',
            attempts = attempts + 1,
            locked_at = now(),
            updated_at = now()
        WHERE id = (
            SELECT id FROM research_jobs
            WHERE status = 'pending'
              AND scheduled_at <= now()
            ORDER BY priority ASC, scheduled_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING *
    """


def fail_or_requeue_sql() -> str:
    return """
        UPDATE research_jobs
        SET status = %s,
            last_error = %s,
            scheduled_at = COALESCE(%s, scheduled_at),
            locked_at = NULL,
            updated_at = now()
        WHERE id = %s
        RETURNING *
    """
