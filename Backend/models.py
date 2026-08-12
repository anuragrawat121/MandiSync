from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship
from geoalchemy2 import Geometry

Base = declarative_base()


class Mandi(Base):
    __tablename__ = "mandis"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    state = Column(String, nullable=False)
    district = Column(String, nullable=False)
    # PostGIS POINT is always (longitude, latitude) for SRID 4326 — never lat/lon.
    coordinates = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)
    # Array of {name, phone, license_id} commission-agent contact cards.
    verified_agents = Column(JSON, nullable=False, default=list)
    # Government-published APMC office contacts — see data/official_mandi_contacts.json.
    official_contacts = Column(JSON, nullable=False, default=dict)

    crop_prices = relationship("CropPrice", back_populates="mandi")


class CropPrice(Base):
    __tablename__ = "crop_prices"

    id = Column(Integer, primary_key=True)
    mandi_id = Column(Integer, ForeignKey("mandis.id"), nullable=False)
    crop_name = Column(String, nullable=False)
    variety = Column(String)
    modal_price_per_quintal = Column(Numeric, nullable=False)
    price_date = Column(Date, nullable=False)
    updated_at = Column(DateTime)
    # "agmarknet" for live ingest; "seed" (or NULL on older rows) for demo data.
    data_source = Column(String)
    # UTC timestamp of the ingest pull — not the market's arrival_date.
    ingested_at = Column(DateTime)
    # True when modal was >3x or <1/3 of same-run (crop, state) median.
    is_price_outlier = Column(Boolean, default=False)

    mandi = relationship("Mandi", back_populates="crop_prices")

    __table_args__ = (
        UniqueConstraint(
            "mandi_id",
            "crop_name",
            "variety",
            "price_date",
            name="uq_crop_prices_mandi_crop_variety_date",
        ),
    )
