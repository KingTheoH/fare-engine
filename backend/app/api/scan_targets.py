"""
scan_targets.py — Scan target endpoints.

GET /api/v1/scan-targets           — list scan targets (filterable by tier, enabled)
GET /api/v1/scan-targets/{id}      — single scan target detail
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_api_key
from app.db.repositories.scan_target_repository import (
    count_scan_targets,
    get_all_scan_targets,
    get_scan_target_by_id,
)
from app.schemas.scan_target import ScanTargetResponse
from app.schemas.common import PaginatedResponse

router = APIRouter(
    prefix="/api/v1/scan-targets",
    tags=["scan-targets"],
    dependencies=[Depends(require_api_key)],
)


@router.get("", response_model=PaginatedResponse[ScanTargetResponse])
async def list_scan_targets(
    tier: int | None = Query(None, ge=1, le=3, description="Filter by scan tier (1/2/3)"),
    enabled: bool | None = Query(None, description="Filter by enabled state"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[ScanTargetResponse]:
    """
    List scan targets the scanner monitors.

    Sorted by tier ASC then origin ASC. Use tier=1 to get high-frequency targets.
    """
    offset = (page - 1) * page_size

    targets = await get_all_scan_targets(
        session,
        tier=tier,
        enabled=enabled,
        limit=page_size,
        offset=offset,
    )
    total = await count_scan_targets(session, tier=tier, enabled=enabled)

    items = [ScanTargetResponse.model_validate(t) for t in targets]

    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{target_id}", response_model=ScanTargetResponse)
async def get_scan_target(
    target_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ScanTargetResponse:
    """Get a single scan target by UUID."""
    target = await get_scan_target_by_id(session, target_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan target not found: {target_id}",
        )
    return ScanTargetResponse.model_validate(target)
