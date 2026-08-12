from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from models import Base

DATABASE_URL = "postgresql://postgres:mandisync_password@localhost:5432/mandisync_db"

engine = create_engine(DATABASE_URL)
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


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


Base.metadata.create_all(bind=engine)
ensure_crop_price_schema()
