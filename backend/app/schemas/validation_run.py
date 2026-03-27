"""
validation_run.py — Pydantic schemas for ValidationRun.

ValidationRuns are the audit trail of every ITA Matrix test.
manual_input_snapshot is immutable — it preserves the exact bundle
that was tested, even if the pattern's bundle changes later.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.manual_input import ManualInputBundle


class ValidationRunCreate(BaseModel):
    """Input schema for recording a new validation run."""

    pattern_id: uuid.UUID = Field(description="UUID of the pattern being validated")
    success: bool = Field(description="Whether the dump successfully eliminated YQ")
    yq_charged_usd: float | None = Field(
        default=None, ge=0, description="Actual YQ returned by ITA Matrix on this run"
    )
    yq_expected_usd: float | None = Field(
        default=None, ge=0, description="Expected YQ from carrier data"
    )
    base_fare_usd: float | None = Field(
        default=None, ge=0, description="Base fare returned by ITA Matrix (informational)"
    )
    raw_ita_response: dict[str, Any] | None = Field(
        default=None, description="Full parsed fare breakdown from ITA Matrix"
    )
    manual_input_snapshot: ManualInputBundle | None = Field(
        default=None,
        description="IMMUTABLE: manual input bundle as-of this run for agent replay",
    )
    error_message: str | None = Field(
        default=None, description="Error details if automation failed"
    )
    proxy_used: str | None = Field(
        default=None, max_length=200, description="Which proxy was used for this run"
    )


class ValidationRunResponse(BaseModel):
    """Full validation run response — used in history views."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pattern_id: uuid.UUID
    ran_at: datetime
    success: bool
    yq_charged_usd: float | None
    yq_expected_usd: float | None
    base_fare_usd: float | None
    raw_ita_response: dict[str, Any] | None
    manual_input_snapshot: dict[str, Any] | None
    error_message: str | None
    proxy_used: str | None
