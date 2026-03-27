"""
ingestion_service.py — Community data ingestion orchestration.

Coordinates the full pipeline:
1. FlyerTalk scraping → raw posts
2. Post credibility scoring
3. LLM extraction (two-pass: haiku filter → sonnet extract)
4. Pattern normalization → validated DB-ready records
5. Storage: community_posts (JSON copy) + dump_patterns (live records)

Key functions:
- ingest_post: Process a single raw post through the LLM pipeline
- process_raw_posts: Batch-process unprocessed community_posts
- submit_url: Scrape a single URL and ingest all posts found
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community_post import CommunityPost
from app.models.enums import ProcessingState

logger = logging.getLogger(__name__)


# ─── Result types ──────────────────────────────────────────────────────────

@dataclass
class PostIngestionResult:
    """Result of processing a single post through the LLM pipeline."""

    post_url: str = ""
    passed_filter: bool = False
    patterns_extracted: int = 0
    patterns_normalized: int = 0
    patterns_stored: int = 0
    patterns_skipped_duplicate: int = 0
    credibility_score: float = 0.0
    rejection_summary: dict[str, int] = field(default_factory=dict)
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class BatchIngestionResult:
    """Result of batch-processing multiple posts."""

    total_posts: int = 0
    posts_filtered_in: int = 0
    posts_filtered_out: int = 0
    posts_errored: int = 0
    total_patterns_extracted: int = 0
    total_patterns_normalized: int = 0
    total_patterns_stored: int = 0
    total_patterns_skipped_duplicate: int = 0
    results: list[PostIngestionResult] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "total_posts": self.total_posts,
            "posts_filtered_in": self.posts_filtered_in,
            "posts_filtered_out": self.posts_filtered_out,
            "posts_errored": self.posts_errored,
            "total_patterns_extracted": self.total_patterns_extracted,
            "total_patterns_normalized": self.total_patterns_normalized,
            "total_patterns_stored": self.total_patterns_stored,
            "total_patterns_skipped_duplicate": self.total_patterns_skipped_duplicate,
        }


# ─── Core service functions ───────────────────────────────────────────────

async def ingest_post(
    session: AsyncSession,
    post_text: str,
    post_url: str,
    llm_extractor: Any,
    author_post_count: int | None = None,
    author_account_age_days: int | None = None,
    posted_at: datetime | None = None,
) -> PostIngestionResult:
    """
    Process a single post through the full ingestion pipeline.

    1. Score post credibility
    2. Run LLM two-pass extraction
    3. Normalize extracted patterns (hard-validate IATA codes, YQ savings, staleness)
    4. Insert valid patterns into dump_patterns table (dedup by routing code)
    5. Store JSON copy on community_post record

    Args:
        session: Database session.
        post_text: Raw text content of the post.
        post_url: URL of the post (for dedup + source tracking).
        llm_extractor: LLMExtractor instance (or mock for testing).
        author_post_count: Author's total post count.
        author_account_age_days: Days since author's account creation.
        posted_at: When the post was published.

    Returns:
        PostIngestionResult with extraction stats.
    """
    from app.services import pattern_service
    from ingestion.extractors.pattern_normalizer import normalize_all
    from ingestion.weighting.post_credibility import score_from_community_post

    result = PostIngestionResult(post_url=post_url)

    try:
        # Step 1: Score credibility
        credibility = score_from_community_post(
            post_author_count=author_post_count,
            post_author_age_days=author_account_age_days,
            posted_at=posted_at,
        )
        result.credibility_score = credibility

        # Step 2: LLM two-pass extraction
        process_result = await llm_extractor.process_post(post_text)

        if process_result.error:
            result.error = process_result.error
            await _mark_post_state(session, post_url, ProcessingState.FAILED)
            return result

        if not process_result.passed_filter:
            result.passed_filter = False
            await _mark_post_state(session, post_url, ProcessingState.PROCESSED)
            return result

        result.passed_filter = True

        # Step 3: Normalize extracted patterns
        if process_result.extraction_result and process_result.extraction_result.patterns:
            # Calculate post age for staleness check
            post_age_days: int | None = None
            if posted_at is not None:
                now = datetime.now(timezone.utc)
                post_dt = posted_at if posted_at.tzinfo else posted_at.replace(tzinfo=timezone.utc)
                post_age_days = (now - post_dt).days

            normalization = normalize_all(
                process_result.extraction_result.patterns,
                source_url=post_url,
                source_post_weight=credibility,
                post_age_days=post_age_days,
            )
            result.patterns_extracted = process_result.total_patterns
            result.patterns_normalized = normalization.valid_count
            result.rejection_summary = normalization.rejection_summary

            # Step 4: Insert validated patterns into dump_patterns
            stored_dicts = []
            for norm_pattern in normalization.patterns:
                if not norm_pattern.is_valid:
                    continue

                merge = await pattern_service.merge_community_pattern(
                    session, norm_pattern.data
                )
                if merge.created:
                    result.patterns_stored += 1
                    stored_dicts.append(norm_pattern.data)
                else:
                    result.patterns_skipped_duplicate += 1
                    stored_dicts.append(norm_pattern.data)  # Still record in post JSON

            # Step 5: Store JSON copy on community_post (all valid patterns, new or existing)
            if stored_dicts:
                await _store_extracted_patterns(session, post_url, stored_dicts)

            if normalization.rejection_summary:
                logger.info(
                    "Post %s: %d extracted, %d normalized, %d stored, %d duplicate, rejections=%s",
                    post_url[:60],
                    result.patterns_extracted,
                    result.patterns_normalized,
                    result.patterns_stored,
                    result.patterns_skipped_duplicate,
                    normalization.rejection_summary,
                )

        await _mark_post_state(session, post_url, ProcessingState.PROCESSED)
        return result

    except Exception as e:
        logger.error("Error ingesting post %s: %s", post_url, e, exc_info=True)
        result.error = f"Ingestion error: {str(e)}"
        await _mark_post_state(session, post_url, ProcessingState.FAILED)
        return result


async def process_raw_posts(
    session: AsyncSession,
    llm_extractor: Any,
    limit: int = 50,
) -> BatchIngestionResult:
    """
    Process unprocessed community_posts through the LLM pipeline.

    Fetches posts with processing_state='raw' and processes them sequentially.

    Args:
        session: Database session.
        llm_extractor: LLMExtractor instance.
        limit: Max posts to process in this batch.

    Returns:
        BatchIngestionResult with aggregated stats.
    """
    batch_result = BatchIngestionResult()

    # Fetch unprocessed posts
    stmt = (
        select(CommunityPost)
        .where(CommunityPost.processing_state == ProcessingState.RAW.value)
        .order_by(CommunityPost.scraped_at.desc())
        .limit(limit)
    )
    db_result = await session.execute(stmt)
    posts = db_result.scalars().all()
    batch_result.total_posts = len(posts)

    for post in posts:
        result = await ingest_post(
            session=session,
            post_text=post.raw_text,
            post_url=post.post_url,
            llm_extractor=llm_extractor,
            author_post_count=post.author_post_count,
            author_account_age_days=post.author_account_age_days,
            posted_at=post.posted_at,
        )

        batch_result.results.append(result)

        if result.error:
            batch_result.posts_errored += 1
        elif result.passed_filter:
            batch_result.posts_filtered_in += 1
            batch_result.total_patterns_extracted += result.patterns_extracted
            batch_result.total_patterns_normalized += result.patterns_normalized
            batch_result.total_patterns_stored += result.patterns_stored
            batch_result.total_patterns_skipped_duplicate += result.patterns_skipped_duplicate
        else:
            batch_result.posts_filtered_out += 1

    logger.info(
        "Batch ingestion complete: %d posts, %d filtered in, %d patterns stored (%d duplicates skipped)",
        batch_result.total_posts,
        batch_result.posts_filtered_in,
        batch_result.total_patterns_stored,
        batch_result.total_patterns_skipped_duplicate,
    )

    return batch_result


async def store_scraped_post(
    session: AsyncSession,
    post_url: str,
    raw_text: str,
    post_author: str | None = None,
    author_post_count: int | None = None,
    author_account_age_days: int | None = None,
    posted_at: datetime | None = None,
    source: str = "FLYERTALK",
) -> CommunityPost | None:
    """
    Store a scraped post in community_posts table.

    Deduplicates by post_url. Returns None if the post already exists.
    """
    # Check for existing
    existing = await session.execute(
        select(CommunityPost).where(CommunityPost.post_url == post_url)
    )
    if existing.scalar_one_or_none():
        logger.debug("Post already exists: %s", post_url)
        return None

    post = CommunityPost(
        source=source,
        post_url=post_url,
        post_author=post_author,
        author_post_count=author_post_count,
        author_account_age_days=author_account_age_days,
        raw_text=raw_text,
        posted_at=posted_at,
        processing_state=ProcessingState.RAW.value,
    )
    session.add(post)
    return post


# ─── Helper functions ──────────────────────────────────────────────────────

async def _mark_post_state(
    session: AsyncSession,
    post_url: str,
    state: ProcessingState,
) -> None:
    """Update the processing_state of a community post."""
    try:
        stmt = (
            update(CommunityPost)
            .where(CommunityPost.post_url == post_url)
            .values(processing_state=state.value)
        )
        await session.execute(stmt)
    except Exception as e:
        logger.error("Failed to update post state for %s: %s", post_url, e)


async def _store_extracted_patterns(
    session: AsyncSession,
    post_url: str,
    patterns: list[dict[str, Any]],
) -> None:
    """Store extracted pattern dicts as JSON on the community_post record."""
    try:
        stmt = (
            update(CommunityPost)
            .where(CommunityPost.post_url == post_url)
            .values(extracted_patterns=patterns)
        )
        await session.execute(stmt)
    except Exception as e:
        logger.error("Failed to store patterns for %s: %s", post_url, e)
