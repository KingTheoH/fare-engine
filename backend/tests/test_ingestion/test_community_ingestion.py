"""
test_community_ingestion.py — Unit tests for Phase 06 community data ingestion.

Tests cover:
- FlyerTalk scraper (HTML parsing, keyword matching, dedup)
- LLM extractor (filter + extract with mocked Claude API)
- Pattern normalizer (IATA validation, routing code generation, confidence)
- Post credibility scoring
- Ingestion tasks

All tests use mocks — no real HTTP calls, LLM API calls, or browser.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Load fixtures ─────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


def _load_fixtures() -> list[dict]:
    with open(FIXTURES_DIR / "flyertalk_posts.json") as f:
        return json.load(f)


FIXTURES = _load_fixtures()


def _fixture(fixture_id: str) -> dict:
    for f in FIXTURES:
        if f["id"] == fixture_id:
            return f
    raise ValueError(f"Fixture {fixture_id} not found")


# ═══════════════════════════════════════════════════════════════════════════
# FlyerTalk Scraper Tests
# ═══════════════════════════════════════════════════════════════════════════

from ingestion.scrapers.flyertalk import (
    FlyerTalkScraper,
    PostData,
    ScanResult,
    ThreadInfo,
    _strip_html,
    contains_dump_keywords,
)


class TestContainsDumpKeywords:
    def test_matches_yq(self):
        assert contains_dump_keywords("This route has high YQ charges") is True

    def test_matches_fuel_dump(self):
        assert contains_dump_keywords("Found a new fuel dump on LH") is True

    def test_matches_tp_dump(self):
        assert contains_dump_keywords("Use a TP dump via FRA") is True

    def test_matches_fuel_surcharge(self):
        assert contains_dump_keywords("How to avoid fuel surcharge") is True

    def test_matches_case_insensitive(self):
        assert contains_dump_keywords("yq-free routing trick") is True

    def test_no_match(self):
        assert contains_dump_keywords("Great hotel deal in Bangkok") is False

    def test_empty_string(self):
        assert contains_dump_keywords("") is False


class TestStripHtml:
    def test_removes_tags(self):
        assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_decodes_entities(self):
        assert _strip_html("A &amp; B &lt; C") == "A & B < C"

    def test_collapses_whitespace(self):
        assert _strip_html("  hello   world  ") == "hello world"

    def test_removes_script_tags(self):
        result = _strip_html("<script>alert('hi')</script>Content")
        assert "alert" not in result
        assert "Content" in result


class TestThreadInfo:
    def test_thread_id_extraction(self):
        t = ThreadInfo(
            thread_url="https://www.flyertalk.com/forum/some-thread-12345/",
            title="Test Thread",
        )
        assert t.thread_id == "12345"

    def test_thread_id_no_match(self):
        t = ThreadInfo(thread_url="https://example.com/no-id", title="Test")
        assert t.thread_id == ""


class TestPostData:
    def test_to_community_post_dict(self):
        post = PostData(
            post_url="https://flyertalk.com/post/123",
            author="TestUser",
            raw_text="Some text about YQ",
            posted_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
            author_post_count=500,
            author_account_age_days=1000,
        )
        d = post.to_community_post_dict()
        assert d["source"] == "FLYERTALK"
        assert d["post_url"] == "https://flyertalk.com/post/123"
        assert d["post_author"] == "TestUser"
        assert d["author_post_count"] == 500
        assert d["raw_text"] == "Some text about YQ"


class TestFlyerTalkScraper:
    def test_parse_thread_listings_extracts_threads(self):
        html = '''
        <div class="thread-list">
            <a href="/forum/lh-yq-dump-discussion-12345/">LH YQ Dump Discussion</a>
            <a href="/forum/hotel-deals-67890/">Hotel Deals Thread</a>
            <a href="/forum/fuel-surcharge-tricks-11111/">Fuel Surcharge Tricks</a>
        </div>
        '''
        scraper = FlyerTalkScraper()
        threads = scraper.parse_thread_listings(html, "https://flyertalk.com/forum/test/")
        assert len(threads) == 3

    def test_parse_thread_listings_flags_keywords(self):
        html = '''
        <a href="/forum/lh-yq-dump-12345/">LH YQ Dump Route</a>
        <a href="/forum/hotel-deals-67890/">Hotel Deals</a>
        '''
        scraper = FlyerTalkScraper()
        threads = scraper.parse_thread_listings(html, "https://flyertalk.com/forum/test/")
        yq_threads = [t for t in threads if t.contains_dump_keywords]
        assert len(yq_threads) >= 1

    def test_parse_thread_listings_deduplicates(self):
        html = '''
        <a href="/forum/thread-12345/">Thread</a>
        <a href="/forum/thread-12345/">Thread</a>
        <a href="/forum/thread-12345/">Thread</a>
        '''
        scraper = FlyerTalkScraper()
        threads = scraper.parse_thread_listings(html, "https://flyertalk.com/forum/test/")
        assert len(threads) == 1

    def test_parse_posts_from_html(self):
        html = '''
        <a class="username" href="#">TestUser</a>
        <div class="post_message" id="post_message_111">
            This is a post about YQ fuel dump via Frankfurt
        </div>
        <a class="username" href="#">AnotherUser</a>
        <div class="post_message" id="post_message_222">
            I confirmed the routing trick works as of today
        </div>
        '''
        scraper = FlyerTalkScraper()
        posts = scraper.parse_posts(html, "https://flyertalk.com/thread/123/", "Test Thread")
        assert len(posts) == 2
        assert "YQ fuel dump" in posts[0].raw_text
        assert posts[0].post_url.endswith("#post111")

    def test_scan_result_summary(self):
        result = ScanResult(
            threads_scanned=10,
            threads_matched=3,
            posts_scraped=15,
            errors=["error1"],
        )
        s = result.summary()
        assert s["threads_matched"] == 3
        assert s["error_count"] == 1


# ═══════════════════════════════════════════════════════════════════════════
# LLM Extractor Tests
# ═══════════════════════════════════════════════════════════════════════════

from ingestion.extractors.llm_extractor import (
    ExtractionResult,
    ExtractedPatternData,
    FilterResult,
    LLMExtractor,
    ProcessResult,
    _parse_json_response,
)


class TestParseJsonResponse:
    def test_direct_json(self):
        result = _parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_markdown_code_block(self):
        result = _parse_json_response('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_json_in_text(self):
        result = _parse_json_response('Here is the result: {"key": "value"} end')
        assert result == {"key": "value"}

    def test_invalid_json(self):
        assert _parse_json_response("not json at all") is None


class TestFilterResult:
    def test_defaults(self):
        r = FilterResult()
        assert r.contains_dump_pattern is False
        assert r.error is None


class TestExtractedPatternData:
    def test_defaults(self):
        p = ExtractedPatternData()
        assert p.dump_type == ""
        assert p.confidence == "low"
        assert p.carriers == []


class TestLLMExtractor:
    @pytest.fixture
    def mock_anthropic_client(self):
        client = AsyncMock()
        return client

    @pytest.fixture
    def extractor(self, mock_anthropic_client):
        ext = LLMExtractor(api_key="test-key")
        ext._client = mock_anthropic_client
        return ext

    def _make_response(self, text: str, input_tokens: int = 100, output_tokens: int = 50):
        """Create a mock Anthropic API response."""
        response = MagicMock()
        content_block = MagicMock()
        content_block.text = text
        response.content = [content_block]
        response.usage = MagicMock()
        response.usage.input_tokens = input_tokens
        response.usage.output_tokens = output_tokens
        return response

    @pytest.mark.asyncio
    async def test_filter_post_positive(self, extractor, mock_anthropic_client):
        mock_anthropic_client.messages.create = AsyncMock(
            return_value=self._make_response(
                '{"contains_dump_pattern": true, "reason": "Describes LH TP dump via FRA"}'
            )
        )
        result = await extractor.filter_post("Some post about LH YQ dump via FRA")
        assert result.contains_dump_pattern is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_filter_post_negative(self, extractor, mock_anthropic_client):
        mock_anthropic_client.messages.create = AsyncMock(
            return_value=self._make_response(
                '{"contains_dump_pattern": false, "reason": "Just a general question"}'
            )
        )
        result = await extractor.filter_post("What is YQ?")
        assert result.contains_dump_pattern is False

    @pytest.mark.asyncio
    async def test_filter_post_api_error(self, extractor, mock_anthropic_client):
        mock_anthropic_client.messages.create = AsyncMock(
            side_effect=RuntimeError("API down")
        )
        result = await extractor.filter_post("test")
        assert result.error is not None
        assert "API" in result.error

    @pytest.mark.asyncio
    async def test_extract_patterns_success(self, extractor, mock_anthropic_client):
        response_json = json.dumps({
            "patterns": [
                {
                    "dump_type": "TP_DUMP",
                    "origin": "JFK",
                    "destination": "BKK",
                    "carriers": ["LH"],
                    "ticketing_carrier": "LH",
                    "ticketing_point": "FRA",
                    "routing_points": ["FRA"],
                    "fare_basis_hint": None,
                    "estimated_yq_savings_usd": 580.0,
                    "confidence": "high",
                    "confirmation_signals": ["just booked this"],
                    "deprecation_signals": [],
                }
            ],
            "extraction_notes": "Clear TP dump pattern",
        })
        mock_anthropic_client.messages.create = AsyncMock(
            return_value=self._make_response(response_json)
        )
        result = await extractor.extract_patterns("Post about LH dump via FRA...")
        assert result.error is None
        assert len(result.patterns) == 1
        assert result.patterns[0].dump_type == "TP_DUMP"
        assert result.patterns[0].origin == "JFK"
        assert result.patterns[0].estimated_yq_savings_usd == 580.0

    @pytest.mark.asyncio
    async def test_extract_patterns_empty(self, extractor, mock_anthropic_client):
        mock_anthropic_client.messages.create = AsyncMock(
            return_value=self._make_response(
                '{"patterns": [], "extraction_notes": "No patterns found"}'
            )
        )
        result = await extractor.extract_patterns("Vague text")
        assert result.error is None
        assert len(result.patterns) == 0

    @pytest.mark.asyncio
    async def test_process_post_full_pipeline(self, extractor, mock_anthropic_client):
        # First call = filter (positive), second = extraction
        filter_response = self._make_response(
            '{"contains_dump_pattern": true, "reason": "Contains pattern"}'
        )
        extract_response = self._make_response(json.dumps({
            "patterns": [{
                "dump_type": "TP_DUMP",
                "origin": "JFK",
                "destination": "BKK",
                "carriers": ["LH"],
                "ticketing_carrier": "LH",
                "ticketing_point": "FRA",
                "routing_points": ["FRA"],
                "confidence": "high",
                "confirmation_signals": [],
                "deprecation_signals": [],
            }],
            "extraction_notes": "",
        }))
        mock_anthropic_client.messages.create = AsyncMock(
            side_effect=[filter_response, extract_response]
        )
        result = await extractor.process_post("LH TP dump via FRA for JFK-BKK")
        assert result.passed_filter is True
        assert result.total_patterns == 1
        assert result.error is None

    @pytest.mark.asyncio
    async def test_process_post_filtered_out(self, extractor, mock_anthropic_client):
        mock_anthropic_client.messages.create = AsyncMock(
            return_value=self._make_response(
                '{"contains_dump_pattern": false, "reason": "No pattern"}'
            )
        )
        result = await extractor.process_post("What is YQ?")
        assert result.passed_filter is False
        assert result.extraction_result is None
        # Only 1 API call (filter only)
        assert mock_anthropic_client.messages.create.call_count == 1

    @pytest.mark.asyncio
    async def test_filter_tracks_tokens(self, extractor, mock_anthropic_client):
        mock_anthropic_client.messages.create = AsyncMock(
            return_value=self._make_response(
                '{"contains_dump_pattern": false, "reason": "No"}',
                input_tokens=200,
                output_tokens=30,
            )
        )
        result = await extractor.filter_post("test")
        assert result.tokens_used == 230


# ═══════════════════════════════════════════════════════════════════════════
# Pattern Normalizer Tests
# ═══════════════════════════════════════════════════════════════════════════

from ingestion.extractors.pattern_normalizer import (
    NormalizationResult,
    NormalizedPattern,
    normalize_all,
    normalize_pattern,
    _assign_freshness_tier,
    _build_routing_code,
    _compute_initial_confidence,
    _is_valid_airport,
    _is_valid_carrier,
)


class TestValidation:
    def test_valid_airport(self):
        assert _is_valid_airport("JFK") is True
        assert _is_valid_airport("FRA") is True

    def test_invalid_airport(self):
        assert _is_valid_airport("jfk") is False  # lowercase
        assert _is_valid_airport("JFKK") is False  # too long
        assert _is_valid_airport("JF") is False  # too short
        assert _is_valid_airport("12A") is False  # numeric

    def test_valid_carrier(self):
        assert _is_valid_carrier("LH") is True
        assert _is_valid_carrier("AA") is True

    def test_invalid_carrier(self):
        assert _is_valid_carrier("lh") is False
        assert _is_valid_carrier("LHX") is False
        assert _is_valid_carrier("1A") is False


class TestBuildRoutingCode:
    def test_tp_dump(self):
        code = _build_routing_code(
            "TP_DUMP", "JFK", "BKK", ["LH"], "LH", ["FRA"], None
        )
        assert "FORCE LH:JFK-FRA" in code
        assert "FORCE LH:FRA-BKK" in code

    def test_carrier_switch(self):
        code = _build_routing_code(
            "CARRIER_SWITCH", "JFK", "LHR", ["QR", "BA"], "QR", ["DOH"], None
        )
        assert "FORCE QR:" in code
        assert "FORCE BA:" in code

    def test_fare_basis(self):
        code = _build_routing_code(
            "FARE_BASIS", "JFK", "SIN", ["LH"], "LH", ["FRA"], "YLOWUS"
        )
        assert "BC=YLOWUS" in code

    def test_alliance_rule(self):
        code = _build_routing_code(
            "ALLIANCE_RULE", "JFK", "SYD", ["BA", "AA"], "BA", ["LHR"], None
        )
        assert "BA/AA" in code


class TestComputeConfidence:
    def test_high_confidence_with_confirmation(self):
        score = _compute_initial_confidence("high", 0.8, True, False)
        assert score > 0.5

    def test_low_confidence(self):
        score = _compute_initial_confidence("low", 0.3, False, False)
        assert score < 0.4

    def test_deprecation_caps_at_02(self):
        score = _compute_initial_confidence("high", 0.9, True, True)
        assert score <= 0.2

    def test_clamped_to_range(self):
        score = _compute_initial_confidence("high", 1.0, True, False)
        assert 0.0 <= score <= 1.0


class TestFreshnessTier:
    def test_high_savings(self):
        assert _assign_freshness_tier(500.0) == 1

    def test_medium_savings(self):
        assert _assign_freshness_tier(100.0) == 2

    def test_low_savings(self):
        assert _assign_freshness_tier(30.0) == 3

    def test_none_savings(self):
        assert _assign_freshness_tier(None) == 3

    def test_zero_savings(self):
        assert _assign_freshness_tier(0.0) == 3


class TestNormalizePattern:
    def test_valid_tp_dump(self):
        extracted = ExtractedPatternData(
            dump_type="TP_DUMP",
            origin="JFK",
            destination="BKK",
            carriers=["LH"],
            ticketing_carrier="LH",
            ticketing_point="FRA",
            routing_points=["FRA"],
            estimated_yq_savings_usd=580.0,
            confidence="high",
            confirmation_signals=["just booked"],
        )
        result = normalize_pattern(extracted, source_url="https://flyertalk.com/post/123")
        assert result.is_valid
        assert result.data["dump_type"] == "TP_DUMP"
        assert result.data["origin_iata"] == "JFK"
        assert result.data["lifecycle_state"] == "discovered"
        assert result.data["manual_input_bundle"] is None
        assert result.data["expected_yq_savings_usd"] == 580.0
        assert "FORCE LH:JFK-FRA" in result.data["ita_routing_code"]

    def test_invalid_dump_type_rejected(self):
        extracted = ExtractedPatternData(
            dump_type="INVALID_TYPE", origin="JFK", destination="FRA",
            carriers=["LH"], ticketing_carrier="LH",
        )
        result = normalize_pattern(extracted)
        assert not result.is_valid

    def test_invalid_origin_rejected(self):
        extracted = ExtractedPatternData(
            dump_type="TP_DUMP", origin="X1", destination="FRA",
            carriers=["LH"], ticketing_carrier="LH",
        )
        result = normalize_pattern(extracted)
        assert not result.is_valid

    def test_no_carriers_rejected(self):
        extracted = ExtractedPatternData(
            dump_type="TP_DUMP", origin="JFK", destination="FRA",
            carriers=[], ticketing_carrier="LH",
        )
        result = normalize_pattern(extracted)
        assert not result.is_valid

    def test_freshness_tier_assigned(self):
        extracted = ExtractedPatternData(
            dump_type="TP_DUMP", origin="JFK", destination="BKK",
            carriers=["LH"], ticketing_carrier="LH", routing_points=["FRA"],
            estimated_yq_savings_usd=580.0, confidence="high",
        )
        result = normalize_pattern(extracted)
        assert result.data["freshness_tier"] == 1  # > $200

    def test_source_flyertalk(self):
        extracted = ExtractedPatternData(
            dump_type="TP_DUMP", origin="JFK", destination="FRA",
            carriers=["LH"], ticketing_carrier="LH", routing_points=["FRA"],
            confidence="medium",
        )
        result = normalize_pattern(extracted)
        assert result.data["source"] == "FLYERTALK"


class TestNormalizeAll:
    def test_mixed_valid_invalid(self):
        patterns = [
            ExtractedPatternData(
                dump_type="TP_DUMP", origin="JFK", destination="BKK",
                carriers=["LH"], ticketing_carrier="LH", routing_points=["FRA"],
                confidence="high",
            ),
            ExtractedPatternData(
                dump_type="INVALID", origin="X", destination="Y",
                carriers=[], ticketing_carrier="",
            ),
        ]
        result = normalize_all(patterns)
        assert result.valid_count == 1
        assert result.skipped == 1

    def test_empty_list(self):
        result = normalize_all([])
        assert result.valid_count == 0
        assert result.skipped == 0


# ═══════════════════════════════════════════════════════════════════════════
# Post Credibility Tests
# ═══════════════════════════════════════════════════════════════════════════

from ingestion.weighting.post_credibility import PostMetrics, score_post, score_from_community_post


class TestPostCredibility:
    @pytest.fixture
    def now(self):
        return datetime(2026, 3, 25, tzinfo=timezone.utc)

    def test_baseline_score(self, now):
        """Minimal post gets baseline 0.50."""
        score = score_post(PostMetrics(), now=now)
        assert score == 0.50

    def test_experienced_author_boost(self, now):
        metrics = PostMetrics(author_post_count=2500, author_account_age_days=2000)
        score = score_post(metrics, now=now)
        assert score > 0.65  # 0.50 + 0.15 + 0.10

    def test_new_author_lower(self, now):
        metrics = PostMetrics(author_post_count=5, author_account_age_days=10)
        score = score_post(metrics, now=now)
        assert score < 0.50  # baseline minus penalty

    def test_recent_post_boost(self, now):
        metrics = PostMetrics(posted_at=now - timedelta(days=3))
        score = score_post(metrics, now=now)
        assert score > 0.60

    def test_old_post_penalty(self, now):
        metrics = PostMetrics(posted_at=now - timedelta(days=400))
        score = score_post(metrics, now=now)
        assert score < 0.35

    def test_confirmations_boost(self, now):
        metrics = PostMetrics(reply_confirms_count=5)
        score = score_post(metrics, now=now)
        assert score > 0.55

    def test_deprecations_penalty(self, now):
        metrics = PostMetrics(reply_deprecates_count=3)
        score = score_post(metrics, now=now)
        assert score < 0.35

    def test_score_clamped_0_1(self, now):
        # Max everything
        metrics = PostMetrics(
            author_post_count=5000,
            author_account_age_days=5000,
            posted_at=now - timedelta(days=1),
            reply_confirms_count=10,
        )
        score = score_post(metrics, now=now)
        assert 0.0 <= score <= 1.0

    def test_score_from_community_post_convenience(self, now):
        score = score_from_community_post(
            post_author_count=500,
            post_author_age_days=1000,
            posted_at=now - timedelta(days=5),
        )
        assert 0.0 <= score <= 1.0

    def test_fixture_experienced_author_high_score(self, now):
        fixture = _fixture("post_tp_dump_lh")
        metrics = PostMetrics(
            author_post_count=fixture["author_post_count"],
            author_account_age_days=fixture["author_account_age_days"],
            posted_at=datetime.fromisoformat(fixture["posted_at"]),
        )
        score = score_post(metrics, now=now)
        assert score >= 0.70  # Experienced author, recent post

    def test_fixture_new_author_low_score(self, now):
        fixture = _fixture("post_no_pattern")
        metrics = PostMetrics(
            author_post_count=fixture["author_post_count"],
            author_account_age_days=fixture["author_account_age_days"],
            posted_at=datetime.fromisoformat(fixture["posted_at"]),
        )
        score = score_post(metrics, now=now)
        assert score < 0.70  # New-ish author, boosted by recency


# ═══════════════════════════════════════════════════════════════════════════
# Ingestion Tasks Tests
# ═══════════════════════════════════════════════════════════════════════════

from backend.app.tasks.ingestion_tasks import (
    process_pending_posts,
    scan_all_forums,
)


class TestIngestionTasks:
    @patch("backend.app.tasks.ingestion_tasks._run_forum_scan")
    def test_scan_all_forums_success(self, mock_scan):
        mock_scan.return_value = {
            "success": True,
            "threads_scanned": 10,
            "threads_matched": 3,
            "posts_scraped": 15,
        }
        with patch("asyncio.run", return_value=mock_scan.return_value):
            result = scan_all_forums()
        assert result["success"] is True

    def test_scan_all_forums_handles_exception(self):
        with patch("asyncio.run", side_effect=RuntimeError("Network error")):
            result = scan_all_forums()
        assert result["success"] is False
        assert "Network error" in result["error"]

    @patch("backend.app.tasks.ingestion_tasks._run_post_processing")
    def test_process_pending_posts_success(self, mock_process):
        mock_process.return_value = {"success": True, "limit": 50}
        with patch("asyncio.run", return_value=mock_process.return_value):
            result = process_pending_posts()
        assert result["success"] is True

    def test_process_pending_posts_handles_exception(self):
        with patch("asyncio.run", side_effect=RuntimeError("DB error")):
            result = process_pending_posts()
        assert result["success"] is False


# ═══════════════════════════════════════════════════════════════════════════
# Fixture-based Integration Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestFixtureIntegration:
    """Test normalization against all fixtures that have expected patterns."""

    def test_all_pattern_fixtures_normalize_successfully(self):
        """Every fixture with expected_dump_type should normalize to a valid pattern."""
        pattern_fixtures = [f for f in FIXTURES if f.get("expected_dump_type")]

        for fixture in pattern_fixtures:
            carriers = fixture.get("expected_carriers", [])
            extracted = ExtractedPatternData(
                dump_type=fixture["expected_dump_type"],
                origin=fixture.get("expected_origin", "JFK"),
                destination=fixture.get("expected_destination", "FRA"),
                carriers=carriers or ["LH"],
                ticketing_carrier=carriers[0] if carriers else "LH",
                routing_points=["FRA"] if fixture["expected_dump_type"] == "TP_DUMP" else [],
                estimated_yq_savings_usd=fixture.get("expected_yq_savings"),
                confidence="high",
            )
            result = normalize_pattern(extracted, source_url=fixture["post_url"])
            assert result.is_valid, (
                f"Fixture {fixture['id']} failed to normalize: {result.warnings}"
            )

    def test_fixture_count(self):
        """Ensure we have at least 10 fixtures."""
        assert len(FIXTURES) >= 10

    def test_non_pattern_fixtures_exist(self):
        """Ensure we have fixtures that should NOT contain patterns."""
        non_patterns = [f for f in FIXTURES if not f.get("expected_filter", True)]
        assert len(non_patterns) >= 2
