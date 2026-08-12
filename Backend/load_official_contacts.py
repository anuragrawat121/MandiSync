"""
Load government-published APMC office contacts into mandis.official_contacts.

Run from Backend/:
    python load_official_contacts.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from sqlalchemy import select

from database import SessionLocal, ensure_crop_price_schema
from models import Mandi

DATA_PATH = Path(__file__).resolve().parent / "data" / "official_mandi_contacts.json"

# ingest short name -> possible DB mandi.name substrings (seed uses longer names).
MANDI_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "Khanna": ("Khanna",),
    "Sirsa": ("Sirsa",),
    "Agra": ("Agra",),
    "Lasalgaon": ("Lasalgaon",),
    "Vashi": ("Vashi",),
    "Pune": ("Pune",),
    "Indore": ("Indore",),
    "Mandsaur": ("Mandsaur",),
    "Jaipur": ("Jaipur",),
    "Gondal": ("Gondal",),
    "Surat": ("Surat",),
    "Bengaluru": ("Bengaluru", "Bangalore"),
    "Howrah": ("Howrah", "Kolkata"),
}


def _normalize(name: str) -> str:
    text = str(name or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*apmc\s*$", "", text).strip()
    return text


def _match_mandi(mandis: list[Mandi], key: str) -> Mandi | None:
    aliases = MANDI_KEY_ALIASES.get(key, (key,))
    alias_norm = {_normalize(alias) for alias in aliases}
    for mandi in mandis:
        name_norm = _normalize(mandi.name)
        if any(alias in name_norm or name_norm.startswith(alias) for alias in alias_norm):
            return mandi
    return None


def load_official_contacts() -> dict[str, int]:
    ensure_crop_price_schema()
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    mandi_entries: dict[str, dict] = payload.get("mandis") or {}

    with SessionLocal() as db:
        mandis = list(db.scalars(select(Mandi)).all())
        updated = 0
        missing: list[str] = []

        for key, entry in mandi_entries.items():
            mandi = _match_mandi(mandis, key)
            if mandi is None:
                missing.append(key)
                continue
            mandi.official_contacts = {
                "contacts": entry.get("contacts") or [],
                "profile_url": entry.get("profile_url"),
                "maps_url": entry.get("maps_url"),
                "source": entry.get("source"),
                "source_url": entry.get("source_url"),
                "enam_url": entry.get("enam_url"),
                "enam_apmc_search": entry.get("enam_apmc_search"),
                "updated_at": payload.get("updated_at"),
            }
            updated += 1

        db.commit()

    return {"updated": updated, "missing": len(missing), "missing_keys": missing}


if __name__ == "__main__":
    result = load_official_contacts()
    print(
        f"Updated {result['updated']} mandi(s) with official APMC contacts. "
        f"Missing: {result['missing']} {result.get('missing_keys') or ''}"
    )
