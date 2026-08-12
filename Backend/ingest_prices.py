"""
Agmarknet price ingest for MandiSync.

  --discover  read-only listing of live market names (no DB writes)
  --ingest    upsert mapped yards into crop_prices (additive; never truncate)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

AGMARKNET_RESOURCE_URL = (
    "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
)
DISCOVER_CROPS = ("Onion", "Tomato", "Potato")
DISCOVER_LIMIT = 100
INGEST_LIMIT = 100
LOOKBACK_DAYS = 3
REQUEST_PAUSE_SECONDS = 0.35
FETCH_TIMEOUT_SECONDS = 90
FETCH_RETRIES = 5
NEAR_MISS_EDIT_DISTANCE = 3

# Unique Mandi.state values from seed.MANDI_HUBS (the 18 seeded APMCs).
SEEDED_STATES = (
    "Andhra Pradesh",
    "Gujarat",
    "Haryana",
    "Karnataka",
    "Madhya Pradesh",
    "Maharashtra",
    "Punjab",
    "Rajasthan",
    "Uttar Pradesh",
    "West Bengal",
)

# (crop_name, real_agmarknet_market_name): our_mandi_name
# Strings are verbatim from a live discovery run — do not "fix" spacing.
MANDI_NAME_MAP = {
    ("Onion", "Khanna APMC"): "Khanna",
    ("Tomato", "Khanna APMC"): "Khanna",
    ("Potato", "Khanna APMC"): "Khanna",

    ("Onion", "Sirsa APMC"): "Sirsa",
    ("Tomato", "Sirsa APMC"): "Sirsa",
    ("Potato", "Sirsa APMC"): "Sirsa",

    ("Onion", "Agra APMC"): "Agra",
    ("Tomato", "Agra APMC"): "Agra",
    ("Potato", "Agra APMC"): "Agra",

    ("Onion", "Lasalgaon"): "Lasalgaon",
    # Lasalgaon: no real Tomato/Potato data at this yard — intentional,
    # not a bug. This is Asia's largest onion market; it doesn't meaningfully
    # trade the other two crops.

    ("Onion", "Mumbai-Onion & Potato Market"): "Vashi",
    ("Potato", "Mumbai-Onion & Potato Market"): "Vashi",
    # Vashi: no Tomato data at this yard — intentional omission

    ("Onion", "Pune"): "Pune",
    ("Tomato", "Pune"): "Pune",
    ("Potato", "Pune"): "Pune",

    ("Onion", "Indore"): "Indore",
    ("Tomato", "Indore(F&V)"): "Indore",
    # Indore: no Potato — Madhya Pradesh reports zero potato prices
    # statewide through this API, not just for Indore

    ("Onion", "Mandsaur"): "Mandsaur",
    ("Tomato", "Mandsaur(F&V)"): "Mandsaur",
    # Mandsaur: same statewide MP potato gap

    ("Onion", "Jaipur (F&V)"): "Jaipur",
    ("Tomato", "Jaipur (F&V)"): "Jaipur",
    ("Potato", "Jaipur (F&V)"): "Jaipur",

    ("Tomato", "Gondal(Veg.market Gondal) APMC"): "Gondal",
    ("Potato", "Gondal(Veg.market Gondal) APMC"): "Gondal",
    # Gondal: no Onion data at this yard — intentional omission

    ("Onion", "Surat APMC"): "Surat",
    ("Tomato", "Surat APMC"): "Surat",
    ("Potato", "Surat APMC"): "Surat",

    ("Onion", "Bengaluru"): "Bengaluru",
    ("Tomato", "Binny Mill (FF&V) Bengaluru"): "Bengaluru",
    ("Potato", "Bengaluru"): "Bengaluru",

    ("Onion", "Ramkrishanpur(Howrah) APMC"): "Howrah",
    ("Tomato", "Ramkrishanpur(Howrah) APMC"): "Howrah",
    ("Potato", "Ramkrishanpur(Howrah) APMC"): "Howrah",
}

MAPPED_MANDI_SHORT_NAMES = frozenset(MANDI_NAME_MAP.values())

logger = logging.getLogger("ingest_prices")


def normalize_market_name(name: str) -> str:
    """
    Bidirectional market-name normalizer for Agmarknet <-> MandiSync matching.

    - case-insensitive
    - collapse internal whitespace
    - strip a trailing APMC token (with or without a preceding space)
    """
    text = str(name or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*apmc\s*$", "", text).strip()
    return text


# Built once from the verbatim map keys — map strings themselves are never edited.
_NORMALIZED_CROP_MARKET_MAP: dict[tuple[str, str], str] = {
    (crop.strip().lower(), normalize_market_name(market)): short_name
    for (crop, market), short_name in MANDI_NAME_MAP.items()
}

_NORMALIZED_MAP_MARKETS_BY_CROP: dict[str, set[str]] = defaultdict(set)
for (crop, market), _short in MANDI_NAME_MAP.items():
    _NORMALIZED_MAP_MARKETS_BY_CROP[crop.strip().lower()].add(
        normalize_market_name(market)
    )


def _api_key() -> str:
    key = (os.getenv("AGMARKNET_API_KEY") or "").strip()
    if not key:
        raise SystemExit(
            "AGMARKNET_API_KEY is missing. Add it to Backend/.env and retry."
        )
    return key


def fetch_agmarknet(
    *,
    state: str,
    commodity: str,
    limit: int = DISCOVER_LIMIT,
    offset: int = 0,
) -> dict:
    """
    GET one page from the confirmed data.gov.in Agmarknet resource.
    state uses filters[state.keyword]; commodity uses filters[commodity].
    """
    query = urllib.parse.urlencode(
        {
            "api-key": _api_key(),
            "format": "json",
            "limit": str(limit),
            "offset": str(offset),
            "filters[state.keyword]": state,
            "filters[commodity]": commodity,
        }
    )
    url = f"{AGMARKNET_RESOURCE_URL}?{query}"
    last_error: dict | None = None
    for attempt in range(1, FETCH_RETRIES + 1):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "MandiSync-ingest/1.0"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
                body = response.read().decode("utf-8")
                status = response.status
            break
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:400]
            if exc.code in {429, 500, 502, 503, 504} and attempt < FETCH_RETRIES:
                last_error = {
                    "ok": False,
                    "http_status": exc.code,
                    "error": f"HTTP {exc.code} {exc.reason}: {detail}",
                    "records": [],
                    "total": None,
                }
                time.sleep(2 * attempt)
                continue
            return {
                "ok": False,
                "http_status": exc.code,
                "error": f"HTTP {exc.code} {exc.reason}: {detail}",
                "records": [],
                "total": None,
            }
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            last_error = {
                "ok": False,
                "http_status": None,
                "error": f"Network error (attempt {attempt}/{FETCH_RETRIES}): {reason}",
                "records": [],
                "total": None,
            }
            time.sleep(2 * attempt)
    else:
        return last_error or {
            "ok": False,
            "http_status": None,
            "error": "Network error: unknown",
            "records": [],
            "total": None,
        }

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "http_status": status,
            "error": "Response was not valid JSON.",
            "records": [],
            "total": None,
        }

    records = payload.get("records")
    if records is None:
        records = []
    if not isinstance(records, list):
        return {
            "ok": False,
            "http_status": status,
            "error": f"'records' was {type(records).__name__}, expected list.",
            "records": [],
            "total": payload.get("total"),
        }

    return {
        "ok": True,
        "http_status": status,
        "error": None,
        "records": records,
        "total": payload.get("total"),
        "count": payload.get("count"),
    }


def fetch_agmarknet_all_pages(*, state: str, commodity: str, limit: int = INGEST_LIMIT) -> dict:
    """Paginate until offset covers API `total`. Fail the whole pull on any bad page."""
    first = fetch_agmarknet(state=state, commodity=commodity, limit=limit, offset=0)
    if not first["ok"]:
        return first

    records = list(first["records"])
    try:
        total = int(first["total"]) if first["total"] is not None else len(records)
    except (TypeError, ValueError):
        total = len(records)

    offset = limit
    while offset < total:
        time.sleep(REQUEST_PAUSE_SECONDS)
        page = fetch_agmarknet(
            state=state, commodity=commodity, limit=limit, offset=offset
        )
        if not page["ok"]:
            return page
        if not page["records"]:
            break
        records.extend(page["records"])
        offset += limit

    return {
        "ok": True,
        "http_status": first["http_status"],
        "error": None,
        "records": records,
        "total": first["total"],
        "count": len(records),
    }


def lookup_mapped_mandi(commodity: str, market: str) -> str | None:
    """Match (commodity, market) after normalizing BOTH sides via normalize_market_name."""
    commodity_key = str(commodity or "").strip().lower()
    market_key = normalize_market_name(market)
    if not commodity_key or not market_key:
        return None
    return _NORMALIZED_CROP_MARKET_MAP.get((commodity_key, market_key))


def _edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            insert_cost = curr[j - 1] + 1
            delete_cost = prev[j] + 1
            replace_cost = prev[j - 1] + (0 if ca == cb else 1)
            curr.append(min(insert_cost, delete_cost, replace_cost))
        prev = curr
    return prev[-1]


def find_near_misses(commodity: str, market: str) -> list[tuple[str, int]]:
    """Normalized edit-distance near-misses against MANDI_NAME_MAP keys for this crop."""
    commodity_key = str(commodity or "").strip().lower()
    market_key = normalize_market_name(market)
    if not commodity_key or not market_key:
        return []
    if (commodity_key, market_key) in _NORMALIZED_CROP_MARKET_MAP:
        return []
    hits: list[tuple[str, int]] = []
    for mapped in _NORMALIZED_MAP_MARKETS_BY_CROP.get(commodity_key, ()):
        dist = _edit_distance(market_key, mapped)
        if 0 < dist < NEAR_MISS_EDIT_DISTANCE:
            hits.append((mapped, dist))
    hits.sort(key=lambda item: (item[1], item[0]))
    return hits


def verify_mapping_normalization() -> None:
    """Self-check: every verbatim map key still resolves to its short name."""
    failures: list[str] = []
    for (crop, market), short_name in MANDI_NAME_MAP.items():
        got = lookup_mapped_mandi(crop, market)
        if got != short_name:
            failures.append(f"{crop!r}/{market!r} -> {got!r} (expected {short_name!r})")
        # Also confirm the common live-API form with an extra trailing APMC still hits.
        with_apmc = market if market.upper().endswith("APMC") else f"{market} APMC"
        got_apmc = lookup_mapped_mandi(crop, with_apmc)
        if got_apmc != short_name:
            failures.append(
                f"{crop!r}/{with_apmc!r} -> {got_apmc!r} (expected {short_name!r})"
            )
    if failures:
        raise SystemExit(
            "normalize_market_name broke existing mappings:\n  " + "\n  ".join(failures)
        )


def _print(*args, **kwargs) -> None:
    print(*args, **kwargs, flush=True)


def discover() -> None:
    _api_key()
    states = list(SEEDED_STATES)
    _print("=" * 72)
    _print(" MandiSync Agmarknet DISCOVER (read-only, no DB writes)")
    _print(f" Seeded states ({len(states)}): {', '.join(states)}")
    _print(f" Crops: {', '.join(DISCOVER_CROPS)}")
    _print(f" Page size: limit={DISCOVER_LIMIT}, offset=0")
    _print("=" * 72)

    for state in states:
        _print(f"\n### STATE: {state}")
        for crop in DISCOVER_CROPS:
            _print(f"  [{crop}] fetching...", end="\r")
            result = fetch_agmarknet(state=state, commodity=crop)
            time.sleep(REQUEST_PAUSE_SECONDS)

            if not result["ok"]:
                _print(f"  [{crop}] ERROR — {result['error']}")
                continue

            records = result["records"]
            if not records:
                _print(
                    f"  [{crop}] EMPTY — 0 records on this page "
                    f"(API total={result['total']!r})"
                )
                continue

            markets = sorted(
                {
                    str(row.get("market") or "").strip()
                    for row in records
                    if str(row.get("market") or "").strip()
                }
            )
            _print(
                f"  [{crop}] API total={result['total']!r}  "
                f"page_records={len(records)}  "
                f"distinct_markets={len(markets)}"
            )
            if result["total"] is not None:
                try:
                    total_n = int(result["total"])
                    if total_n > DISCOVER_LIMIT:
                        _print(
                            f"           NOTE: total ({total_n}) > limit "
                            f"({DISCOVER_LIMIT}) — pagination via offset needed later."
                        )
                except (TypeError, ValueError):
                    pass
            for market in markets:
                _print(f"           - {market}")

    _print("\n" + "=" * 72)
    _print(" Discover complete. No matching and no DB writes were performed.")
    _print("=" * 72)


def parse_arrival_date(raw: object) -> date | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        return None


def parse_modal_price(raw: object) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    if value <= 0:
        return None
    return value


def parse_optional_price(raw: object) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def _median(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


@dataclass(frozen=True)
class ParsedQuote:
    our_mandi: str
    crop_name: str
    state: str
    variety: str
    price_date: date
    modal_price: Decimal
    market: str
    is_price_outlier: bool


def resolve_mandi_row(db, short_name: str):
    """Resolve map short name to a mandis row using bidirectional normalization."""
    from sqlalchemy import select

    from models import Mandi

    target = normalize_market_name(short_name)
    rows = db.execute(select(Mandi)).scalars().all()
    matches: list = []
    for row in rows:
        normalized = normalize_market_name(row.name)
        if (
            normalized == target
            or normalized.startswith(f"{target}/")
            or normalized.startswith(f"{target} ")
        ):
            matches.append(row)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = ", ".join(repr(m.name) for m in matches)
        raise SystemExit(
            f"Ambiguous mandi resolve for {short_name!r} (normalized={target!r}): {names}"
        )
    return None


def ingest() -> None:
    _api_key()
    verify_mapping_normalization()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(message)s",
    )

    from sqlalchemy.dialects.postgresql import insert

    from database import SessionLocal, ensure_crop_price_schema
    from models import CropPrice, Mandi

    db = SessionLocal()
    try:
        mandi_by_short: dict[str, Mandi] = {}
        for short_name in sorted(MAPPED_MANDI_SHORT_NAMES):
            row = resolve_mandi_row(db, short_name)
            if row is None:
                raise SystemExit(
                    f"Cannot resolve mapped name {short_name!r} to a mandis row. "
                    "No crop_prices were written."
                )
            mandi_by_short[short_name] = row
            _print(
                f"  map {short_name!r} -> {row.name} "
                f"(norm={normalize_market_name(row.name)!r}, id={row.id}, {row.state})"
            )

        needed_queries: set[tuple[str, str]] = set()
        for (crop, _market), short_name in MANDI_NAME_MAP.items():
            needed_queries.add((crop, mandi_by_short[short_name].state))
    finally:
        db.close()

    _print("=" * 72)
    _print(" MandiSync Agmarknet INGEST (additive upsert, no truncate)")
    _print(f" Queries: {len(needed_queries)} state×crop pages")
    _print("=" * 72)

    pulled: list[tuple[str, str, list[dict]]] = []
    for crop, state in sorted(needed_queries, key=lambda item: (item[1], item[0])):
        _print(f"  fetching {state} / {crop} ...")
        result = fetch_agmarknet_all_pages(state=state, commodity=crop)
        time.sleep(REQUEST_PAUSE_SECONDS)
        if not result["ok"]:
            _print(f"FAILED: {state} / {crop} — {result['error']}")
            _print("Aborting. Existing crop_prices rows were not modified.")
            raise SystemExit(1)
        _print(
            f"    ok  total={result['total']!r}  pulled={len(result['records'])}"
        )
        pulled.append((crop, state, result["records"]))

    # Statewide median modal per (crop, state) across this run's raw pull.
    statewide_modals: dict[tuple[str, str], list[Decimal]] = defaultdict(list)
    for crop, state, records in pulled:
        for row in records:
            modal = parse_modal_price(row.get("modal_price"))
            if modal is not None:
                statewide_modals[(crop, state)].append(modal)
    statewide_median: dict[tuple[str, str], Decimal] = {
        key: med for key, values in statewide_modals.items() if (med := _median(values))
    }

    today = date.today()
    earliest = today - timedelta(days=LOOKBACK_DAYS)
    unmatched = 0
    skipped_bad = 0
    rejected_inconsistent = 0
    near_miss_events: list[tuple[str, str, str, str, int]] = []
    parsed: list[ParsedQuote] = []

    for crop, state, records in pulled:
        for row in records:
            commodity = str(row.get("commodity") or "").strip() or crop
            market = str(row.get("market") or "").strip()
            our_name = lookup_mapped_mandi(commodity, market)
            if our_name is None:
                unmatched += 1
                logger.debug("unmatched %s / %s / %s", state, commodity, market)
                for mapped_norm, dist in find_near_misses(commodity, market):
                    near_miss_events.append(
                        (state, commodity, market, mapped_norm, dist)
                    )
                # Only flag a real matcher bug for crops we actually ingest.
                if commodity in DISCOVER_CROPS and normalize_market_name(market) in {
                    normalize_market_name(s) for s in MAPPED_MANDI_SHORT_NAMES
                }:
                    logger.warning(
                        "Matching bug: API market %r normalizes to a mapped short "
                        "name but (commodity=%r, market=%r) was not caught.",
                        market,
                        commodity,
                        market,
                    )
                continue

            price_date = parse_arrival_date(row.get("arrival_date"))
            if price_date is None:
                skipped_bad += 1
                logger.warning(
                    "Bad arrival_date %r for %s / %s — row skipped",
                    row.get("arrival_date"),
                    our_name,
                    commodity,
                )
                continue

            modal = parse_modal_price(row.get("modal_price"))
            if modal is None:
                skipped_bad += 1
                logger.warning(
                    "Bad modal_price %r for %s / %s on %s — row skipped",
                    row.get("modal_price"),
                    our_name,
                    commodity,
                    price_date,
                )
                continue

            min_price = parse_optional_price(row.get("min_price"))
            max_price = parse_optional_price(row.get("max_price"))
            if min_price is not None and max_price is not None:
                if not (min_price <= modal <= max_price):
                    rejected_inconsistent += 1
                    logger.warning(
                        "REJECT inconsistent %s / %s / %s on %s: "
                        "modal=%s not in [min=%s, max=%s]",
                        our_name,
                        commodity,
                        market,
                        price_date,
                        modal,
                        min_price,
                        max_price,
                    )
                    continue

            median = statewide_median.get((crop, state))
            is_outlier = False
            if median is not None and median > 0:
                if modal > median * 3 or modal < median / 3:
                    is_outlier = True
                    logger.warning(
                        "OUTLIER %s / %s / %s on %s: modal=%s vs %s median=%s "
                        "(still storing)",
                        our_name,
                        commodity,
                        market,
                        price_date,
                        modal,
                        state,
                        median,
                    )

            variety = str(row.get("variety") or "").strip()
            parsed.append(
                ParsedQuote(
                    our_mandi=our_name,
                    crop_name=commodity,
                    state=state,
                    variety=variety,
                    price_date=price_date,
                    modal_price=modal,
                    market=market,
                    is_price_outlier=is_outlier,
                )
            )

    # Keep today if present for a mandi+crop; else most recent date in the 3-day window.
    by_mandi_crop: dict[tuple[str, str], list[ParsedQuote]] = defaultdict(list)
    for quote in parsed:
        by_mandi_crop[(quote.our_mandi, quote.crop_name)].append(quote)

    to_upsert: list[ParsedQuote] = []
    for (short_name, crop), quotes in sorted(by_mandi_crop.items()):
        in_window = [q for q in quotes if earliest <= q.price_date <= today]
        if not in_window:
            newest = max(q.price_date for q in quotes)
            _print(
                f"  skip {short_name} / {crop}: newest arrival {newest.isoformat()} "
                f"is outside {LOOKBACK_DAYS}-day lookback (kept real dates, not relabeled)"
            )
            continue
        today_quotes = [q for q in in_window if q.price_date == today]
        chosen_date = today if today_quotes else max(q.price_date for q in in_window)
        chosen = [q for q in in_window if q.price_date == chosen_date]
        if chosen_date != today:
            _print(
                f"  lookback {short_name} / {crop}: no today row, "
                f"using {chosen_date.isoformat()} (real price_date kept)"
            )
        to_upsert.extend(chosen)

    mapped_pairs = {(short, crop) for (crop, _m), short in MANDI_NAME_MAP.items()}
    seen_pairs = {(q.our_mandi, q.crop_name) for q in to_upsert}
    for short_name, crop in sorted(mapped_pairs - seen_pairs):
        _print(f"  no usable rows for {short_name} / {crop} in lookback window")

    # Deduplicate near-miss warnings (same API market can appear many times).
    unique_near_misses = sorted(
        {
            (state, commodity, market, mapped_norm, dist)
            for state, commodity, market, mapped_norm, dist in near_miss_events
        }
    )
    if unique_near_misses:
        _print("\n  NEAR-MISS WARNINGS (edit distance < 3, not an exact map hit):")
        for state, commodity, market, mapped_norm, dist in unique_near_misses:
            _print(
                f"  possible near-miss: {state} / {commodity} / API={market!r} "
                f"~ map_key_norm={mapped_norm!r} (edit_distance={dist})"
            )
    else:
        _print("  near-miss warnings: none")

    rows_flagged_outliers = sum(1 for q in to_upsert if q.is_price_outlier)
    _print(
        f"  unmatched_out_of_scope={unmatched}  "
        f"skipped_bad_fields={skipped_bad}  "
        f"rejected_inconsistent={rejected_inconsistent}  "
        f"upsert_candidates={len(to_upsert)}  "
        f"flagged_outliers={rows_flagged_outliers}"
    )

    # Surface Agra Onion vs UP median for the verification report.
    up_onion_median = statewide_median.get(("Onion", "Uttar Pradesh"))
    if up_onion_median is not None:
        _print(
            f"  UP Onion statewide median (this run) = {up_onion_median}"
        )
    for quote in to_upsert:
        if quote.our_mandi == "Agra" and quote.crop_name == "Onion":
            _print(
                f"  Agra Onion candidate: variety={quote.variety!r} "
                f"modal={quote.modal_price} outlier={quote.is_price_outlier} "
                f"vs UP median={up_onion_median}"
            )

    if not to_upsert:
        _print("Nothing to write. Existing crop_prices rows were not modified.")
        _print(
            f" SUMMARY: accepted=0  rejected_inconsistent={rejected_inconsistent}  "
            f"flagged_outliers=0"
        )
        return

    ingested_at = datetime.now(timezone.utc).replace(tzinfo=None)
    now = ingested_at

    ensure_crop_price_schema()
    db = SessionLocal()
    written = 0
    written_outliers = 0
    try:
        for quote in to_upsert:
            mandi = mandi_by_short[quote.our_mandi]
            stmt = insert(CropPrice).values(
                mandi_id=mandi.id,
                crop_name=quote.crop_name,
                variety=quote.variety,
                modal_price_per_quintal=quote.modal_price,
                price_date=quote.price_date,
                updated_at=now,
                data_source="agmarknet",
                ingested_at=ingested_at,
                is_price_outlier=quote.is_price_outlier,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["mandi_id", "crop_name", "variety", "price_date"],
                set_={
                    "modal_price_per_quintal": stmt.excluded.modal_price_per_quintal,
                    "updated_at": stmt.excluded.updated_at,
                    "data_source": stmt.excluded.data_source,
                    "ingested_at": stmt.excluded.ingested_at,
                    "is_price_outlier": stmt.excluded.is_price_outlier,
                },
            )
            db.execute(stmt)
            written += 1
            if quote.is_price_outlier:
                written_outliers += 1
        db.commit()
    except Exception as exc:
        db.rollback()
        _print(f"FAILED during upsert: {exc}")
        _print("Transaction rolled back. Existing crop_prices rows were not modified.")
        raise SystemExit(1) from exc
    finally:
        db.close()

    _print("=" * 72)
    _print(f" Ingest complete. Upserted {written} agmarknet row(s).")
    _print(
        f" SUMMARY: accepted={written}  "
        f"rejected_inconsistent={rejected_inconsistent}  "
        f"flagged_outliers={written_outliers}"
    )
    _print(" seed.py was not touched. Demo seed rows remain as offline fallback.")
    _print("=" * 72)


def main() -> None:
    parser = argparse.ArgumentParser(description="Agmarknet ingest for MandiSync")
    parser.add_argument(
        "--discover",
        action="store_true",
        help="List live Agmarknet market names for seeded states (read-only).",
    )
    parser.add_argument(
        "--ingest",
        action="store_true",
        help="Upsert mapped Agmarknet prices into crop_prices (no truncate).",
    )
    args = parser.parse_args()

    if args.discover and args.ingest:
        raise SystemExit("Use either --discover or --ingest, not both.")
    if args.discover:
        discover()
        return
    if args.ingest:
        ingest()
        return

    parser.print_help()
    raise SystemExit("\nRun `python ingest_prices.py --discover` or `--ingest`.")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
