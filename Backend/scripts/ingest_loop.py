"""Periodic Agmarknet ingest loop for the ingest container."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone


def run_ingest() -> None:
    print(
        f"[ingest-loop] {datetime.now(timezone.utc).isoformat()} starting ingest…",
        flush=True,
    )
    code = subprocess.call([sys.executable, "ingest_prices.py", "--ingest"])
    if code != 0:
        print(f"[ingest-loop] ingest exited {code}; will retry next cycle", flush=True)


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)
    os.environ["PYTHONPATH"] = root
    subprocess.check_call([sys.executable, "scripts/wait_for_db.py"])
    subprocess.call([sys.executable, "scripts/enable_postgis.py"])
    print("[ingest-loop] Running initial Agmarknet ingest…", flush=True)
    run_ingest()

    interval = int(os.getenv("INGEST_INTERVAL_SECONDS", "86400"))
    print(f"[ingest-loop] Sleeping {interval}s between runs…", flush=True)
    while True:
        time.sleep(interval)
        run_ingest()


if __name__ == "__main__":
    main()
