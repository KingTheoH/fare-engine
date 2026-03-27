"""
dump_candidates.py — Dump candidate endpoints.

GET /api/v1/dump-candidates           — list dump candidates (filterable by enabled)
GET /api/v1/dump-candidates/{id}      — single dump candidate detail
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_api_key
from app.db.repositories.dump_candidate_repository import (
    count_dump_candidates,
    get_all_dump_candidates,
    get_dump_candidate_by_id,
)
from app.schemas.dump_candidate import DumpCandidateResponse
from app.schemas.common import PaginatedResponse

router = APIRouter(
    prefix="/api/v1/dump-candidates",
    tags=["dump-candidates"],
    dependencies=[Depends(require_api_key)],
)


@router.get("", response_model=PaginatedResponse[DumpCandidateResponse])
async def list_dump_candidates(
    enabled: bool | None = Query(None, description="Filter by enabled state"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[DumpCandidateResponse]:
    """
    List short-haul dump candidate segments, sorted by empirical success rate DESC.

    These are the segments injected into multi-city itineraries to disrupt YQ.
    Never-tested candidates appear at the bottom (success_rate=null).
    """
    offset = (page - 1) * page_size

    candidates = await get_all_dump_candidates(
        session,
        enabled=enabled,
        limit=page_size,
        offset=offset,
    )
    total = await count_dump_candidates(session, enabled=enabled)

    items = [DumpCandidateResponse.model_validate(c) for c in candidates]

    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{candidate_id}", response_model=DumpCandidateResponse)
async def get_dump_candidate(
    candidate_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> DumpCandidateResponse:
    """Get a single dump candidate by UUID."""
    candidate = await get_dump_candidate_by_id(session, candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dump candidate not found: {candidate_id}",
        )
    return DumpCandidateResponse.model_validate(candidate)
