"""Periodic Agmarknet ingest loop for the ingest container."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone


def run_ingest() -> int:
    print(
        f"[ingest-loop] {datetime.now(timezone.utc).isoformat()} starting ingest…",
        flush=True,
    )
    code = subprocess.call([sys.executable, "ingest_prices.py", "--ingest"])
    if code != 0:
        print(f"[ingest-loop] ingest exited {code}; will retry sooner", flush=True)
    return code


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)
    os.environ["PYTHONPATH"] = root
    subprocess.check_call([sys.executable, "scripts/wait_for_db.py"])
    subprocess.call([sys.executable, "scripts/enable_postgis.py"])
    warmup = int(os.getenv("INGEST_START_DELAY_SECONDS", "0"))
    if warmup > 0:
        print(
            f"[ingest-loop] waiting {warmup}s so the API can finish waking…",
            flush=True,
        )
        time.sleep(warmup)

    interval = int(os.getenv("INGEST_INTERVAL_SECONDS", "86400"))
    retry = int(os.getenv("INGEST_RETRY_SECONDS", "1800"))
    while True:
        code = run_ingest()
        wait = interval if code == 0 else retry
        print(f"[ingest-loop] Sleeping {wait}s between runs…", flush=True)
        time.sleep(wait)


if __name__ == "__main__":
    main()
