"""
pattern_repository.py — Database queries for dump patterns.

Pure data access — no business logic. Services call these functions.
"""

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dump_pattern import DumpPattern
from app.models.enums import LifecycleState


async def get_pattern_by_id(
    session: AsyncSession,
    pattern_id: uuid.UUID,
) -> DumpPattern | None:
    """Fetch a single dump pattern by ID."""
    stmt = select(DumpPattern).where(DumpPattern.id == pattern_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_active_patterns(
    session: AsyncSession,
    dump_type: str | None = None,
    origin: str | None = None,
    destination: str | None = None,
    carrier: str | None = None,
    freshness_tier: int | None = None,
    include_discovered: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[DumpPattern]:
    """
    Get patterns surfaceable to agents.

    By default returns active + degrading patterns. With include_discovered=True,
    also returns discovered patterns so agents can manually test unvalidated
    patterns via ITA Matrix.

    Filters are all optional and additive (AND).
    """
    allowed_states = [
        LifecycleState.ACTIVE.value,
        LifecycleState.DEGRADING.value,
    ]
    if include_discovered:
        allowed_states.append(LifecycleState.DISCOVERED.value)

    stmt = select(DumpPattern).where(
        DumpPattern.lifecycle_state.in_(allowed_states)
    )

    if dump_type:
        stmt = stmt.where(DumpPattern.dump_type == dump_type)
    if origin:
        stmt = stmt.where(DumpPattern.origin_iata == origin.upper())
    if destination:
        stmt = stmt.where(DumpPattern.destination_iata == destination.upper())
    if carrier:
        stmt = stmt.where(DumpPattern.ticketing_carrier_iata == carrier.upper())
    if freshness_tier is not None:
        stmt = stmt.where(DumpPattern.freshness_tier == freshness_tier)

    stmt = (
        stmt.order_by(DumpPattern.confidence_score.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_patterns_needing_validation(
    session: AsyncSession,
    freshness_tier: int | None = None,
    limit: int = 50,
) -> list[DumpPattern]:
    """
    Get patterns that are due for validation.

    Returns discovered, active, and degrading patterns sorted by
    confidence (lowest first — most in need of validation).
    """
    stmt = select(DumpPattern).where(
        DumpPattern.lifecycle_state.in_([
            LifecycleState.DISCOVERED.value,
            LifecycleState.ACTIVE.value,
            LifecycleState.DEGRADING.value,
        ])
    )

    if freshness_tier is not None:
        stmt = stmt.where(DumpPattern.freshness_tier == freshness_tier)

    stmt = (
        stmt.order_by(DumpPattern.confidence_score.asc())
        .limit(limit)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def upsert_community_pattern(
    session: AsyncSession,
    pattern_data: dict[str, Any],
) -> tuple[DumpPattern, bool]:
    """
    Insert a community-sourced pattern, skipping if routing code already exists.

    Checks the unique ita_routing_code constraint before inserting.
    Returns (pattern, created) where created=False if it already existed.
    """
    ita_routing_code = pattern_data.get("ita_routing_code")

    # Check if a pattern with this routing code already exists
    if ita_routing_code:
        existing_result = await session.execute(
            select(DumpPattern).where(
                DumpPattern.ita_routing_code == ita_routing_code
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            return existing, False

    # Insert new pattern — strip metadata keys (prefixed with _) not in ORM
    db_data = {k: v for k, v in pattern_data.items() if not k.startswith("_")}
    pattern = DumpPattern(**db_data)
    session.add(pattern)
    await session.flush()  # Flush to assign ID without committing
    return pattern, True


async def update_pattern_fields(
    session: AsyncSession,
    pattern_id: uuid.UUID,
    **fields: Any,
) -> None:
    """Update arbitrary fields on a dump pattern."""
    if not fields:
        return

    stmt = (
        update(DumpPattern)
        .where(DumpPattern.id == pattern_id)
        .values(**fields)
    )
    await session.execute(stmt)


async def update_lifecycle_state(
    session: AsyncSession,
    pattern_id: uuid.UUID,
    new_state: str,
) -> None:
    """Update the lifecycle state of a pattern."""
    await update_pattern_fields(
        session, pattern_id, lifecycle_state=new_state
    )


async def update_confidence_score(
    session: AsyncSession,
    pattern_id: uuid.UUID,
    score: float,
) -> None:
    """Update the confidence score of a pattern."""
    await update_pattern_fields(
        session, pattern_id, confidence_score=score
    )


async def update_freshness_tier(
    session: AsyncSession,
    pattern_id: uuid.UUID,
    tier: int,
) -> None:
    """Update the freshness tier of a pattern."""
    await update_pattern_fields(
        session, pattern_id, freshness_tier=tier
    )


async def get_patterns_by_state(
    session: AsyncSession,
    state: str,
    limit: int = 100,
) -> list[DumpPattern]:
    """Get all patterns in a given lifecycle state."""
    stmt = (
        select(DumpPattern)
        .where(DumpPattern.lifecycle_state == state)
        .order_by(DumpPattern.updated_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
