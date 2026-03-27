"""Tests for dump pattern schemas."""

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.enums import DumpType, LifecycleState, PatternSource
from app.schemas.dump_pattern import (
    DumpPatternCreate,
    DumpPatternResponse,
    DumpPatternSummary,
    DumpPatternUpdate,
)
from app.schemas.manual_input import ManualInputBundle


def _valid_create(**overrides) -> dict:
    base = {
        "dump_type": DumpType.TP_DUMP,
        "origin_iata": "JFK",
        "destination_iata": "BKK",
        "ticketing_carrier_iata": "LH",
        "operating_carriers": ["LH", "LH", "AA"],
        "routing_points": ["FRA"],
        "ita_routing_code": "FORCE LH:JFK-FRA / FORCE LH:FRA-BKK / FORCE AA:BKK-JFK",
        "expected_yq_savings_usd": 580.0,
        "source": PatternSource.FLYERTALK,
        "source_url": "https://www.flyertalk.com/forum/post/12345",
        "source_post_weight": 0.8,
    }
    base.update(overrides)
    return base


class TestDumpPatternCreate:
    def test_valid_tp_dump(self):
        p = DumpPatternCreate(**_valid_create())
        assert p.dump_type == DumpType.TP_DUMP
        assert p.origin_iata == "JFK"
        assert p.operating_carriers == ["LH", "LH", "AA"]
        assert p.routing_points == ["FRA"]

    def test_carrier_switch_no_routing_points(self):
        p = DumpPatternCreate(
            **_valid_create(
                dump_type=DumpType.CARRIER_SWITCH,
                routing_points=[],
                ita_routing_code="FORCE QR:JFK-DOH-BKK / FORCE AA:BKK-JFK",
            )
        )
        assert p.dump_type == DumpType.CARRIER_SWITCH
        assert p.routing_points == []

    def test_fare_basis_with_hint(self):
        p = DumpPatternCreate(
            **_valid_create(
                dump_type=DumpType.FARE_BASIS,
                fare_basis_hint="YLOWUS",
            )
        )
        assert p.fare_basis_hint == "YLOWUS"

    def test_invalid_origin_length(self):
        with pytest.raises(ValidationError):
            DumpPatternCreate(**_valid_create(origin_iata="JF"))

    def test_invalid_carrier_length(self):
        with pytest.raises(ValidationError):
            DumpPatternCreate(**_valid_create(ticketing_carrier_iata="LHX"))

    def test_empty_routing_code_rejected(self):
        with pytest.raises(ValidationError):
            DumpPatternCreate(**_valid_create(ita_routing_code=""))

    def test_negative_savings_rejected(self):
        with pytest.raises(ValidationError):
            DumpPatternCreate(**_valid_create(expected_yq_savings_usd=-50))

    def test_post_weight_bounds(self):
        with pytest.raises(ValidationError):
            DumpPatternCreate(**_valid_create(source_post_weight=1.5))
        with pytest.raises(ValidationError):
            DumpPatternCreate(**_valid_create(source_post_weight=-0.1))

    def test_defaults(self):
        p = DumpPatternCreate(**_valid_create())
        assert p.backup_pattern_id is None
        assert p.fare_basis_hint is None


class TestDumpPatternUpdate:
    def test_all_optional(self):
        u = DumpPatternUpdate()
        assert u.dump_type is None
        assert u.lifecycle_state is None

    def test_partial_update(self):
        u = DumpPatternUpdate(
            lifecycle_state=LifecycleState.ACTIVE,
            confidence_score=0.92,
        )
        assert u.lifecycle_state == LifecycleState.ACTIVE
        assert u.confidence_score == 0.92
        assert u.origin_iata is None


class TestDumpPatternSummary:
    def test_excludes_manual_input_bundle(self):
        """Summary must NOT include manual_input_bundle (too heavy for list views)."""
        assert "manual_input_bundle" not in DumpPatternSummary.model_fields

    def test_excludes_heavy_fields(self):
        """Summary should not include fare_basis_hint, ita_routing_code, etc."""
        assert "fare_basis_hint" not in DumpPatternSummary.model_fields
        assert "ita_routing_code" not in DumpPatternSummary.model_fields
        assert "source_post_weight" not in DumpPatternSummary.model_fields

    def test_includes_essential_fields(self):
        """Summary must include fields needed for leaderboard display."""
        fields = DumpPatternSummary.model_fields
        assert "id" in fields
        assert "dump_type" in fields
        assert "lifecycle_state" in fields
        assert "origin_iata" in fields
        assert "destination_iata" in fields
        assert "expected_yq_savings_usd" in fields
        assert "confidence_score" in fields

    def test_from_dict(self):
        now = datetime.now(timezone.utc)
        summary = DumpPatternSummary(
            id=uuid.uuid4(),
            dump_type="TP_DUMP",
            lifecycle_state="active",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH", "AA"],
            routing_points=["FRA"],
            expected_yq_savings_usd=580.0,
            confidence_score=0.85,
            freshness_tier=1,
            source="FLYERTALK",
            source_url="https://flyertalk.com/post/123",
            created_at=now,
            updated_at=now,
        )
        assert summary.dump_type == "TP_DUMP"
        assert summary.lifecycle_state == "active"


class TestDumpPatternResponse:
    def test_includes_manual_input_bundle(self):
        """Response MUST include manual_input_bundle for detail views."""
        assert "manual_input_bundle" in DumpPatternResponse.model_fields

    def test_includes_all_fields(self):
        fields = DumpPatternResponse.model_fields
        assert "fare_basis_hint" in fields
        assert "ita_routing_code" in fields
        assert "source_post_weight" in fields
        assert "backup_pattern_id" in fields

    def test_from_dict_with_bundle(self):
        now = datetime.now(timezone.utc)
        bundle = ManualInputBundle(
            routing_code_string="FORCE LH:JFK-FRA",
            human_description="JFK → FRA (LH)",
            ita_matrix_steps=["1. Go to ITA Matrix", "2. Search"],
            expected_yq_savings_usd=580.0,
            expected_yq_carrier="LH",
            validation_timestamp=now,
            confidence_score=0.85,
        )
        resp = DumpPatternResponse(
            id=uuid.uuid4(),
            dump_type="TP_DUMP",
            lifecycle_state="active",
            origin_iata="JFK",
            destination_iata="FRA",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH"],
            routing_points=[],
            fare_basis_hint=None,
            ita_routing_code="FORCE LH:JFK-FRA",
            manual_input_bundle=bundle,
            expected_yq_savings_usd=580.0,
            confidence_score=0.85,
            freshness_tier=1,
            source="FLYERTALK",
            source_url=None,
            source_post_weight=0.8,
            backup_pattern_id=None,
            created_at=now,
            updated_at=now,
        )
        assert resp.manual_input_bundle is not None
        assert resp.manual_input_bundle.expected_yq_carrier == "LH"

    def test_nullable_bundle(self):
        """Newly discovered patterns may not have a bundle yet."""
        now = datetime.now(timezone.utc)
        resp = DumpPatternResponse(
            id=uuid.uuid4(),
            dump_type="TP_DUMP",
            lifecycle_state="discovered",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH", "AA"],
            routing_points=["FRA"],
            fare_basis_hint=None,
            ita_routing_code="FORCE LH:JFK-FRA-BKK",
            manual_input_bundle=None,
            expected_yq_savings_usd=None,
            confidence_score=0.0,
            freshness_tier=3,
            source="MANUAL",
            source_url=None,
            source_post_weight=0.5,
            backup_pattern_id=None,
            created_at=now,
            updated_at=now,
        )
        assert resp.manual_input_bundle is None
        assert resp.lifecycle_state == "discovered"
