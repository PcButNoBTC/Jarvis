import time
from datetime import datetime, timezone

def run_cycle():
    print(f"[jarvis-worker] cycle {datetime.now(timezone.utc).isoformat()}", flush=True)
    # V1.1: scheduled lead discovery and research jobs land here.

if __name__ == "__main__":
    while True:
        run_cycle()
        time.sleep(300)
