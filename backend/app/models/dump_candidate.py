"""
dump_candidate.py — DumpCandidate ORM model.

A dump candidate is a short-haul flight segment that can be injected
into a multi-city itinerary to disrupt YQ calculation. The scanner
tests each scan_target against all enabled dump_candidates to find
price deltas.

Good dump candidates are:
- Short-haul (< 2h flight time)
- In a different fare pricing zone than the main route
- Loose (no carrier/connection/timing forced) → more likely to apply
- Cheap standalone (don't add significant cost when injected)

The success_count/test_count ratio is the empirical dump rate.
"""

import uuid

from sqlalchemy import Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class DumpCandidate(TimestampMixin, Base):
    __tablename__ = "dump_candidates"
    __table_args__ = (
        UniqueConstraint("from_iata", "to_iata", "carrier_iata", name="uq_dump_candidate"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    from_iata: Mapped[str] = mapped_column(
        String(3), nullable=False, comment="Origin of the short-haul dump segment"
    )
    to_iata: Mapped[str] = mapped_column(
        String(3), nullable=False, comment="Destination of the short-haul dump segment"
    )
    carrier_iata: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
        comment="Preferred carrier — NULL means leave loose (best practice for dumps)",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Why this segment works as a dump — pricing zone, alliance quirk, etc.",
    )

    # Scanner tracks success rate per candidate
    success_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times this segment produced a measurable price delta",
    )
    test_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of times this candidate was tested by the scanner",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Set to false to exclude from scanner runs",
    )

    @property
    def success_rate(self) -> float | None:
        """Empirical dump success rate (0.0–1.0). None if never tested."""
        if self.test_count == 0:
            return None
        return self.success_count / self.test_count

    def __repr__(self) -> str:
        carrier = self.carrier_iata or "loose"
        return (
            f"<DumpCandidate {self.from_iata}→{self.to_iata} "
            f"carrier={carrier} success={self.success_count}/{self.test_count}>"
        )
