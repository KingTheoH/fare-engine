"""
scoring_service.py — Confidence score calculation for dump patterns.

Implements the weighted formula:
    confidence = (
        0.50 * recent_validation_success_rate   # last 10 runs, recency-weighted
      + 0.25 * source_post_weight               # community credibility of source
      + 0.15 * multi_source_bonus               # bonus if confirmed in >1 independent post
      + 0.10 * recency_factor                   # decays if not validated recently
    )

All components clamped to [0.0, 1.0]. Final score also clamped.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ─── Constants ──────────────────────────────────────────────────────────────

# Weights for each component of the confidence formula
W_VALIDATION = 0.50
W_SOURCE = 0.25
W_MULTI_SOURCE = 0.15
W_RECENCY = 0.10

# How many recent validation runs to consider
MAX_RECENT_RUNS = 10

# Recency decay: half-life in days (after this many days, recency_factor = 0.5)
RECENCY_HALF_LIFE_DAYS = 14

# Multi-source bonus thresholds
MULTI_SOURCE_THRESHOLD_FULL = 3   # 3+ independent sources → 1.0 bonus
MULTI_SOURCE_THRESHOLD_PARTIAL = 2  # 2 independent sources → 0.5 bonus


# ─── Result types ──────────────────────────────────────────────────────────

@dataclass
class ConfidenceBreakdown:
    """Detailed breakdown of a confidence score calculation."""

    validation_component: float = 0.0
    source_component: float = 0.0
    multi_source_component: float = 0.0
    recency_component: float = 0.0
    final_score: float = 0.0

    # Raw values (before weighting)
    validation_success_rate: float = 0.0
    source_post_weight: float = 0.0
    multi_source_bonus: float = 0.0
    recency_factor: float = 0.0

    total_runs_considered: int = 0


# ─── Core calculation ──────────────────────────────────────────────────────

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    """Clamp a value to [lo, hi]."""
    return max(lo, min(hi, value))


def calculate_validation_success_rate(
    runs: list[dict],
    max_runs: int = MAX_RECENT_RUNS,
) -> float:
    """
    Calculate recency-weighted validation success rate.

    More recent runs have higher weight. Uses exponential decay:
    weight_i = 0.9^i where i=0 is the most recent run.

    Args:
        runs: List of validation run dicts, ordered most-recent-first.
              Each must have a 'success' bool key.
        max_runs: Max number of runs to consider.

    Returns:
        Weighted success rate in [0.0, 1.0]. Returns 0.0 if no runs.
    """
    if not runs:
        return 0.0

    recent = runs[:max_runs]
    decay_factor = 0.9

    weighted_sum = 0.0
    weight_total = 0.0

    for i, run in enumerate(recent):
        weight = decay_factor ** i
        weighted_sum += weight * (1.0 if run.get("success", False) else 0.0)
        weight_total += weight

    if weight_total == 0:
        return 0.0

    return weighted_sum / weight_total


def calculate_recency_factor(
    last_validated_at: datetime | None,
    now: datetime | None = None,
) -> float:
    """
    Calculate recency factor based on time since last validation.

    Uses exponential decay with half-life of RECENCY_HALF_LIFE_DAYS.
    Returns 1.0 if validated just now, 0.5 at half-life, approaching 0.0
    as time goes on.

    Args:
        last_validated_at: Timestamp of last validation (timezone-aware).
        now: Current time (for testing). Defaults to UTC now.

    Returns:
        Recency factor in [0.0, 1.0]. Returns 0.0 if never validated.
    """
    if last_validated_at is None:
        return 0.0

    if now is None:
        now = datetime.now(timezone.utc)

    # Ensure timezone-aware comparison
    if last_validated_at.tzinfo is None:
        last_validated_at = last_validated_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    days_since = (now - last_validated_at).total_seconds() / 86400.0

    if days_since <= 0:
        return 1.0

    # Exponential decay: factor = 2^(-days/half_life)
    factor = math.pow(2, -days_since / RECENCY_HALF_LIFE_DAYS)
    return _clamp(factor)


def calculate_multi_source_bonus(independent_source_count: int) -> float:
    """
    Calculate multi-source bonus.

    More independent community sources confirming a pattern = higher bonus.

    Args:
        independent_source_count: Number of independent posts confirming pattern.

    Returns:
        Multi-source bonus in [0.0, 1.0].
    """
    if independent_source_count >= MULTI_SOURCE_THRESHOLD_FULL:
        return 1.0
    elif independent_source_count >= MULTI_SOURCE_THRESHOLD_PARTIAL:
        return 0.5
    elif independent_source_count == 1:
        return 0.0
    else:
        return 0.0


def calculate_confidence_score(
    validation_runs: list[dict],
    source_post_weight: float,
    independent_source_count: int = 1,
    last_validated_at: datetime | None = None,
    now: datetime | None = None,
) -> ConfidenceBreakdown:
    """
    Calculate the full confidence score for a dump pattern.

    confidence = (
        0.50 * validation_success_rate
      + 0.25 * source_post_weight
      + 0.15 * multi_source_bonus
      + 0.10 * recency_factor
    )

    Args:
        validation_runs: List of validation run dicts, ordered most-recent-first.
                         Each must have a 'success' bool key.
        source_post_weight: Community credibility score of the original post [0.0, 1.0].
        independent_source_count: How many independent community sources confirm this.
        last_validated_at: When the pattern was last validated.
        now: Current time (for testing).

    Returns:
        ConfidenceBreakdown with full breakdown and final score.
    """
    # Calculate each component
    validation_rate = calculate_validation_success_rate(validation_runs)
    recency = calculate_recency_factor(last_validated_at, now)
    multi_source = calculate_multi_source_bonus(independent_source_count)
    source_weight = _clamp(source_post_weight)

    # Apply weights
    validation_component = W_VALIDATION * validation_rate
    source_component = W_SOURCE * source_weight
    multi_source_component = W_MULTI_SOURCE * multi_source
    recency_component = W_RECENCY * recency

    # Sum and clamp
    final = _clamp(
        validation_component
        + source_component
        + multi_source_component
        + recency_component
    )

    return ConfidenceBreakdown(
        validation_component=round(validation_component, 4),
        source_component=round(source_component, 4),
        multi_source_component=round(multi_source_component, 4),
        recency_component=round(recency_component, 4),
        final_score=round(final, 4),
        validation_success_rate=round(validation_rate, 4),
        source_post_weight=round(source_weight, 4),
        multi_source_bonus=round(multi_source, 4),
        recency_factor=round(recency, 4),
        total_runs_considered=min(len(validation_runs), MAX_RECENT_RUNS),
    )
