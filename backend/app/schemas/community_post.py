"""
community_post.py — Pydantic schemas for CommunityPost.

Raw community data before and after LLM extraction.
ExtractedPattern represents a single pattern pulled from a post by the LLM.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DumpType, PatternSource, ProcessingState


class ExtractedPattern(BaseModel):
    """
    A single dump pattern extracted from a community post by the LLM.

    This is the structured output of the LLM extraction pipeline (Phase 06).
    Stored in community_posts.extracted_patterns as a JSON array.
    """

    dump_type: DumpType = Field(description="Classified dump type")
    origin_iata: str = Field(min_length=3, max_length=3, description="Origin airport")
    destination_iata: str = Field(min_length=3, max_length=3, description="Destination airport")
    ticketing_carrier_iata: str = Field(
        min_length=2, max_length=2, description="Ticketing carrier"
    )
    operating_carriers: list[str] = Field(description="Operating carrier codes in order")
    routing_points: list[str] = Field(
        default=[], description="Via/TP points in order"
    )
    fare_basis_hint: str | None = Field(
        default=None, description="Fare basis code if mentioned"
    )
    estimated_yq_savings_usd: float | None = Field(
        default=None, ge=0, description="Estimated savings if mentioned in post"
    )
    confidence_note: str | None = Field(
        default=None, description="LLM's note on extraction confidence"
    )


class CommunityPostCreate(BaseModel):
    """Input schema for submitting a community post for ingestion."""

    source: PatternSource = Field(
        default=PatternSource.FLYERTALK, description="Source platform"
    )
    post_url: str = Field(
        min_length=1, max_length=500, description="Direct URL to the forum post"
    )
    post_author: str | None = Field(
        default=None, max_length=100, description="Forum username (for dedup only)"
    )
    author_post_count: int | None = Field(
        default=None, ge=0, description="Author's total post count"
    )
    author_account_age_days: int | None = Field(
        default=None, ge=0, description="Days since author's account creation"
    )
    raw_text: str = Field(min_length=1, description="Raw post text content (HTML stripped)")
    posted_at: datetime | None = Field(
        default=None, description="When the original post was published"
    )


class CommunityPostResponse(BaseModel):
    """Full community post response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    post_url: str
    post_author: str | None
    author_post_count: int | None
    author_account_age_days: int | None
    raw_text: str
    extracted_patterns: list[dict[str, Any]] | None
    processing_state: str
    posted_at: datetime | None
    scraped_at: datetime
