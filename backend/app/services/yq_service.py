"""
yq_service.py — YQ data service layer.

Wraps YQ scraping operations and database writes.
Called by Celery tasks (Phase 08) and API endpoints (Phase 09).

Key functions:
- update_carrier_yq: scrape + store + update carrier record
- get_highest_yq_carriers: sorted list for agent prioritization
- get_current_yq: latest known YQ for a carrier/route
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.carrier import Carrier
from app.models.route import Route
from app.models.yq_schedule import YQSchedule

logger = logging.getLogger(__name__)


@dataclass
class CarrierYQSummary:
    """Summary of a carrier's YQ profile for agent-facing views."""

    iata_code: str
    name: str
    alliance: str
    charges_yq: bool | None
    typical_yq_usd: float | None
    last_yq_updated: datetime | None
    route_count: int = 0


async def store_yq_result(
    session: AsyncSession,
    carrier_iata: str,
    origin: str,
    destination: str,
    yq_amount_usd: float,
    source_url: str = "",
) -> None:
    """
    Store a single YQ scrape result in yq_schedules.

    Also ensures the route exists (creates if not).
    """
    # Find or create route
    route = await _get_or_create_route(session, origin, destination)

    yq_record = YQSchedule(
        carrier_iata=carrier_iata,
        route_id=route.id,
        yq_amount_usd=yq_amount_usd,
        effective_date=date.today(),
        source_url=source_url,
    )
    session.add(yq_record)


async def update_carrier_typical_yq(
    session: AsyncSession,
    carrier_iata: str,
    typical_yq_usd: float,
) -> None:
    """
    Update a carrier's typical_yq_usd and last_yq_updated timestamp.
    """
    stmt = (
        update(Carrier)
        .where(Carrier.iata_code == carrier_iata)
        .values(
            typical_yq_usd=typical_yq_usd,
            last_yq_updated=datetime.now(timezone.utc),
        )
    )
    await session.execute(stmt)


async def get_highest_yq_carriers(
    session: AsyncSession,
    limit: int = 10,
) -> list[CarrierYQSummary]:
    """
    Get carriers sorted by typical_yq_usd DESC.

    Used by agents to prioritize which routes to research for dumps.
    """
    stmt = (
        select(Carrier)
        .where(Carrier.charges_yq == True)  # noqa: E712
        .where(Carrier.typical_yq_usd.is_not(None))
        .order_by(Carrier.typical_yq_usd.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    carriers = result.scalars().all()

    return [
        CarrierYQSummary(
            iata_code=c.iata_code,
            name=c.name,
            alliance=c.alliance,
            charges_yq=c.charges_yq,
            typical_yq_usd=c.typical_yq_usd,
            last_yq_updated=c.last_yq_updated,
        )
        for c in carriers
    ]


async def get_current_yq(
    session: AsyncSession,
    carrier_iata: str,
    origin: str,
    destination: str,
) -> float | None:
    """
    Get the most recent YQ amount for a carrier on a specific route.

    Falls back to carrier-level typical_yq_usd if no route-specific data.
    """
    # Try route-specific first
    route_stmt = select(Route).where(
        Route.origin_iata == origin,
        Route.destination_iata == destination,
    )
    route_result = await session.execute(route_stmt)
    route = route_result.scalar_one_or_none()

    if route:
        yq_stmt = (
            select(YQSchedule)
            .where(
                YQSchedule.carrier_iata == carrier_iata,
                YQSchedule.route_id == route.id,
            )
            .order_by(YQSchedule.scraped_at.desc())
            .limit(1)
        )
        yq_result = await session.execute(yq_stmt)
        yq = yq_result.scalar_one_or_none()
        if yq:
            return yq.yq_amount_usd

    # Fall back to carrier typical
    carrier_stmt = select(Carrier).where(Carrier.iata_code == carrier_iata)
    carrier_result = await session.execute(carrier_stmt)
    carrier = carrier_result.scalar_one_or_none()
    if carrier and carrier.typical_yq_usd is not None:
        return carrier.typical_yq_usd

    return None


async def _get_or_create_route(
    session: AsyncSession,
    origin: str,
    destination: str,
) -> Route:
    """Get existing route or create a new one."""
    stmt = select(Route).where(
        Route.origin_iata == origin,
        Route.destination_iata == destination,
    )
    result = await session.execute(stmt)
    route = result.scalar_one_or_none()

    if route is None:
        route = Route(
            origin_iata=origin,
            destination_iata=destination,
            is_intercontinental=True,  # Default for YQ-relevant routes
        )
        session.add(route)
        await session.flush()  # Populate route.id

    return route
