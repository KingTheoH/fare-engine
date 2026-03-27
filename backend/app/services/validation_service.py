"""
validation_service.py — Validation orchestration service.

The heart of the system: takes a dump pattern, runs it through ITA Matrix,
records the result, updates confidence scores, and manages lifecycle state.

Key functions:
- run_validation: Full validation pipeline for a single pattern
- evaluate_validation_result: Post-run scoring + lifecycle evaluation
- record_validation_run: Store a validation result (also used for manual entries)

Key design decision (2026-03):
- Infrastructure errors (proxy timeout, bot detection, parse failures) are
  recorded but do NOT count toward lifecycle transitions or confidence scoring.
  Only "pattern failures" (ITA returned results but YQ wasn't reduced) affect
  the pattern's health. This prevents proxy outages from killing valid patterns.
"""

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import pattern_repository, validation_repository
from app.models.enums import FreshnessTier, LifecycleState
from app.services import pattern_service, scoring_service

logger = logging.getLogger(__name__)


# ─── Infrastructure error detection ───────────────────────────────────────

# Error messages that indicate infrastructure/automation problems, NOT pattern failures.
# When these occur, the pattern should not be penalized.
INFRA_ERROR_PATTERNS = [
    r"(?i)timeout",
    r"(?i)bot.?detect",
    r"(?i)captcha",
    r"(?i)proxy",
    r"(?i)connection.?(refused|reset|closed|error)",
    r"(?i)rate.?limit",
    r"(?i)playwright",
    r"(?i)browser.?(crash|closed|disconnected)",
    r"(?i)no ITA client",
    r"(?i)navigation.?failed",
    r"(?i)page.?(load|crash)",
    r"(?i)network.?error",
    r"(?i)ssl.?error",
    r"(?i)dns.?(resolution|lookup)",
    r"(?i)503|502|504",  # server errors from ITA
]

_INFRA_RE = re.compile("|".join(INFRA_ERROR_PATTERNS))


def is_infrastructure_error(error_message: str | None) -> bool:
    """
    Determine if a validation error was caused by infrastructure (proxy, timeout,
    bot detection, etc.) rather than the pattern itself being invalid.

    Infrastructure errors should NOT count toward lifecycle transitions or
    confidence scoring — they say nothing about whether the pattern works.
    """
    if error_message is None:
        return False
    return bool(_INFRA_RE.search(error_message))


# ─── Result types ──────────────────────────────────────────────────────────

@dataclass
class ValidationResult:
    """Result of a single pattern validation attempt."""

    pattern_id: uuid.UUID
    success: bool
    is_infra_error: bool = False  # True = don't count toward lifecycle/scoring
    yq_charged_usd: float | None = None
    yq_expected_usd: float | None = None
    base_fare_usd: float | None = None
    raw_ita_response: dict | None = None
    error_message: str | None = None
    proxy_used: str | None = None


@dataclass
class ValidationOutcome:
    """Full outcome after validation + scoring + lifecycle evaluation."""

    pattern_id: uuid.UUID
    validation_success: bool
    new_confidence_score: float
    old_confidence_score: float
    confidence_breakdown: scoring_service.ConfidenceBreakdown | None = None
    lifecycle_transition: pattern_service.LifecycleTransition | None = None
    new_freshness_tier: int | None = None
    error: str | None = None

    @property
    def had_transition(self) -> bool:
        return (
            self.lifecycle_transition is not None
            and self.lifecycle_transition.transitioned
        )


# ─── Core validation pipeline ─────────────────────────────────────────────

async def record_validation_run(
    session: AsyncSession,
    result: ValidationResult,
    manual_input_snapshot: dict | None = None,
) -> uuid.UUID:
    """
    Record a validation run in the database.

    This stores the raw result. It does NOT update confidence scores
    or lifecycle state — call evaluate_validation_result for that.

    Args:
        session: Database session.
        result: Validation result to record.
        manual_input_snapshot: Manual input bundle snapshot for replay.

    Returns:
        UUID of the created validation run.
    """
    run = await validation_repository.create_validation_run(
        session=session,
        pattern_id=result.pattern_id,
        success=result.success,
        yq_charged_usd=result.yq_charged_usd,
        yq_expected_usd=result.yq_expected_usd,
        base_fare_usd=result.base_fare_usd,
        raw_ita_response=result.raw_ita_response,
        manual_input_snapshot=manual_input_snapshot,
        error_message=result.error_message,
        proxy_used=result.proxy_used,
    )
    return run.id


async def evaluate_validation_result(
    session: AsyncSession,
    pattern_id: uuid.UUID,
    latest_success: bool,
    yq_savings_usd: float | None = None,
) -> ValidationOutcome:
    """
    Post-validation evaluation: update confidence, lifecycle, freshness.

    Called after a validation run has been recorded. This is the function
    that makes the system learn from each validation attempt.

    Pipeline:
    1. Fetch pattern + recent validation runs
    2. Calculate new confidence score
    3. Evaluate lifecycle state transition
    4. Recalculate freshness tier (if savings changed)
    5. Persist all updates

    Args:
        session: Database session.
        pattern_id: Pattern UUID.
        latest_success: Whether the most recent validation succeeded.
        yq_savings_usd: YQ savings from this run (if success).

    Returns:
        ValidationOutcome with full details.
    """
    pattern = await pattern_repository.get_pattern_by_id(session, pattern_id)
    if pattern is None:
        return ValidationOutcome(
            pattern_id=pattern_id,
            validation_success=latest_success,
            new_confidence_score=0.0,
            old_confidence_score=0.0,
            error="Pattern not found",
        )

    old_confidence = pattern.confidence_score

    # 1. Get recent validation runs for scoring
    recent_runs = await validation_repository.get_recent_runs(
        session, pattern_id, limit=scoring_service.MAX_RECENT_RUNS
    )
    run_dicts = [{"success": r.success} for r in recent_runs]

    # 2. Get last validation time
    last_validated = await validation_repository.get_last_validation_time(
        session, pattern_id
    )

    # 3. Calculate new confidence score
    breakdown = scoring_service.calculate_confidence_score(
        validation_runs=run_dicts,
        source_post_weight=pattern.source_post_weight,
        independent_source_count=1,  # TODO: track multi-source in Phase 09
        last_validated_at=last_validated,
    )

    # 4. Persist confidence score
    await pattern_repository.update_confidence_score(
        session, pattern_id, breakdown.final_score
    )

    # 5. Evaluate lifecycle transition
    transition = await pattern_service.evaluate_lifecycle(
        session, pattern_id, latest_success
    )

    # 6. Update savings and recalculate freshness tier if needed
    new_tier = None
    if latest_success and yq_savings_usd is not None:
        await pattern_repository.update_pattern_fields(
            session, pattern_id,
            expected_yq_savings_usd=yq_savings_usd,
        )
        new_tier = await pattern_service.recalculate_freshness_tier(
            session, pattern_id, yq_savings_usd
        )

    return ValidationOutcome(
        pattern_id=pattern_id,
        validation_success=latest_success,
        new_confidence_score=breakdown.final_score,
        old_confidence_score=old_confidence,
        confidence_breakdown=breakdown,
        lifecycle_transition=transition,
        new_freshness_tier=new_tier,
    )


# ─── YQ success evaluation ────────────────────────────────────────────────

# Absolute ceiling: if YQ charged is below this, always count as success
YQ_ABSOLUTE_SUCCESS_CEILING = 20.0  # $20

# Relative threshold: YQ must be reduced by at least this fraction of expected
YQ_RELATIVE_REDUCTION_THRESHOLD = 0.75  # 75% reduction


def _evaluate_yq_success(
    yq_charged: float | None,
    yq_expected: float | None,
) -> bool:
    """
    Determine if a dump successfully reduced YQ.

    Uses a two-pronged test (either one passing = success):
    1. Absolute: YQ charged < $20 (effectively dumped)
    2. Relative: YQ reduced by ≥75% from expected baseline

    This prevents partial dumps that still save $400+ from being
    marked as failures just because residual YQ is $15.

    Examples:
        yq_expected=$580, yq_charged=$5   → True  (absolute: <$20)
        yq_expected=$580, yq_charged=$15  → True  (absolute: <$20)
        yq_expected=$580, yq_charged=$50  → True  (relative: 91% reduction)
        yq_expected=$580, yq_charged=$200 → False (only 65% reduction, >$20)
        yq_expected=None, yq_charged=$8   → True  (absolute: <$20)
        yq_expected=None, yq_charged=$50  → False (no baseline to compare, >$20)
    """
    if yq_charged is None:
        return False

    # Test 1: absolute ceiling
    if yq_charged < YQ_ABSOLUTE_SUCCESS_CEILING:
        return True

    # Test 2: relative reduction (only if we have a baseline)
    if yq_expected is not None and yq_expected > 0:
        reduction_ratio = 1.0 - (yq_charged / yq_expected)
        if reduction_ratio >= YQ_RELATIVE_REDUCTION_THRESHOLD:
            return True

    return False


async def run_validation(
    session: AsyncSession,
    pattern_id: uuid.UUID,
    ita_client: Any = None,
) -> ValidationOutcome:
    """
    Full validation pipeline: query ITA Matrix → record → evaluate.

    This is the main entry point for automated validation. It:
    1. Fetches the pattern
    2. Runs the ITA Matrix query (via ita_client)
    3. Records the validation run
    4. Evaluates the result (score + lifecycle)

    Args:
        session: Database session.
        pattern_id: Pattern UUID.
        ita_client: ITA Matrix automation client. If None, records a
                    manual validation failure (useful for testing).

    Returns:
        ValidationOutcome with full details.
    """
    pattern = await pattern_repository.get_pattern_by_id(session, pattern_id)
    if pattern is None:
        return ValidationOutcome(
            pattern_id=pattern_id,
            validation_success=False,
            new_confidence_score=0.0,
            old_confidence_score=0.0,
            error="Pattern not found",
        )

    # Skip archived/deprecated patterns
    if pattern.lifecycle_state in (
        LifecycleState.ARCHIVED.value,
        LifecycleState.DEPRECATED.value,
    ):
        return ValidationOutcome(
            pattern_id=pattern_id,
            validation_success=False,
            new_confidence_score=pattern.confidence_score,
            old_confidence_score=pattern.confidence_score,
            error=f"Pattern is {pattern.lifecycle_state} — skipping validation",
        )

    # Build validation result
    result: ValidationResult
    yq_savings: float | None = None

    if ita_client is None:
        # No ITA client — infrastructure error, not a pattern failure
        result = ValidationResult(
            pattern_id=pattern_id,
            success=False,
            is_infra_error=True,
            error_message="No ITA client available",
        )
    else:
        try:
            # Run ITA Matrix automation
            ita_result = await ita_client.query(pattern.ita_routing_code)

            # Evaluate: did the dump work?
            # Use relative threshold: success if YQ reduced by ≥75% from expected,
            # OR absolute YQ charged < $20. This prevents partial dumps that save
            # hundreds of dollars from being marked as failures.
            yq_charged = ita_result.get("yq_charged_usd", None)
            yq_expected = pattern.expected_yq_savings_usd

            success = _evaluate_yq_success(yq_charged, yq_expected)

            if success and yq_expected is not None and yq_charged is not None:
                yq_savings = yq_expected - yq_charged

            result = ValidationResult(
                pattern_id=pattern_id,
                success=success,
                is_infra_error=False,
                yq_charged_usd=yq_charged,
                yq_expected_usd=yq_expected,
                base_fare_usd=ita_result.get("base_fare_usd"),
                raw_ita_response=ita_result,
                proxy_used=ita_result.get("proxy_used"),
            )
        except Exception as e:
            error_msg = f"ITA query error: {str(e)}"
            logger.error(
                "ITA query failed for pattern %s: %s",
                pattern_id, e, exc_info=True,
            )
            result = ValidationResult(
                pattern_id=pattern_id,
                success=False,
                is_infra_error=is_infrastructure_error(error_msg),
                error_message=error_msg,
            )

    # Record the validation run (always — infra errors are still logged for debugging)
    await record_validation_run(
        session, result,
        manual_input_snapshot=pattern.manual_input_bundle,
    )

    # Only evaluate scoring + lifecycle for non-infrastructure errors.
    # Infra errors (proxy timeout, bot detection) say nothing about the pattern
    # and should not degrade confidence or trigger lifecycle transitions.
    if result.is_infra_error:
        logger.info(
            "Pattern %s: infrastructure error — skipping lifecycle/scoring. Error: %s",
            pattern_id, result.error_message,
        )
        outcome = ValidationOutcome(
            pattern_id=pattern_id,
            validation_success=False,
            new_confidence_score=pattern.confidence_score,
            old_confidence_score=pattern.confidence_score,
            error=f"Infrastructure error (not counted): {result.error_message}",
        )
    else:
        # Evaluate the result (scoring + lifecycle)
        outcome = await evaluate_validation_result(
            session, pattern_id, result.success, yq_savings
        )

    return outcome


async def get_consecutive_failure_count(
    session: AsyncSession,
    pattern_id: uuid.UUID,
) -> int:
    """Get the count of consecutive failures for a pattern."""
    return await validation_repository.get_consecutive_failures(
        session, pattern_id
    )
