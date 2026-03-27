"""
post_credibility.py — Community post credibility scoring.

Scores FlyerTalk (and other forum) posts on a 0.0–1.0 scale based on:
- Author experience (post count, account age)
- Post recency
- Thread confirmation/deprecation signals

Used to weight community source data when computing pattern confidence scores.

The score formula is defined in ingestion/CLAUDE.md and services/CLAUDE.md.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class PostMetrics:
    """
    Metrics for scoring a community post.

    Can be constructed from a CommunityPost ORM model or raw data.
    """

    author_post_count: int | None = None
    author_account_age_days: int | None = None
    posted_at: datetime | None = None
    reply_confirms_count: int = 0
    reply_deprecates_count: int = 0


def score_post(metrics: PostMetrics, now: datetime | None = None) -> float:
    """
    Calculate credibility score for a community post.

    Returns a float between 0.0 and 1.0.

    Scoring breakdown:
    - Baseline: 0.50
    - Author post count: up to +0.15
    - Author account age: up to +0.10
    - Recency: up to +0.15 / down to -0.25
    - Thread confirmations: up to +0.10
    - Thread deprecations: down to -0.20

    Args:
        metrics: Post metrics to score.
        now: Current time (for recency calculation). Defaults to UTC now.

    Returns:
        Float 0.0–1.0.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    score = 0.50  # Baseline

    # ─── Author experience ─────────────────────────────────────────
    if metrics.author_post_count is not None:
        if metrics.author_post_count > 1000:
            score += 0.15
        elif metrics.author_post_count > 200:
            score += 0.08
        elif metrics.author_post_count > 50:
            score += 0.03

    if metrics.author_account_age_days is not None:
        if metrics.author_account_age_days > 1825:  # 5+ years
            score += 0.10
        elif metrics.author_account_age_days > 365:  # 1+ years
            score += 0.05
        elif metrics.author_account_age_days < 30:  # Very new account
            score -= 0.05

    # ─── Recency ───────────────────────────────────────────────────
    if metrics.posted_at is not None:
        # Ensure timezone-aware comparison
        posted = metrics.posted_at
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)

        days_since_post = (now - posted).days

        if days_since_post < 7:
            score += 0.15
        elif days_since_post < 30:
            score += 0.08
        elif days_since_post < 90:
            score += 0.03
        elif days_since_post > 365:
            score -= 0.25
        elif days_since_post > 180:
            score -= 0.15

    # ─── Thread confirmation signals ───────────────────────────────
    if metrics.reply_confirms_count > 3:
        score += 0.10
    elif metrics.reply_confirms_count > 1:
        score += 0.05

    # ─── Thread deprecation signals ────────────────────────────────
    if metrics.reply_deprecates_count > 2:
        score -= 0.20
    elif metrics.reply_deprecates_count > 0:
        score -= 0.10

    return max(0.0, min(1.0, round(score, 2)))


def score_from_community_post(
    post_author_count: int | None,
    post_author_age_days: int | None,
    posted_at: datetime | None,
    reply_confirms: int = 0,
    reply_deprecates: int = 0,
) -> float:
    """
    Convenience function that takes raw values instead of a PostMetrics dataclass.

    Used when scoring directly from CommunityPost model attributes.
    """
    return score_post(
        PostMetrics(
            author_post_count=post_author_count,
            author_account_age_days=post_author_age_days,
            posted_at=posted_at,
            reply_confirms_count=reply_confirms,
            reply_deprecates_count=reply_deprecates,
        )
    )
