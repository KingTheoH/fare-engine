"""
test_scoring_service.py — Tests for scoring_service.py

Tests the confidence score calculation formula and all its components.
Pure calculation — no database or async needed.
"""

import math
from datetime import datetime, timedelta, timezone

import pytest

from app.services.scoring_service import (
    ConfidenceBreakdown,
    MAX_RECENT_RUNS,
    MULTI_SOURCE_THRESHOLD_FULL,
    MULTI_SOURCE_THRESHOLD_PARTIAL,
    RECENCY_HALF_LIFE_DAYS,
    W_MULTI_SOURCE,
    W_RECENCY,
    W_SOURCE,
    W_VALIDATION,
    _clamp,
    calculate_confidence_score,
    calculate_multi_source_bonus,
    calculate_recency_factor,
    calculate_validation_success_rate,
)


# ─── _clamp ────────────────────────────────────────────────────────────────

class TestClamp:
    def test_clamp_within_range(self):
        assert _clamp(0.5) == 0.5

    def test_clamp_at_zero(self):
        assert _clamp(0.0) == 0.0

    def test_clamp_at_one(self):
        assert _clamp(1.0) == 1.0

    def test_clamp_below_zero(self):
        assert _clamp(-0.5) == 0.0

    def test_clamp_above_one(self):
        assert _clamp(1.5) == 1.0

    def test_clamp_custom_range(self):
        assert _clamp(5, 0, 10) == 5
        assert _clamp(-1, 0, 10) == 0
        assert _clamp(15, 0, 10) == 10


# ─── calculate_validation_success_rate ─────────────────────────────────────

class TestValidationSuccessRate:
    def test_no_runs(self):
        assert calculate_validation_success_rate([]) == 0.0

    def test_all_successes(self):
        runs = [{"success": True}] * 5
        rate = calculate_validation_success_rate(runs)
        assert rate == pytest.approx(1.0)

    def test_all_failures(self):
        runs = [{"success": False}] * 5
        rate = calculate_validation_success_rate(runs)
        assert rate == pytest.approx(0.0)

    def test_single_success(self):
        runs = [{"success": True}]
        assert calculate_validation_success_rate(runs) == pytest.approx(1.0)

    def test_single_failure(self):
        runs = [{"success": False}]
        assert calculate_validation_success_rate(runs) == pytest.approx(0.0)

    def test_mixed_results_recent_success_weighted_higher(self):
        """Recent success (index 0) has higher weight than old failure (index 1)."""
        runs = [{"success": True}, {"success": False}]
        rate = calculate_validation_success_rate(runs)
        # weight_0 = 0.9^0 = 1.0, weight_1 = 0.9^1 = 0.9
        # weighted_sum = 1.0 * 1.0 + 0.9 * 0.0 = 1.0
        # weight_total = 1.0 + 0.9 = 1.9
        # rate = 1.0 / 1.9 ≈ 0.5263
        assert rate == pytest.approx(1.0 / 1.9)

    def test_mixed_results_recent_failure_weighted_higher(self):
        """Recent failure (index 0) drags score down more."""
        runs = [{"success": False}, {"success": True}]
        rate = calculate_validation_success_rate(runs)
        # weighted_sum = 1.0 * 0.0 + 0.9 * 1.0 = 0.9
        # weight_total = 1.0 + 0.9 = 1.9
        # rate = 0.9 / 1.9 ≈ 0.4737
        assert rate == pytest.approx(0.9 / 1.9)

    def test_half_and_half(self):
        """Alternating pattern — recent runs get more weight."""
        runs = [
            {"success": True}, {"success": False},
            {"success": True}, {"success": False},
        ]
        rate = calculate_validation_success_rate(runs)
        # Successes at positions 0 and 2 (weights 1.0, 0.81)
        # Failures at positions 1 and 3 (weights 0.9, 0.729)
        expected_sum = 1.0 + 0.81
        expected_total = 1.0 + 0.9 + 0.81 + 0.729
        assert rate == pytest.approx(expected_sum / expected_total)

    def test_respects_max_runs(self):
        """Only considers the last N runs."""
        # 12 runs total, but max_runs=3
        runs = [{"success": True}] * 3 + [{"success": False}] * 9
        rate = calculate_validation_success_rate(runs, max_runs=3)
        assert rate == pytest.approx(1.0)  # only sees the 3 successes

    def test_default_max_runs(self):
        """Default max is MAX_RECENT_RUNS (10)."""
        runs = [{"success": True}] * 15
        rate = calculate_validation_success_rate(runs)
        assert rate == pytest.approx(1.0)
        # Only first 10 should matter
        assert MAX_RECENT_RUNS == 10

    def test_missing_success_key_treated_as_false(self):
        runs = [{"success": True}, {}]
        rate = calculate_validation_success_rate(runs)
        # Second run has no 'success' key → False
        assert rate == pytest.approx(1.0 / 1.9)


# ─── calculate_recency_factor ─────────────────────────────────────────────

class TestRecencyFactor:
    def test_never_validated(self):
        assert calculate_recency_factor(None) == 0.0

    def test_just_validated(self):
        now = datetime.now(timezone.utc)
        factor = calculate_recency_factor(now, now)
        assert factor == pytest.approx(1.0)

    def test_at_half_life(self):
        now = datetime.now(timezone.utc)
        validated_at = now - timedelta(days=RECENCY_HALF_LIFE_DAYS)
        factor = calculate_recency_factor(validated_at, now)
        assert factor == pytest.approx(0.5, abs=0.01)

    def test_at_double_half_life(self):
        now = datetime.now(timezone.utc)
        validated_at = now - timedelta(days=RECENCY_HALF_LIFE_DAYS * 2)
        factor = calculate_recency_factor(validated_at, now)
        assert factor == pytest.approx(0.25, abs=0.01)

    def test_one_day_ago(self):
        now = datetime.now(timezone.utc)
        validated_at = now - timedelta(days=1)
        factor = calculate_recency_factor(validated_at, now)
        expected = math.pow(2, -1.0 / RECENCY_HALF_LIFE_DAYS)
        assert factor == pytest.approx(expected, abs=0.001)

    def test_very_old(self):
        now = datetime.now(timezone.utc)
        validated_at = now - timedelta(days=365)
        factor = calculate_recency_factor(validated_at, now)
        assert factor < 0.01

    def test_future_validation_clamps_to_one(self):
        now = datetime.now(timezone.utc)
        validated_at = now + timedelta(hours=1)
        factor = calculate_recency_factor(validated_at, now)
        assert factor == pytest.approx(1.0)

    def test_naive_datetime_treated_as_utc(self):
        """Naive datetimes are assumed to be UTC."""
        now = datetime(2025, 6, 15, 12, 0, 0)
        validated_at = datetime(2025, 6, 15, 12, 0, 0)
        factor = calculate_recency_factor(validated_at, now)
        assert factor == pytest.approx(1.0)


# ─── calculate_multi_source_bonus ──────────────────────────────────────────

class TestMultiSourceBonus:
    def test_zero_sources(self):
        assert calculate_multi_source_bonus(0) == 0.0

    def test_one_source(self):
        assert calculate_multi_source_bonus(1) == 0.0

    def test_two_sources(self):
        assert calculate_multi_source_bonus(2) == 0.5

    def test_three_sources(self):
        assert calculate_multi_source_bonus(3) == 1.0

    def test_many_sources(self):
        assert calculate_multi_source_bonus(10) == 1.0

    def test_thresholds_match_constants(self):
        assert calculate_multi_source_bonus(MULTI_SOURCE_THRESHOLD_PARTIAL) == 0.5
        assert calculate_multi_source_bonus(MULTI_SOURCE_THRESHOLD_FULL) == 1.0


# ─── calculate_confidence_score (full formula) ────────────────────────────

class TestConfidenceScore:
    def test_no_data_returns_source_weight_only(self):
        """With no runs, no recency, only source weight contributes."""
        breakdown = calculate_confidence_score(
            validation_runs=[],
            source_post_weight=0.8,
            independent_source_count=1,
            last_validated_at=None,
        )
        assert breakdown.final_score == pytest.approx(W_SOURCE * 0.8, abs=0.01)
        assert breakdown.validation_component == pytest.approx(0.0)
        assert breakdown.recency_component == pytest.approx(0.0)
        assert breakdown.multi_source_component == pytest.approx(0.0)

    def test_perfect_score(self):
        """All components maxed out → final score near 1.0."""
        now = datetime.now(timezone.utc)
        breakdown = calculate_confidence_score(
            validation_runs=[{"success": True}] * 10,
            source_post_weight=1.0,
            independent_source_count=5,
            last_validated_at=now,
            now=now,
        )
        expected = W_VALIDATION * 1.0 + W_SOURCE * 1.0 + W_MULTI_SOURCE * 1.0 + W_RECENCY * 1.0
        assert breakdown.final_score == pytest.approx(expected, abs=0.01)
        assert breakdown.final_score == pytest.approx(1.0, abs=0.01)

    def test_all_failures_low_source(self):
        """All failures + low source weight → very low score."""
        now = datetime.now(timezone.utc)
        breakdown = calculate_confidence_score(
            validation_runs=[{"success": False}] * 5,
            source_post_weight=0.2,
            independent_source_count=1,
            last_validated_at=now - timedelta(days=60),
            now=now,
        )
        assert breakdown.final_score < 0.15
        assert breakdown.validation_component == pytest.approx(0.0)

    def test_source_weight_clamped(self):
        """Source weight > 1.0 should be clamped."""
        breakdown = calculate_confidence_score(
            validation_runs=[],
            source_post_weight=1.5,
        )
        assert breakdown.source_component == pytest.approx(W_SOURCE * 1.0)

    def test_breakdown_has_all_fields(self):
        now = datetime.now(timezone.utc)
        breakdown = calculate_confidence_score(
            validation_runs=[{"success": True}, {"success": False}],
            source_post_weight=0.7,
            independent_source_count=2,
            last_validated_at=now,
            now=now,
        )
        assert isinstance(breakdown, ConfidenceBreakdown)
        assert breakdown.total_runs_considered == 2
        assert 0 <= breakdown.validation_success_rate <= 1
        assert 0 <= breakdown.source_post_weight <= 1
        assert 0 <= breakdown.multi_source_bonus <= 1
        assert 0 <= breakdown.recency_factor <= 1
        assert 0 <= breakdown.final_score <= 1

    def test_weights_sum_to_one(self):
        """The four weights must sum to 1.0."""
        total = W_VALIDATION + W_SOURCE + W_MULTI_SOURCE + W_RECENCY
        assert total == pytest.approx(1.0)

    def test_multi_source_bonus_contributes(self):
        """3+ sources should add the multi_source component."""
        breakdown_single = calculate_confidence_score(
            validation_runs=[],
            source_post_weight=0.5,
            independent_source_count=1,
        )
        breakdown_multi = calculate_confidence_score(
            validation_runs=[],
            source_post_weight=0.5,
            independent_source_count=3,
        )
        diff = breakdown_multi.final_score - breakdown_single.final_score
        assert diff == pytest.approx(W_MULTI_SOURCE * 1.0, abs=0.01)

    def test_recency_decays_over_time(self):
        """Score should decrease as time since last validation increases."""
        now = datetime.now(timezone.utc)
        runs = [{"success": True}] * 5

        breakdown_recent = calculate_confidence_score(
            validation_runs=runs,
            source_post_weight=0.5,
            last_validated_at=now,
            now=now,
        )
        breakdown_old = calculate_confidence_score(
            validation_runs=runs,
            source_post_weight=0.5,
            last_validated_at=now - timedelta(days=30),
            now=now,
        )
        assert breakdown_recent.final_score > breakdown_old.final_score

    def test_mixed_realistic_scenario(self):
        """Realistic scenario: 7/10 successes, decent source, 2 sources, recent."""
        now = datetime.now(timezone.utc)
        runs = [{"success": True}] * 7 + [{"success": False}] * 3
        breakdown = calculate_confidence_score(
            validation_runs=runs,
            source_post_weight=0.65,
            independent_source_count=2,
            last_validated_at=now - timedelta(days=3),
            now=now,
        )
        # Should be a moderate-to-good score
        assert 0.4 < breakdown.final_score < 0.85

    def test_negative_source_weight_clamped(self):
        breakdown = calculate_confidence_score(
            validation_runs=[],
            source_post_weight=-0.5,
        )
        assert breakdown.source_component == pytest.approx(0.0)

    def test_default_now_used(self):
        """If now is not provided, defaults to UTC now."""
        validated_at = datetime.now(timezone.utc)
        breakdown = calculate_confidence_score(
            validation_runs=[{"success": True}],
            source_post_weight=0.5,
            last_validated_at=validated_at,
            # now=None — should use current time
        )
        # Recency should be near 1.0 since we just set last_validated_at
        assert breakdown.recency_factor > 0.95


# ─── Edge cases ────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_everything(self):
        breakdown = calculate_confidence_score(
            validation_runs=[],
            source_post_weight=0.0,
            independent_source_count=0,
            last_validated_at=None,
        )
        assert breakdown.final_score == pytest.approx(0.0)

    def test_final_score_never_exceeds_one(self):
        """Even with all max inputs, score stays <= 1.0."""
        now = datetime.now(timezone.utc)
        breakdown = calculate_confidence_score(
            validation_runs=[{"success": True}] * 20,
            source_post_weight=2.0,
            independent_source_count=100,
            last_validated_at=now,
            now=now,
        )
        assert breakdown.final_score <= 1.0

    def test_final_score_never_below_zero(self):
        breakdown = calculate_confidence_score(
            validation_runs=[{"success": False}] * 20,
            source_post_weight=-1.0,
            independent_source_count=0,
            last_validated_at=None,
        )
        assert breakdown.final_score >= 0.0
