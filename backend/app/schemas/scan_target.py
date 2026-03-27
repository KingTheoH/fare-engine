"""
scan_target.py — Pydantic schemas for ScanTarget CRUD.

A scan target is a city pair the scanner actively monitors.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScanTargetCreate(BaseModel):
    """Input schema for creating a new scan target."""

    origin_iata: str = Field(min_length=3, max_length=3, description="3-letter origin airport")
    destination_iata: str = Field(
        min_length=3, max_length=3, description="3-letter destination airport"
    )
    carrier_iata: str | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="Preferred carrier IATA — NULL means test all high-YQ carriers",
    )
    tier: int = Field(
        default=1, ge=1, le=3, description="Scan frequency: 1=daily, 2=weekly, 3=monthly"
    )
    enabled: bool = Field(default=True, description="Whether this target is active")


class ScanTargetUpdate(BaseModel):
    """Input schema for updating a scan target. All fields optional."""

    carrier_iata: str | None = Field(default=None, min_length=2, max_length=2)
    tier: int | None = Field(default=None, ge=1, le=3)
    enabled: bool | None = None


class ScanTargetResponse(BaseModel):
    """Full scan target response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    origin_iata: str
    destination_iata: str
    carrier_iata: str | None
    tier: int
    last_scanned_at: datetime | None
    enabled: bool
    created_at: datetime
    updated_at: datetime
