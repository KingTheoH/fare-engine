"""Tests for community post schemas."""

import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.enums import DumpType, PatternSource
from app.schemas.community_post import (
    CommunityPostCreate,
    CommunityPostResponse,
    ExtractedPattern,
)


class TestExtractedPattern:
    def test_valid_extraction(self):
        ep = ExtractedPattern(
            dump_type=DumpType.TP_DUMP,
            origin_iata="JFK",
            destination_iata="BKK",
            ticketing_carrier_iata="LH",
            operating_carriers=["LH", "LH", "AA"],
            routing_points=["FRA"],
            estimated_yq_savings_usd=580.0,
            confidence_note="High confidence — explicit routing mentioned",
        )
        assert ep.dump_type == DumpType.TP_DUMP
        assert ep.routing_points == ["FRA"]

    def test_minimal_extraction(self):
        ep = ExtractedPattern(
            dump_type=DumpType.CARRIER_SWITCH,
            origin_iata="LAX",
            destination_iata="SIN",
            ticketing_carrier_iata="QR",
            operating_carriers=["QR"],
        )
        assert ep.fare_basis_hint is None
        assert ep.estimated_yq_savings_usd is None
        assert ep.routing_points == []

    def test_invalid_airport_code(self):
        with pytest.raises(ValidationError):
            ExtractedPattern(
                dump_type=DumpType.TP_DUMP,
                origin_iata="JF",  # too short
                destination_iata="BKK",
                ticketing_carrier_iata="LH",
                operating_carriers=["LH"],
            )


class TestCommunityPostCreate:
    def test_basic_create(self):
        post = CommunityPostCreate(
            post_url="https://www.flyertalk.com/forum/post/12345",
            raw_text="Found a great dump JFK-BKK via FRA on LH ticket, YQ drops to zero!",
        )
        assert post.source == PatternSource.FLYERTALK
        assert post.post_author is None

    def test_full_create(self):
        post = CommunityPostCreate(
            source=PatternSource.FLYERTALK,
            post_url="https://www.flyertalk.com/forum/post/12345",
            post_author="ExpertFlyer99",
            author_post_count=5000,
            author_account_age_days=3650,
            raw_text="Confirmed: JFK-FRA-BKK on LH metal, TP at FRA, YQ=$0",
            posted_at=datetime(2026, 3, 20, 14, 30, tzinfo=timezone.utc),
        )
        assert post.author_post_count == 5000
        assert post.author_account_age_days == 3650

    def test_empty_url_rejected(self):
        with pytest.raises(ValidationError):
            CommunityPostCreate(post_url="", raw_text="Some text")

    def test_empty_text_rejected(self):
        with pytest.raises(ValidationError):
            CommunityPostCreate(
                post_url="https://example.com/post/1",
                raw_text="",
            )

    def test_negative_post_count_rejected(self):
        with pytest.raises(ValidationError):
            CommunityPostCreate(
                post_url="https://example.com/post/1",
                raw_text="Text",
                author_post_count=-1,
            )


class TestCommunityPostResponse:
    def test_from_dict(self):
        now = datetime.now(timezone.utc)
        resp = CommunityPostResponse(
            id=uuid.uuid4(),
            source="FLYERTALK",
            post_url="https://flyertalk.com/post/123",
            post_author="TestUser",
            author_post_count=100,
            author_account_age_days=365,
            raw_text="Some fuel dump discussion",
            extracted_patterns=[
                {
                    "dump_type": "TP_DUMP",
                    "origin_iata": "JFK",
                    "destination_iata": "BKK",
                    "ticketing_carrier_iata": "LH",
                    "operating_carriers": ["LH"],
                }
            ],
            processing_state="processed",
            posted_at=now,
            scraped_at=now,
        )
        assert resp.processing_state == "processed"
        assert len(resp.extracted_patterns) == 1

    def test_unprocessed_post(self):
        now = datetime.now(timezone.utc)
        resp = CommunityPostResponse(
            id=uuid.uuid4(),
            source="FLYERTALK",
            post_url="https://flyertalk.com/post/456",
            post_author=None,
            author_post_count=None,
            author_account_age_days=None,
            raw_text="Unprocessed text",
            extracted_patterns=None,
            processing_state="raw",
            posted_at=None,
            scraped_at=now,
        )
        assert resp.processing_state == "raw"
        assert resp.extracted_patterns is None
