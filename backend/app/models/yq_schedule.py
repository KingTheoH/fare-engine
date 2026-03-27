"""
yq_schedule.py — YQSchedule ORM model.

Point-in-time snapshots of what a carrier charges for YQ on specific routes.
Each row is a single scrape result — they accumulate over time to form
a history of YQ changes per carrier/route.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class YQSchedule(Base):
    __tablename__ = "yq_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    carrier_iata: Mapped[str] = mapped_column(
        String(2),
        ForeignKey("carriers.iata_code", ondelete="CASCADE"),
        nullable=False,
        comment="2-letter IATA carrier code",
    )
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("routes.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK to the route this YQ applies to",
    )
    yq_amount_usd: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="YQ amount in USD for this carrier on this route",
    )
    effective_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Date this YQ amount is effective",
    )
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When this data point was scraped",
    )
    source_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="URL the YQ data was scraped from",
    )

    def __repr__(self) -> str:
        return (
            f"<YQSchedule {self.carrier_iata} ${self.yq_amount_usd} "
            f"effective={self.effective_date}>"
        )
