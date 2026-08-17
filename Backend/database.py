from __future__ import annotations

import os
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from models import Base

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:mandisync_password@localhost:5432/mandisync_db",
)

# Railway/Render sometimes provide postgres:// — SQLAlchemy wants postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://") :]

# Supabase requires TLS. Direct URIs often omit sslmode.
if "supabase.co" in DATABASE_URL and "sslmode=" not in DATABASE_URL:
    DATABASE_URL += ("&" if "?" in DATABASE_URL else "?") + "sslmode=require"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_crop_price_schema() -> None:
    """Additive ALTER for existing DBs (no migration tool). Safe to re-run."""
    with engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE crop_prices ADD COLUMN IF NOT EXISTS data_source VARCHAR")
        )
        conn.execute(
            text("ALTER TABLE crop_prices ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMP")
        )
        conn.execute(
            text(
                "ALTER TABLE crop_prices ADD COLUMN IF NOT EXISTS is_price_outlier BOOLEAN DEFAULT FALSE"
            )
        )
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uq_crop_prices_mandi_crop_variety_date'
                  ) AND NOT EXISTS (
                    SELECT 1 FROM pg_class
                    WHERE relname = 'ux_crop_prices_mandi_crop_variety_date'
                  ) THEN
                    CREATE UNIQUE INDEX ux_crop_prices_mandi_crop_variety_date
                    ON crop_prices (mandi_id, crop_name, variety, price_date);
                  END IF;
                END $$;
                """
            )
        )
        conn.execute(
            text(
                "ALTER TABLE mandis ADD COLUMN IF NOT EXISTS official_contacts JSONB DEFAULT '{}'::jsonb"
            )
        )


def init_db() -> None:
    """Create tables + apply additive schema. Call after Postgres is reachable."""
    Base.metadata.create_all(bind=engine)
    ensure_crop_price_schema()


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Local/dev import path: connect immediately. Docker entrypoint calls init_db()
# after wait-for-db so cold starts do not crash the container.
if os.getenv("SKIP_DB_INIT_ON_IMPORT", "").strip().lower() not in {
    "1",
    "true",
    "yes",
    "on",
}:
    init_db()
