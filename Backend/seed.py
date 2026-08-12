"""
Advanced Indian Agricultural Market Simulator
=============================================
Resets PostGIS tables and seeds 15 pan-India APMC hubs with verified
commission agents plus Onion / Tomato / Potato modal prices engineered
to create realistic inter-state arbitrage corridors.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from geoalchemy2.elements import WKTElement
from sqlalchemy import text

from database import SessionLocal, engine
from models import CropPrice, Mandi


# ---------------------------------------------------------------------------
# Geometry helpers - PostGIS WKT is ALWAYS (longitude, latitude)
# ---------------------------------------------------------------------------

def point_wkt(longitude: float, latitude: float) -> WKTElement:
    """Build SRID 4326 POINT(lon lat). Never invert to lat/lon."""
    return WKTElement(f"POINT({longitude} {latitude})", srid=4326)


def agent(name: str, phone: str, license_id: str) -> dict[str, str]:
    return {"name": name, "phone": phone, "license_id": license_id}


# ---------------------------------------------------------------------------
# 1) Mapped core dataset - 10 states, all listed APMC hub mandis
# ---------------------------------------------------------------------------
# Spec title said "15 hubs"; the coordinate list embeds 18 distinct APMCs.
# We seed every hub provided so no listed market is dropped.

MANDI_HUBS: list[dict[str, Any]] = [
    # Punjab
    {
        "name": "Khanna APMC",
        "state": "Punjab",
        "district": "Ludhiana",
        "longitude": 76.21,
        "latitude": 30.70,
        "verified_agents": [
            agent("Singh Grain Merchants", "+91 98140 11234", "APMC-PB-KHN-2024-11A"),
            agent("Batra Commission Agency", "+91 98761 44550", "APMC-PB-KHN-2024-22C"),
            agent("Grewal Trading House", "+91 99150 77821", "APMC-PB-KHN-2023-09F"),
        ],
    },
    # Haryana
    {
        "name": "Karnal APMC",
        "state": "Haryana",
        "district": "Karnal",
        "longitude": 76.98,
        "latitude": 29.68,
        "verified_agents": [
            agent("Aggarwal Trading Co.", "+91 94140 12345", "APMC-HR-KNL-2024-89B"),
            agent("Malik Sabzi Agency", "+91 98960 33412", "APMC-HR-KNL-2024-14D"),
            agent("Yadav Brothers Mandi", "+91 97290 55108", "APMC-HR-KNL-2023-61E"),
        ],
    },
    {
        "name": "Sirsa APMC",
        "state": "Haryana",
        "district": "Sirsa",
        "longitude": 75.03,
        "latitude": 29.53,
        "verified_agents": [
            agent("Dahiya Commission Works", "+91 94160 88210", "APMC-HR-SRS-2024-33A"),
            agent("Sharma Produce Link", "+91 98120 66745", "APMC-HR-SRS-2024-07C"),
        ],
    },
    # Uttar Pradesh (NCR + Agra belt)
    {
        "name": "Sahibabad APMC",
        "state": "Uttar Pradesh",
        "district": "Ghaziabad",
        "longitude": 77.34,
        "latitude": 28.66,
        "verified_agents": [
            agent("Gupta Fresh Mandi", "+91 98101 55678", "APMC-UP-SHB-2024-44A"),
            agent("Sharma Trading Co.", "+91 98765 43210", "APMC-UP-SHB-2024-12B"),
            agent("Verma Onion Yard", "+91 99990 22134", "APMC-UP-SHB-2023-78K"),
        ],
    },
    {
        "name": "Agra APMC",
        "state": "Uttar Pradesh",
        "district": "Agra",
        "longitude": 78.00,
        "latitude": 27.18,
        "verified_agents": [
            agent("Agarwal Potato Depot", "+91 94122 33456", "APMC-UP-AGR-2024-19A"),
            agent("Singh & Sons Agency", "+91 98370 11988", "APMC-UP-AGR-2024-55C"),
            agent("Rathore Commission", "+91 99270 44801", "APMC-UP-AGR-2023-28D"),
        ],
    },
    # Maharashtra
    {
        "name": "Lasalgaon APMC",
        "state": "Maharashtra",
        "district": "Nashik",
        "longitude": 74.23,
        "latitude": 20.14,
        "verified_agents": [
            agent("Patil Agro Commission", "+91 98220 11453", "APMC-MH-LSG-2024-01A"),
            agent("Shinde Onion Traders", "+91 97564 33821", "APMC-MH-LSG-2024-16B"),
            agent("Kulkarni Market Yard", "+91 90112 77640", "APMC-MH-LSG-2023-42C"),
        ],
    },
    {
        "name": "Vashi APMC",
        "state": "Maharashtra",
        "district": "Thane",
        "longitude": 73.00,
        "latitude": 19.03,
        "verified_agents": [
            agent("Deshmukh Fresh Link", "+91 98201 44890", "APMC-MH-VSH-2024-30A"),
            agent("Joshi Produce Agency", "+91 97695 11207", "APMC-MH-VSH-2024-51B"),
            agent("More Logistics Yard", "+91 90040 66512", "APMC-MH-VSH-2023-08D"),
        ],
    },
    {
        "name": "Pune APMC",
        "state": "Maharashtra",
        "district": "Pune",
        "longitude": 73.85,
        "latitude": 18.52,
        "verified_agents": [
            agent("Jadhav Tomato Works", "+91 98810 22344", "APMC-MH-PUN-2024-21A"),
            agent("Desai Commission House", "+91 99220 77861", "APMC-MH-PUN-2024-37C"),
        ],
    },
    # Madhya Pradesh
    {
        "name": "Indore APMC",
        "state": "Madhya Pradesh",
        "district": "Indore",
        "longitude": 75.85,
        "latitude": 22.71,
        "verified_agents": [
            agent("Chouhan Trading Co.", "+91 98260 33410", "APMC-MP-IND-2024-15A"),
            agent("Shrivastava Mandi Link", "+91 94250 11927", "APMC-MP-IND-2024-62B"),
            agent("Tiwari Agro Agency", "+91 97550 88403", "APMC-MP-IND-2023-44E"),
        ],
    },
    {
        "name": "Mandsaur APMC",
        "state": "Madhya Pradesh",
        "district": "Mandsaur",
        "longitude": 75.07,
        "latitude": 24.03,
        "verified_agents": [
            agent("Rathod Onion Syndicate", "+91 94251 66780", "APMC-MP-MDS-2024-09A"),
            agent("Jain Commission Depot", "+91 98272 44519", "APMC-MP-MDS-2024-27C"),
        ],
    },
    # Rajasthan
    {
        "name": "Jaipur APMC",
        "state": "Rajasthan",
        "district": "Jaipur",
        "longitude": 75.78,
        "latitude": 26.91,
        "verified_agents": [
            agent("Sharma Sabzi Traders", "+91 98290 11256", "APMC-RJ-JPR-2024-18A"),
            agent("Meena Produce Co.", "+91 94140 77890", "APMC-RJ-JPR-2024-53B"),
            agent("Choudhary Market Yard", "+91 99280 33467", "APMC-RJ-JPR-2023-71D"),
        ],
    },
    {
        "name": "Alwar APMC",
        "state": "Rajasthan",
        "district": "Alwar",
        "longitude": 76.61,
        "latitude": 27.56,
        "verified_agents": [
            agent("Yadav Commission Agency", "+91 94140 55612", "APMC-RJ-ALW-2024-25A"),
            agent("Gupta Trading Works", "+91 98292 88901", "APMC-RJ-ALW-2024-40C"),
        ],
    },
    # Gujarat
    {
        "name": "Gondal APMC",
        "state": "Gujarat",
        "district": "Rajkot",
        "longitude": 70.80,
        "latitude": 21.96,
        "verified_agents": [
            agent("Patel Agro Commission", "+91 98250 22311", "APMC-GJ-GND-2024-12A"),
            agent("Shah Produce Link", "+91 98795 66140", "APMC-GJ-GND-2024-36B"),
            agent("Jadeja Market Agency", "+91 99099 44852", "APMC-GJ-GND-2023-58C"),
        ],
    },
    {
        "name": "Surat APMC",
        "state": "Gujarat",
        "district": "Surat",
        "longitude": 72.83,
        "latitude": 21.17,
        "verified_agents": [
            agent("Desai Fresh Traders", "+91 98251 77820", "APMC-GJ-SRT-2024-20A"),
            agent("Mehta Commission Yard", "+91 98791 33458", "APMC-GJ-SRT-2024-47D"),
        ],
    },
    # Karnataka
    {
        "name": "Kolar APMC",
        "state": "Karnataka",
        "district": "Kolar",
        "longitude": 78.13,
        "latitude": 13.13,
        "verified_agents": [
            agent("Reddy Tomato Syndicate", "+91 98450 11267", "APMC-KA-KLR-2024-08A"),
            agent("Shetty Produce Agency", "+91 98860 44591", "APMC-KA-KLR-2024-29B"),
            agent("Rao Market Commission", "+91 99001 77834", "APMC-KA-KLR-2023-63C"),
        ],
    },
    {
        "name": "Bengaluru APMC",
        "state": "Karnataka",
        "district": "Bengaluru Urban",
        "longitude": 77.59,
        "latitude": 12.97,
        "verified_agents": [
            agent("Nair Fresh Logistics", "+91 98440 55678", "APMC-KA-BLR-2024-15A"),
            agent("Iyer Commission House", "+91 98800 22345", "APMC-KA-BLR-2024-41B"),
            agent("Gowda Trading Co.", "+91 99020 88912", "APMC-KA-BLR-2023-77E"),
        ],
    },
    # Andhra Pradesh
    {
        "name": "Guntur APMC",
        "state": "Andhra Pradesh",
        "district": "Guntur",
        "longitude": 80.43,
        "latitude": 16.30,
        "verified_agents": [
            agent("Naidu Produce Traders", "+91 98480 33421", "APMC-AP-GNT-2024-10A"),
            agent("Reddy Commission Works", "+91 98660 77895", "APMC-AP-GNT-2024-34C"),
            agent("Rao & Sons Agency", "+91 97010 11258", "APMC-AP-GNT-2023-52D"),
        ],
    },
    # West Bengal
    {
        "name": "Howrah/Kolkata APMC",
        "state": "West Bengal",
        "district": "Howrah",
        "longitude": 88.33,
        "latitude": 22.58,
        "verified_agents": [
            agent("Banerjee Fresh Agency", "+91 98300 44567", "APMC-WB-HWH-2024-13A"),
            agent("Ghosh Trading Co.", "+91 98310 77890", "APMC-WB-HWH-2024-38B"),
            agent("Mukherjee Mandi Link", "+91 99030 22145", "APMC-WB-HWH-2023-66C"),
        ],
    },
]


# ---------------------------------------------------------------------------
# 2) Advanced crop pricing engine - hardcoded arbitrage corridors
#    Values are modal INR / quintal for today's session.
# ---------------------------------------------------------------------------

# Onion: MH/MP surplus -> NCR / Bengal / Bengaluru deficit
ONION_PRICES: dict[str, int] = {
    "Lasalgaon APMC": 1050,          # capital - extremely low
    "Mandsaur APMC": 1180,           # capital - extremely low
    "Indore APMC": 1450,
    "Pune APMC": 1520,
    "Vashi APMC": 2100,
    "Gondal APMC": 1680,
    "Surat APMC": 1750,
    "Karnal APMC": 1980,
    "Sirsa APMC": 1850,
    "Khanna APMC": 1920,
    "Agra APMC": 2050,
    "Alwar APMC": 2200,
    "Jaipur APMC": 2350,
    "Sahibabad APMC": 2950,          # destination hub - high
    "Bengaluru APMC": 3100,          # destination hub - high
    "Howrah/Kolkata APMC": 2780,     # destination hub - high
    "Kolar APMC": 2400,
    "Guntur APMC": 2550,
}

# Potato: Punjab/UP surplus -> Mumbai / Guntur deficit
POTATO_PRICES: dict[str, int] = {
    "Khanna APMC": 820,              # capital - low
    "Agra APMC": 950,                # capital - low
    "Sirsa APMC": 1100,
    "Karnal APMC": 1180,
    "Sahibabad APMC": 1350,
    "Alwar APMC": 1280,
    "Jaipur APMC": 1420,
    "Indore APMC": 1500,
    "Mandsaur APMC": 1380,
    "Lasalgaon APMC": 1600,
    "Pune APMC": 1750,
    "Gondal APMC": 1680,
    "Surat APMC": 1800,
    "Kolar APMC": 1900,
    "Bengaluru APMC": 2050,
    "Howrah/Kolkata APMC": 1950,
    "Vashi APMC": 2380,              # destination hub - high
    "Guntur APMC": 2450,             # destination hub - high
}

# Tomato: KA/MH surplus -> Jaipur / Delhi deficit
TOMATO_PRICES: dict[str, int] = {
    "Kolar APMC": 1420,              # capital - low
    "Pune APMC": 1550,               # capital - low
    "Bengaluru APMC": 1680,
    "Lasalgaon APMC": 1720,
    "Vashi APMC": 1950,
    "Guntur APMC": 1800,
    "Indore APMC": 1880,
    "Mandsaur APMC": 1750,
    "Gondal APMC": 1900,
    "Surat APMC": 1980,
    "Howrah/Kolkata APMC": 2100,
    "Agra APMC": 2250,
    "Khanna APMC": 2150,
    "Karnal APMC": 2400,
    "Sirsa APMC": 2300,
    "Alwar APMC": 2550,
    "Jaipur APMC": 3200,             # destination hub - high
    "Sahibabad APMC": 3050,          # destination hub - high
}

CROP_VARIETIES: dict[str, str] = {
    "Onion": "Red Nasik",
    "Tomato": "Hybrid",
    "Potato": "Jyoti",
}

PRICE_BOOKS: dict[str, dict[str, int]] = {
    "Onion": ONION_PRICES,
    "Tomato": TOMATO_PRICES,
    "Potato": POTATO_PRICES,
}


# ---------------------------------------------------------------------------
# 3) Database bootstrap
# ---------------------------------------------------------------------------

def ensure_postgis() -> None:
    print("[1/5] Ensuring PostGIS extension is available...")
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    print("      [OK] PostGIS ready")


def ensure_schema() -> None:
    print("[2/5] Ensuring mandis.verified_agents column exists...")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE mandis
                ADD COLUMN IF NOT EXISTS verified_agents JSONB NOT NULL DEFAULT '[]'::jsonb
                """
            )
        )
    print("      [OK] Schema ready")


def reset_tables(db) -> None:
    """Clear crop_prices + mandis in one transaction (CASCADE + identity reset)."""
    print("[3/5] Clearing existing mandis / crop_prices...")
    db.execute(text("TRUNCATE TABLE crop_prices, mandis RESTART IDENTITY CASCADE"))
    db.flush()
    print("      [OK] Tables truncated")


# ---------------------------------------------------------------------------
# 4) Seed orchestration
# ---------------------------------------------------------------------------

def seed() -> None:
    print("=" * 64)
    print(" MandiSync - Advanced Indian Agricultural Market Simulator")
    print("=" * 64)

    ensure_postgis()
    ensure_schema()

    db = SessionLocal()
    today = date.today()
    now = datetime.now(timezone.utc)

    try:
        reset_tables(db)

        print(f"[4/5] Inserting {len(MANDI_HUBS)} APMC hub mandis with verified agents...")
        mandi_by_name: dict[str, Mandi] = {}

        for hub in MANDI_HUBS:
            lon = float(hub["longitude"])
            lat = float(hub["latitude"])
            # Strict PostGIS order: POINT(longitude latitude)
            mandi = Mandi(
                name=hub["name"],
                state=hub["state"],
                district=hub["district"],
                coordinates=point_wkt(longitude=lon, latitude=lat),
                verified_agents=hub["verified_agents"],
            )
            db.add(mandi)
            mandi_by_name[hub["name"]] = mandi
            print(
                f"      + {hub['name']:24} | {hub['state']:16} | "
                f"POINT({lon:.2f} {lat:.2f}) | agents={len(hub['verified_agents'])}"
            )

        db.flush()
        print(f"      [OK] {len(mandi_by_name)} mandis staged")

        print("[5/5] Seeding Onion / Tomato / Potato modal prices...")
        price_count = 0

        for crop_name, price_map in PRICE_BOOKS.items():
            variety = CROP_VARIETIES[crop_name]
            for mandi_name, modal_price in price_map.items():
                mandi = mandi_by_name.get(mandi_name)
                if mandi is None:
                    raise KeyError(
                        f"Price book references unknown mandi '{mandi_name}' "
                        f"for crop '{crop_name}'."
                    )
                db.add(
                    CropPrice(
                        mandi_id=mandi.id,
                        crop_name=crop_name,
                        variety=variety,
                        modal_price_per_quintal=modal_price,
                        price_date=today,
                        updated_at=now,
                    )
                )
                price_count += 1
            print(f"      [OK] {crop_name}: {len(price_map)} mandi quotes loaded")

        db.commit()

        states = sorted({hub["state"] for hub in MANDI_HUBS})
        print("-" * 64)
        print(" SEED COMPLETE")
        print(f"  Mandis loaded : {len(mandi_by_name)}")
        print(f"  States covered: {len(states)} -> {', '.join(states)}")
        print(f"  Price rows    : {price_count}")
        print("  Corridors     : Onion MH/MP->NCR/WB/KA | Potato PB/UP->MH/AP | Tomato KA/MH->RJ/NCR")
        print("-" * 64)

    except Exception as exc:
        db.rollback()
        print("!" * 64)
        print(f" SEED FAILED - transaction rolled back: {exc}")
        print("!" * 64)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
