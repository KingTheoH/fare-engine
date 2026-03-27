"""
scan_target_repository.py — Database queries for scan targets.

Pure data access — no business logic. Services and route handlers call these.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan_target import ScanTarget


async def get_all_scan_targets(
    session: AsyncSession,
    tier: int | None = None,
    enabled: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ScanTarget]:
    """Get all scan targets, optionally filtered by tier and/or enabled state."""
    stmt = select(ScanTarget)

    if tier is not None:
        stmt = stmt.where(ScanTarget.tier == tier)
    if enabled is not None:
        stmt = stmt.where(ScanTarget.enabled == enabled)

    stmt = (
        stmt.order_by(ScanTarget.tier.asc(), ScanTarget.origin_iata.asc())
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_scan_target_by_id(
    session: AsyncSession,
    target_id: uuid.UUID,
) -> ScanTarget | None:
    """Fetch a single scan target by UUID."""
    result = await session.execute(
        select(ScanTarget).where(ScanTarget.id == target_id)
    )
    return result.scalar_one_or_none()


async def count_scan_targets(
    session: AsyncSession,
    tier: int | None = None,
    enabled: bool | None = None,
) -> int:
    """Count scan targets, optionally filtered."""
    stmt = select(func.count()).select_from(ScanTarget)
    if tier is not None:
        stmt = stmt.where(ScanTarget.tier == tier)
    if enabled is not None:
        stmt = stmt.where(ScanTarget.enabled == enabled)
    result = await session.execute(stmt)
    return result.scalar_one()
