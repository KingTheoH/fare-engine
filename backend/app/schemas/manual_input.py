"""
manual_input.py — ManualInputBundle schema.

THE MOST CRITICAL SCHEMA IN THE SYSTEM.

This schema defines the 1:1 manual input package that agents receive
for every validated dump pattern. It must be completely self-contained —
an agent should be able to replicate the fare construction using only
this bundle, with no other context.

This schema must match exactly what ManualInputBundle.tsx renders
on the frontend dashboard.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ManualInputBundle(BaseModel):
    """
    Complete manual input package for a fuel dump fare construction.

    Agents paste the routing_code_string directly into ITA Matrix,
    follow the ita_matrix_steps sequentially, and verify the expected
    YQ savings. If the primary routing fails, they fall back to
    backup_routing_code.
    """

    routing_code_string: str = Field(
        description="Exact string to paste into ITA Matrix 'Routing codes' field"
    )
    human_description: str = Field(
        description=(
            "Plain English route description, e.g. "
            "'JFK → Frankfurt (LH) → Bangkok (LH) // Bangkok → JFK (AA)'"
        )
    )
    ita_matrix_steps: list[str] = Field(
        min_length=1,
        description=(
            "Numbered step-by-step instructions. Must be self-contained — "
            "usable with no prior context. "
            "Example: ['1. Go to matrix.itasoftware.com', '2. Enter JFK as origin...']"
        ),
    )
    expected_yq_savings_usd: float = Field(
        ge=0, description="Expected YQ savings per roundtrip in USD"
    )
    expected_yq_carrier: str = Field(
        min_length=2,
        max_length=2,
        description="2-letter IATA code of the carrier whose YQ is being avoided",
    )
    validation_timestamp: datetime = Field(
        description="When this bundle was last validated against ITA Matrix"
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0, description="Confidence score from 0.0 (unverified) to 1.0 (certain)"
    )
    backup_routing_code: str | None = Field(
        default=None,
        description="Alternate routing code if primary fails (e.g. use LX instead of LH)",
    )
    notes: str | None = Field(
        default=None,
        description="Free text: fare class hints, caveats, known booking windows",
    )
