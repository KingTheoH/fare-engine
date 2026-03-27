"""
test_validation_service.py — Tests for validation_service.py and pattern_service.py

Tests lifecycle transitions, validation recording, and the full
validation pipeline. Uses mocked database sessions and repositories.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import FreshnessTier, LifecycleState
from app.services.pattern_service import (
    DEGRADING_SUCCESS_RATE_THRESHOLD,
    DEGRADING_WINDOW_SIZE,
    DEPRECATED_CONSECUTIVE_FAILURES,
    RECOVERY_CONSECUTIVE_SUCCESSES,
    TIER_1_SAVINGS_THRESHOLD,
    TIER_2_SAVINGS_THRESHOLD,
    VALID_TRANSITIONS,
    LifecycleTransition,
    archive_pattern,
    compute_freshness_tier,
    evaluate_lifecycle,
)
from app.services.scoring_service import ConfidenceBreakdown
from app.services.validation_service import (
    ValidationOutcome,
    ValidationResult,
    evaluate_validation_result,
    get_consecutive_failure_count,
    record_validation_run,
    run_validation,
)


# ─── Fixtures & helpers ───────────────────────────────────────────────────

def make_pattern_id() -> uuid.UUID:
    return uuid.uuid4()


def make_mock_pattern(
    pattern_id: uuid.UUID | None = None,
    lifecycle_state: str = LifecycleState.ACTIVE.value,
    confidence_score: float = 0.5,
    source_post_weight: float = 0.6,
    expected_yq_savings_usd: float | None = 200.0,
    freshness_tier: int = FreshnessTier.MEDIUM.value,
    ita_routing_code: str = "LH JFK FRA BKK",
    manual_input_bundle: dict | None = None,
):
    """Create a mock DumpPattern object."""
    pattern = MagicMock()
    pattern.id = pattern_id or make_pattern_id()
    pattern.lifecycle_state = lifecycle_state
    pattern.confidence_score = confidence_score
    pattern.source_post_weight = source_post_weight
    pattern.expected_yq_savings_usd = expected_yq_savings_usd
    pattern.freshness_tier = freshness_tier
    pattern.ita_routing_code = ita_routing_code
    pattern.manual_input_bundle = manual_input_bundle
    return pattern


def make_mock_run(success: bool, ran_at: datetime | None = None):
    """Create a mock ValidationRun object."""
    run = MagicMock()
    run.success = success
    run.ran_at = ran_at or datetime.now(timezone.utc)
    return run


# ─── compute_freshness_tier ───────────────────────────────────────────────

class TestComputeFreshnessTier:
    def test_high_savings(self):
        assert compute_freshness_tier(300.0) == FreshnessTier.HIGH.value

    def test_medium_savings(self):
        assert compute_freshness_tier(100.0) == FreshnessTier.MEDIUM.value

    def test_low_savings(self):
        assert compute_freshness_tier(30.0) == FreshnessTier.LOW.value

    def test_zero_savings(self):
        assert compute_freshness_tier(0.0) == FreshnessTier.LOW.value

    def test_none_savings(self):
        assert compute_freshness_tier(None) == FreshnessTier.LOW.value

    def test_negative_savings(self):
        assert compute_freshness_tier(-50.0) == FreshnessTier.LOW.value

    def test_boundary_tier1(self):
        """Exactly $200 is tier 2 (threshold is >$200)."""
        assert compute_freshness_tier(200.0) == FreshnessTier.MEDIUM.value
        assert compute_freshness_tier(200.01) == FreshnessTier.HIGH.value

    def test_boundary_tier2(self):
        """Exactly $50 is tier 3 (threshold is >$50)."""
        assert compute_freshness_tier(50.0) == FreshnessTier.LOW.value
        assert compute_freshness_tier(50.01) == FreshnessTier.MEDIUM.value


# ─── VALID_TRANSITIONS ───────────────────────────────────────────────────

class TestValidTransitions:
    def test_discovered_can_become_active(self):
        assert LifecycleState.ACTIVE.value in VALID_TRANSITIONS[LifecycleState.DISCOVERED.value]

    def test_active_can_become_degrading(self):
        assert LifecycleState.DEGRADING.value in VALID_TRANSITIONS[LifecycleState.ACTIVE.value]

    def test_degrading_can_recover_or_deprecate(self):
        trans = VALID_TRANSITIONS[LifecycleState.DEGRADING.value]
        assert LifecycleState.ACTIVE.value in trans
        assert LifecycleState.DEPRECATED.value in trans

    def test_deprecated_can_archive(self):
        assert LifecycleState.ARCHIVED.value in VALID_TRANSITIONS[LifecycleState.DEPRECATED.value]

    def test_archived_is_terminal(self):
        assert len(VALID_TRANSITIONS[LifecycleState.ARCHIVED.value]) == 0


# ─── evaluate_lifecycle ──────────────────────────────────────────────────

class TestEvaluateLifecycle:
    """Test lifecycle state transitions via evaluate_lifecycle."""

    @pytest.mark.asyncio
    async def test_discovered_to_active_on_success(self):
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.DISCOVERED.value)

        with patch("app.services.pattern_service.pattern_repository") as mock_repo:
            mock_repo.get_pattern_by_id = AsyncMock(return_value=pattern)
            mock_repo.update_lifecycle_state = AsyncMock()

            session = AsyncMock()
            result = await evaluate_lifecycle(session, pid, latest_run_success=True)

            assert result.transitioned
            assert result.old_state == LifecycleState.DISCOVERED.value
            assert result.new_state == LifecycleState.ACTIVE.value
            mock_repo.update_lifecycle_state.assert_called_once_with(
                session, pid, LifecycleState.ACTIVE.value
            )

    @pytest.mark.asyncio
    async def test_discovered_stays_on_failure(self):
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.DISCOVERED.value)

        with patch("app.services.pattern_service.pattern_repository") as mock_repo:
            mock_repo.get_pattern_by_id = AsyncMock(return_value=pattern)

            session = AsyncMock()
            result = await evaluate_lifecycle(session, pid, latest_run_success=False)

            assert not result.transitioned
            assert result.old_state == LifecycleState.DISCOVERED.value
            assert result.new_state == LifecycleState.DISCOVERED.value

    @pytest.mark.asyncio
    async def test_active_to_degrading_on_low_success_rate(self):
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.ACTIVE.value)

        with (
            patch("app.services.pattern_service.pattern_repository") as mock_pat_repo,
            patch("app.services.pattern_service.validation_repository") as mock_val_repo,
        ):
            mock_pat_repo.get_pattern_by_id = AsyncMock(return_value=pattern)
            mock_pat_repo.update_lifecycle_state = AsyncMock()
            # Success rate below threshold
            mock_val_repo.get_success_rate = AsyncMock(return_value=0.40)

            session = AsyncMock()
            result = await evaluate_lifecycle(session, pid, latest_run_success=False)

            assert result.transitioned
            assert result.new_state == LifecycleState.DEGRADING.value

    @pytest.mark.asyncio
    async def test_active_stays_on_good_success_rate(self):
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.ACTIVE.value)

        with (
            patch("app.services.pattern_service.pattern_repository") as mock_pat_repo,
            patch("app.services.pattern_service.validation_repository") as mock_val_repo,
        ):
            mock_pat_repo.get_pattern_by_id = AsyncMock(return_value=pattern)
            mock_val_repo.get_success_rate = AsyncMock(return_value=0.80)

            session = AsyncMock()
            result = await evaluate_lifecycle(session, pid, latest_run_success=True)

            assert not result.transitioned
            assert result.new_state == LifecycleState.ACTIVE.value

    @pytest.mark.asyncio
    async def test_degrading_to_active_on_recovery(self):
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.DEGRADING.value)

        with (
            patch("app.services.pattern_service.pattern_repository") as mock_pat_repo,
            patch("app.services.pattern_service.validation_repository") as mock_val_repo,
        ):
            mock_pat_repo.get_pattern_by_id = AsyncMock(return_value=pattern)
            mock_pat_repo.update_lifecycle_state = AsyncMock()
            mock_val_repo.get_consecutive_successes = AsyncMock(
                return_value=RECOVERY_CONSECUTIVE_SUCCESSES
            )
            mock_val_repo.get_consecutive_failures = AsyncMock(return_value=0)

            session = AsyncMock()
            result = await evaluate_lifecycle(session, pid, latest_run_success=True)

            assert result.transitioned
            assert result.new_state == LifecycleState.ACTIVE.value
            assert "recovered" in result.reason

    @pytest.mark.asyncio
    async def test_degrading_to_deprecated_on_failures(self):
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.DEGRADING.value)

        with (
            patch("app.services.pattern_service.pattern_repository") as mock_pat_repo,
            patch("app.services.pattern_service.validation_repository") as mock_val_repo,
        ):
            mock_pat_repo.get_pattern_by_id = AsyncMock(return_value=pattern)
            mock_pat_repo.update_lifecycle_state = AsyncMock()
            mock_val_repo.get_consecutive_successes = AsyncMock(return_value=0)
            mock_val_repo.get_consecutive_failures = AsyncMock(
                return_value=DEPRECATED_CONSECUTIVE_FAILURES
            )

            session = AsyncMock()
            result = await evaluate_lifecycle(session, pid, latest_run_success=False)

            assert result.transitioned
            assert result.new_state == LifecycleState.DEPRECATED.value

    @pytest.mark.asyncio
    async def test_degrading_stays_when_neither_recovered_nor_deprecated(self):
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.DEGRADING.value)

        with (
            patch("app.services.pattern_service.pattern_repository") as mock_pat_repo,
            patch("app.services.pattern_service.validation_repository") as mock_val_repo,
        ):
            mock_pat_repo.get_pattern_by_id = AsyncMock(return_value=pattern)
            mock_val_repo.get_consecutive_successes = AsyncMock(return_value=1)
            mock_val_repo.get_consecutive_failures = AsyncMock(return_value=1)

            session = AsyncMock()
            result = await evaluate_lifecycle(session, pid, latest_run_success=True)

            assert not result.transitioned

    @pytest.mark.asyncio
    async def test_deprecated_never_auto_transitions(self):
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.DEPRECATED.value)

        with patch("app.services.pattern_service.pattern_repository") as mock_repo:
            mock_repo.get_pattern_by_id = AsyncMock(return_value=pattern)

            session = AsyncMock()
            result = await evaluate_lifecycle(session, pid, latest_run_success=True)

            assert not result.transitioned

    @pytest.mark.asyncio
    async def test_archived_is_terminal(self):
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.ARCHIVED.value)

        with patch("app.services.pattern_service.pattern_repository") as mock_repo:
            mock_repo.get_pattern_by_id = AsyncMock(return_value=pattern)

            session = AsyncMock()
            result = await evaluate_lifecycle(session, pid, latest_run_success=True)

            assert not result.transitioned

    @pytest.mark.asyncio
    async def test_pattern_not_found(self):
        pid = make_pattern_id()

        with patch("app.services.pattern_service.pattern_repository") as mock_repo:
            mock_repo.get_pattern_by_id = AsyncMock(return_value=None)

            session = AsyncMock()
            result = await evaluate_lifecycle(session, pid, latest_run_success=True)

            assert not result.transitioned
            assert "not found" in result.reason.lower()


# ─── archive_pattern ─────────────────────────────────────────────────────

class TestArchivePattern:
    @pytest.mark.asyncio
    async def test_archive_deprecated_pattern(self):
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.DEPRECATED.value)

        with patch("app.services.pattern_service.pattern_repository") as mock_repo:
            mock_repo.get_pattern_by_id = AsyncMock(return_value=pattern)
            mock_repo.update_lifecycle_state = AsyncMock()

            session = AsyncMock()
            result = await archive_pattern(session, pid)

            assert result.transitioned
            assert result.new_state == LifecycleState.ARCHIVED.value

    @pytest.mark.asyncio
    async def test_cannot_archive_active_pattern(self):
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.ACTIVE.value)

        with patch("app.services.pattern_service.pattern_repository") as mock_repo:
            mock_repo.get_pattern_by_id = AsyncMock(return_value=pattern)

            session = AsyncMock()
            result = await archive_pattern(session, pid)

            assert not result.transitioned
            assert "must be deprecated" in result.reason

    @pytest.mark.asyncio
    async def test_cannot_archive_discovered_pattern(self):
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.DISCOVERED.value)

        with patch("app.services.pattern_service.pattern_repository") as mock_repo:
            mock_repo.get_pattern_by_id = AsyncMock(return_value=pattern)

            session = AsyncMock()
            result = await archive_pattern(session, pid)

            assert not result.transitioned

    @pytest.mark.asyncio
    async def test_archive_nonexistent_pattern(self):
        pid = make_pattern_id()

        with patch("app.services.pattern_service.pattern_repository") as mock_repo:
            mock_repo.get_pattern_by_id = AsyncMock(return_value=None)

            session = AsyncMock()
            result = await archive_pattern(session, pid)

            assert not result.transitioned


# ─── ValidationResult dataclass ──────────────────────────────────────────

class TestValidationResult:
    def test_success_result(self):
        pid = make_pattern_id()
        r = ValidationResult(
            pattern_id=pid,
            success=True,
            yq_charged_usd=0.0,
            yq_expected_usd=450.0,
        )
        assert r.success
        assert r.yq_charged_usd == 0.0

    def test_failure_result(self):
        pid = make_pattern_id()
        r = ValidationResult(
            pattern_id=pid,
            success=False,
            error_message="Timeout",
        )
        assert not r.success
        assert r.error_message == "Timeout"


# ─── ValidationOutcome ───────────────────────────────────────────────────

class TestValidationOutcome:
    def test_had_transition_true(self):
        transition = LifecycleTransition(
            pattern_id=make_pattern_id(),
            old_state="discovered",
            new_state="active",
            transitioned=True,
            reason="test",
        )
        outcome = ValidationOutcome(
            pattern_id=make_pattern_id(),
            validation_success=True,
            new_confidence_score=0.8,
            old_confidence_score=0.5,
            lifecycle_transition=transition,
        )
        assert outcome.had_transition

    def test_had_transition_false(self):
        transition = LifecycleTransition(
            pattern_id=make_pattern_id(),
            old_state="active",
            new_state="active",
            transitioned=False,
            reason="test",
        )
        outcome = ValidationOutcome(
            pattern_id=make_pattern_id(),
            validation_success=True,
            new_confidence_score=0.8,
            old_confidence_score=0.5,
            lifecycle_transition=transition,
        )
        assert not outcome.had_transition

    def test_had_transition_no_transition_object(self):
        outcome = ValidationOutcome(
            pattern_id=make_pattern_id(),
            validation_success=True,
            new_confidence_score=0.8,
            old_confidence_score=0.5,
        )
        assert not outcome.had_transition


# ─── record_validation_run ───────────────────────────────────────────────

class TestRecordValidationRun:
    @pytest.mark.asyncio
    async def test_records_successful_run(self):
        pid = make_pattern_id()
        run_id = uuid.uuid4()

        mock_run = MagicMock()
        mock_run.id = run_id

        with patch("app.services.validation_service.validation_repository") as mock_repo:
            mock_repo.create_validation_run = AsyncMock(return_value=mock_run)

            session = AsyncMock()
            result = ValidationResult(
                pattern_id=pid,
                success=True,
                yq_charged_usd=0.0,
                yq_expected_usd=450.0,
            )
            returned_id = await record_validation_run(session, result)

            assert returned_id == run_id
            mock_repo.create_validation_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_records_failed_run_with_error(self):
        pid = make_pattern_id()
        run_id = uuid.uuid4()

        mock_run = MagicMock()
        mock_run.id = run_id

        with patch("app.services.validation_service.validation_repository") as mock_repo:
            mock_repo.create_validation_run = AsyncMock(return_value=mock_run)

            session = AsyncMock()
            result = ValidationResult(
                pattern_id=pid,
                success=False,
                error_message="ITA timeout",
            )
            returned_id = await record_validation_run(
                session, result, manual_input_snapshot={"routing": "LH JFK FRA"}
            )

            assert returned_id == run_id
            call_kwargs = mock_repo.create_validation_run.call_args[1]
            assert call_kwargs["error_message"] == "ITA timeout"
            assert call_kwargs["manual_input_snapshot"] == {"routing": "LH JFK FRA"}


# ─── evaluate_validation_result ──────────────────────────────────────────

class TestEvaluateValidationResult:
    @pytest.mark.asyncio
    async def test_updates_confidence_and_lifecycle(self):
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid)
        now = datetime.now(timezone.utc)

        with (
            patch("app.services.validation_service.pattern_repository") as mock_pat_repo,
            patch("app.services.validation_service.validation_repository") as mock_val_repo,
            patch("app.services.validation_service.pattern_service") as mock_pat_svc,
        ):
            mock_pat_repo.get_pattern_by_id = AsyncMock(return_value=pattern)
            mock_pat_repo.update_confidence_score = AsyncMock()
            mock_pat_repo.update_pattern_fields = AsyncMock()

            mock_val_repo.get_recent_runs = AsyncMock(
                return_value=[make_mock_run(True), make_mock_run(True)]
            )
            mock_val_repo.get_last_validation_time = AsyncMock(return_value=now)

            mock_pat_svc.evaluate_lifecycle = AsyncMock(
                return_value=LifecycleTransition(
                    pattern_id=pid,
                    old_state="active",
                    new_state="active",
                    transitioned=False,
                    reason="Active",
                )
            )
            mock_pat_svc.recalculate_freshness_tier = AsyncMock(return_value=1)

            session = AsyncMock()
            outcome = await evaluate_validation_result(
                session, pid, latest_success=True, yq_savings_usd=350.0
            )

            assert outcome.new_confidence_score > 0
            assert outcome.old_confidence_score == 0.5
            mock_pat_repo.update_confidence_score.assert_called_once()
            mock_pat_svc.evaluate_lifecycle.assert_called_once()
            mock_pat_svc.recalculate_freshness_tier.assert_called_once()

    @pytest.mark.asyncio
    async def test_pattern_not_found(self):
        pid = make_pattern_id()

        with patch("app.services.validation_service.pattern_repository") as mock_repo:
            mock_repo.get_pattern_by_id = AsyncMock(return_value=None)

            session = AsyncMock()
            outcome = await evaluate_validation_result(session, pid, True)

            assert outcome.error == "Pattern not found"
            assert outcome.new_confidence_score == 0.0

    @pytest.mark.asyncio
    async def test_no_freshness_update_on_failure(self):
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid)

        with (
            patch("app.services.validation_service.pattern_repository") as mock_pat_repo,
            patch("app.services.validation_service.validation_repository") as mock_val_repo,
            patch("app.services.validation_service.pattern_service") as mock_pat_svc,
        ):
            mock_pat_repo.get_pattern_by_id = AsyncMock(return_value=pattern)
            mock_pat_repo.update_confidence_score = AsyncMock()
            mock_val_repo.get_recent_runs = AsyncMock(return_value=[])
            mock_val_repo.get_last_validation_time = AsyncMock(return_value=None)
            mock_pat_svc.evaluate_lifecycle = AsyncMock(
                return_value=LifecycleTransition(
                    pattern_id=pid, old_state="active", new_state="active",
                    transitioned=False, reason="",
                )
            )

            session = AsyncMock()
            outcome = await evaluate_validation_result(session, pid, False)

            assert outcome.new_freshness_tier is None
            mock_pat_svc.recalculate_freshness_tier.assert_not_called()


# ─── run_validation ──────────────────────────────────────────────────────

class TestRunValidation:
    @pytest.mark.asyncio
    async def test_skips_archived_pattern(self):
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.ARCHIVED.value)

        with patch("app.services.validation_service.pattern_repository") as mock_repo:
            mock_repo.get_pattern_by_id = AsyncMock(return_value=pattern)

            session = AsyncMock()
            outcome = await run_validation(session, pid)

            assert not outcome.validation_success
            assert "archived" in outcome.error.lower()

    @pytest.mark.asyncio
    async def test_skips_deprecated_pattern(self):
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.DEPRECATED.value)

        with patch("app.services.validation_service.pattern_repository") as mock_repo:
            mock_repo.get_pattern_by_id = AsyncMock(return_value=pattern)

            session = AsyncMock()
            outcome = await run_validation(session, pid)

            assert not outcome.validation_success
            assert "deprecated" in outcome.error.lower()

    @pytest.mark.asyncio
    async def test_pattern_not_found(self):
        pid = make_pattern_id()

        with patch("app.services.validation_service.pattern_repository") as mock_repo:
            mock_repo.get_pattern_by_id = AsyncMock(return_value=None)

            session = AsyncMock()
            outcome = await run_validation(session, pid)

            assert outcome.error == "Pattern not found"

    @pytest.mark.asyncio
    async def test_no_ita_client(self):
        """With no ITA client, records infrastructure error."""
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.ACTIVE.value)
        now = datetime.now(timezone.utc)

        with (
            patch("app.services.validation_service.pattern_repository") as mock_pat_repo,
            patch("app.services.validation_service.validation_repository") as mock_val_repo,
            patch("app.services.validation_service.pattern_service") as mock_pat_svc,
        ):
            mock_pat_repo.get_pattern_by_id = AsyncMock(return_value=pattern)
            mock_pat_repo.update_confidence_score = AsyncMock()

            mock_run = MagicMock()
            mock_run.id = uuid.uuid4()
            mock_val_repo.create_validation_run = AsyncMock(return_value=mock_run)
            mock_val_repo.get_recent_runs = AsyncMock(return_value=[])
            mock_val_repo.get_last_validation_time = AsyncMock(return_value=None)

            mock_pat_svc.evaluate_lifecycle = AsyncMock(
                return_value=LifecycleTransition(
                    pattern_id=pid, old_state="active", new_state="active",
                    transitioned=False, reason="",
                )
            )

            session = AsyncMock()
            outcome = await run_validation(session, pid, ita_client=None)

            assert not outcome.validation_success
            # The run should still be recorded
            mock_val_repo.create_validation_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_successful_ita_validation(self):
        """Successful ITA query with low YQ → success."""
        pid = make_pattern_id()
        pattern = make_mock_pattern(
            pid,
            LifecycleState.ACTIVE.value,
            expected_yq_savings_usd=400.0,
        )
        now = datetime.now(timezone.utc)

        mock_ita = AsyncMock()
        mock_ita.query = AsyncMock(return_value={
            "yq_charged_usd": 0.0,
            "base_fare_usd": 850.0,
            "proxy_used": "proxy1.example.com",
        })

        with (
            patch("app.services.validation_service.pattern_repository") as mock_pat_repo,
            patch("app.services.validation_service.validation_repository") as mock_val_repo,
            patch("app.services.validation_service.pattern_service") as mock_pat_svc,
        ):
            mock_pat_repo.get_pattern_by_id = AsyncMock(return_value=pattern)
            mock_pat_repo.update_confidence_score = AsyncMock()
            mock_pat_repo.update_pattern_fields = AsyncMock()

            mock_run = MagicMock()
            mock_run.id = uuid.uuid4()
            mock_val_repo.create_validation_run = AsyncMock(return_value=mock_run)
            mock_val_repo.get_recent_runs = AsyncMock(
                return_value=[make_mock_run(True)]
            )
            mock_val_repo.get_last_validation_time = AsyncMock(return_value=now)

            mock_pat_svc.evaluate_lifecycle = AsyncMock(
                return_value=LifecycleTransition(
                    pattern_id=pid, old_state="active", new_state="active",
                    transitioned=False, reason="Active",
                )
            )
            mock_pat_svc.recalculate_freshness_tier = AsyncMock(return_value=1)

            session = AsyncMock()
            outcome = await run_validation(session, pid, ita_client=mock_ita)

            assert outcome.validation_success
            assert outcome.new_confidence_score > 0

            # Verify ITA was called with the routing code
            mock_ita.query.assert_called_once_with("LH JFK FRA BKK")

    @pytest.mark.asyncio
    async def test_failed_ita_high_yq(self):
        """ITA returns high YQ → failure."""
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.ACTIVE.value)
        now = datetime.now(timezone.utc)

        mock_ita = AsyncMock()
        mock_ita.query = AsyncMock(return_value={
            "yq_charged_usd": 350.0,
            "base_fare_usd": 900.0,
        })

        with (
            patch("app.services.validation_service.pattern_repository") as mock_pat_repo,
            patch("app.services.validation_service.validation_repository") as mock_val_repo,
            patch("app.services.validation_service.pattern_service") as mock_pat_svc,
        ):
            mock_pat_repo.get_pattern_by_id = AsyncMock(return_value=pattern)
            mock_pat_repo.update_confidence_score = AsyncMock()

            mock_run = MagicMock()
            mock_run.id = uuid.uuid4()
            mock_val_repo.create_validation_run = AsyncMock(return_value=mock_run)
            mock_val_repo.get_recent_runs = AsyncMock(
                return_value=[make_mock_run(False)]
            )
            mock_val_repo.get_last_validation_time = AsyncMock(return_value=now)

            mock_pat_svc.evaluate_lifecycle = AsyncMock(
                return_value=LifecycleTransition(
                    pattern_id=pid, old_state="active", new_state="active",
                    transitioned=False, reason="",
                )
            )

            session = AsyncMock()
            outcome = await run_validation(session, pid, ita_client=mock_ita)

            assert not outcome.validation_success

    @pytest.mark.asyncio
    async def test_ita_exception_handled(self):
        """ITA client raises exception → error handled gracefully."""
        pid = make_pattern_id()
        pattern = make_mock_pattern(pid, LifecycleState.ACTIVE.value)
        now = datetime.now(timezone.utc)

        mock_ita = AsyncMock()
        mock_ita.query = AsyncMock(side_effect=TimeoutError("ITA timeout"))

        with (
            patch("app.services.validation_service.pattern_repository") as mock_pat_repo,
            patch("app.services.validation_service.validation_repository") as mock_val_repo,
            patch("app.services.validation_service.pattern_service") as mock_pat_svc,
        ):
            mock_pat_repo.get_pattern_by_id = AsyncMock(return_value=pattern)
            mock_pat_repo.update_confidence_score = AsyncMock()

            mock_run = MagicMock()
            mock_run.id = uuid.uuid4()
            mock_val_repo.create_validation_run = AsyncMock(return_value=mock_run)
            mock_val_repo.get_recent_runs = AsyncMock(return_value=[])
            mock_val_repo.get_last_validation_time = AsyncMock(return_value=None)

            mock_pat_svc.evaluate_lifecycle = AsyncMock(
                return_value=LifecycleTransition(
                    pattern_id=pid, old_state="active", new_state="active",
                    transitioned=False, reason="",
                )
            )

            session = AsyncMock()
            outcome = await run_validation(session, pid, ita_client=mock_ita)

            assert not outcome.validation_success
            # Error should be recorded
            call_kwargs = mock_val_repo.create_validation_run.call_args[1]
            assert "timeout" in call_kwargs["error_message"].lower()


# ─── get_consecutive_failure_count ───────────────────────────────────────

class TestGetConsecutiveFailureCount:
    @pytest.mark.asyncio
    async def test_delegates_to_repository(self):
        pid = make_pattern_id()

        with patch("app.services.validation_service.validation_repository") as mock_repo:
            mock_repo.get_consecutive_failures = AsyncMock(return_value=3)

            session = AsyncMock()
            count = await get_consecutive_failure_count(session, pid)

            assert count == 3
            mock_repo.get_consecutive_failures.assert_called_once_with(session, pid)


# ─── Validation tasks ───────────────────────────────────────────────────

class TestValidationTasks:
    def test_validate_single_pattern_error_handling(self):
        """Task returns error dict on exception, never raises."""
        from app.tasks.validation_tasks import validate_single_pattern

        with patch("app.tasks.validation_tasks._run_single_validation") as mock_run:
            mock_run.side_effect = RuntimeError("DB connection failed")

            result = validate_single_pattern("some-bad-id")

            assert result["success"] is False
            assert "error" in result

    def test_validate_tier_patterns_error_handling(self):
        """Task returns error dict on exception, never raises."""
        from app.tasks.validation_tasks import validate_tier_patterns

        with patch("app.tasks.validation_tasks._run_tier_validations") as mock_run:
            mock_run.side_effect = RuntimeError("Redis down")

            result = validate_tier_patterns(1)

            assert result["errors"] == 1
            assert "error" in result


# ─── Integration-style tests ────────────────────────────────────────────

class TestLifecycleIntegration:
    """Test realistic lifecycle sequences."""

    def test_threshold_constants_are_consistent(self):
        """Verify our thresholds make sense together."""
        assert DEGRADING_SUCCESS_RATE_THRESHOLD == 0.60
        assert DEGRADING_WINDOW_SIZE == 5
        assert RECOVERY_CONSECUTIVE_SUCCESSES == 2
        assert DEPRECATED_CONSECUTIVE_FAILURES == 3

    def test_tier_thresholds_are_correct(self):
        assert TIER_1_SAVINGS_THRESHOLD == 200.0
        assert TIER_2_SAVINGS_THRESHOLD == 50.0

    def test_success_rate_threshold_math(self):
        """2/5 = 40% < 60% → should trigger degrading."""
        rate = 2 / 5
        assert rate < DEGRADING_SUCCESS_RATE_THRESHOLD

        """3/5 = 60% is NOT < 60% → should NOT trigger degrading."""
        rate = 3 / 5
        assert not (rate < DEGRADING_SUCCESS_RATE_THRESHOLD)
