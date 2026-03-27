"""
manual_inputs.py — Manual input bundle endpoints.

GET /api/v1/manual-inputs/{pattern_id} — get manual input bundle for a pattern

This is a convenience alias for GET /api/v1/patterns/{id}/manual-input.
Kept as a separate router for clean API organization.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_api_key
from app.db.repositories import pattern_repository

router = APIRouter(
    prefix="/api/v1/manual-inputs",
    tags=["manual-inputs"],
    dependencies=[Depends(require_api_key)],
)


@router.get("/{pattern_id}")
async def get_manual_input_bundle(
    pattern_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Export the ManualInputBundle for a pattern.

    Returns a self-contained JSON object that agents can use
    directly with ITA Matrix — no other context needed.
    """
    pattern = await pattern_repository.get_pattern_by_id(session, pattern_id)
    if pattern is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern not found: {pattern_id}",
        )

    if pattern.manual_input_bundle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No manual input bundle available — pattern has not been validated yet",
        )

    return pattern.manual_input_bundle
