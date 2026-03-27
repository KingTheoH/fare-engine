"""Tests for validation run schemas."""

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.manual_input import ManualInputBundle
from app.schemas.validation_run import ValidationRunCreate, ValidationRunResponse


class TestValidationRunCreate:
    def test_successful_run(self):
        v = ValidationRunCreate(
            pattern_id=uuid.uuid4(),
            success=True,
            yq_charged_usd=0.0,
            yq_expected_usd=580.0,
            base_fare_usd=450.0,
        )
        assert v.success is True
        assert v.yq_charged_usd == 0.0

    def test_failed_run_with_error(self):
        v = ValidationRunCreate(
            pattern_id=uuid.uuid4(),
            success=False,
            error_message="Timeout waiting for ITA Matrix results",
            proxy_used="proxy-us-east-1.example.com:8080",
        )
        assert v.success is False
        assert "Timeout" in v.error_message

    def test_with_manual_input_snapshot(self):
        now = datetime.now(timezone.utc)
        bundle = ManualInputBundle(
            routing_code_string="FORCE LH:JFK-FRA",
            human_description="JFK → FRA",
            ita_matrix_steps=["1. Search"],
            expected_yq_savings_usd=580.0,
            expected_yq_carrier="LH",
            validation_timestamp=now,
            confidence_score=0.9,
        )
        v = ValidationRunCreate(
            pattern_id=uuid.uuid4(),
            success=True,
            manual_input_snapshot=bundle,
        )
        assert v.manual_input_snapshot is not None
        assert v.manual_input_snapshot.expected_yq_carrier == "LH"

    def test_negative_yq_rejected(self):
        with pytest.raises(ValidationError):
            ValidationRunCreate(
                pattern_id=uuid.uuid4(),
                success=True,
                yq_charged_usd=-10.0,
            )


class TestValidationRunResponse:
    def test_from_dict(self):
        now = datetime.now(timezone.utc)
        resp = ValidationRunResponse(
            id=uuid.uuid4(),
            pattern_id=uuid.uuid4(),
            ran_at=now,
            success=True,
            yq_charged_usd=0.0,
            yq_expected_usd=580.0,
            base_fare_usd=450.0,
            raw_ita_response={"fare_class": "Y", "segments": []},
            manual_input_snapshot={"routing_code_string": "FORCE LH:JFK-FRA"},
            error_message=None,
            proxy_used=None,
        )
        assert resp.success is True
        assert resp.raw_ita_response["fare_class"] == "Y"
