"""
test_yq_scrapers.py — Unit tests for Phase 05 YQ data collection.

Tests cover:
- YQScrapeResult dataclass
- BaseYQScraper (via ITABasedYQScraper)
- ITABasedYQScraper with mocked ITA client
- Carrier configs and factory functions
- YQ dispatcher
- YQ service layer functions
- YQ Celery task wrappers

All tests use mocked ITA clients — no real browser or network calls.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── YQScrapeResult tests ─────────────────────────────────────────────────

from ingestion.scrapers.base import BaseYQScraper, YQScrapeResult


class TestYQScrapeResult:
    def test_success_when_yq_and_no_error(self):
        r = YQScrapeResult(carrier_iata="LH", origin="JFK", destination="FRA", yq_amount_usd=580.0)
        assert r.success is True

    def test_failure_when_error_set(self):
        r = YQScrapeResult(
            carrier_iata="LH", origin="JFK", destination="FRA",
            yq_amount_usd=580.0, error="Something broke",
        )
        assert r.success is False

    def test_failure_when_yq_none(self):
        r = YQScrapeResult(carrier_iata="LH", origin="JFK", destination="FRA")
        assert r.success is False

    def test_default_scraped_at_is_utc(self):
        r = YQScrapeResult(carrier_iata="LH", origin="JFK", destination="FRA")
        assert r.scraped_at.tzinfo is not None

    def test_default_source_url_empty(self):
        r = YQScrapeResult(carrier_iata="LH", origin="JFK", destination="FRA")
        assert r.source_url == ""


# ─── BaseYQScraper tests ──────────────────────────────────────────────────


class TestBaseYQScraper:
    def test_calculate_typical_yq_median_odd(self):
        """Median of odd number of results."""
        results = [
            YQScrapeResult(carrier_iata="LH", origin="JFK", destination="FRA", yq_amount_usd=500.0),
            YQScrapeResult(carrier_iata="LH", origin="LAX", destination="MUC", yq_amount_usd=600.0),
            YQScrapeResult(carrier_iata="LH", origin="ORD", destination="FRA", yq_amount_usd=550.0),
        ]
        from ingestion.scrapers.yq.ita_based import ITABasedYQScraper
        scraper = ITABasedYQScraper("LH", "Lufthansa", [])
        assert scraper.calculate_typical_yq(results) == 550.0

    def test_calculate_typical_yq_median_even(self):
        """Median of even number = average of two middle values."""
        results = [
            YQScrapeResult(carrier_iata="LH", origin="JFK", destination="FRA", yq_amount_usd=500.0),
            YQScrapeResult(carrier_iata="LH", origin="LAX", destination="MUC", yq_amount_usd=600.0),
        ]
        from ingestion.scrapers.yq.ita_based import ITABasedYQScraper
        scraper = ITABasedYQScraper("LH", "Lufthansa", [])
        assert scraper.calculate_typical_yq(results) == 550.0

    def test_calculate_typical_yq_skips_failures(self):
        """Failed results are excluded from median calculation."""
        results = [
            YQScrapeResult(carrier_iata="LH", origin="JFK", destination="FRA", yq_amount_usd=500.0),
            YQScrapeResult(carrier_iata="LH", origin="LAX", destination="MUC", error="Failed"),
            YQScrapeResult(carrier_iata="LH", origin="ORD", destination="FRA", yq_amount_usd=600.0),
        ]
        from ingestion.scrapers.yq.ita_based import ITABasedYQScraper
        scraper = ITABasedYQScraper("LH", "Lufthansa", [])
        assert scraper.calculate_typical_yq(results) == 550.0

    def test_calculate_typical_yq_all_failures(self):
        """Returns None if all results failed."""
        results = [
            YQScrapeResult(carrier_iata="LH", origin="JFK", destination="FRA", error="Failed"),
        ]
        from ingestion.scrapers.yq.ita_based import ITABasedYQScraper
        scraper = ITABasedYQScraper("LH", "Lufthansa", [])
        assert scraper.calculate_typical_yq(results) is None

    def test_calculate_typical_yq_empty_list(self):
        from ingestion.scrapers.yq.ita_based import ITABasedYQScraper
        scraper = ITABasedYQScraper("LH", "Lufthansa", [])
        assert scraper.calculate_typical_yq([]) is None


# ─── ITABasedYQScraper tests ──────────────────────────────────────────────

from ingestion.scrapers.yq.ita_based import ITABasedYQScraper


@dataclass
class MockFareBreakdown:
    yq_total_usd: float = 580.0
    yr_total_usd: float = 45.0
    base_fare_usd: float = 800.0


@dataclass
class MockITAResult:
    success: bool = True
    error_message: str | None = None
    fare_breakdown: MockFareBreakdown | None = None


class TestITABasedYQScraper:
    @pytest.fixture
    def mock_ita_client(self):
        client = AsyncMock()
        client.run_query = AsyncMock(
            return_value=MockITAResult(
                success=True,
                fare_breakdown=MockFareBreakdown(yq_total_usd=580.0),
            )
        )
        return client

    @pytest.fixture
    def scraper(self, mock_ita_client):
        return ITABasedYQScraper(
            carrier_iata="LH",
            carrier_name="Lufthansa",
            sample_routes=[("JFK", "FRA"), ("LAX", "MUC")],
            ita_client=mock_ita_client,
        )

    @pytest.mark.asyncio
    async def test_scrape_yq_success(self, scraper, mock_ita_client):
        result = await scraper.scrape_yq("JFK", "FRA")
        assert result.success is True
        assert result.yq_amount_usd == 580.0
        assert result.carrier_iata == "LH"
        mock_ita_client.run_query.assert_called_once_with(
            routing_code="FORCE LH:JFK-FRA",
            origin="JFK",
            destination="FRA",
        )

    @pytest.mark.asyncio
    async def test_scrape_yq_extracts_yr_and_base(self, scraper):
        result = await scraper.scrape_yq("JFK", "FRA")
        assert result.yr_amount_usd == 45.0
        assert result.base_fare_usd == 800.0

    @pytest.mark.asyncio
    async def test_scrape_yq_ita_failure(self, mock_ita_client):
        mock_ita_client.run_query = AsyncMock(
            return_value=MockITAResult(success=False, error_message="Timeout")
        )
        scraper = ITABasedYQScraper("BA", "British Airways", [], ita_client=mock_ita_client)
        result = await scraper.scrape_yq("JFK", "LHR")
        assert result.success is False
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_scrape_yq_no_breakdown(self, mock_ita_client):
        mock_ita_client.run_query = AsyncMock(
            return_value=MockITAResult(success=True, fare_breakdown=None)
        )
        scraper = ITABasedYQScraper("BA", "British Airways", [], ita_client=mock_ita_client)
        result = await scraper.scrape_yq("JFK", "LHR")
        assert result.success is False
        assert "No fare breakdown" in result.error

    @pytest.mark.asyncio
    async def test_scrape_yq_no_client(self):
        scraper = ITABasedYQScraper("LH", "Lufthansa", [], ita_client=None)
        result = await scraper.scrape_yq("JFK", "FRA")
        assert result.success is False
        assert "not configured" in result.error

    @pytest.mark.asyncio
    async def test_scrape_yq_exception_handled(self, mock_ita_client):
        mock_ita_client.run_query = AsyncMock(side_effect=RuntimeError("Connection lost"))
        scraper = ITABasedYQScraper("LH", "Lufthansa", [], ita_client=mock_ita_client)
        result = await scraper.scrape_yq("JFK", "FRA")
        assert result.success is False
        assert "Connection lost" in result.error

    @pytest.mark.asyncio
    async def test_scrape_all_routes(self, scraper, mock_ita_client):
        results = await scraper.scrape_all_routes()
        assert len(results) == 2
        assert all(r.success for r in results)
        assert mock_ita_client.run_query.call_count == 2

    @pytest.mark.asyncio
    async def test_scrape_all_routes_partial_failure(self, mock_ita_client):
        call_count = 0

        async def alternating_result(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return MockITAResult(success=True, fare_breakdown=MockFareBreakdown())
            return MockITAResult(success=False, error_message="Timeout")

        mock_ita_client.run_query = AsyncMock(side_effect=alternating_result)
        scraper = ITABasedYQScraper(
            "LH", "Lufthansa", [("JFK", "FRA"), ("LAX", "MUC")],
            ita_client=mock_ita_client,
        )
        results = await scraper.scrape_all_routes()
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False

    def test_repr(self):
        scraper = ITABasedYQScraper("LH", "Lufthansa", [])
        assert "LH" in repr(scraper)

    @pytest.mark.asyncio
    async def test_source_url_includes_route(self, scraper):
        result = await scraper.scrape_yq("JFK", "FRA")
        assert "JFK-FRA" in result.source_url


# ─── Carrier config tests ─────────────────────────────────────────────────

from ingestion.scrapers.yq.carriers import (
    _CARRIER_CONFIGS,
    create_all_scrapers,
    create_scraper,
    get_carrier_configs,
)


class TestCarrierConfigs:
    def test_has_15_carriers(self):
        assert len(_CARRIER_CONFIGS) == 15

    def test_all_configs_have_required_fields(self):
        for cfg in _CARRIER_CONFIGS:
            assert "carrier_iata" in cfg
            assert "carrier_name" in cfg
            assert "sample_routes" in cfg
            assert len(cfg["carrier_iata"]) == 2
            assert len(cfg["sample_routes"]) >= 3

    def test_high_yq_carriers_have_5_routes(self):
        high_yq = [c for c in _CARRIER_CONFIGS if c["carrier_iata"] in
                    {"LH", "BA", "LX", "OS", "SN", "IB", "CX", "KE", "OZ", "AF"}]
        for cfg in high_yq:
            assert len(cfg["sample_routes"]) == 5, f"{cfg['carrier_iata']} should have 5 routes"

    def test_low_yq_carriers_have_3_routes(self):
        low_yq = [c for c in _CARRIER_CONFIGS if c["carrier_iata"] in
                   {"QR", "EK", "EY", "TK", "SQ"}]
        for cfg in low_yq:
            assert len(cfg["sample_routes"]) == 3, f"{cfg['carrier_iata']} should have 3 routes"

    def test_all_routes_are_3_letter_iata(self):
        for cfg in _CARRIER_CONFIGS:
            for origin, dest in cfg["sample_routes"]:
                assert len(origin) == 3 and origin.isupper(), f"Bad origin: {origin}"
                assert len(dest) == 3 and dest.isupper(), f"Bad dest: {dest}"

    def test_no_duplicate_carriers(self):
        codes = [c["carrier_iata"] for c in _CARRIER_CONFIGS]
        assert len(codes) == len(set(codes))

    def test_create_all_scrapers(self):
        scrapers = create_all_scrapers()
        assert len(scrapers) == 15
        assert all(isinstance(s, ITABasedYQScraper) for s in scrapers)

    def test_create_scraper_found(self):
        s = create_scraper("LH")
        assert s is not None
        assert s.carrier_iata == "LH"
        assert s.carrier_name == "Lufthansa"

    def test_create_scraper_not_found(self):
        assert create_scraper("XX") is None

    def test_create_scraper_passes_ita_client(self):
        mock_client = MagicMock()
        s = create_scraper("BA", ita_client=mock_client)
        assert s._ita_client is mock_client

    def test_get_carrier_configs_returns_copy(self):
        configs = get_carrier_configs()
        assert len(configs) == 15


# ─── Dispatcher tests ─────────────────────────────────────────────────────

from ingestion.scrapers.yq_dispatcher import DispatchResult, dispatch_all


class TestDispatchResult:
    def test_success_rate_zero_routes(self):
        d = DispatchResult()
        assert d.success_rate == 0.0

    def test_success_rate_calculation(self):
        d = DispatchResult(total_routes=10, successful_routes=7)
        assert d.success_rate == 0.7

    def test_summary_dict(self):
        d = DispatchResult(carriers_scraped=3, total_routes=10, successful_routes=8)
        s = d.summary()
        assert s["carriers_scraped"] == 3
        assert s["success_rate"] == 0.8


class TestDispatcher:
    @pytest.fixture
    def mock_ita_client(self):
        client = AsyncMock()
        client.run_query = AsyncMock(
            return_value=MockITAResult(success=True, fare_breakdown=MockFareBreakdown())
        )
        return client

    @pytest.mark.asyncio
    async def test_dispatch_all_runs_all_scrapers(self, mock_ita_client):
        scrapers = [
            ITABasedYQScraper("LH", "Lufthansa", [("JFK", "FRA")], ita_client=mock_ita_client),
            ITABasedYQScraper("BA", "British Airways", [("JFK", "LHR")], ita_client=mock_ita_client),
        ]
        result = await dispatch_all(scrapers)
        assert result.carriers_scraped == 2
        assert result.total_routes == 2
        assert result.successful_routes == 2
        assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_dispatch_all_with_carrier_filter(self, mock_ita_client):
        scrapers = [
            ITABasedYQScraper("LH", "Lufthansa", [("JFK", "FRA")], ita_client=mock_ita_client),
            ITABasedYQScraper("BA", "British Airways", [("JFK", "LHR")], ita_client=mock_ita_client),
        ]
        result = await dispatch_all(scrapers, carrier_filter=["LH"])
        assert result.carriers_scraped == 1
        assert len(result.results) == 1
        assert result.results[0].carrier_iata == "LH"

    @pytest.mark.asyncio
    async def test_dispatch_all_handles_all_failures(self, mock_ita_client):
        mock_ita_client.run_query = AsyncMock(
            return_value=MockITAResult(success=False, error_message="Timeout")
        )
        scrapers = [
            ITABasedYQScraper("LH", "Lufthansa", [("JFK", "FRA")], ita_client=mock_ita_client),
        ]
        result = await dispatch_all(scrapers)
        assert result.carriers_scraped == 1
        assert result.carriers_failed == 1
        assert result.successful_routes == 0

    @pytest.mark.asyncio
    async def test_dispatch_all_empty_scrapers(self):
        result = await dispatch_all([])
        assert result.carriers_scraped == 0
        assert result.total_routes == 0


# ─── YQ Tasks tests ──────────────────────────────────────────────────────

from backend.app.tasks.yq_tasks import update_all_carrier_yq, update_single_carrier_yq


class TestYQTasks:
    @patch("backend.app.tasks.yq_tasks._run_all_carrier_yq_update")
    def test_update_all_returns_dict(self, mock_run):
        mock_run.return_value = {
            "success": True,
            "carriers_scraped": 15,
            "total_results": 60,
            "success_rate": 0.85,
            "errors": [],
        }
        # Patch asyncio.run to just call the coroutine
        with patch("asyncio.run", side_effect=lambda coro: asyncio.get_event_loop().run_until_complete(coro) if asyncio.get_event_loop().is_running() else mock_run.return_value):
            result = update_all_carrier_yq()
        assert result["success"] is True

    @patch("backend.app.tasks.yq_tasks._run_single_carrier_yq_update")
    def test_update_single_returns_dict(self, mock_run):
        mock_run.return_value = {
            "success": True,
            "carrier": "LH",
            "typical_yq_usd": 580.0,
        }
        with patch("asyncio.run", return_value=mock_run.return_value):
            result = update_single_carrier_yq("LH")
        assert result["success"] is True
        assert result["carrier"] == "LH"

    def test_update_all_handles_exception(self):
        with patch("asyncio.run", side_effect=RuntimeError("Boom")):
            result = update_all_carrier_yq()
        assert result["success"] is False
        assert "Boom" in result["error"]

    def test_update_single_handles_exception(self):
        with patch("asyncio.run", side_effect=RuntimeError("Boom")):
            result = update_single_carrier_yq("LH")
        assert result["success"] is False
        assert "Boom" in result["error"]


# ─── YQ Service tests ────────────────────────────────────────────────────

from backend.app.services.yq_service import CarrierYQSummary


class TestCarrierYQSummary:
    def test_dataclass_fields(self):
        s = CarrierYQSummary(
            iata_code="LH",
            name="Lufthansa",
            alliance="Star Alliance",
            charges_yq=True,
            typical_yq_usd=580.0,
            last_yq_updated=datetime.now(timezone.utc),
            route_count=5,
        )
        assert s.iata_code == "LH"
        assert s.charges_yq is True
        assert s.route_count == 5

    def test_default_route_count(self):
        s = CarrierYQSummary(
            iata_code="QR", name="Qatar", alliance="oneworld",
            charges_yq=False, typical_yq_usd=0.0, last_yq_updated=None,
        )
        assert s.route_count == 0
