"""API container entrypoint: wait for DB, bootstrap, run uvicorn."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(root)
    os.environ["PYTHONPATH"] = root
    env = os.environ.copy()
    run([sys.executable, "scripts/wait_for_db.py"], env=env)
    run([sys.executable, "scripts/enable_postgis.py"], env=env)
    run(
        [sys.executable, "-c", "from database import init_db; init_db()"],
        env=env,
    )
    run([sys.executable, "scripts/bootstrap_data.py"], env=env)
    if os.getenv("RUN_INGEST_LOOP", "").strip().lower() in {"1", "true", "yes", "on"}:
        print("[entrypoint] starting ingest loop in background", flush=True)
        subprocess.Popen(
            [sys.executable, "scripts/ingest_loop.py"],
            env=env,
            start_new_session=True,
        )
    port = os.getenv("PORT", "8000")
    os.execvp(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
            "--workers",
            "1",
        ],
    )


def run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    print(f"[entrypoint] {' '.join(cmd)}", flush=True)
    subprocess.check_call(cmd, env=env)


if __name__ == "__main__":
    main()
