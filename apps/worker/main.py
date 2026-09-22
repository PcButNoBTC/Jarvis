import time
from datetime import datetime, timezone

def run_cycle():
    print(f"[luma-worker] cycle {datetime.now(timezone.utc).isoformat()}", flush=True)
    # Discovery/research scheduling will be added here after source adapters
    # are configured. Outbound communication remains human-approved.

if __name__ == "__main__":
    while True:
        run_cycle()
        time.sleep(300)
