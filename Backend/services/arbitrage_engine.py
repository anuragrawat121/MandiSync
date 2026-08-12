"""
Crop arbitrage optimization engine.

Identifies profitable buy-low / sell-high routes across Indian mandis by
combining modal price spreads with PostGIS-derived road-distance transit costs.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from geoalchemy2.functions import ST_DistanceSphere, ST_X, ST_Y
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from models import CropPrice, Mandi


def _allow_seed_fallback() -> bool:
    """
    Product default is live-only: never show synthetic seed corridors as if
    they were market reality. Set ALLOW_SEED_FALLBACK=true for offline demos.
    """
    return os.getenv("ALLOW_SEED_FALLBACK", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

# Drop a mandi from pairing if its newest quote is older than this.
DEFAULT_MAX_STALENESS_DAYS = 3

# Realistic all-India commercial truck hire estimate (INR per km).
TRUCK_RATE_PER_KM_INR = Decimal("25")

# Standard ~10 MT FTL payload expressed in quintals (1 tonne = 10 quintals).
# Modal prices are INR/quintal, so haul cost is amortized per quintal.
TRUCK_CAPACITY_QUINTALS = Decimal("100")

# Typical APMC market fee + commission-agent cut on the sell side (~6–10%).
# Applied to destination modal price so net_profit is not a raw spread fantasy.
MANDI_FEE_RATE = Decimal("0.07")

# Expected value lost to spoilage / quality dock per 1000 km of haul.
# Tomato is highly perishable; onion/potato degrade far more slowly.
PERISHABILITY_LOSS_PER_1000_KM: dict[str, Decimal] = {
    "Tomato": Decimal("0.12"),
    "Onion": Decimal("0.03"),
    "Potato": Decimal("0.02"),
}


@dataclass(frozen=True)
class ArbitrageOpportunity:
    """A single profitable source -> destination crop route."""

    crop_name: str
    source_mandi: str
    destination_mandi: str
    source_state: str
    destination_state: str
    source_price_per_quintal: float
    destination_price_per_quintal: float
    gross_spread: float
    distance_km: float
    transit_cost: float
    mandi_fee_per_quintal: float
    perishability_cost_per_quintal: float
    net_profit: float
    # Leaflet expects [latitude, longitude].
    source_coordinates: list[float]
    destination_coordinates: list[float]
    # Commission agents waiting at the destination market (who to call on arrival).
    destination_verified_agents: list[dict[str, Any]]
    # Arrival dates may differ across yards; never mix quotes from other days
    # for the *same* mandi, but source vs dest can legitimately be different days.
    source_price_date: str
    destination_price_date: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _leaflet_latlng(db_session: Session, mandi: Mandi) -> list[float]:
    """Extract [lat, lng] from a PostGIS POINT stored as (longitude, latitude)."""
    longitude = db_session.scalar(select(ST_X(mandi.coordinates)))
    latitude = db_session.scalar(select(ST_Y(mandi.coordinates)))
    if longitude is None or latitude is None:
        raise ValueError(f"Missing coordinates for mandi '{mandi.name}'.")
    return [float(latitude), float(longitude)]


def _kilometers_between(db_session: Session, source: Mandi, destination: Mandi) -> float:
    """
    Compute great-circle distance between two mandis in kilometers.

    PostGIS steps:
      1. Both mandi rows store WGS84 points (SRID 4326) in `coordinates`.
      2. ST_DistanceSphere(geom_a, geom_b) returns the spherical surface
         distance in *meters* (avoids degree-based ST_Distance on lon/lat).
      3. Divide meters by 1000 to express the haul length in kilometers.
    """
    distance_meters = db_session.scalar(
        select(ST_DistanceSphere(source.coordinates, destination.coordinates))
    )
    if distance_meters is None:
        raise ValueError(
            f"Unable to compute distance between '{source.name}' and '{destination.name}'."
        )
    return float(distance_meters) / 1000.0


def _evaluate_pair(
    db_session: Session,
    crop_name: str,
    source: CropPrice,
    destination: CropPrice,
) -> ArbitrageOpportunity | None:
    """
    Evaluate one source/destination price pair.

    Gross spread       = destination modal - source modal (INR / quintal)
    Transit / quintal  = distance_km * Rs.25 / km / 100 quintals
    Mandi fee          = ~7% of destination modal (APMC + commission haircut)
    Perishability      = crop-specific loss rate × (km / 1000) × destination modal
    Net profit         = spread - transit - mandi fee - perishability
    """
    source_price = Decimal(str(source.modal_price_per_quintal))
    destination_price = Decimal(str(destination.modal_price_per_quintal))
    gross_spread = destination_price - source_price

    # Only consider buy-low / sell-high pairs.
    if gross_spread <= 0:
        return None

    distance_km = _kilometers_between(db_session, source.mandi, destination.mandi)

    total_transit_cost = Decimal(str(distance_km)) * TRUCK_RATE_PER_KM_INR
    transit_cost_per_quintal = total_transit_cost / TRUCK_CAPACITY_QUINTALS

    mandi_fee_per_quintal = destination_price * MANDI_FEE_RATE
    loss_rate_per_1000 = PERISHABILITY_LOSS_PER_1000_KM.get(
        crop_name,
        Decimal("0.04"),
    )
    perishability_cost = (
        destination_price * loss_rate_per_1000 * (Decimal(str(distance_km)) / Decimal("1000"))
    )

    net_profit = (
        gross_spread
        - transit_cost_per_quintal
        - mandi_fee_per_quintal
        - perishability_cost
    )

    if net_profit <= 0:
        return None

    return ArbitrageOpportunity(
        crop_name=crop_name,
        source_mandi=source.mandi.name,
        destination_mandi=destination.mandi.name,
        source_state=source.mandi.state,
        destination_state=destination.mandi.state,
        source_price_per_quintal=float(source_price),
        destination_price_per_quintal=float(destination_price),
        gross_spread=float(gross_spread),
        distance_km=round(distance_km, 2),
        transit_cost=round(float(transit_cost_per_quintal), 2),
        mandi_fee_per_quintal=round(float(mandi_fee_per_quintal), 2),
        perishability_cost_per_quintal=round(float(perishability_cost), 2),
        net_profit=round(float(net_profit), 2),
        source_coordinates=_leaflet_latlng(db_session, source.mandi),
        destination_coordinates=_leaflet_latlng(db_session, destination.mandi),
        destination_verified_agents=list(destination.mandi.verified_agents or []),
        source_price_date=source.price_date.isoformat(),
        destination_price_date=destination.price_date.isoformat(),
    )


def _is_live_source(row: CropPrice) -> bool:
    return (row.data_source or "").strip().lower() == "agmarknet"


def _newest_date_in_window(
    group: list[CropPrice],
    *,
    cutoff: date,
) -> date | None:
    newest_date = max(item.price_date for item in group)
    if newest_date < cutoff:
        return None
    return newest_date


def _pick_median_variety(on_date: list[CropPrice]) -> CropPrice:
    ordered = sorted(
        on_date,
        key=lambda item: Decimal(str(item.modal_price_per_quintal)),
    )
    return ordered[len(ordered) // 2]


def _select_one_per_mandi(
    rows: list[CropPrice],
    *,
    max_staleness_days: int,
    as_of: date,
) -> list[CropPrice]:
    """Newest price_date per mandi within the staleness window; median variety."""
    by_mandi: dict[int, list[CropPrice]] = {}
    for row in rows:
        by_mandi.setdefault(row.mandi_id, []).append(row)

    cutoff = as_of - timedelta(days=max_staleness_days)
    selected: list[CropPrice] = []
    for group in by_mandi.values():
        newest_date = _newest_date_in_window(group, cutoff=cutoff)
        if newest_date is None:
            continue
        on_date = [item for item in group if item.price_date == newest_date]
        selected.append(_pick_median_variety(on_date))
    return selected


def _has_fresh_agmarknet(
    rows: list[CropPrice],
    *,
    max_staleness_days: int,
    as_of: date,
) -> bool:
    """True iff at least one agmarknet row survives the staleness window for this crop."""
    live = [row for row in rows if _is_live_source(row)]
    if not live:
        return False
    return bool(
        _select_one_per_mandi(
            live,
            max_staleness_days=max_staleness_days,
            as_of=as_of,
        )
    )


def _select_current_prices(
    rows: list[CropPrice],
    *,
    max_staleness_days: int,
    as_of: date,
) -> tuple[list[CropPrice], str, str]:
    """
    One quote per mandi: newest price_date within the staleness window.

    Live-first (default):
      - Fresh agmarknet → use only those rows (data_source_used=agmarknet).
      - No fresh agmarknet → empty set (data_source_used=none, status=no_fresh_prices).
        Seed is NOT used unless ALLOW_SEED_FALLBACK=true (offline demos only).
    """
    if _has_fresh_agmarknet(
        rows,
        max_staleness_days=max_staleness_days,
        as_of=as_of,
    ):
        pool = [row for row in rows if _is_live_source(row)]
        selected = _select_one_per_mandi(
            pool,
            max_staleness_days=max_staleness_days,
            as_of=as_of,
        )
        return selected, "agmarknet", "ok"

    if _allow_seed_fallback():
        pool = [row for row in rows if not _is_live_source(row)]
        selected = _select_one_per_mandi(
            pool,
            max_staleness_days=max_staleness_days,
            as_of=as_of,
        )
        return selected, "seed", "ok"

    return [], "none", "no_fresh_prices"


def _attach_agents(
    opportunity: ArbitrageOpportunity,
    *,
    agents_status: str,
) -> dict[str, Any]:
    payload = opportunity.to_dict()
    if agents_status == "unavailable":
        # Live markets: never surface seeded fiction as callable contacts.
        payload["destination_verified_agents"] = []
    payload["agents_status"] = agents_status
    return payload


def calculate_crop_arbitrage(
    db_session: Session,
    crop_name: str,
    max_staleness_days: int = DEFAULT_MAX_STALENESS_DAYS,
) -> dict[str, Any]:
    """
    Find all profitable arbitrage routes for ``crop_name``.

    Returns:
      {
        "routes": [...],
        "data_source_used": "agmarknet" | "seed" | "none",
        "status": "ok" | "no_fresh_prices",
        "message": str,
        "agents_status": "unavailable" | "demo",
        "max_staleness_days": int,
      }
    """
    prices: list[CropPrice] = (
        db_session.execute(
            select(CropPrice)
            .options(joinedload(CropPrice.mandi))
            .where(CropPrice.crop_name == crop_name)
        )
        .scalars()
        .unique()
        .all()
    )

    prices, data_source_used, status = _select_current_prices(
        prices,
        max_staleness_days=max_staleness_days,
        as_of=date.today(),
    )

    if status == "no_fresh_prices":
        return {
            "routes": [],
            "data_source_used": "none",
            "status": "no_fresh_prices",
            "message": (
                f"No fresh Agmarknet prices for {crop_name} within the last "
                f"{max_staleness_days} days. Run daily ingest or try again later. "
                "Seed demo prices are not shown in live mode."
            ),
            "agents_status": "unavailable",
            "max_staleness_days": max_staleness_days,
        }

    agents_status = "unavailable" if data_source_used == "agmarknet" else "demo"

    opportunities: list[ArbitrageOpportunity] = []

    for source in prices:
        for destination in prices:
            if source.mandi_id == destination.mandi_id:
                continue

            opportunity = _evaluate_pair(db_session, crop_name, source, destination)
            if opportunity is not None:
                opportunities.append(opportunity)

    opportunities.sort(key=lambda item: item.net_profit, reverse=True)
    return {
        "routes": [
            _attach_agents(item, agents_status=agents_status)
            for item in opportunities
        ],
        "data_source_used": data_source_used,
        "status": "ok",
        "message": (
            "Live Agmarknet prices."
            if data_source_used == "agmarknet"
            else "Demo seed prices (ALLOW_SEED_FALLBACK=true)."
        ),
        "agents_status": agents_status,
        "max_staleness_days": max_staleness_days,
    }
