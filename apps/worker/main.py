import os
import time
from datetime import datetime, timezone

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
    except Exception as exc:
        print(f"[luma-worker] cycle error: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    while True:
        run_cycle()
        time.sleep(POLL_SECONDS)
