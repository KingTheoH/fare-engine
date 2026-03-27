"""Tests for route schemas."""

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.route import RouteCreate, RouteResponse


class TestRouteCreate:
    def test_basic_route(self):
        r = RouteCreate(origin_iata="JFK", destination_iata="FRA")
        assert r.origin_iata == "JFK"
        assert r.destination_iata == "FRA"
        assert r.is_intercontinental is False

    def test_intercontinental(self):
        r = RouteCreate(
            origin_iata="JFK",
            destination_iata="BKK",
            is_intercontinental=True,
        )
        assert r.is_intercontinental is True

    def test_iata_too_short(self):
        with pytest.raises(ValidationError):
            RouteCreate(origin_iata="JF", destination_iata="FRA")

    def test_iata_too_long(self):
        with pytest.raises(ValidationError):
            RouteCreate(origin_iata="JFKX", destination_iata="FRA")


class TestRouteResponse:
    def test_from_dict(self):
        route_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        resp = RouteResponse(
            id=route_id,
            origin_iata="LAX",
            destination_iata="NRT",
            is_intercontinental=True,
            created_at=now,
        )
        assert resp.id == route_id
        assert resp.origin_iata == "LAX"
