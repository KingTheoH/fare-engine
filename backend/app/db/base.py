"""
base.py — SQLAlchemy declarative base and shared mixin.

All ORM models import Base from here. Never create a second Base elsewhere.
TimestampMixin provides created_at/updated_at on any model that needs it.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Single shared declarative base for all ORM models.
    Alembic's env.py imports this to discover all tables for migrations.
    """
    pass


class TimestampMixin:
    """
    Adds created_at and updated_at columns.
    updated_at is set on INSERT and refreshed on every UPDATE via onupdate.
    Use on any table that benefits from audit timestamps.
    """
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
