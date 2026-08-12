"""Block until DATABASE_URL accepts connections."""

from __future__ import annotations

import os
import sys
import time

from sqlalchemy import create_engine, text


def main() -> None:
    url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:mandisync_password@localhost:5432/mandisync_db",
    )
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    deadline = time.time() + int(os.getenv("DB_WAIT_SECONDS", "90"))
    last_error = ""
    while time.time() < deadline:
        try:
            engine = create_engine(url, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("[wait_for_db] Postgres is ready.")
            return
        except Exception as exc:  # noqa: BLE001 — retry any connect failure
            last_error = str(exc)
            time.sleep(2)

    print(f"[wait_for_db] Timed out: {last_error}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
