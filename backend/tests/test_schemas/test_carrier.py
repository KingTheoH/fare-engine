"""Tests for carrier schemas."""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.schemas.carrier import CarrierCreate, CarrierUpdate, CarrierResponse
from app.models.enums import Alliance


class TestCarrierCreate:
    def test_minimal_create(self):
        c = CarrierCreate(iata_code="LH", name="Lufthansa")
        assert c.iata_code == "LH"
        assert c.name == "Lufthansa"
        assert c.alliance == Alliance.NONE
        assert c.charges_yq is None
        assert c.typical_yq_usd is None

    def test_full_create(self):
        c = CarrierCreate(
            iata_code="BA",
            name="British Airways",
            alliance=Alliance.ONEWORLD,
            charges_yq=True,
            typical_yq_usd=550.0,
            yq_scrape_url="https://example.com/ba",
        )
        assert c.alliance == Alliance.ONEWORLD
        assert c.charges_yq is True
        assert c.typical_yq_usd == 550.0

    def test_iata_code_too_short(self):
        with pytest.raises(ValidationError):
            CarrierCreate(iata_code="L", name="Lufthansa")

    def test_iata_code_too_long(self):
        with pytest.raises(ValidationError):
            CarrierCreate(iata_code="LHX", name="Lufthansa")

    def test_negative_yq_rejected(self):
        with pytest.raises(ValidationError):
            CarrierCreate(iata_code="LH", name="Lufthansa", typical_yq_usd=-10.0)

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            CarrierCreate(iata_code="LH", name="")


class TestCarrierUpdate:
    def test_all_fields_optional(self):
        u = CarrierUpdate()
        assert u.name is None
        assert u.alliance is None

    def test_partial_update(self):
        u = CarrierUpdate(typical_yq_usd=600.0)
        assert u.typical_yq_usd == 600.0
        assert u.name is None


class TestCarrierResponse:
    def test_from_dict(self):
        now = datetime.now(timezone.utc)
        resp = CarrierResponse(
            iata_code="QR",
            name="Qatar Airways",
            alliance="NONE",
            charges_yq=False,
            typical_yq_usd=0.0,
            last_yq_updated=None,
            yq_scrape_url=None,
            created_at=now,
            updated_at=now,
        )
        assert resp.iata_code == "QR"
        assert resp.charges_yq is False

    def test_serialization_round_trip(self):
        now = datetime.now(timezone.utc)
        resp = CarrierResponse(
            iata_code="LH",
            name="Lufthansa",
            alliance="STAR",
            charges_yq=True,
            typical_yq_usd=580.0,
            last_yq_updated=now,
            yq_scrape_url="https://example.com",
            created_at=now,
            updated_at=now,
        )
        data = resp.model_dump()
        resp2 = CarrierResponse.model_validate(data)
        assert resp2.iata_code == resp.iata_code
        assert resp2.typical_yq_usd == resp.typical_yq_usd
