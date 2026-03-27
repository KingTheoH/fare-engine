"""
route.py — Route ORM model.

A canonical origin-destination pair. Used as a reference table
for YQ schedules and pattern route searches.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Route(Base):
    __tablename__ = "routes"
    __table_args__ = (
        UniqueConstraint("origin_iata", "destination_iata", name="uq_route_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    origin_iata: Mapped[str] = mapped_column(
        String(3), nullable=False, comment="3-letter IATA airport code"
    )
    destination_iata: Mapped[str] = mapped_column(
        String(3), nullable=False, comment="3-letter IATA airport code"
    )
    is_intercontinental: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="Whether route crosses continents"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Route {self.origin_iata}→{self.destination_iata}>"
