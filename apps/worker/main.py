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

            while True:
                claim = client.post(f"{API_URL}/automation/schedules/claim")
                claim.raise_for_status()
                data = claim.json()
                if not data.get("claimed"):
                    break
                schedule = data["schedule"]
                run = client.post(f"{API_URL}/automation/runs", json={
                    "workflow_name": schedule["workflow_name"],
                    "trigger_type": "schedule",
                    "input": schedule.get("input") or {},
                })
                if run.status_code >= 400:
                    print(f"[luma-worker] schedule {schedule['id']}: {run.text}", flush=True)
    except Exception as exc:
        print(f"[luma-worker] cycle failed: {type(exc).__name__}: {exc}", flush=True)
