#!/usr/bin/env python3
"""
seed_carriers.py — Populate the carriers table from seeds/carriers.json.

Idempotent: safe to run multiple times. Uses upsert (INSERT ... ON CONFLICT DO UPDATE).

Usage:
    cd backend && python scripts/seed_carriers.py

Requires:
    - PostgreSQL running and accessible via DATABASE_URL
    - Alembic migrations applied (alembic upgrade head)
"""

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Add the backend directory to the Python path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings


SEEDS_DIR = Path(__file__).resolve().parent.parent / "seeds"


async def seed_carriers() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    carriers_file = SEEDS_DIR / "carriers.json"
    if not carriers_file.exists():
        print(f"ERROR: {carriers_file} not found")
        sys.exit(1)

    with open(carriers_file) as f:
        carriers = json.load(f)

    print(f"Loading {len(carriers)} carriers from {carriers_file.name}...")

    inserted = 0
    updated = 0
    errors = 0

    async with async_session() as session:
        for carrier in carriers:
            try:
                result = await session.execute(
                    text("""
                        INSERT INTO carriers (iata_code, name, alliance, charges_yq, typical_yq_usd)
                        VALUES (:iata_code, :name, :alliance, :charges_yq, :typical_yq_usd)
                        ON CONFLICT (iata_code) DO UPDATE SET
                            name = EXCLUDED.name,
                            alliance = EXCLUDED.alliance,
                            charges_yq = EXCLUDED.charges_yq,
                            typical_yq_usd = EXCLUDED.typical_yq_usd,
                            updated_at = now()
                        RETURNING (xmax = 0) AS is_insert
                    """),
                    {
                        "iata_code": carrier["iata_code"],
                        "name": carrier["name"],
                        "alliance": carrier["alliance"],
                        "charges_yq": carrier["charges_yq"],
                        "typical_yq_usd": carrier["typical_yq_usd"],
                    },
                )
                row = result.fetchone()
                if row and row[0]:
                    inserted += 1
                else:
                    updated += 1
            except Exception as e:
                errors += 1
                print(f"  ERROR seeding {carrier['iata_code']}: {e}")

        await session.commit()

    await engine.dispose()

    print(f"Seeded {len(carriers)} carriers ({inserted} inserted, {updated} updated, {errors} errors)")
    if errors > 0:
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    asyncio.run(seed_carriers())
