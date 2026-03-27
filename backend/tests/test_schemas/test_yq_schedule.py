"""Tests for YQ schedule schemas."""

import uuid
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.yq_schedule import YQScheduleCreate, YQScheduleResponse


class TestYQScheduleCreate:
    def test_basic_create(self):
        yq = YQScheduleCreate(
            carrier_iata="LH",
            route_id=uuid.uuid4(),
            yq_amount_usd=580.0,
            effective_date=date(2026, 3, 25),
        )
        assert yq.carrier_iata == "LH"
        assert yq.yq_amount_usd == 580.0
        assert yq.source_url is None

    def test_with_source_url(self):
        yq = YQScheduleCreate(
            carrier_iata="BA",
            route_id=uuid.uuid4(),
            yq_amount_usd=550.0,
            effective_date=date(2026, 3, 1),
            source_url="https://ba.com/booking",
        )
        assert yq.source_url is not None

    def test_negative_amount_rejected(self):
        with pytest.raises(ValidationError):
            YQScheduleCreate(
                carrier_iata="LH",
                route_id=uuid.uuid4(),
                yq_amount_usd=-100.0,
                effective_date=date(2026, 3, 25),
            )

    def test_invalid_carrier_code(self):
        with pytest.raises(ValidationError):
            YQScheduleCreate(
                carrier_iata="LHX",
                route_id=uuid.uuid4(),
                yq_amount_usd=580.0,
                effective_date=date(2026, 3, 25),
            )


class TestYQScheduleResponse:
    def test_from_dict(self):
        now = datetime.now(timezone.utc)
        resp = YQScheduleResponse(
            id=uuid.uuid4(),
            carrier_iata="LH",
            route_id=uuid.uuid4(),
            yq_amount_usd=580.0,
            effective_date=date(2026, 3, 25),
            scraped_at=now,
            source_url=None,
        )
        assert resp.carrier_iata == "LH"
        assert resp.effective_date == date(2026, 3, 25)
