"""
seed_scan_targets.py — Seed the 15 Tier 1 city pairs the scanner monitors.

These are high-value routes where high-YQ carriers (LH, BA, QR, etc.) operate
and meaningful fuel dump savings are achievable. The scanner will iterate over
these targets × dump_candidates to discover price deltas.

Usage:
    cd backend
    python scripts/seed_scan_targets.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://theoh@localhost:5432/fare_engine"
)

SCAN_TARGETS = [
    # YVR routes — Tier 1 (Vancouver: high-YQ carriers dominant on these routes)
    ("YVR", "LHR", None, 1),
    ("YVR", "CDG", None, 1),
    ("YVR", "FRA", None, 1),
    ("YVR", "BKK", None, 1),
    ("YVR", "ICN", None, 1),
    ("YVR", "NRT", None, 1),
    # SEA routes — Tier 1 (Seattle: similar profile to YVR)
    ("SEA", "LHR", None, 1),
    ("SEA", "CDG", None, 1),
    ("SEA", "FRA", None, 1),
    ("SEA", "BKK", None, 1),
    ("SEA", "ICN", None, 1),
    ("SEA", "NRT", None, 1),
    # Europe → BKK — Tier 1 (LH/BA/QR all charge heavy YQ on these)
    ("LHR", "BKK", None, 1),
    ("FRA", "BKK", None, 1),
    ("CDG", "BKK", None, 1),
]


async def seed() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)

    insert_sql = sa.text("""
        INSERT INTO scan_targets (origin_iata, destination_iata, carrier_iata, tier, enabled)
        VALUES (:origin, :dest, :carrier, :tier, true)
        ON CONFLICT (origin_iata, destination_iata, carrier_iata)
        DO UPDATE SET
            tier = EXCLUDED.tier,
            updated_at = NOW()
    """)

    async with engine.begin() as conn:
        count = 0
        for origin, dest, carrier, tier in SCAN_TARGETS:
            await conn.execute(insert_sql, {
                "origin": origin,
                "dest": dest,
                "carrier": carrier,
                "tier": tier,
            })
            count += 1
            print(f"  ✓ {origin} → {dest} (carrier={carrier or 'any'}, tier={tier})")

    await engine.dispose()
    print(f"\nSeeded {count} scan targets.")


if __name__ == "__main__":
    asyncio.run(seed())
