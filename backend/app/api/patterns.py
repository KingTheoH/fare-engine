"""
patterns.py — Dump pattern endpoints.

GET  /api/v1/patterns            — leaderboard (filterable, paginated)
GET  /api/v1/patterns/{id}       — full pattern detail + manual_input_bundle
POST /api/v1/patterns/{id}/resurrect — revive a deprecated pattern
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db_session, require_api_key
from app.db.repositories import pattern_repository
from app.models.enums import DumpType, LifecycleState
from app.schemas.common import PaginatedResponse
from app.schemas.dump_pattern import DumpPatternResponse, DumpPatternSummary
from app.services import pattern_service

router = APIRouter(
    prefix="/api/v1/patterns",
    tags=["patterns"],
    dependencies=[Depends(require_api_key)],
)


@router.get("", response_model=PaginatedResponse[DumpPatternSummary])
async def list_patterns(
    origin: str | None = Query(None, min_length=3, max_length=3, description="Filter by origin IATA"),
    destination: str | None = Query(None, min_length=3, max_length=3, description="Filter by destination IATA"),
    dump_type: str | None = Query(None, description="Filter by dump type"),
    carrier: str | None = Query(None, min_length=2, max_length=2, description="Filter by ticketing carrier"),
    min_confidence: float | None = Query(None, ge=0.0, le=1.0, description="Minimum confidence score"),
    min_savings_usd: float | None = Query(None, ge=0, description="Minimum expected YQ savings"),
    include_discovered: bool = Query(False, description="Include unvalidated discovered patterns"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[DumpPatternSummary]:
    """
    Get paginated leaderboard of dump patterns.

    By default returns active + degrading patterns. Set include_discovered=true
    to also show unvalidated patterns that agents can manually test.

    Sorted by confidence_score DESC.
    """
    offset = (page - 1) * page_size

    patterns = await pattern_repository.get_active_patterns(
        session,
        dump_type=dump_type,
        origin=origin,
        destination=destination,
        carrier=carrier,
        include_discovered=include_discovered,
        limit=page_size,
        offset=offset,
    )

    # Post-filter by confidence and savings (could be pushed to repo)
    filtered = patterns
    if min_confidence is not None:
        filtered = [p for p in filtered if p.confidence_score >= min_confidence]
    if min_savings_usd is not None:
        filtered = [
            p for p in filtered
            if p.expected_yq_savings_usd is not None
            and p.expected_yq_savings_usd >= min_savings_usd
        ]

    items = [DumpPatternSummary.model_validate(p) for p in filtered]

    return PaginatedResponse(
        items=items,
        total=len(items),
        page=page,
        page_size=page_size,
    )


@router.get("/{pattern_id}", response_model=DumpPatternResponse)
async def get_pattern(
    pattern_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> DumpPatternResponse:
    """Get full detail for a single pattern, including manual_input_bundle."""
    pattern = await pattern_repository.get_pattern_by_id(session, pattern_id)
    if pattern is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern not found: {pattern_id}",
        )
    return DumpPatternResponse.model_validate(pattern)


@router.get("/{pattern_id}/manual-input")
async def get_manual_input(
    pattern_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Get the ManualInputBundle for a specific pattern.

    Returns the stored manual_input_bundle if available (from a successful
    validation). Otherwise, generates one on-the-fly from the pattern's
    routing data so agents can manually test even unvalidated patterns.
    """
    pattern = await pattern_repository.get_pattern_by_id(session, pattern_id)
    if pattern is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pattern not found: {pattern_id}",
        )

    # Return stored bundle if available (validated patterns)
    if pattern.manual_input_bundle is not None:
        return pattern.manual_input_bundle

    # Generate a provisional bundle from pattern data so agents can
    # manually test unvalidated patterns in ITA Matrix
    return _build_provisional_manual_input(pattern)


def _build_provisional_manual_input(pattern) -> dict:
    """
    Build a provisional manual input bundle from a pattern that hasn't
    been validated yet. Uses whatever routing data is available.

    Marked as provisional so agents know this hasn't been confirmed working.
    """
    routing = (
        pattern.optimized_routing
        or pattern.baseline_routing
        or pattern.ita_routing_code
        or ""
    )

    # Build human-readable route description
    carriers = pattern.operating_carriers or []
    points = pattern.routing_points or []
    carrier_str = "/".join(carriers) if carriers else pattern.ticketing_carrier_iata
    points_str = " via " + ",".join(points) if points else ""
    description = (
        f"{pattern.origin_iata} → {pattern.destination_iata} "
        f"({carrier_str}){points_str}. "
        f"Dump type: {pattern.dump_type}."
    )

    segments = pattern.multi_city_segments or []
    dump_seg = pattern.dump_segment

    bundle: dict = {
        "routing_code_string": routing,
        "human_description": description,
        "expected_yq_savings_usd": pattern.expected_yq_savings_usd,
        "confidence_score": pattern.confidence_score,
        "validation_timestamp": None,  # not yet validated
        "provisional": True,  # flag: this hasn't been confirmed by automation
        "origin_iata": pattern.origin_iata,
        "destination_iata": pattern.destination_iata,
        "ticketing_carrier_iata": pattern.ticketing_carrier_iata,
        "fare_basis_hint": pattern.fare_basis_hint,
    }

    if segments:
        bundle["multi_city_segments"] = segments
    if dump_seg:
        bundle["dump_segment"] = dump_seg
    if pattern.baseline_routing:
        bundle["baseline_routing"] = pattern.baseline_routing
    if pattern.optimized_routing:
        bundle["optimized_routing"] = pattern.optimized_routing

    if routing:
        bundle["ita_matrix_steps"] = [
            "1. Go to matrix.itasoftware.com",
            f"2. Set up a multi-city search: {pattern.origin_iata} → {pattern.destination_iata}",
            f"3. Open 'Routing Codes' → paste: {routing}",
            "4. Click Search",
            "⚠️ This is a PROVISIONAL bundle — pattern has not been validated yet.",
        ]
    else:
        bundle["ita_matrix_steps"] = [
            "⚠️ No routing code available yet. Pattern needs manual routing setup.",
        ]

    return bundle


@router.post("/{pattern_id}/resurrect")
async def resurrect_pattern(
    pattern_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """
    Resurrect a deprecated pattern back to discovered state.

    This re-enters the pattern into the validation queue so it gets
    another chance. Useful when infrastructure issues caused false
    deprecation, or when market conditions have changed.

    Only deprecated patterns can be resurrected.
    """
    transition = await pattern_service.resurrect_pattern(session, pattern_id)

    if not transition.transitioned:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=transition.reason,
        )

    return {
        "pattern_id": str(pattern_id),
        "old_state": transition.old_state,
        "new_state": transition.new_state,
        "reason": transition.reason,
    }
