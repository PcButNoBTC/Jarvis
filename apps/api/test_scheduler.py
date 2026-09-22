from datetime import datetime, timezone, timedelta
from scheduler import due_schedules

def test_due_schedule_detection():
    now = datetime.now(timezone.utc)
    rows = [
        {"enabled": True, "next_run_at": now - timedelta(seconds=1)},
        {"enabled": False, "next_run_at": now - timedelta(seconds=1)},
        {"enabled": True, "next_run_at": now + timedelta(hours=1)},
    ]
    assert len(due_schedules(rows, now)) == 1
