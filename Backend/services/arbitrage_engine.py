"""
Crop arbitrage optimization engine.

Identifies profitable buy-low / sell-high routes across Indian mandis by
combining modal price spreads with PostGIS-derived road-distance transit costs.
"""

from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from geoalchemy2.functions import ST_X, ST_Y
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


def _max_staleness_days(explicit: int | None = None) -> int:
    if explicit is not None:
        return explicit
    raw = os.getenv("MAX_STALENESS_DAYS", "").strip()
    if raw.isdigit():
        return max(1, int(raw))
    return DEFAULT_MAX_STALENESS_DAYS

# Government e-NAM mandi directory (no per-mandi deep link — user picks state/APMC).
ENAM_MANDI_PORTAL_URL = "https://enam.gov.in/web/apmc-contact-details"
ENAM_HELPLINE = "18002700224"

# Agmarknet market name hint for the e-NAM mandi picker (matches ingest map keys).
ENAM_APMC_SEARCH: dict[str, str] = {
    "Khanna": "Khanna APMC",
    "Sirsa": "Sirsa APMC",
    "Agra": "Agra APMC",
    "Lasalgaon": "Lasalgaon",
    "Vashi": "Mumbai-Onion & Potato Market",
    "Pune": "Pune",
    "Indore": "Indore",
    "Mandsaur": "Mandsaur",
    "Jaipur": "Jaipur (F&V)",
    "Gondal": "Gondal(Veg.market Gondal) APMC",
    "Surat": "Surat APMC",
    "Bengaluru": "Bengaluru",
    "Howrah": "Ramkrishanpur(Howrah) APMC",
}

# Drop a mandi from pairing if its newest quote is older than this.
# Agmarknet's public feed is a *current-day* snapshot; many APMCs do not
# report every calendar day, so 3 days is too tight for weekends/holidays.
DEFAULT_MAX_STALENESS_DAYS = 7

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
    # Government-published APMC office contacts for the destination yard.
    destination_contacts: list[dict[str, Any]]
    destination_profile_url: str | None
    destination_maps_url: str | None
    destination_contact_source: str | None
    destination_enam_url: str | None
    destination_enam_apmc_search: str | None
    # Arrival dates may differ across yards; never mix quotes from other days
    # for the *same* mandi, but source vs dest can legitimately be different days.
    source_price_date: str
    destination_price_date: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _contact_bundle(mandi: Mandi) -> dict[str, Any]:
    """Extract official APMC contacts stored on the mandi row."""
    raw = mandi.official_contacts or {}
    if isinstance(raw, list):
        return {
            "contacts": raw,
            "profile_url": None,
            "maps_url": None,
            "source": None,
        }
    return {
        "contacts": list(raw.get("contacts") or []),
        "profile_url": raw.get("profile_url"),
        "maps_url": raw.get("maps_url"),
        "source": raw.get("source"),
        "enam_url": raw.get("enam_url") or ENAM_MANDI_PORTAL_URL,
        "enam_apmc_search": raw.get("enam_apmc_search"),
    }


def _mandi_short_key(mandi: Mandi) -> str | None:
    """Match ingest short names used in ENAM_APMC_SEARCH."""
    name_norm = mandi.name.lower()
    for key in ENAM_APMC_SEARCH:
        if key.lower() in name_norm:
            return key
    return None


def _enam_search_label(mandi: Mandi, bundle: dict[str, Any]) -> str:
    if bundle.get("enam_apmc_search"):
        return str(bundle["enam_apmc_search"])
    short = _mandi_short_key(mandi)
    if short:
        return ENAM_APMC_SEARCH[short]
    return mandi.name.replace(" APMC", "").strip()


def _load_mandi_latlng(
    db_session: Session,
    mandis: list[Mandi],
) -> dict[int, list[float]]:
    """One round-trip: mandi_id -> [lat, lng] for Leaflet and haversine."""
    ids = [mandi.id for mandi in mandis if mandi is not None]
    if not ids:
        return {}
    rows = db_session.execute(
        select(Mandi.id, ST_Y(Mandi.coordinates), ST_X(Mandi.coordinates)).where(
            Mandi.id.in_(ids)
        )
    ).all()
    coords: dict[int, list[float]] = {}
    for mandi_id, latitude, longitude in rows:
        if latitude is None or longitude is None:
            continue
        coords[int(mandi_id)] = [float(latitude), float(longitude)]
    return coords


def _haversine_km(source: list[float], destination: list[float]) -> float:
    """Great-circle km (WGS84 mean radius), matching ST_DistanceSphere closely."""
    lat1, lon1 = source
    lat2, lon2 = destination
    radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    chord = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(min(1.0, math.sqrt(chord)))


def _evaluate_pair(
    crop_name: str,
    source: CropPrice,
    destination: CropPrice,
    coords: dict[int, list[float]],
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

    source_xy = coords.get(source.mandi_id)
    dest_xy = coords.get(destination.mandi_id)
    if not source_xy or not dest_xy:
        return None

    distance_km = _haversine_km(source_xy, dest_xy)

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

    dest_bundle = _contact_bundle(destination.mandi)
    profile_url = dest_bundle.get("profile_url")
    maps_url = dest_bundle.get("maps_url")
    if not maps_url:
        lat, lng = dest_xy
        label = destination.mandi.name.replace(" ", "+")
        maps_url = f"https://maps.google.com/?q={lat},{lng}({label})"

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
        source_coordinates=source_xy,
        destination_coordinates=dest_xy,
        destination_verified_agents=list(destination.mandi.verified_agents or []),
        destination_contacts=list(dest_bundle.get("contacts") or []),
        destination_profile_url=profile_url,
        destination_maps_url=maps_url,
        destination_contact_source=dest_bundle.get("source"),
        destination_enam_url=dest_bundle.get("enam_url"),
        destination_enam_apmc_search=_enam_search_label(destination.mandi, dest_bundle),
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


def _curated_agents(raw: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """
    Only agents stamped with verified_at (admin-curated) are callable in live mode.
    Seed demo cards lack that field and must never surface as real contacts.
    """
    curated: list[dict[str, Any]] = []
    for agent in raw or []:
        if not isinstance(agent, dict):
            continue
        if not str(agent.get("verified_at") or "").strip():
            continue
        if not str(agent.get("phone") or "").strip():
            continue
        curated.append(
            {
                "name": str(agent.get("name") or "").strip(),
                "phone": str(agent.get("phone") or "").strip(),
                "license_id": str(agent.get("license_id") or "").strip(),
            }
        )
    return curated


def _attach_agents(
    opportunity: ArbitrageOpportunity,
    *,
    agents_status: str,
    data_source: str,
) -> dict[str, Any]:
    payload = opportunity.to_dict()
    official = payload.get("destination_contacts") or []
    curated = _curated_agents(payload.get("destination_verified_agents"))

    if data_source == "agmarknet":
        if curated:
            # Prefer real commission agents when an admin has curated them.
            payload["agents_status"] = "verified"
            payload["destination_verified_agents"] = curated
        elif official:
            payload["agents_status"] = "official"
            payload["destination_verified_agents"] = []
        else:
            payload["agents_status"] = "unavailable"
            payload["destination_verified_agents"] = []
    elif agents_status == "demo":
        payload["agents_status"] = "demo"
        payload["destination_contacts"] = []
    else:
        payload["agents_status"] = agents_status
        payload["destination_verified_agents"] = []
        payload["destination_contacts"] = []

    return payload


def calculate_crop_arbitrage(
    db_session: Session,
    crop_name: str,
    max_staleness_days: int | None = None,
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
    max_staleness_days = _max_staleness_days(max_staleness_days)
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

    coords = _load_mandi_latlng(
        db_session,
        [row.mandi for row in prices if row.mandi is not None],
    )

    opportunities: list[ArbitrageOpportunity] = []

    for source in prices:
        for destination in prices:
            if source.mandi_id == destination.mandi_id:
                continue

            opportunity = _evaluate_pair(
                crop_name, source, destination, coords
            )
            if opportunity is not None:
                opportunities.append(opportunity)

    opportunities.sort(key=lambda item: item.net_profit, reverse=True)
    routes = [
        _attach_agents(
            item,
            agents_status=agents_status,
            data_source=data_source_used,
        )
        for item in opportunities
    ]
    if data_source_used == "agmarknet":
        statuses = {route.get("agents_status") for route in routes}
        if "verified" in statuses:
            agents_status = "verified"
        elif "official" in statuses:
            agents_status = "official"

    return {
        "routes": routes,
        "data_source_used": data_source_used,
        "status": "ok",
        "message": (
            "Live Agmarknet prices."
            if data_source_used == "agmarknet"
            else "Demo seed prices (ALLOW_SEED_FALLBACK=true)."
        ),
        "agents_status": agents_status,
        "max_staleness_days": max_staleness_days,
        "enam_helpline": ENAM_HELPLINE,
    }
