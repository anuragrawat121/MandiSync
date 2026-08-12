"""Seed mandis + official contacts on empty databases (idempotent)."""

from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sqlalchemy import func, select

from database import SessionLocal, init_db
from models import Mandi


def main() -> None:
    init_db()
    with SessionLocal() as db:
        count = db.scalar(select(func.count()).select_from(Mandi)) or 0

    if count == 0:
        print("[bootstrap] No mandis found — running seed.py")
        import seed as seed_module

        seed_module.seed()
    else:
        print(f"[bootstrap] Found {count} mandi(s) — skip seed")

    print("[bootstrap] Loading official APMC contacts…")
    from load_official_contacts import load_official_contacts

    result = load_official_contacts()
    print(
        f"[bootstrap] Official contacts updated={result['updated']} "
        f"missing={result['missing']}"
    )


if __name__ == "__main__":
    main()
