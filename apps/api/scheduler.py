"""Small deterministic scheduler helper.

The worker can call due_schedules() on each cycle. Actual cron parsing is kept
out of the database layer so it can later be replaced by APScheduler/Celery
without changing API records.
"""

from datetime import datetime, timezone

def due_schedules(rows, now=None):
    now = now or datetime.now(timezone.utc)
    return [row for row in rows if row.get("enabled") and (row.get("next_run_at") is None or row["next_run_at"] <= now)]
