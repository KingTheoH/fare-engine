"""
route.py — Pydantic schemas for Route CRUD.

Routes are canonical origin-destination pairs.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RouteCreate(BaseModel):
    """Input schema for creating a new route."""

    origin_iata: str = Field(
        min_length=3, max_length=3, description="3-letter IATA origin airport code"
    )
    destination_iata: str = Field(
        min_length=3, max_length=3, description="3-letter IATA destination airport code"
    )
    is_intercontinental: bool = Field(
        default=False, description="Whether route crosses continents"
    )


class RouteResponse(BaseModel):
    """Full route response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    origin_iata: str
    destination_iata: str
    is_intercontinental: bool
    created_at: datetime
