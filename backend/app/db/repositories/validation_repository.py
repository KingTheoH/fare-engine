"""
validation_repository.py — Database queries for validation runs.

Pure data access — no business logic. Services call these functions.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.validation_run import ValidationRun


async def create_validation_run(
    session: AsyncSession,
    pattern_id: uuid.UUID,
    success: bool,
    yq_charged_usd: float | None = None,
    yq_expected_usd: float | None = None,
    base_fare_usd: float | None = None,
    raw_ita_response: dict | None = None,
    manual_input_snapshot: dict | None = None,
    error_message: str | None = None,
    proxy_used: str | None = None,
) -> ValidationRun:
    """Create and persist a new validation run record."""
    run = ValidationRun(
        pattern_id=pattern_id,
        success=success,
        yq_charged_usd=yq_charged_usd,
        yq_expected_usd=yq_expected_usd,
        base_fare_usd=base_fare_usd,
        raw_ita_response=raw_ita_response,
        manual_input_snapshot=manual_input_snapshot,
        error_message=error_message,
        proxy_used=proxy_used,
    )
    session.add(run)
    await session.flush()
    return run


async def get_recent_runs(
    session: AsyncSession,
    pattern_id: uuid.UUID,
    limit: int = 10,
) -> list[ValidationRun]:
    """Get the most recent validation runs for a pattern, newest first."""
    stmt = (
        select(ValidationRun)
        .where(ValidationRun.pattern_id == pattern_id)
        .order_by(ValidationRun.ran_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_consecutive_failures(
    session: AsyncSession,
    pattern_id: uuid.UUID,
) -> int:
    """
    Count consecutive failures from the most recent run backwards.

    Returns 0 if the most recent run was a success (or no runs exist).
    """
    runs = await get_recent_runs(session, pattern_id, limit=10)

    count = 0
    for run in runs:
        if not run.success:
            count += 1
        else:
            break

    return count


async def get_consecutive_successes(
    session: AsyncSession,
    pattern_id: uuid.UUID,
) -> int:
    """
    Count consecutive successes from the most recent run backwards.

    Returns 0 if the most recent run was a failure (or no runs exist).
    """
    runs = await get_recent_runs(session, pattern_id, limit=10)

    count = 0
    for run in runs:
        if run.success:
            count += 1
        else:
            break

    return count


async def get_success_rate(
    session: AsyncSession,
    pattern_id: uuid.UUID,
    last_n: int = 5,
) -> float | None:
    """
    Get the success rate over the last N runs.

    Returns None if no runs exist, otherwise a ratio in [0.0, 1.0].
    """
    runs = await get_recent_runs(session, pattern_id, limit=last_n)

    if not runs:
        return None

    successes = sum(1 for r in runs if r.success)
    return successes / len(runs)


async def get_last_validation_time(
    session: AsyncSession,
    pattern_id: uuid.UUID,
) -> datetime | None:
    """Get the timestamp of the most recent validation run."""
    stmt = (
        select(ValidationRun.ran_at)
        .where(ValidationRun.pattern_id == pattern_id)
        .order_by(ValidationRun.ran_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_all_recent_runs(
    session: AsyncSession,
    since: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[ValidationRun], int]:
    """Get recent validation runs across ALL patterns, newest first."""
    base = select(ValidationRun)
    count_base = select(func.count(ValidationRun.id))

    if since is not None:
        base = base.where(ValidationRun.ran_at >= since)
        count_base = count_base.where(ValidationRun.ran_at >= since)

    total_result = await session.execute(count_base)
    total = total_result.scalar_one()

    stmt = base.order_by(ValidationRun.ran_at.desc()).offset(offset).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all()), total


async def get_run_history(
    session: AsyncSession,
    pattern_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[ValidationRun]:
    """Get paginated validation run history for a pattern."""
    stmt = (
        select(ValidationRun)
        .where(ValidationRun.pattern_id == pattern_id)
        .order_by(ValidationRun.ran_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
