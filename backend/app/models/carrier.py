"""
carrier.py — Carrier ORM model.

Tracks every airline relevant to the system.
Primary key is the 2-letter IATA code (e.g. "LH", "QR", "AA").
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import Alliance


class Carrier(Base):
    __tablename__ = "carriers"

    iata_code: Mapped[str] = mapped_column(
        String(2), primary_key=True, comment="2-letter IATA airline code"
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Full airline name"
    )
    alliance: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=Alliance.NONE.value,
        comment="Alliance: STAR, ONEWORLD, SKYTEAM, or NONE",
    )
    charges_yq: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Whether this carrier typically levies YQ. null = unknown",
    )
    typical_yq_usd: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Approximate YQ per intercontinental roundtrip in USD",
    )
    last_yq_updated: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When YQ data was last scraped/updated",
    )
    yq_scrape_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="URL used to scrape current YQ schedule",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Carrier {self.iata_code} ({self.name})>"
