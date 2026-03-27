"""
pattern_service.py — Pattern lifecycle management.

Handles lifecycle state transitions, freshness tier recalculation,
and pattern queries for agents.

Lifecycle transitions (updated 2026-03 to be more resilient):
    discovered → active       : first successful validation
    active → degrading        : success rate < 40% over last 10 runs
    degrading → active        : 2 consecutive successes (recovery)
    degrading → deprecated    : 5 consecutive pattern failures (infra errors excluded upstream)
    deprecated → discovered   : manual resurrection (re-enters validation queue)
    deprecated → archived     : manual agent action only

Key design change (2026-03):
    Infrastructure errors (proxy timeout, bot detection) are now filtered out
    in validation_service.py BEFORE reaching lifecycle evaluation. Only genuine
    pattern failures count here. The thresholds were also relaxed:
    - Degrading window: 5 → 10 runs (more stable signal)
    - Degrading threshold: 60% → 40% (more tolerant)
    - Deprecated threshold: 3 → 5 consecutive failures (more chances)
    - Added resurrection: deprecated → discovered (agents can revive patterns)
"""

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import pattern_repository, validation_repository
from app.models.enums import FreshnessTier, LifecycleState

logger = logging.getLogger(__name__)


# ─── Constants ──────────────────────────────────────────────────────────────

# Lifecycle transition thresholds (relaxed 2026-03 to reduce false deprecations)
# Note: infra errors (proxy, timeout, bot detection) are filtered out upstream
# in validation_service.py — only genuine pattern failures reach lifecycle evaluation.
DEGRADING_SUCCESS_RATE_THRESHOLD = 0.40  # < 40% over last 10 → degrading (was 60%/5)
DEGRADING_WINDOW_SIZE = 10               # wider window = more stable signal (was 5)
RECOVERY_CONSECUTIVE_SUCCESSES = 2       # 2 consecutive successes → recovery
DEPRECATED_CONSECUTIVE_FAILURES = 5      # 5 consecutive failures → deprecated (was 3)

# Freshness tier thresholds (USD per roundtrip)
TIER_1_SAVINGS_THRESHOLD = 200.0  # > $200 → daily validation
TIER_2_SAVINGS_THRESHOLD = 50.0   # $50-200 → weekly validation


# ─── Result types ──────────────────────────────────────────────────────────

@dataclass
class LifecycleTransition:
    """Result of a lifecycle state evaluation."""

    pattern_id: uuid.UUID
    old_state: str
    new_state: str
    transitioned: bool
    reason: str


# ─── Lifecycle transitions ─────────────────────────────────────────────────

# Valid transitions map
VALID_TRANSITIONS: dict[str, set[str]] = {
    LifecycleState.DISCOVERED.value: {LifecycleState.ACTIVE.value},
    LifecycleState.ACTIVE.value: {LifecycleState.DEGRADING.value},
    LifecycleState.DEGRADING.value: {
        LifecycleState.ACTIVE.value,
        LifecycleState.DEPRECATED.value,
    },
    LifecycleState.DEPRECATED.value: {
        LifecycleState.ARCHIVED.value,
        LifecycleState.DISCOVERED.value,  # resurrection path
    },
    LifecycleState.ARCHIVED.value: set(),  # terminal state
}


async def evaluate_lifecycle(
    session: AsyncSession,
    pattern_id: uuid.UUID,
    latest_run_success: bool,
) -> LifecycleTransition:
    """
    Evaluate whether a pattern's lifecycle state should change
    after a new validation run.

    This is called after every non-infrastructure validation. Infra errors
    (proxy timeout, bot detection) are filtered out in validation_service.py
    and never reach this function.

    Args:
        session: Database session.
        pattern_id: Pattern UUID.
        latest_run_success: Whether the most recent validation succeeded.

    Returns:
        LifecycleTransition describing what happened.
    """
    pattern = await pattern_repository.get_pattern_by_id(session, pattern_id)
    if pattern is None:
        return LifecycleTransition(
            pattern_id=pattern_id,
            old_state="unknown",
            new_state="unknown",
            transitioned=False,
            reason="Pattern not found",
        )

    current_state = pattern.lifecycle_state

    # Determine new state based on current state + validation results
    new_state, reason = await _determine_transition(
        session, pattern_id, current_state, latest_run_success
    )

    if new_state != current_state:
        await pattern_repository.update_lifecycle_state(
            session, pattern_id, new_state
        )
        logger.info(
            "Pattern %s transitioned: %s → %s (%s)",
            pattern_id, current_state, new_state, reason,
        )
        return LifecycleTransition(
            pattern_id=pattern_id,
            old_state=current_state,
            new_state=new_state,
            transitioned=True,
            reason=reason,
        )

    return LifecycleTransition(
        pattern_id=pattern_id,
        old_state=current_state,
        new_state=current_state,
        transitioned=False,
        reason=reason,
    )


async def _determine_transition(
    session: AsyncSession,
    pattern_id: uuid.UUID,
    current_state: str,
    latest_success: bool,
) -> tuple[str, str]:
    """
    Determine what state transition (if any) should occur.

    Returns:
        Tuple of (new_state, reason).
    """

    if current_state == LifecycleState.DISCOVERED.value:
        # discovered → active: first successful validation
        if latest_success:
            return LifecycleState.ACTIVE.value, "First successful validation"
        return current_state, "Awaiting first successful validation"

    elif current_state == LifecycleState.ACTIVE.value:
        # active → degrading: success rate < 40% over last 10 runs
        success_rate = await validation_repository.get_success_rate(
            session, pattern_id, last_n=DEGRADING_WINDOW_SIZE
        )
        if success_rate is not None and success_rate < DEGRADING_SUCCESS_RATE_THRESHOLD:
            return (
                LifecycleState.DEGRADING.value,
                f"Success rate {success_rate:.0%} < {DEGRADING_SUCCESS_RATE_THRESHOLD:.0%} "
                f"over last {DEGRADING_WINDOW_SIZE} runs",
            )
        return current_state, f"Active — success rate {success_rate:.0%}" if success_rate else "Active"

    elif current_state == LifecycleState.DEGRADING.value:
        # degrading → active: 2 consecutive successes (recovery)
        consecutive_successes = await validation_repository.get_consecutive_successes(
            session, pattern_id
        )
        if consecutive_successes >= RECOVERY_CONSECUTIVE_SUCCESSES:
            return (
                LifecycleState.ACTIVE.value,
                f"{consecutive_successes} consecutive successes — recovered",
            )

        # degrading → deprecated: 5 consecutive failures
        consecutive_failures = await validation_repository.get_consecutive_failures(
            session, pattern_id
        )
        if consecutive_failures >= DEPRECATED_CONSECUTIVE_FAILURES:
            return (
                LifecycleState.DEPRECATED.value,
                f"{consecutive_failures} consecutive failures",
            )

        return current_state, "Degrading — monitoring"

    elif current_state == LifecycleState.DEPRECATED.value:
        # deprecated → archived or resurrected: manual only — never auto-transition
        return current_state, "Deprecated — manual archive or resurrect only"

    elif current_state == LifecycleState.ARCHIVED.value:
        return current_state, "Archived — terminal state"

    return current_state, f"Unknown state: {current_state}"


async def archive_pattern(
    session: AsyncSession,
    pattern_id: uuid.UUID,
) -> LifecycleTransition:
    """
    Manually archive a deprecated pattern.

    Only deprecated patterns can be archived. This is the one
    transition that requires explicit agent action.
    """
    pattern = await pattern_repository.get_pattern_by_id(session, pattern_id)
    if pattern is None:
        return LifecycleTransition(
            pattern_id=pattern_id,
            old_state="unknown",
            new_state="unknown",
            transitioned=False,
            reason="Pattern not found",
        )

    if pattern.lifecycle_state != LifecycleState.DEPRECATED.value:
        return LifecycleTransition(
            pattern_id=pattern_id,
            old_state=pattern.lifecycle_state,
            new_state=pattern.lifecycle_state,
            transitioned=False,
            reason=f"Cannot archive from state '{pattern.lifecycle_state}' — must be deprecated",
        )

    await pattern_repository.update_lifecycle_state(
        session, pattern_id, LifecycleState.ARCHIVED.value
    )

    logger.info("Pattern %s manually archived", pattern_id)
    return LifecycleTransition(
        pattern_id=pattern_id,
        old_state=LifecycleState.DEPRECATED.value,
        new_state=LifecycleState.ARCHIVED.value,
        transitioned=True,
        reason="Manually archived by agent",
    )


async def resurrect_pattern(
    session: AsyncSession,
    pattern_id: uuid.UUID,
) -> LifecycleTransition:
    """
    Resurrect a deprecated pattern back to discovered state.

    This gives the pattern another chance to be validated. Useful when:
    - Infrastructure issues caused false deprecation
    - Market conditions changed (new routes, carrier policy changes)
    - Agent believes the pattern should be re-tested

    Resets the pattern to 'discovered' so it re-enters the validation queue.
    Confidence score is preserved (not reset) so the system remembers its history.
    """
    pattern = await pattern_repository.get_pattern_by_id(session, pattern_id)
    if pattern is None:
        return LifecycleTransition(
            pattern_id=pattern_id,
            old_state="unknown",
            new_state="unknown",
            transitioned=False,
            reason="Pattern not found",
        )

    if pattern.lifecycle_state != LifecycleState.DEPRECATED.value:
        return LifecycleTransition(
            pattern_id=pattern_id,
            old_state=pattern.lifecycle_state,
            new_state=pattern.lifecycle_state,
            transitioned=False,
            reason=f"Cannot resurrect from state '{pattern.lifecycle_state}' — must be deprecated",
        )

    await pattern_repository.update_lifecycle_state(
        session, pattern_id, LifecycleState.DISCOVERED.value
    )

    logger.info("Pattern %s resurrected: deprecated → discovered", pattern_id)
    return LifecycleTransition(
        pattern_id=pattern_id,
        old_state=LifecycleState.DEPRECATED.value,
        new_state=LifecycleState.DISCOVERED.value,
        transitioned=True,
        reason="Manually resurrected by agent — re-entering validation queue",
    )


# ─── Freshness tier ───────────────────────────────────────────────────────

def compute_freshness_tier(expected_yq_savings_usd: float | None) -> int:
    """
    Determine the freshness tier based on expected YQ savings.

    Tier 1 (HIGH): > $200 savings → daily validation
    Tier 2 (MEDIUM): $50-200 savings → weekly validation
    Tier 3 (LOW): < $50 savings → monthly validation
    """
    if expected_yq_savings_usd is None or expected_yq_savings_usd <= 0:
        return FreshnessTier.LOW.value

    if expected_yq_savings_usd > TIER_1_SAVINGS_THRESHOLD:
        return FreshnessTier.HIGH.value
    elif expected_yq_savings_usd > TIER_2_SAVINGS_THRESHOLD:
        return FreshnessTier.MEDIUM.value
    else:
        return FreshnessTier.LOW.value


async def recalculate_freshness_tier(
    session: AsyncSession,
    pattern_id: uuid.UUID,
    expected_yq_savings_usd: float | None = None,
) -> int:
    """
    Recalculate and persist the freshness tier for a pattern.

    If expected_yq_savings_usd is not provided, reads from the pattern record.

    Returns:
        The new tier value (1, 2, or 3).
    """
    if expected_yq_savings_usd is None:
        pattern = await pattern_repository.get_pattern_by_id(session, pattern_id)
        if pattern is None:
            return FreshnessTier.LOW.value
        expected_yq_savings_usd = pattern.expected_yq_savings_usd

    new_tier = compute_freshness_tier(expected_yq_savings_usd)
    await pattern_repository.update_freshness_tier(session, pattern_id, new_tier)

    return new_tier


# ─── Query helpers ─────────────────────────────────────────────────────────

async def get_active_patterns(
    session: AsyncSession,
    dump_type: str | None = None,
    origin: str | None = None,
    destination: str | None = None,
    carrier: str | None = None,
    freshness_tier: int | None = None,
    include_discovered: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list:
    """
    Get patterns surfaceable to agents.

    Delegates to pattern_repository with optional filters.
    Set include_discovered=True to also show unvalidated patterns.
    """
    return await pattern_repository.get_active_patterns(
        session,
        dump_type=dump_type,
        origin=origin,
        destination=destination,
        carrier=carrier,
        freshness_tier=freshness_tier,
        include_discovered=include_discovered,
        limit=limit,
        offset=offset,
    )


# ─── Community ingestion ────────────────────────────────────────────────────

@dataclass
class MergeResult:
    """Result of merging a community-sourced pattern."""

    pattern_id: uuid.UUID
    created: bool  # True = new pattern inserted, False = already existed
    routing_code: str


async def merge_community_pattern(
    session: AsyncSession,
    pattern_data: dict,
) -> MergeResult:
    """
    Insert a community-sourced normalized pattern into dump_patterns.

    Deduplicates by ita_routing_code — if the exact same routing code
    already exists, skips the insert and returns the existing pattern.

    This is the bridge between the ingestion pipeline and the validation queue:
    every pattern that passes LLM extraction + normalization gates ends up here
    and enters lifecycle_state='discovered', ready for ITA Matrix validation.

    Args:
        session: Async DB session (caller must commit).
        pattern_data: Validated dict from pattern_normalizer.normalize_pattern().

    Returns:
        MergeResult with pattern_id and whether it was newly created.
    """
    pattern, created = await pattern_repository.upsert_community_pattern(
        session, pattern_data
    )

    if created:
        logger.info(
            "Inserted new community pattern %s→%s [%s] routing=%s",
            pattern_data.get("origin_iata"),
            pattern_data.get("destination_iata"),
            pattern_data.get("dump_type"),
            pattern_data.get("ita_routing_code", "")[:60],
        )
    else:
        logger.debug(
            "Skipped duplicate routing code: %s",
            pattern_data.get("ita_routing_code", "")[:60],
        )

    return MergeResult(
        pattern_id=pattern.id,
        created=created,
        routing_code=pattern_data.get("ita_routing_code", ""),
    )
