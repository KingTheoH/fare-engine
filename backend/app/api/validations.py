"""
validations.py — Validation endpoints.

GET  /api/v1/validations — recent validation runs across all patterns
POST /api/v1/validations/trigger/{pattern_id} — enqueue validation task
GET  /api/v1/validations/{pattern_id}/history — validation run history
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_api_key
from app.db.repositories import pattern_repository, validation_repository
from app.schemas.common import PaginatedResponse
from app.schemas.validation_run import ValidationRunResponse

router = APIRouter(
    prefix="/api/v1/validations",
    tags=["validations"],
    dependencies=[Depends(require_api_key)],
)


PERIOD_MAP = {
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


@router.get("", response_model=PaginatedResponse[ValidationRunResponse])
async def get_recent_validations(
    period: str = Query("7d", description="Time period: 24h, 7d, or 30d"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[ValidationRunResponse]:
    """
    Get recent validation runs across all patterns, newest first.
    """
    delta = PERIOD_MAP.get(period)
    since = (datetime.now(timezone.utc) - delta) if delta else None

    offset = (page - 1) * page_size
    runs, total = await validation_repository.get_all_recent_runs(
        session, since=since, limit=page_size, offset=offset
    )

    items = [ValidationRunResponse.model_validate(r) for r in runs]
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/trigger/{pattern_id}")
async def trigger_validation(
    pattern_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Manually trigger a validation run for a specific pattern.

    Enqueues a Celery task. Returns the task ID for tracking.
    """
    # Verify pattern exists
    pattern = await pattern_repository.get_pattern_by_id(session, pattern_id)
    if pattern is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern not found: {pattern_id}",
        )

    # Don't validate archived/deprecated patterns
    if pattern.lifecycle_state in ("archived", "deprecated"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot validate pattern in '{pattern.lifecycle_state}' state",
        )

    # Enqueue Celery task
    from app.tasks.validation_tasks import validate_single_pattern

    task = validate_single_pattern.delay(str(pattern_id))

    return {
        "status": "queued",
        "task_id": task.id,
        "pattern_id": str(pattern_id),
    }


@router.get("/{pattern_id}/history", response_model=PaginatedResponse[ValidationRunResponse])
async def get_validation_history(
    pattern_id: uuid.UUID,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[ValidationRunResponse]:
    """
    Get validation run history for a pattern, newest first.
    """
    # Verify pattern exists
    pattern = await pattern_repository.get_pattern_by_id(session, pattern_id)
    if pattern is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern not found: {pattern_id}",
        )

    offset = (page - 1) * page_size

    runs = await validation_repository.get_run_history(
        session, pattern_id, limit=page_size, offset=offset
    )

    items = [ValidationRunResponse.model_validate(r) for r in runs]

    return PaginatedResponse(
        items=items,
        total=len(items),
        page=page,
        page_size=page_size,
    )
