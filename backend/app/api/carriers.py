"""
carriers.py — Carrier / YQ tracker endpoints.

GET /api/v1/carriers           — list all carriers, sorted by typical_yq_usd DESC
GET /api/v1/carriers/{iata}    — single carrier detail
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_api_key
from app.db.repositories.carrier_repository import (
    count_carriers,
    get_all_carriers,
    get_carrier_by_iata,
)
from app.schemas.carrier import CarrierResponse
from app.schemas.common import PaginatedResponse

router = APIRouter(
    prefix="/api/v1/carriers",
    tags=["carriers"],
    dependencies=[Depends(require_api_key)],
)


@router.get("", response_model=PaginatedResponse[CarrierResponse])
async def list_carriers(
    charges_yq: bool | None = Query(None, description="Filter to carriers that charge YQ"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[CarrierResponse]:
    """
    List all carriers, sorted by typical_yq_usd DESC.

    Used by agents to see which carriers charge the most YQ
    and are therefore the best targets for fuel dumps.
    """
    offset = (page - 1) * page_size

    carriers = await get_all_carriers(
        session,
        charges_yq=charges_yq,
        limit=page_size,
        offset=offset,
    )
    total = await count_carriers(session, charges_yq=charges_yq)

    items = [CarrierResponse.model_validate(c) for c in carriers]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{iata_code}", response_model=CarrierResponse)
async def get_carrier(
    iata_code: str,
    session: AsyncSession = Depends(get_db_session),
) -> CarrierResponse:
    """Get a single carrier by its 2-letter IATA code."""
    carrier = await get_carrier_by_iata(session, iata_code)
    if carrier is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Carrier not found: {iata_code.upper()}",
        )
    return CarrierResponse.model_validate(carrier)
