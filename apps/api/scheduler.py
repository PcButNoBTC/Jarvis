"""Dependency-free five-field cron scheduling."""
from datetime import datetime, timedelta, timezone

def _field(expr, minimum, maximum):
    values=set()
    for part in expr.split(","):
        part=part.strip()
        if part=="*":
            values.update(range(minimum, maximum+1)); continue
        if part.startswith("*/"):
            step=int(part[2:])
            if step<=0: raise ValueError("cron step must be positive")
            values.update(range(minimum, maximum+1, step)); continue
        if "-" in part:
            a,b=map(int,part.split("-",1))
            if a>b or a<minimum or b>maximum: raise ValueError("invalid cron range")
            values.update(range(a,b+1)); continue
        n=int(part)
        if n<minimum or n>maximum: raise ValueError("invalid cron value")
        values.add(n)
    return values

def cron_matches(expression, dt):
    parts=expression.split()
    if len(parts)!=5: raise ValueError("cron expression must have five fields")
    minute,hour,dom,month,dow=parts
    return (dt.minute in _field(minute,0,59) and dt.hour in _field(hour,0,23)
            and dt.day in _field(dom,1,31) and dt.month in _field(month,1,12)
            and (dt.weekday()+1)%7 in _field(dow,0,7))

def next_run(expression, after=None):
    after=after or datetime.now(timezone.utc)
    if after.tzinfo is None: after=after.replace(tzinfo=timezone.utc)
    candidate=after.replace(second=0,microsecond=0)+timedelta(minutes=1)
    for _ in range(60*24*366*5):
        if cron_matches(expression,candidate): return candidate
        candidate += timedelta(minutes=1)
    raise ValueError("No cron occurrence found within five years")

def due_schedules(rows, now=None):
    now=now or datetime.now(timezone.utc)
    return [row for row in rows if row.get("enabled") and row.get("next_run_at") and row["next_run_at"] <= now]
