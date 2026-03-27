"""
dump_pattern.py — DumpPattern ORM model.

The core entity. One row = one known fuel dump fare construction.
This is the most important table in the system.

Key relationships:
- Has many ValidationRuns (audit trail)
- Optional self-FK to backup_pattern (alternate routing)
- References carriers via iata codes (no FK — carriers may be added lazily)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import DumpType, FreshnessTier, LifecycleState, PatternSource


class DumpPattern(TimestampMixin, Base):
    __tablename__ = "dump_patterns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # --- Classification ---
    dump_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="TP_DUMP, CARRIER_SWITCH, FARE_BASIS, or ALLIANCE_RULE",
    )
    lifecycle_state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=LifecycleState.DISCOVERED.value,
        comment="discovered, active, degrading, deprecated, archived",
    )

    # --- Route ---
    origin_iata: Mapped[str] = mapped_column(
        String(3), nullable=False, comment="3-letter IATA origin airport"
    )
    destination_iata: Mapped[str] = mapped_column(
        String(3), nullable=False, comment="3-letter IATA destination airport"
    )

    # --- Carrier Info ---
    ticketing_carrier_iata: Mapped[str] = mapped_column(
        String(2), nullable=False, comment="Carrier the ticket is issued on"
    )
    operating_carriers: Mapped[list[str]] = mapped_column(
        ARRAY(String(2)),
        nullable=False,
        comment="Ordered sequence of operating carrier IATA codes",
    )
    routing_points: Mapped[list[str]] = mapped_column(
        ARRAY(String(3)),
        nullable=False,
        default=[],
        comment="Via/TP points in order (IATA airport codes)",
    )

    # --- Fare Construction ---
    fare_basis_hint: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Known fare basis code pattern that triggers the dump",
    )
    ita_routing_code: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        unique=True,
        comment="Legacy single routing code (nullable — new patterns use baseline/optimized_routing)",
    )
    manual_input_bundle: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="1:1 manual input package — populated after first successful validation",
    )

    # --- Scan Engine Fields ---
    baseline_routing: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="ITA Matrix routing code for the baseline query (no dump segment injected)",
    )
    optimized_routing: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="ITA Matrix routing code with the dump segment injected",
    )
    multi_city_segments: Mapped[list[dict] | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Ordered list of multi-city legs [{from, to, carrier, notes}]",
    )
    dump_segment: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="The injected short-haul segment that disrupts YQ calculation",
    )
    baseline_price_usd: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Price from ITA Matrix for the baseline routing (no dump)",
    )
    optimized_price_usd: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Price from ITA Matrix with the dump segment injected",
    )
    last_scan_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of the last scanner run that produced a price delta",
    )

    # --- Scoring ---
    expected_yq_savings_usd: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Last known YQ savings per roundtrip in USD",
    )
    confidence_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, comment="0.0–1.0 confidence score"
    )
    freshness_tier: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=FreshnessTier.LOW.value,
        comment="1=daily, 2=weekly, 3=monthly validation",
    )

    # --- Source ---
    source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=PatternSource.MANUAL.value,
        comment="FLYERTALK, MANUAL, or INTERNAL_DISCOVERY",
    )
    source_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Link to original community post"
    )
    source_post_weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
        comment="Community credibility score of source post (0.0–1.0)",
    )

    # --- Backup ---
    backup_pattern_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dump_patterns.id", ondelete="SET NULL"),
        nullable=True,
        comment="Alternate routing pattern if primary fails",
    )

    # --- Relationships ---
    validation_runs: Mapped[list["ValidationRun"]] = relationship(
        "ValidationRun",
        back_populates="pattern",
        order_by="ValidationRun.ran_at.desc()",
        lazy="selectin",
    )
    backup_pattern: Mapped["DumpPattern | None"] = relationship(
        "DumpPattern",
        remote_side="DumpPattern.id",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return (
            f"<DumpPattern {self.origin_iata}→{self.destination_iata} "
            f"via {self.ticketing_carrier_iata} [{self.dump_type}] "
            f"state={self.lifecycle_state}>"
        )


# Avoid circular import — ValidationRun imported at module level by SQLAlchemy
from app.models.validation_run import ValidationRun  # noqa: E402, F401
