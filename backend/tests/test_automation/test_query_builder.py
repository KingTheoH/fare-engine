"""
Tests for the ITA Matrix query builder and manual input bundle generator.

Tests cover:
- Routing code generation for all 4 dump types
- Backup routing generation
- Manual input bundle generation
- Round-trip: pattern → routing code → manual bundle
- Edge cases (missing data, invalid dump types)
- Fixture-driven tests using dump_patterns.json
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Add project root to path so automation package is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from automation.query_builder import (
    PatternInput,
    build_routing_code,
    generate_backup_routing_code,
)
from automation.manual_input import (
    build_human_description,
    build_ita_matrix_steps,
    build_notes,
    generate_manual_input_bundle,
)

# ─── Fixtures ───────────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def fixtures() -> list[dict]:
    """Load test fixtures from dump_patterns.json."""
    with open(FIXTURES_DIR / "dump_patterns.json") as f:
        return json.load(f)


def _pattern_from_fixture(fix: dict) -> PatternInput:
    """Convert a fixture dict to a PatternInput."""
    return PatternInput(
        dump_type=fix["dump_type"],
        origin_iata=fix["origin_iata"],
        destination_iata=fix["destination_iata"],
        ticketing_carrier_iata=fix["ticketing_carrier_iata"],
        operating_carriers=fix["operating_carriers"],
        routing_points=fix["routing_points"],
        fare_basis_hint=fix.get("fare_basis_hint"),
    )


# ─── TP_DUMP Tests ──────────────────────────────────────────────────────────


class TestTPDump:
    def test_classic_lh_jfk_bkk(self):
        pattern = PatternInput(
            dump_type="TP_DUMP",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH", "LH", "AA"],
            routing_points=["FRA"],
        )
        code = build_routing_code(pattern)
        assert code == "FORCE LH:JFK-FRA / FORCE LH:FRA-BKK / FORCE AA:BKK-JFK"

    def test_ba_lax_sin(self):
        pattern = PatternInput(
            dump_type="TP_DUMP",
            origin_iata="LAX",
            destination_iata="SIN",
            ticketing_carrier_iata="BA",
            operating_carriers=["BA", "BA", "AA"],
            routing_points=["LHR"],
        )
        code = build_routing_code(pattern)
        assert code == "FORCE BA:LAX-LHR / FORCE BA:LHR-SIN / FORCE AA:SIN-LAX"

    def test_no_return_carrier(self):
        """Pattern with only outbound carriers (no dedicated return)."""
        pattern = PatternInput(
            dump_type="TP_DUMP",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH", "LH"],
            routing_points=["FRA"],
        )
        code = build_routing_code(pattern)
        assert code == "FORCE LH:JFK-FRA / FORCE LH:FRA-BKK"


# ─── CARRIER_SWITCH Tests ───────────────────────────────────────────────────


class TestCarrierSwitch:
    def test_qr_jfk_bkk(self):
        pattern = PatternInput(
            dump_type="CARRIER_SWITCH",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="QR",
            operating_carriers=["QR", "AA"],
            routing_points=["DOH"],
        )
        code = build_routing_code(pattern)
        assert code == "FORCE QR:JFK-DOH-BKK / FORCE AA:BKK-JFK"

    def test_ek_lax_sin(self):
        pattern = PatternInput(
            dump_type="CARRIER_SWITCH",
            origin_iata="LAX",
            destination_iata="SIN",
            ticketing_carrier_iata="EK",
            operating_carriers=["EK", "AA"],
            routing_points=["DXB"],
        )
        code = build_routing_code(pattern)
        assert code == "FORCE EK:LAX-DXB-SIN / FORCE AA:SIN-LAX"

    def test_single_carrier_no_return(self):
        """Carrier switch with same carrier throughout — no return split."""
        pattern = PatternInput(
            dump_type="CARRIER_SWITCH",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="EY",
            operating_carriers=["EY"],
            routing_points=["AUH"],
        )
        code = build_routing_code(pattern)
        assert code == "FORCE EY:JFK-AUH-BKK"


# ─── FARE_BASIS Tests ───────────────────────────────────────────────────────


class TestFareBasis:
    def test_lh_ylowus(self):
        pattern = PatternInput(
            dump_type="FARE_BASIS",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH", "AA"],
            routing_points=["FRA"],
            fare_basis_hint="YLOWUS",
        )
        code = build_routing_code(pattern)
        assert code == "FORCE LH:JFK-FRA-BKK BC=YLOWUS / FORCE AA:BKK-JFK"

    def test_ba_wowgb(self):
        pattern = PatternInput(
            dump_type="FARE_BASIS",
            origin_iata="JFK",
            destination_iata="LHR",
            ticketing_carrier_iata="BA",
            operating_carriers=["BA", "AA"],
            routing_points=[],
            fare_basis_hint="WOWGB",
        )
        code = build_routing_code(pattern)
        assert code == "FORCE BA:JFK-LHR BC=WOWGB / FORCE AA:LHR-JFK"

    def test_missing_fare_basis_raises(self):
        pattern = PatternInput(
            dump_type="FARE_BASIS",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH"],
            routing_points=["FRA"],
            fare_basis_hint=None,
        )
        with pytest.raises(ValueError, match="fare_basis_hint"):
            build_routing_code(pattern)


# ─── ALLIANCE_RULE Tests ────────────────────────────────────────────────────


class TestAllianceRule:
    def test_ba_aa_jfk_syd(self):
        pattern = PatternInput(
            dump_type="ALLIANCE_RULE",
            origin_iata="JFK",
            destination_iata="SYD",
            ticketing_carrier_iata="BA",
            operating_carriers=["BA", "AA"],
            routing_points=["LHR"],
        )
        code = build_routing_code(pattern)
        assert code == "FORCE BA/AA:JFK-LHR-SYD / FORCE BA/AA:SYD-LHR-JFK"

    def test_lh_nh_jfk_nrt(self):
        pattern = PatternInput(
            dump_type="ALLIANCE_RULE",
            origin_iata="JFK",
            destination_iata="NRT",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH", "NH"],
            routing_points=["FRA"],
        )
        code = build_routing_code(pattern)
        assert code == "FORCE LH/NH:JFK-FRA-NRT / FORCE LH/NH:NRT-FRA-JFK"

    def test_insufficient_carriers_raises(self):
        pattern = PatternInput(
            dump_type="ALLIANCE_RULE",
            origin_iata="JFK",
            destination_iata="SYD",
            ticketing_carrier_iata="BA",
            operating_carriers=["BA"],
            routing_points=["LHR"],
        )
        with pytest.raises(ValueError, match="2 operating carriers"):
            build_routing_code(pattern)

    def test_same_carrier_twice_raises(self):
        pattern = PatternInput(
            dump_type="ALLIANCE_RULE",
            origin_iata="JFK",
            destination_iata="SYD",
            ticketing_carrier_iata="BA",
            operating_carriers=["BA", "BA"],
            routing_points=["LHR"],
        )
        with pytest.raises(ValueError, match="2 distinct"):
            build_routing_code(pattern)


# ─── Unknown Dump Type ──────────────────────────────────────────────────────


class TestUnknownDumpType:
    def test_unknown_type_raises(self):
        pattern = PatternInput(
            dump_type="MAGIC_DUMP",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH"],
            routing_points=[],
        )
        with pytest.raises(ValueError, match="Unknown dump type"):
            build_routing_code(pattern)


# ─── Backup Routing ─────────────────────────────────────────────────────────


class TestBackupRouting:
    def test_lh_backup_uses_lx(self):
        """LH primary should generate LX backup with ZRH hub."""
        pattern = PatternInput(
            dump_type="TP_DUMP",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH", "LH", "AA"],
            routing_points=["FRA"],
        )
        backup = generate_backup_routing_code(pattern)
        assert backup is not None
        assert "LX" in backup
        assert "ZRH" in backup

    def test_os_backup_uses_lh(self):
        pattern = PatternInput(
            dump_type="TP_DUMP",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="OS",
            operating_carriers=["OS", "OS", "UA"],
            routing_points=["VIE"],
        )
        backup = generate_backup_routing_code(pattern)
        assert backup is not None
        assert "LH" in backup
        assert "FRA" in backup

    def test_no_sisters_returns_none(self):
        """Carrier with no known sisters returns None."""
        pattern = PatternInput(
            dump_type="TP_DUMP",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="ZZ",  # Unknown carrier
            operating_carriers=["ZZ", "ZZ"],
            routing_points=["XXX"],
        )
        backup = generate_backup_routing_code(pattern)
        assert backup is None


# ─── Manual Input Bundle ────────────────────────────────────────────────────


class TestManualInputBundle:
    def test_human_description_tp_dump(self):
        pattern = PatternInput(
            dump_type="TP_DUMP",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH", "LH", "AA"],
            routing_points=["FRA"],
        )
        desc = build_human_description(pattern)
        assert "JFK" in desc
        assert "Frankfurt" in desc or "FRA" in desc
        assert "Bangkok" in desc or "BKK" in desc
        assert "LH" in desc
        assert "AA" in desc

    def test_steps_are_numbered(self):
        pattern = PatternInput(
            dump_type="TP_DUMP",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH", "LH", "AA"],
            routing_points=["FRA"],
        )
        routing_code = build_routing_code(pattern)
        steps = build_ita_matrix_steps(pattern, routing_code)
        assert len(steps) >= 10
        # All steps must be numbered
        for i, step in enumerate(steps, 1):
            assert step.startswith(f"{i}."), f"Step {i} not numbered: {step}"

    def test_steps_contain_routing_code(self):
        pattern = PatternInput(
            dump_type="TP_DUMP",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH", "LH", "AA"],
            routing_points=["FRA"],
        )
        routing_code = build_routing_code(pattern)
        steps = build_ita_matrix_steps(pattern, routing_code)
        # At least one step must contain the routing code
        assert any(routing_code in step for step in steps)

    def test_steps_include_backup_when_provided(self):
        pattern = PatternInput(
            dump_type="TP_DUMP",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH", "LH", "AA"],
            routing_points=["FRA"],
        )
        routing_code = build_routing_code(pattern)
        backup = "FORCE LX:JFK-ZRH / FORCE LX:ZRH-BKK / FORCE AA:BKK-JFK"
        steps = build_ita_matrix_steps(pattern, routing_code, backup)
        assert any("backup" in step.lower() for step in steps)
        assert any(backup in step for step in steps)

    def test_notes_contain_dump_mechanism(self):
        pattern = PatternInput(
            dump_type="TP_DUMP",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH", "LH", "AA"],
            routing_points=["FRA"],
        )
        notes = build_notes(pattern)
        assert "Ticketing Point" in notes
        assert "Frankfurt" in notes or "FRA" in notes
        assert "Lufthansa" in notes or "LH" in notes

    def test_full_bundle_generation(self):
        pattern = PatternInput(
            dump_type="TP_DUMP",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH", "LH", "AA"],
            routing_points=["FRA"],
        )
        now = datetime.now(timezone.utc)
        bundle = generate_manual_input_bundle(
            pattern,
            expected_yq_savings_usd=580.0,
            confidence_score=0.85,
            validation_timestamp=now,
        )
        # Verify all required fields
        assert "routing_code_string" in bundle
        assert "human_description" in bundle
        assert "ita_matrix_steps" in bundle
        assert "expected_yq_savings_usd" in bundle
        assert "expected_yq_carrier" in bundle
        assert "validation_timestamp" in bundle
        assert "confidence_score" in bundle
        assert "backup_routing_code" in bundle
        assert "notes" in bundle

        # Verify values
        assert bundle["expected_yq_savings_usd"] == 580.0
        assert bundle["expected_yq_carrier"] == "LH"
        assert bundle["confidence_score"] == 0.85
        assert len(bundle["ita_matrix_steps"]) >= 10
        assert bundle["backup_routing_code"] is not None  # LH has sisters

    def test_bundle_validates_as_schema(self):
        """Round-trip: pattern → bundle dict → ManualInputBundle Pydantic model."""
        # Import schema from backend
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))
        from app.schemas.manual_input import ManualInputBundle

        pattern = PatternInput(
            dump_type="CARRIER_SWITCH",
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="QR",
            operating_carriers=["QR", "AA"],
            routing_points=["DOH"],
        )
        bundle_dict = generate_manual_input_bundle(
            pattern,
            expected_yq_savings_usd=580.0,
            confidence_score=0.9,
        )
        # This should not raise — the dict must match the Pydantic schema
        bundle = ManualInputBundle.model_validate(bundle_dict)
        assert bundle.expected_yq_carrier == "QR"
        assert bundle.confidence_score == 0.9
        assert len(bundle.ita_matrix_steps) >= 10


# ─── Fixture-Driven Tests ───────────────────────────────────────────────────


class TestFixtures:
    def test_all_fixtures_produce_expected_code(self, fixtures):
        """Every fixture's expected_routing_code must match build_routing_code output."""
        for fix in fixtures:
            pattern = _pattern_from_fixture(fix)
            code = build_routing_code(pattern)
            assert code == fix["expected_routing_code"], (
                f"Fixture {fix['id']}: expected '{fix['expected_routing_code']}', "
                f"got '{code}'"
            )

    def test_all_fixtures_generate_bundle(self, fixtures):
        """Every fixture should produce a valid manual input bundle."""
        for fix in fixtures:
            pattern = _pattern_from_fixture(fix)
            bundle = generate_manual_input_bundle(
                pattern,
                expected_yq_savings_usd=fix.get("expected_yq_savings_usd", 0.0),
                confidence_score=0.8,
            )
            assert bundle["routing_code_string"] == fix["expected_routing_code"]
            assert len(bundle["ita_matrix_steps"]) >= 10

    def test_fixture_backup_codes(self, fixtures):
        """Fixtures with expected_backup_code should match."""
        for fix in fixtures:
            if "expected_backup_code" not in fix:
                continue
            pattern = _pattern_from_fixture(fix)
            backup = generate_backup_routing_code(pattern)
            assert backup == fix["expected_backup_code"], (
                f"Fixture {fix['id']}: expected backup '{fix['expected_backup_code']}', "
                f"got '{backup}'"
            )

    def test_fixture_count(self, fixtures):
        """We need at least 10 fixtures covering all 4 dump types."""
        assert len(fixtures) >= 10
        types = {fix["dump_type"] for fix in fixtures}
        assert "TP_DUMP" in types
        assert "CARRIER_SWITCH" in types
        assert "FARE_BASIS" in types
        assert "ALLIANCE_RULE" in types
