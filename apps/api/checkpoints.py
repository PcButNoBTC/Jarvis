"""Small durable checkpoint helpers for workflow recovery."""
from __future__ import annotations

def checkpoint_state(run, *, step=None, state=None):
    return {
        "workflow_run_id":str(run["id"]),
        "step":step if step is not None else run.get("current_step"),
        "state":state if state is not None else run.get("output") or {},
        "resume_safe":True,
    }

def retry_delay(attempt, base_seconds=5, max_seconds=300):
    return min(max_seconds, base_seconds*(2**max(0,int(attempt)-1)))
