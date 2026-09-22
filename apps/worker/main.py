import os
import time
from datetime import datetime, timezone
import json

import httpx

API_URL = os.getenv("API_URL", "http://api:8000")
POLL_SECONDS = int(os.getenv("WORKER_POLL_SECONDS", "30"))
LUMA_API_KEY = os.getenv("LUMA_API_KEY", "")


def run_cycle():
    print(f"[luma-worker] cycle {datetime.now(timezone.utc).isoformat()}", flush=True)
    try:
        with httpx.Client(timeout=20, headers={"X-Luma-Key": LUMA_API_KEY} if LUMA_API_KEY else {}) as client:
            response = client.get(f"{API_URL}/research/jobs", params={"status": "pending", "limit": 5})
            response.raise_for_status()
            for job in response.json():
                result = client.post(f"{API_URL}/research/jobs/{job['id']}/run")
                if result.status_code >= 400:
                    print(f"[luma-worker] job {job['id']}: {result.text}", flush=True)

            schedules = client.get(f"{API_URL}/automation/schedules").json()
            now = datetime.now(timezone.utc)
            for schedule in schedules:
                next_run = schedule.get("next_run_at")
                if not schedule.get("enabled") or not next_run:
                    continue
                try:
                    due = datetime.fromisoformat(next_run.replace("Z", "+00:00")) <= now
                except (TypeError, ValueError):
                    due = False
                if due:
                    run = client.post(f"{API_URL}/automation/runs", json={
                        "workflow_name": schedule["workflow_name"],
                        "trigger_type": "schedule",
                        "input": schedule.get("input") or {},
                    })
                    if run.status_code < 400:
                        client.patch(f"{API_URL}/automation/schedules/{schedule['id']}",
                                     json={"last_run_at": now.isoformat()})
    except Exception as exc:
        print(f"[luma-worker] cycle error: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    while True:
        run_cycle()
        time.sleep(POLL_SECONDS)
