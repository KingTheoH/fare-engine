#!/usr/bin/env python3
"""
seed_patterns.py — Populate the dump_patterns table with initial patterns.

Includes:
- 10 patterns from test fixtures (JFK-centric routes)
- 8 additional patterns relevant to user's airport watchlist (YVR, SEA, ICN, NRT, TPE, etc.)

Idempotent: uses upsert on ita_routing_code (unique constraint).

Usage:
    cd backend && python scripts/seed_patterns.py

Requires:
    - PostgreSQL running and accessible via DATABASE_URL
    - Alembic migrations applied (alembic upgrade head)
"""

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings


# Patterns from test fixtures + new patterns for user airports
PATTERNS = [
    # --- From test fixtures (JFK-centric) ---
    {
        "dump_type": "TP_DUMP",
        "lifecycle_state": "active",
        "origin_iata": "JFK",
        "destination_iata": "BKK",
        "ticketing_carrier_iata": "LH",
        "operating_carriers": ["LH", "LH", "AA"],
        "routing_points": ["FRA"],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE LH:JFK-FRA / FORCE LH:FRA-BKK / FORCE AA:BKK-JFK",
        "expected_yq_savings_usd": 580.0,
        "confidence_score": 0.85,
        "freshness_tier": 1,
        "source": "FLYERTALK",
        "source_url": "https://www.flyertalk.com/forum/mileage-run-deals/fuel-dump-jfk-bkk-lh",
        "source_post_weight": 0.8,
    },
    {
        "dump_type": "TP_DUMP",
        "lifecycle_state": "active",
        "origin_iata": "LAX",
        "destination_iata": "SIN",
        "ticketing_carrier_iata": "BA",
        "operating_carriers": ["BA", "BA", "AA"],
        "routing_points": ["LHR"],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE BA:LAX-LHR / FORCE BA:LHR-SIN / FORCE AA:SIN-LAX",
        "expected_yq_savings_usd": 550.0,
        "confidence_score": 0.82,
        "freshness_tier": 1,
        "source": "FLYERTALK",
        "source_url": "https://www.flyertalk.com/forum/mileage-run-deals/fuel-dump-lax-sin-ba",
        "source_post_weight": 0.75,
    },
    {
        "dump_type": "TP_DUMP",
        "lifecycle_state": "active",
        "origin_iata": "ORD",
        "destination_iata": "BKK",
        "ticketing_carrier_iata": "LX",
        "operating_carriers": ["LX", "LX", "UA"],
        "routing_points": ["ZRH"],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE LX:ORD-ZRH / FORCE LX:ZRH-BKK / FORCE UA:BKK-ORD",
        "expected_yq_savings_usd": 520.0,
        "confidence_score": 0.78,
        "freshness_tier": 1,
        "source": "FLYERTALK",
        "source_url": None,
        "source_post_weight": 0.6,
    },
    {
        "dump_type": "CARRIER_SWITCH",
        "lifecycle_state": "active",
        "origin_iata": "JFK",
        "destination_iata": "BKK",
        "ticketing_carrier_iata": "QR",
        "operating_carriers": ["QR", "AA"],
        "routing_points": ["DOH"],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE QR:JFK-DOH-BKK / FORCE AA:BKK-JFK",
        "expected_yq_savings_usd": 580.0,
        "confidence_score": 0.88,
        "freshness_tier": 1,
        "source": "FLYERTALK",
        "source_url": "https://www.flyertalk.com/forum/mileage-run-deals/qr-carrier-switch-jfk-bkk",
        "source_post_weight": 0.85,
    },
    {
        "dump_type": "CARRIER_SWITCH",
        "lifecycle_state": "active",
        "origin_iata": "LAX",
        "destination_iata": "SIN",
        "ticketing_carrier_iata": "EK",
        "operating_carriers": ["EK", "AA"],
        "routing_points": ["DXB"],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE EK:LAX-DXB-SIN / FORCE AA:SIN-LAX",
        "expected_yq_savings_usd": 450.0,
        "confidence_score": 0.80,
        "freshness_tier": 1,
        "source": "FLYERTALK",
        "source_url": None,
        "source_post_weight": 0.7,
    },
    {
        "dump_type": "CARRIER_SWITCH",
        "lifecycle_state": "active",
        "origin_iata": "JFK",
        "destination_iata": "BKK",
        "ticketing_carrier_iata": "EY",
        "operating_carriers": ["EY"],
        "routing_points": ["AUH"],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE EY:JFK-AUH-BKK",
        "expected_yq_savings_usd": 400.0,
        "confidence_score": 0.75,
        "freshness_tier": 1,
        "source": "FLYERTALK",
        "source_url": None,
        "source_post_weight": 0.65,
    },
    {
        "dump_type": "FARE_BASIS",
        "lifecycle_state": "active",
        "origin_iata": "JFK",
        "destination_iata": "BKK",
        "ticketing_carrier_iata": "LH",
        "operating_carriers": ["LH", "AA"],
        "routing_points": ["FRA"],
        "fare_basis_hint": "YLOWUS",
        "ita_routing_code": "FORCE LH:JFK-FRA-BKK BC=YLOWUS / FORCE AA:BKK-JFK",
        "expected_yq_savings_usd": 580.0,
        "confidence_score": 0.72,
        "freshness_tier": 1,
        "source": "FLYERTALK",
        "source_url": None,
        "source_post_weight": 0.6,
    },
    {
        "dump_type": "ALLIANCE_RULE",
        "lifecycle_state": "active",
        "origin_iata": "JFK",
        "destination_iata": "NRT",
        "ticketing_carrier_iata": "LH",
        "operating_carriers": ["LH", "NH"],
        "routing_points": ["FRA"],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE LH/NH:JFK-FRA-NRT / FORCE LH/NH:NRT-FRA-JFK",
        "expected_yq_savings_usd": 480.0,
        "confidence_score": 0.77,
        "freshness_tier": 1,
        "source": "FLYERTALK",
        "source_url": None,
        "source_post_weight": 0.7,
    },
    {
        "dump_type": "TP_DUMP",
        "lifecycle_state": "active",
        "origin_iata": "JFK",
        "destination_iata": "BKK",
        "ticketing_carrier_iata": "OS",
        "operating_carriers": ["OS", "OS", "UA"],
        "routing_points": ["VIE"],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE OS:JFK-VIE / FORCE OS:VIE-BKK / FORCE UA:BKK-JFK",
        "expected_yq_savings_usd": 480.0,
        "confidence_score": 0.73,
        "freshness_tier": 1,
        "source": "FLYERTALK",
        "source_url": None,
        "source_post_weight": 0.55,
    },
    # --- User airport patterns (YVR, SEA, ICN, NRT, TPE, MNL, BKK, LHR, MAD, BCN) ---
    {
        "dump_type": "CARRIER_SWITCH",
        "lifecycle_state": "active",
        "origin_iata": "SEA",
        "destination_iata": "ICN",
        "ticketing_carrier_iata": "KE",
        "operating_carriers": ["KE", "AA"],
        "routing_points": [],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE KE:SEA-ICN / FORCE AA:ICN-SEA",
        "expected_yq_savings_usd": 420.0,
        "confidence_score": 0.83,
        "freshness_tier": 1,
        "source": "FLYERTALK",
        "source_url": "https://www.flyertalk.com/forum/mileage-run-deals/ke-sea-icn-carrier-switch",
        "source_post_weight": 0.8,
    },
    {
        "dump_type": "CARRIER_SWITCH",
        "lifecycle_state": "active",
        "origin_iata": "SEA",
        "destination_iata": "TPE",
        "ticketing_carrier_iata": "BR",
        "operating_carriers": ["BR", "UA"],
        "routing_points": [],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE BR:SEA-TPE / FORCE UA:TPE-SEA",
        "expected_yq_savings_usd": 380.0,
        "confidence_score": 0.81,
        "freshness_tier": 1,
        "source": "FLYERTALK",
        "source_url": "https://www.flyertalk.com/forum/mileage-run-deals/br-sea-tpe-dump",
        "source_post_weight": 0.75,
    },
    {
        "dump_type": "CARRIER_SWITCH",
        "lifecycle_state": "active",
        "origin_iata": "YVR",
        "destination_iata": "MNL",
        "ticketing_carrier_iata": "PR",
        "operating_carriers": ["PR", "AC"],
        "routing_points": [],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE PR:YVR-MNL / FORCE AC:MNL-YVR",
        "expected_yq_savings_usd": 350.0,
        "confidence_score": 0.76,
        "freshness_tier": 2,
        "source": "FLYERTALK",
        "source_url": None,
        "source_post_weight": 0.65,
    },
    {
        "dump_type": "TP_DUMP",
        "lifecycle_state": "active",
        "origin_iata": "YVR",
        "destination_iata": "BKK",
        "ticketing_carrier_iata": "QR",
        "operating_carriers": ["QR", "AC"],
        "routing_points": ["DOH"],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE QR:YVR-DOH-BKK / FORCE AC:BKK-YVR",
        "expected_yq_savings_usd": 520.0,
        "confidence_score": 0.84,
        "freshness_tier": 1,
        "source": "FLYERTALK",
        "source_url": "https://www.flyertalk.com/forum/mileage-run-deals/qr-yvr-bkk-via-doh",
        "source_post_weight": 0.8,
    },
    {
        "dump_type": "CARRIER_SWITCH",
        "lifecycle_state": "active",
        "origin_iata": "SEA",
        "destination_iata": "NRT",
        "ticketing_carrier_iata": "NH",
        "operating_carriers": ["NH", "UA"],
        "routing_points": [],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE NH:SEA-NRT / FORCE UA:NRT-SEA",
        "expected_yq_savings_usd": 440.0,
        "confidence_score": 0.79,
        "freshness_tier": 1,
        "source": "FLYERTALK",
        "source_url": None,
        "source_post_weight": 0.7,
    },
    {
        "dump_type": "TP_DUMP",
        "lifecycle_state": "active",
        "origin_iata": "YVR",
        "destination_iata": "LHR",
        "ticketing_carrier_iata": "LX",
        "operating_carriers": ["LX", "LX", "AC"],
        "routing_points": ["ZRH"],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE LX:YVR-ZRH / FORCE LX:ZRH-LHR / FORCE AC:LHR-YVR",
        "expected_yq_savings_usd": 490.0,
        "confidence_score": 0.80,
        "freshness_tier": 1,
        "source": "FLYERTALK",
        "source_url": None,
        "source_post_weight": 0.7,
    },
    {
        "dump_type": "CARRIER_SWITCH",
        "lifecycle_state": "active",
        "origin_iata": "YVR",
        "destination_iata": "MAD",
        "ticketing_carrier_iata": "EY",
        "operating_carriers": ["EY", "AC"],
        "routing_points": ["AUH"],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE EY:YVR-AUH-MAD / FORCE AC:MAD-YVR",
        "expected_yq_savings_usd": 410.0,
        "confidence_score": 0.74,
        "freshness_tier": 1,
        "source": "FLYERTALK",
        "source_url": None,
        "source_post_weight": 0.6,
    },
    {
        "dump_type": "TP_DUMP",
        "lifecycle_state": "degrading",
        "origin_iata": "SEA",
        "destination_iata": "BCN",
        "ticketing_carrier_iata": "TK",
        "operating_carriers": ["TK", "TK", "AA"],
        "routing_points": ["IST"],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE TK:SEA-IST / FORCE TK:IST-BCN / FORCE AA:BCN-SEA",
        "expected_yq_savings_usd": 370.0,
        "confidence_score": 0.52,
        "freshness_tier": 2,
        "source": "FLYERTALK",
        "source_url": None,
        "source_post_weight": 0.5,
    },
    {
        "dump_type": "CARRIER_SWITCH",
        "lifecycle_state": "discovered",
        "origin_iata": "YVR",
        "destination_iata": "NRT",
        "ticketing_carrier_iata": "JL",
        "operating_carriers": ["JL", "AC"],
        "routing_points": [],
        "fare_basis_hint": None,
        "ita_routing_code": "FORCE JL:YVR-NRT / FORCE AC:NRT-YVR",
        "expected_yq_savings_usd": 460.0,
        "confidence_score": 0.45,
        "freshness_tier": 2,
        "source": "FLYERTALK",
        "source_url": "https://www.flyertalk.com/forum/mileage-run-deals/jl-yvr-nrt-new",
        "source_post_weight": 0.55,
    },
]


async def seed_patterns() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print(f"Loading {len(PATTERNS)} dump patterns...")

    inserted = 0
    updated = 0
    errors = 0

    async with async_session() as session:
        for p in PATTERNS:
            try:
                pattern_id = str(uuid.uuid4())
                result = await session.execute(
                    text("""
                        INSERT INTO dump_patterns (
                            id, dump_type, lifecycle_state,
                            origin_iata, destination_iata,
                            ticketing_carrier_iata, operating_carriers, routing_points,
                            fare_basis_hint, ita_routing_code,
                            expected_yq_savings_usd, confidence_score, freshness_tier,
                            source, source_url, source_post_weight,
                            created_at, updated_at
                        ) VALUES (
                            :id, :dump_type, :lifecycle_state,
                            :origin_iata, :destination_iata,
                            :ticketing_carrier_iata, :operating_carriers, :routing_points,
                            :fare_basis_hint, :ita_routing_code,
                            :expected_yq_savings_usd, :confidence_score, :freshness_tier,
                            :source, :source_url, :source_post_weight,
                            now(), now()
                        )
                        ON CONFLICT (ita_routing_code) DO UPDATE SET
                            lifecycle_state = EXCLUDED.lifecycle_state,
                            expected_yq_savings_usd = EXCLUDED.expected_yq_savings_usd,
                            confidence_score = EXCLUDED.confidence_score,
                            freshness_tier = EXCLUDED.freshness_tier,
                            updated_at = now()
                        RETURNING (xmax = 0) AS is_insert
                    """),
                    {
                        "id": pattern_id,
                        "dump_type": p["dump_type"],
                        "lifecycle_state": p["lifecycle_state"],
                        "origin_iata": p["origin_iata"],
                        "destination_iata": p["destination_iata"],
                        "ticketing_carrier_iata": p["ticketing_carrier_iata"],
                        "operating_carriers": p["operating_carriers"],
                        "routing_points": p["routing_points"],
                        "fare_basis_hint": p["fare_basis_hint"],
                        "ita_routing_code": p["ita_routing_code"],
                        "expected_yq_savings_usd": p["expected_yq_savings_usd"],
                        "confidence_score": p["confidence_score"],
                        "freshness_tier": p["freshness_tier"],
                        "source": p["source"],
                        "source_url": p["source_url"],
                        "source_post_weight": p["source_post_weight"],
                    },
                )
                row = result.fetchone()
                if row and row[0]:
                    inserted += 1
                else:
                    updated += 1
                route_str = f"{p['origin_iata']}→{p['destination_iata']} via {p['ticketing_carrier_iata']}"
                print(f"  {'✓' if row and row[0] else '↻'} {route_str} [{p['dump_type']}]")
            except Exception as e:
                errors += 1
                print(f"  ERROR seeding {p['origin_iata']}→{p['destination_iata']}: {e}")

        await session.commit()

    await engine.dispose()

    print(f"\nSeeded {len(PATTERNS)} patterns ({inserted} inserted, {updated} updated, {errors} errors)")
    if errors > 0:
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(seed_patterns())
