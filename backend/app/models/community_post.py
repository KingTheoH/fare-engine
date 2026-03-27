"""
community_post.py — CommunityPost ORM model.

Raw community data before pattern extraction. Posts from FlyerTalk
and other forums are stored here first, then processed through the
LLM extraction pipeline (Phase 06).

Privacy note: we store post_author for deduplication only.
Never expose usernames in the dashboard.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import PatternSource, ProcessingState


class CommunityPost(Base):
    __tablename__ = "community_posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default=PatternSource.FLYERTALK.value,
        comment="Source platform: FLYERTALK, MANUAL, etc.",
    )
    post_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
        comment="Direct URL to the forum post (for deduplication)",
    )
    post_author: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Forum username (for dedup only, never display)",
    )
    author_post_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Author's total post count on the forum",
    )
    author_account_age_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Days since author's account creation",
    )
    raw_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Raw post text content (HTML stripped)",
    )
    extracted_patterns: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Array of patterns extracted by LLM (Phase 06 output)",
    )
    processing_state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ProcessingState.RAW.value,
        comment="raw, processed, or failed",
    )
    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the original post was published on the forum",
    )
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When we scraped this post",
    )

    def __repr__(self) -> str:
        return (
            f"<CommunityPost source={self.source} state={self.processing_state} "
            f"url={self.post_url[:50]}...>"
        )
