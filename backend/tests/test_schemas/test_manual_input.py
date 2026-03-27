"""Tests for ManualInputBundle — the most critical schema."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.manual_input import ManualInputBundle


def _valid_bundle(**overrides) -> dict:
    """Factory for valid ManualInputBundle data."""
    base = {
        "routing_code_string": "FORCE LH:JFK-FRA / FORCE LH:FRA-BKK / FORCE AA:BKK-JFK",
        "human_description": "JFK → Frankfurt (LH) → Bangkok (LH) // Bangkok → JFK (AA)",
        "ita_matrix_steps": [
            "1. Go to matrix.itasoftware.com",
            "2. Enter JFK as origin, BKK as destination",
            "3. Paste routing code into 'Routing codes' field",
            "4. Click 'Search'",
            "5. Verify YQ is $0 or near-$0 in fare breakdown",
        ],
        "expected_yq_savings_usd": 580.0,
        "expected_yq_carrier": "LH",
        "validation_timestamp": datetime.now(timezone.utc).isoformat(),
        "confidence_score": 0.85,
        "backup_routing_code": None,
        "notes": None,
    }
    base.update(overrides)
    return base


class TestManualInputBundle:
    def test_valid_bundle(self):
        bundle = ManualInputBundle(**_valid_bundle())
        assert bundle.routing_code_string.startswith("FORCE LH")
        assert len(bundle.ita_matrix_steps) == 5
        assert bundle.expected_yq_savings_usd == 580.0
        assert bundle.expected_yq_carrier == "LH"
        assert bundle.confidence_score == 0.85
        assert bundle.backup_routing_code is None
        assert bundle.notes is None

    def test_with_backup_and_notes(self):
        bundle = ManualInputBundle(
            **_valid_bundle(
                backup_routing_code="FORCE LX:JFK-ZRH / FORCE LX:ZRH-BKK / FORCE AA:BKK-JFK",
                notes="Works best in Y class. Avoid peak summer dates.",
            )
        )
        assert bundle.backup_routing_code is not None
        assert "LX" in bundle.backup_routing_code
        assert "Y class" in bundle.notes

    def test_empty_steps_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            ManualInputBundle(**_valid_bundle(ita_matrix_steps=[]))
        assert "ita_matrix_steps" in str(exc_info.value)

    def test_negative_savings_rejected(self):
        with pytest.raises(ValidationError):
            ManualInputBundle(**_valid_bundle(expected_yq_savings_usd=-100.0))

    def test_confidence_above_1_rejected(self):
        with pytest.raises(ValidationError):
            ManualInputBundle(**_valid_bundle(confidence_score=1.5))

    def test_confidence_below_0_rejected(self):
        with pytest.raises(ValidationError):
            ManualInputBundle(**_valid_bundle(confidence_score=-0.1))

    def test_carrier_code_validation(self):
        # Too short
        with pytest.raises(ValidationError):
            ManualInputBundle(**_valid_bundle(expected_yq_carrier="L"))
        # Too long
        with pytest.raises(ValidationError):
            ManualInputBundle(**_valid_bundle(expected_yq_carrier="LHX"))

    def test_serialization_to_json(self):
        bundle = ManualInputBundle(**_valid_bundle())
        json_str = bundle.model_dump_json()
        assert "routing_code_string" in json_str
        assert "ita_matrix_steps" in json_str

    def test_round_trip_serialization(self):
        bundle = ManualInputBundle(**_valid_bundle())
        data = bundle.model_dump()
        bundle2 = ManualInputBundle.model_validate(data)
        assert bundle2.routing_code_string == bundle.routing_code_string
        assert bundle2.ita_matrix_steps == bundle.ita_matrix_steps
        assert bundle2.expected_yq_savings_usd == bundle.expected_yq_savings_usd

    def test_self_contained_bundle(self):
        """Verify the bundle contains everything an agent needs."""
        bundle = ManualInputBundle(**_valid_bundle())
        # Must have routing code (the thing they paste)
        assert len(bundle.routing_code_string) > 0
        # Must have human-readable description
        assert len(bundle.human_description) > 0
        # Must have at least one step
        assert len(bundle.ita_matrix_steps) >= 1
        # Must identify the carrier being dumped
        assert len(bundle.expected_yq_carrier) == 2
        # Must have savings amount
        assert bundle.expected_yq_savings_usd > 0
        # Must have validation freshness indicator
        assert bundle.validation_timestamp is not None
        assert bundle.confidence_score >= 0.0
