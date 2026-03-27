"""
dump_candidate.py — Pydantic schemas for DumpCandidate CRUD.

A dump candidate is a short-haul segment injected into multi-city itineraries
to disrupt YQ calculation.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DumpCandidateCreate(BaseModel):
    """Input schema for creating a new dump candidate."""

    from_iata: str = Field(
        min_length=3, max_length=3, description="Origin of the short-haul dump segment"
    )
    to_iata: str = Field(
        min_length=3, max_length=3, description="Destination of the short-haul dump segment"
    )
    carrier_iata: str | None = Field(
        default=None,
        min_length=2,
        max_length=2,
        description="Preferred carrier — NULL means leave loose (best practice for dumps)",
    )
    notes: str | None = Field(
        default=None,
        description="Why this segment works as a dump — pricing zone, alliance quirk, etc.",
    )
    enabled: bool = Field(default=True, description="Whether this candidate is active")


class DumpCandidateUpdate(BaseModel):
    """Input schema for updating a dump candidate. All fields optional."""

    carrier_iata: str | None = Field(default=None, min_length=2, max_length=2)
    notes: str | None = None
    enabled: bool | None = None


class DumpCandidateResponse(BaseModel):
    """Full dump candidate response, includes success tracking stats."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_iata: str
    to_iata: str
    carrier_iata: str | None
    notes: str | None
    success_count: int
    test_count: int
    success_rate: float | None  # computed property on the ORM model
    enabled: bool
    created_at: datetime
    updated_at: datetime
