"""
scan_target.py — ScanTarget ORM model.

A scan target is a city pair (+ optional carrier preference) that the
scanner actively monitors. The scanner iterates over all enabled scan
targets, tests them against dump_candidates, and records price deltas
as new or updated DumpPattern rows.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class ScanTarget(TimestampMixin, Base):
    __tablename__ = "scan_targets"
    __table_args__ = (
        UniqueConstraint("origin_iata", "destination_iata", "carrier_iata", name="uq_scan_target"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    origin_iata: Mapped[str] = mapped_column(
        String(3), nullable=False, comment="Origin airport (e.g. YVR, SEA, LHR)"
    )
    destination_iata: Mapped[str] = mapped_column(
        String(3), nullable=False, comment="Destination airport (e.g. LHR, BKK, ICN)"
    )
    carrier_iata: Mapped[str | None] = mapped_column(
        String(2),
        nullable=True,
        comment="Preferred carrier to test — NULL means try all high-YQ carriers",
    )
    tier: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="1=daily, 2=weekly, 3=monthly scan frequency",
    )
    last_scanned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this target was last scanned",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Set to false to pause scanning this target",
    )

    def __repr__(self) -> str:
        carrier = self.carrier_iata or "any"
        return (
            f"<ScanTarget {self.origin_iata}→{self.destination_iata} "
            f"carrier={carrier} tier={self.tier} enabled={self.enabled}>"
        )
