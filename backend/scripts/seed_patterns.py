"""
seed_patterns.py — Seed dump_patterns with real scan-engine-style entries.

These patterns represent high-probability scan_target x dump_candidate
combinations. Each one has:
  - baseline_routing: ITA Matrix query WITHOUT dump injection
  - optimized_routing: ITA Matrix query WITH dump injection
  - multi_city_segments: full multi-city itinerary structure
  - dump_segment: the injected short-haul leg

ITA Matrix routing code syntax:
  - Carrier code alone: "LH" = constrain ticketing carrier to LH
  - Connection city: "LH FRA LH" = fly LH to FRA, then LH onward
  - Extension codes: /f bc=J (booking class), /minfare 200
  - Multi-city: separate legs entered as separate city pairs in ITA multi-city mode
  - NEVER use FORCE syntax -- that is not real ITA Matrix syntax

All patterns start as 'active'. baseline_price/optimized_price filled by scanner.

Usage:
    cd backend
    python scripts/seed_patterns.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://theoh@localhost:5432/fare_engine"
)

PATTERNS = [
    # 1. JFK -> BKK on LH via FRA/MUC, dump: FRA -> AMS  (most-requested route)
    {
        "origin_iata": "JFK", "destination_iata": "BKK",
        "ticketing_carrier_iata": "LH", "operating_carriers": ["LH", "TG"],
        "routing_points": ["FRA"], "dump_type": "TP_DUMP",
        "baseline_routing": "LH+ FRA,MUC LH+",
        "optimized_routing": "LH+ FRA,MUC",
        "multi_city_segments": [
            {"from": "JFK", "to": "BKK", "carrier": "LH", "via": "FRA", "notes": "Main — LH via Frankfurt or Munich, onward TG/LH metal to BKK"},
            {"from": "FRA", "to": "AMS", "carrier": None, "via": None, "notes": "Dump — FRA\u2192AMS Star Alliance zone boundary (no routing code on this leg)"},
        ],
        "dump_segment": {"from": "FRA", "to": "AMS", "carrier": None, "notes": "Star Alliance zone boundary disrupts LH intra-Europe YQ chain"},
        "expected_yq_savings_usd": 580.0, "confidence_score": 0.38, "freshness_tier": 1,
        "source": "INTERNAL_DISCOVERY",
    },
    # 2. YVR -> LHR via LH (via FRA), dump: FRA -> AMS
    {
        "origin_iata": "YVR", "destination_iata": "LHR",
        "ticketing_carrier_iata": "LH", "operating_carriers": ["LH"],
        "routing_points": ["FRA"], "dump_type": "TP_DUMP",
        "baseline_routing": "LH+ FRA,MUC LH+",
        "optimized_routing": "LH+ FRA,MUC",
        "multi_city_segments": [
            {"from": "YVR", "to": "LHR", "carrier": "LH", "via": "FRA", "notes": "Main — LH via Frankfurt"},
            {"from": "FRA", "to": "AMS", "carrier": None, "via": None, "notes": "Dump — FRA->AMS Star Alliance zone boundary"},
        ],
        "dump_segment": {"from": "FRA", "to": "AMS", "carrier": None, "notes": "Star Alliance zone boundary, disrupts LH intra-Europe YQ"},
        "expected_yq_savings_usd": 280.0, "confidence_score": 0.35, "freshness_tier": 1,
        "source": "INTERNAL_DISCOVERY",
    },
    # 2. YVR -> FRA on LH direct, dump: FRA -> AMS
    {
        "origin_iata": "YVR", "destination_iata": "FRA",
        "ticketing_carrier_iata": "LH", "operating_carriers": ["LH"],
        "routing_points": [], "dump_type": "TP_DUMP",
        "baseline_routing": "LH+",
        "optimized_routing": "LH+",
        "multi_city_segments": [
            {"from": "YVR", "to": "FRA", "carrier": "LH", "via": None, "notes": "Main — LH direct"},
            {"from": "FRA", "to": "AMS", "carrier": None, "via": None, "notes": "Dump — loose short-haul Amsterdam"},
        ],
        "dump_segment": {"from": "FRA", "to": "AMS", "carrier": None, "notes": "FRA->AMS Star Alliance zone boundary"},
        "expected_yq_savings_usd": 310.0, "confidence_score": 0.40, "freshness_tier": 1,
        "source": "INTERNAL_DISCOVERY",
    },
    # 3. SEA -> LHR on BA, dump: LHR -> OSL
    {
        "origin_iata": "SEA", "destination_iata": "LHR",
        "ticketing_carrier_iata": "BA", "operating_carriers": ["BA"],
        "routing_points": [], "dump_type": "CARRIER_SWITCH",
        "baseline_routing": "BA+",
        "optimized_routing": "BA+",
        "multi_city_segments": [
            {"from": "SEA", "to": "LHR", "carrier": "BA", "via": None, "notes": "Main — BA direct"},
            {"from": "LHR", "to": "OSL", "carrier": None, "via": None, "notes": "Dump — intra-Europe, separate fare zone"},
        ],
        "dump_segment": {"from": "LHR", "to": "OSL", "carrier": None, "notes": "LHR->OSL intra-Europe zone separation"},
        "expected_yq_savings_usd": 420.0, "confidence_score": 0.30, "freshness_tier": 1,
        "source": "INTERNAL_DISCOVERY",
    },
    # 4. YVR -> BKK on QR via DOH, dump: BKK -> SIN
    {
        "origin_iata": "YVR", "destination_iata": "BKK",
        "ticketing_carrier_iata": "QR", "operating_carriers": ["QR"],
        "routing_points": ["DOH"], "dump_type": "TP_DUMP",
        "baseline_routing": "QR+ DOH QR+",
        "optimized_routing": "QR+ DOH",
        "multi_city_segments": [
            {"from": "YVR", "to": "BKK", "carrier": "QR", "via": "DOH", "notes": "Main — QR via Doha"},
            {"from": "BKK", "to": "SIN", "carrier": None, "via": None, "notes": "Dump — SEA zone 3 boundary"},
        ],
        "dump_segment": {"from": "BKK", "to": "SIN", "carrier": None, "notes": "BKK->SIN zone 3 boundary disrupts QR YQ"},
        "expected_yq_savings_usd": 195.0, "confidence_score": 0.28, "freshness_tier": 1,
        "source": "INTERNAL_DISCOVERY",
    },
    # 5. LHR -> BKK on QR via DOH, dump: BKK -> SIN
    {
        "origin_iata": "LHR", "destination_iata": "BKK",
        "ticketing_carrier_iata": "QR", "operating_carriers": ["QR"],
        "routing_points": ["DOH"], "dump_type": "TP_DUMP",
        "baseline_routing": "QR+ DOH QR+",
        "optimized_routing": "QR+ DOH",
        "multi_city_segments": [
            {"from": "LHR", "to": "BKK", "carrier": "QR", "via": "DOH", "notes": "Main — QR via Doha"},
            {"from": "BKK", "to": "SIN", "carrier": None, "via": None, "notes": "Dump — SEA zone 3 boundary"},
        ],
        "dump_segment": {"from": "BKK", "to": "SIN", "carrier": None, "notes": "BKK->SIN breaks QR YQ continuity"},
        "expected_yq_savings_usd": 380.0, "confidence_score": 0.32, "freshness_tier": 1,
        "source": "INTERNAL_DISCOVERY",
    },
    # 6. YVR -> ICN on KE, dump: ICN -> PUS
    {
        "origin_iata": "YVR", "destination_iata": "ICN",
        "ticketing_carrier_iata": "KE", "operating_carriers": ["KE"],
        "routing_points": [], "dump_type": "TP_DUMP",
        "baseline_routing": "KE+ ICN,GMP KE+",
        "optimized_routing": "KE+ ICN,GMP",
        "multi_city_segments": [
            {"from": "YVR", "to": "ICN", "carrier": "KE", "via": None, "notes": "Main — KE direct"},
            {"from": "ICN", "to": "GMP", "carrier": None, "via": None, "notes": "Dump — Incheon→Gimpo Korean domestic zone"},
        ],
        "dump_segment": {"from": "ICN", "to": "GMP", "carrier": None, "notes": "ICN→GMP Korean domestic zone disrupts KE international YQ"},
        "expected_yq_savings_usd": 145.0, "confidence_score": 0.25, "freshness_tier": 1,
        "source": "INTERNAL_DISCOVERY",
    },
    # 7. YVR -> NRT on NH, dump: NRT -> HND
    {
        "origin_iata": "YVR", "destination_iata": "NRT",
        "ticketing_carrier_iata": "NH", "operating_carriers": ["NH"],
        "routing_points": [], "dump_type": "TP_DUMP",
        "baseline_routing": "NH+ NRT,HND NH+",
        "optimized_routing": "NH+ NRT,HND",
        "multi_city_segments": [
            {"from": "YVR", "to": "NRT", "carrier": "NH", "via": None, "notes": "Main — ANA direct or 1-stop (NRT or HND accepted)"},
            {"from": "NRT", "to": "HND", "carrier": None, "via": None, "notes": "Dump — Narita to Haneda, different Tokyo tariff node"},
        ],
        "dump_segment": {"from": "NRT", "to": "HND", "carrier": None, "notes": "NRT->HND different Tokyo tariff node"},
        "expected_yq_savings_usd": 120.0, "confidence_score": 0.22, "freshness_tier": 1,
        "source": "INTERNAL_DISCOVERY",
    },
    # 8. FRA -> BKK on LH (may interline TG), dump: CDG -> BRU
    {
        "origin_iata": "FRA", "destination_iata": "BKK",
        "ticketing_carrier_iata": "LH", "operating_carriers": ["LH", "TG"],
        "routing_points": [], "dump_type": "CARRIER_SWITCH",
        "baseline_routing": "LH+",
        "optimized_routing": "LH+",
        "multi_city_segments": [
            {"from": "FRA", "to": "BKK", "carrier": "LH", "via": None, "notes": "Main — LH metal, may interline TG"},
            {"from": "CDG", "to": "BRU", "carrier": None, "via": None, "notes": "Dump — Paris to Brussels, ultra-short intra-Europe"},
        ],
        "dump_segment": {"from": "CDG", "to": "BRU", "carrier": None, "notes": "CDG->BRU ultra-short, different zone from LH intercontinental"},
        "expected_yq_savings_usd": 320.0, "confidence_score": 0.27, "freshness_tier": 1,
        "source": "INTERNAL_DISCOVERY",
    },
    # 9. SEA -> BKK on QR via DOH, dump: TAS -> SKD (Uzbekistan, zone 9)
    {
        "origin_iata": "SEA", "destination_iata": "BKK",
        "ticketing_carrier_iata": "QR", "operating_carriers": ["QR"],
        "routing_points": ["DOH"], "dump_type": "ALLIANCE_RULE",
        "baseline_routing": "QR+ DOH QR+",
        "optimized_routing": "QR+ DOH",
        "multi_city_segments": [
            {"from": "SEA", "to": "BKK", "carrier": "QR", "via": "DOH", "notes": "Main — QR via Doha"},
            {"from": "TAS", "to": "SKD", "carrier": "HY", "via": None, "notes": "Dump — Uzbekistan domestic, IATA zone 9"},
        ],
        "dump_segment": {"from": "TAS", "to": "SKD", "carrier": "HY", "notes": "Uzbekistan Airways domestic -- zone 9, strongest zone disruption"},
        "expected_yq_savings_usd": 230.0, "confidence_score": 0.20, "freshness_tier": 1,
        "source": "INTERNAL_DISCOVERY",
    },
    # 10. CDG -> BKK on QR via DOH, dump: SIN -> BKK
    {
        "origin_iata": "CDG", "destination_iata": "BKK",
        "ticketing_carrier_iata": "QR", "operating_carriers": ["QR"],
        "routing_points": ["DOH"], "dump_type": "TP_DUMP",
        "baseline_routing": "QR+ DOH QR+",
        "optimized_routing": "QR+ DOH",
        "multi_city_segments": [
            {"from": "CDG", "to": "BKK", "carrier": "QR", "via": "DOH", "notes": "Main — QR CDG->DOH->BKK"},
            {"from": "SIN", "to": "BKK", "carrier": None, "via": None, "notes": "Dump — SIN->BKK zone 3 reverse boundary"},
        ],
        "dump_segment": {"from": "SIN", "to": "BKK", "carrier": None, "notes": "SIN->BKK reverse zone 3 boundary on return"},
        "expected_yq_savings_usd": 350.0, "confidence_score": 0.30, "freshness_tier": 1,
        "source": "INTERNAL_DISCOVERY",
    },
]

INSERT_SQL = text("""
    INSERT INTO dump_patterns (
        dump_type, lifecycle_state,
        origin_iata, destination_iata,
        ticketing_carrier_iata, operating_carriers, routing_points,
        baseline_routing, optimized_routing,
        multi_city_segments, dump_segment,
        expected_yq_savings_usd, confidence_score, freshness_tier,
        source, source_url
    )
    VALUES (
        :dump_type, 'active',
        :origin_iata, :destination_iata,
        :ticketing_carrier_iata, :operating_carriers, :routing_points,
        :baseline_routing, :optimized_routing,
        CAST(:multi_city_segments AS jsonb), CAST(:dump_segment AS jsonb),
        :expected_yq_savings_usd, :confidence_score, :freshness_tier,
        :source, NULL
    )
    ON CONFLICT DO NOTHING
""")


async def seed() -> None:
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        # Remove old FORCE-syntax patterns and any INTERNAL_DISCOVERY patterns
        # (full re-seed to pick up corrected routing codes)
        deleted = await conn.execute(text(
            "DELETE FROM dump_patterns WHERE source = 'INTERNAL_DISCOVERY'"
        ))
        print(f"Cleared {deleted.rowcount} old patterns (re-seeding with corrected routing codes).\n")

        inserted = 0
        for p in PATTERNS:
            await conn.execute(INSERT_SQL, {
                "dump_type": p["dump_type"],
                "origin_iata": p["origin_iata"],
                "destination_iata": p["destination_iata"],
                "ticketing_carrier_iata": p["ticketing_carrier_iata"],
                "operating_carriers": p["operating_carriers"],
                "routing_points": p.get("routing_points", []),
                "baseline_routing": p.get("baseline_routing"),
                "optimized_routing": p.get("optimized_routing"),
                "multi_city_segments": json.dumps(p.get("multi_city_segments")),
                "dump_segment": json.dumps(p.get("dump_segment")),
                "expected_yq_savings_usd": p.get("expected_yq_savings_usd"),
                "confidence_score": p.get("confidence_score", 0.3),
                "freshness_tier": p.get("freshness_tier", 1),
                "source": p.get("source", "INTERNAL_DISCOVERY"),
            })
            inserted += 1
            origin = p["origin_iata"]
            dest = p["destination_iata"]
            carrier = p["ticketing_carrier_iata"]
            dump_type = p["dump_type"]
            dump_seg = p["dump_segment"]
            print(f"  + {origin} -> {dest} on {carrier} [{dump_type}]  dump: {dump_seg['from']}->{dump_seg['to']}")

    await engine.dispose()
    print(f"\nInserted {inserted} patterns (skipped any duplicates).")
    print("All are 'active'. baseline_price / optimized_price will be filled by the scanner.")


if __name__ == "__main__":
    asyncio.run(seed())
