"""Enable PostGIS on Railway/managed Postgres before seed."""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text

url = os.getenv("DATABASE_URL", "")
if url.startswith("postgres://"):
    url = "postgresql://" + url[len("postgres://") :]
if "supabase.co" in url and "sslmode=" not in url:
    url += ("&" if "?" in url else "?") + "sslmode=require"

if not url:
    print("[enable_postgis] DATABASE_URL missing", file=sys.stderr)
    sys.exit(1)

engine = create_engine(url, pool_pre_ping=True)
with engine.begin() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
print("[enable_postgis] postgis extension ready")
