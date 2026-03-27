"""
carrier.py — Pydantic schemas for Carrier CRUD.

Carrier PK is iata_code (String(2)), not a UUID.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Alliance


class CarrierCreate(BaseModel):
    """Input schema for creating a new carrier."""

    iata_code: str = Field(min_length=2, max_length=2, description="2-letter IATA airline code")
    name: str = Field(min_length=1, max_length=100, description="Full airline name")
    alliance: Alliance = Field(default=Alliance.NONE, description="Alliance membership")
    charges_yq: bool | None = Field(default=None, description="Whether carrier typically levies YQ")
    typical_yq_usd: float | None = Field(
        default=None, ge=0, description="Approximate YQ per intercontinental roundtrip in USD"
    )
    yq_scrape_url: str | None = Field(
        default=None, max_length=500, description="URL for scraping current YQ schedule"
    )


class CarrierUpdate(BaseModel):
    """Input schema for updating a carrier. All fields optional."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    alliance: Alliance | None = None
    charges_yq: bool | None = None
    typical_yq_usd: float | None = Field(default=None, ge=0)
    last_yq_updated: datetime | None = None
    yq_scrape_url: str | None = Field(default=None, max_length=500)


class CarrierResponse(BaseModel):
    """Full carrier response — used in detail views and carrier list."""

    model_config = ConfigDict(from_attributes=True)

    iata_code: str
    name: str
    alliance: str
    charges_yq: bool | None
    typical_yq_usd: float | None
    last_yq_updated: datetime | None
    yq_scrape_url: str | None
    created_at: datetime
    updated_at: datetime
