"""
dump_pattern.py — Pydantic schemas for DumpPattern CRUD.

DumpPatternSummary is used in list views (excludes manual_input_bundle).
DumpPatternResponse is used in detail views (includes manual_input_bundle).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DumpType, FreshnessTier, LifecycleState, PatternSource
from app.schemas.manual_input import ManualInputBundle


class DumpPatternCreate(BaseModel):
    """Input schema for creating a new dump pattern."""

    dump_type: DumpType = Field(description="How the dump eliminates YQ")
    origin_iata: str = Field(min_length=3, max_length=3, description="3-letter origin airport")
    destination_iata: str = Field(
        min_length=3, max_length=3, description="3-letter destination airport"
    )
    ticketing_carrier_iata: str = Field(
        min_length=2, max_length=2, description="Carrier the ticket is issued on"
    )
    operating_carriers: list[str] = Field(
        min_length=1, description="Ordered sequence of operating carrier IATA codes"
    )
    routing_points: list[str] = Field(
        default=[], description="Via/TP points in order (IATA airport codes)"
    )
    fare_basis_hint: str | None = Field(
        default=None, max_length=50, description="Fare basis code pattern that triggers the dump"
    )
    # Legacy single routing code — optional, new patterns use baseline/optimized_routing
    ita_routing_code: str | None = Field(
        default=None, description="Legacy single routing code for ITA Matrix"
    )
    # Scan engine fields
    baseline_routing: str | None = Field(
        default=None, description="ITA Matrix routing code for baseline query (no dump injected)"
    )
    optimized_routing: str | None = Field(
        default=None, description="ITA Matrix routing code with dump segment injected"
    )
    multi_city_segments: list[dict] | None = Field(
        default=None, description="Ordered list of multi-city legs [{from, to, carrier, notes}]"
    )
    dump_segment: dict | None = Field(
        default=None, description="The injected short-haul segment {from, to, carrier, notes}"
    )
    strike_segment: dict | None = Field(
        default=None,
        description="Throwaway segment appended to end of routing to zero YQ {origin, destination, carrier, note}",
    )
    expected_yq_savings_usd: float | None = Field(
        default=None, ge=0, description="Expected YQ savings per roundtrip in USD"
    )
    source: PatternSource = Field(
        default=PatternSource.MANUAL, description="Where the pattern was discovered"
    )
    source_url: str | None = Field(
        default=None, max_length=500, description="Link to original community post"
    )
    source_post_weight: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Community credibility of source post"
    )
    backup_pattern_id: uuid.UUID | None = Field(
        default=None, description="UUID of alternate routing pattern if primary fails"
    )


class DumpPatternUpdate(BaseModel):
    """Input schema for updating a dump pattern. All fields optional."""

    dump_type: DumpType | None = None
    lifecycle_state: LifecycleState | None = None
    origin_iata: str | None = Field(default=None, min_length=3, max_length=3)
    destination_iata: str | None = Field(default=None, min_length=3, max_length=3)
    ticketing_carrier_iata: str | None = Field(default=None, min_length=2, max_length=2)
    operating_carriers: list[str] | None = None
    routing_points: list[str] | None = None
    fare_basis_hint: str | None = Field(default=None, max_length=50)
    ita_routing_code: str | None = None
    manual_input_bundle: ManualInputBundle | None = None
    baseline_routing: str | None = None
    optimized_routing: str | None = None
    multi_city_segments: list[dict] | None = None
    dump_segment: dict | None = None
    strike_segment: dict | None = None
    baseline_price_usd: float | None = Field(default=None, ge=0)
    optimized_price_usd: float | None = Field(default=None, ge=0)
    expected_yq_savings_usd: float | None = Field(default=None, ge=0)
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    freshness_tier: FreshnessTier | None = None
    source_url: str | None = Field(default=None, max_length=500)
    source_post_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    backup_pattern_id: uuid.UUID | None = None


class DumpPatternSummary(BaseModel):
    """
    Lightweight pattern response for list views / leaderboard.

    Excludes manual_input_bundle (too heavy for list responses).
    Used by GET /api/v1/patterns.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dump_type: str
    lifecycle_state: str
    origin_iata: str
    destination_iata: str
    ticketing_carrier_iata: str
    operating_carriers: list[str]
    routing_points: list[str]
    expected_yq_savings_usd: float | None
    # Price delta — the actual measured signal from the scanner
    baseline_price_usd: float | None = None
    optimized_price_usd: float | None = None
    confidence_score: float
    freshness_tier: int
    source: str
    source_url: str | None
    last_scan_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DumpPatternResponse(BaseModel):
    """
    Full pattern response for detail views.

    Includes manual_input_bundle and scan engine fields.
    Used by GET /api/v1/patterns/{id}.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dump_type: str
    lifecycle_state: str
    origin_iata: str
    destination_iata: str
    ticketing_carrier_iata: str
    operating_carriers: list[str]
    routing_points: list[str]
    fare_basis_hint: str | None
    # Legacy — may be None for scanner-generated patterns
    ita_routing_code: str | None
    manual_input_bundle: ManualInputBundle | None
    # Scan engine fields
    baseline_routing: str | None
    optimized_routing: str | None
    multi_city_segments: list[dict] | None
    dump_segment: dict | None
    strike_segment: dict | None
    baseline_price_usd: float | None
    optimized_price_usd: float | None
    last_scan_at: datetime | None
    # Scoring
    expected_yq_savings_usd: float | None
    confidence_score: float
    freshness_tier: int
    # Source
    source: str
    source_url: str | None
    source_post_weight: float
    backup_pattern_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
