"""
dump_candidate_repository.py — Database queries for dump candidates.

Pure data access — no business logic. Services and route handlers call these.
"""

import uuid

from sqlalchemy import Float, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dump_candidate import DumpCandidate


async def get_all_dump_candidates(
    session: AsyncSession,
    enabled: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[DumpCandidate]:
    """Get all dump candidates, optionally filtered by enabled state."""
    stmt = select(DumpCandidate)

    if enabled is not None:
        stmt = stmt.where(DumpCandidate.enabled == enabled)

    # Sort by empirical success rate descending (nulls last — never-tested go to the bottom)
    stmt = (
        stmt.order_by(
            (
                DumpCandidate.success_count.cast(Float)
                / func.nullif(DumpCandidate.test_count, 0)
            ).desc().nullslast(),
            DumpCandidate.from_iata.asc(),
        )
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_dump_candidate_by_id(
    session: AsyncSession,
    candidate_id: uuid.UUID,
) -> DumpCandidate | None:
    """Fetch a single dump candidate by UUID."""
    result = await session.execute(
        select(DumpCandidate).where(DumpCandidate.id == candidate_id)
    )
    return result.scalar_one_or_none()


async def count_dump_candidates(
    session: AsyncSession,
    enabled: bool | None = None,
) -> int:
    """Count dump candidates, optionally filtered."""
    stmt = select(func.count()).select_from(DumpCandidate)
    if enabled is not None:
        stmt = stmt.where(DumpCandidate.enabled == enabled)
    result = await session.execute(stmt)
    return result.scalar_one()
