"""
yq_schedule.py — Pydantic schemas for YQSchedule.

Point-in-time snapshots of carrier YQ amounts on specific routes.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class YQScheduleCreate(BaseModel):
    """Input schema for recording a new YQ scrape result."""

    carrier_iata: str = Field(
        min_length=2, max_length=2, description="2-letter IATA carrier code"
    )
    route_id: uuid.UUID = Field(description="UUID of the route this YQ applies to")
    yq_amount_usd: float = Field(ge=0, description="YQ amount in USD")
    effective_date: date = Field(description="Date this YQ amount is effective")
    source_url: str | None = Field(
        default=None, max_length=500, description="URL the YQ data was scraped from"
    )


class YQScheduleResponse(BaseModel):
    """Full YQ schedule response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    carrier_iata: str
    route_id: uuid.UUID
    yq_amount_usd: float
    effective_date: date
    scraped_at: datetime
    source_url: str | None
