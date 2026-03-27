"""
validation_run.py — ValidationRun ORM model.

Every time we test a dump pattern against ITA Matrix, a row is created here.
This is the audit trail — validation_runs should NEVER be deleted.

Key design note: manual_input_snapshot is immutable after creation.
Even if the pattern's manual_input_bundle changes later, old validation runs
preserve the exact routing that was tested. Agents can replay specific runs.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pattern_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dump_patterns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to the dump pattern being validated",
    )
    ran_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When this validation was executed",
    )
    success: Mapped[bool] = mapped_column(
        Boolean, nullable=False, comment="Whether the dump successfully eliminated YQ"
    )

    # --- Fare Data ---
    yq_charged_usd: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Actual YQ returned by ITA Matrix on this run",
    )
    yq_expected_usd: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="What we expected the YQ to be (from carrier data)",
    )
    base_fare_usd: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Base fare returned by ITA Matrix (informational)",
    )

    # --- Raw Data ---
    raw_ita_response: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Full parsed fare breakdown from ITA Matrix",
    )
    manual_input_snapshot: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="IMMUTABLE: manual input bundle as-of this run for agent replay",
    )

    # --- Error / Debug ---
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error details if automation failed (timeout, parse error, etc.)",
    )
    proxy_used: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Which proxy was used for this run (debugging rate limits)",
    )

    # --- Relationship ---
    pattern: Mapped["DumpPattern"] = relationship(
        "DumpPattern",
        back_populates="validation_runs",
    )

    def __repr__(self) -> str:
        status = "✓" if self.success else "✗"
        return f"<ValidationRun {status} pattern={self.pattern_id} at={self.ran_at}>"


from app.models.dump_pattern import DumpPattern  # noqa: E402, F401
