"""
seed_dump_candidates.py — Seed the 10 real short-haul dump candidate segments.

These are real routes used as injected segments in multi-city itineraries.
Each one disrupts YQ calculation by introducing a different fare pricing zone,
incompatible interline rule, or carrier mismatch on a cheap, loose leg.

Key properties of a good dump candidate:
  - Short-haul (< 2h flight)
  - Different fare pricing region than the main route
  - Left loose (no carrier forced) where possible — more likely to apply
  - Cheap standalone ticket (doesn't inflate the injected itinerary cost)

Usage:
    cd backend
    python scripts/seed_dump_candidates.py
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

# (from_iata, to_iata, carrier_iata, notes)
DUMP_CANDIDATES = [
    # Central Asia — Uzbekistan Airways (HY) is a separate pricing zone entirely.
    # TAS↔SKD is a real domestic Uzbekistan route, very short, rarely over-constrained.
    ("TAS", "SKD", "HY", "Uzbekistan domestic — separate IATA pricing zone, disrupts YQ chain on Central Asia routings"),
    ("SKD", "TAS", "HY", "Reverse TAS↔SKD — same zone disruption, useful for return leg injection"),

    # Northern Europe — cheap, short, loose
    ("LHR", "OSL", None, "London–Oslo: intra-Europe, separate from Atlantic fare zone, loose carrier"),
    ("OSL", "LHR", None, "Oslo–London reverse: same logic, useful for outbound injection"),

    # Benelux
    ("CDG", "BRU", None, "Paris–Brussels: ultra-short intra-Europe, often treated as domestic-class fare zone"),

    # Frankfurt–Amsterdam: Star Alliance zone boundary, frequently misaligned with LH long-haul fares
    ("FRA", "AMS", None, "Frankfurt–Amsterdam: LH Star Alliance boundary, known YQ disruption on LH metal"),

    # Southeast Asia — BKK↔SIN crosses IATA Southeast Asia zone boundary
    ("BKK", "SIN", None, "Bangkok–Singapore: Southeast Asia zone 3 boundary, useful after BKK arrival"),
    ("SIN", "BKK", None, "Singapore–Bangkok reverse: zone 3 boundary, use as return dump leg"),

    # Korea — ICN↔PUS is a real domestic Korean route, separate zone
    ("ICN", "PUS", None, "Seoul–Busan: Korean domestic zone, breaks Northeast Asia YQ continuity"),

    # Japan — NRT↔HND is technically two separate airports serving Tokyo, sometimes different tariff treatment
    ("NRT", "HND", None, "Narita–Haneda: Tokyo intra-city, different tariff node, disrupts Northeast Asia YQ"),
]


async def seed() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)

    insert_sql = sa.text("""
        INSERT INTO dump_candidates (from_iata, to_iata, carrier_iata, notes, enabled)
        VALUES (:from_iata, :to_iata, :carrier, :notes, true)
        ON CONFLICT (from_iata, to_iata, carrier_iata)
        DO UPDATE SET
            notes = EXCLUDED.notes,
            updated_at = NOW()
    """)

    async with engine.begin() as conn:
        count = 0
        for from_iata, to_iata, carrier, notes in DUMP_CANDIDATES:
            await conn.execute(insert_sql, {
                "from_iata": from_iata,
                "to_iata": to_iata,
                "carrier": carrier,
                "notes": notes,
            })
            count += 1
            print(f"  ✓ {from_iata} → {to_iata} (carrier={carrier or 'loose'})")

    await engine.dispose()
    print(f"\nSeeded {count} dump candidates.")


if __name__ == "__main__":
    asyncio.run(seed())
