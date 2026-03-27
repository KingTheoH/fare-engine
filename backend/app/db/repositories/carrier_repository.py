"""
carrier_repository.py — Database queries for carriers.

Pure data access — no business logic. Services call these functions.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.carrier import Carrier


async def get_all_carriers(
    session: AsyncSession,
    charges_yq: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Carrier]:
    """Get all carriers, optionally filtered by charges_yq."""
    stmt = select(Carrier)

    if charges_yq is not None:
        stmt = stmt.where(Carrier.charges_yq == charges_yq)

    stmt = (
        stmt.order_by(Carrier.typical_yq_usd.desc().nullslast())
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_carrier_by_iata(
    session: AsyncSession,
    iata_code: str,
) -> Carrier | None:
    """Fetch a single carrier by IATA code."""
    stmt = select(Carrier).where(Carrier.iata_code == iata_code.upper())
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def count_carriers(
    session: AsyncSession,
    charges_yq: bool | None = None,
) -> int:
    """Count carriers, optionally filtered."""
    from sqlalchemy import func

    stmt = select(func.count()).select_from(Carrier)
    if charges_yq is not None:
        stmt = stmt.where(Carrier.charges_yq == charges_yq)

    result = await session.execute(stmt)
    return result.scalar_one()
