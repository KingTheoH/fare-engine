"""
Tests for the ITA Matrix automation engine (Phase 04).

Unit tests mock Playwright — no real browser needed.
Integration tests (marked @pytest.mark.integration) require Playwright and network access.

Test coverage:
- Rate limiter behavior
- Proxy manager rotation and retirement
- Browser manager session recycling
- Result parser text extraction
- ITAResult serialization
- ITAClient error handling (mocked)
"""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from automation.browser import SESSION_LIMIT, BrowserManager, USER_AGENTS, VIEWPORTS
from automation.ita_client import ITAClient, ITAResult
from automation.proxy_manager import DAILY_LIMIT, ProxyManager
from automation.rate_limiter import RateLimiter
from automation.result_parser import (
    FareBreakdown,
    SegmentInfo,
    TaxLine,
    parse_fare_text,
)


# ─── Rate Limiter ───────────────────────────────────────────────────────────


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_first_request_no_wait(self):
        """First request should not wait."""
        limiter = RateLimiter(min_delay=1.0, jitter_max=0.0)
        start = time.monotonic()
        await limiter.wait()
        elapsed = time.monotonic() - start
        # Should be near-instant (< 0.1s)
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_enforces_min_delay(self):
        """Second request should wait at least min_delay."""
        limiter = RateLimiter(min_delay=0.2, jitter_max=0.0)
        await limiter.wait()
        start = time.monotonic()
        await limiter.wait()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.15  # Allow small timing tolerance

    @pytest.mark.asyncio
    async def test_jitter_adds_randomness(self):
        """Jitter should add variable delay."""
        limiter = RateLimiter(min_delay=0.1, jitter_max=0.1)
        await limiter.wait()
        start = time.monotonic()
        await limiter.wait()
        elapsed = time.monotonic() - start
        # Should be at least min_delay (0.1)
        assert elapsed >= 0.09

    def test_reset(self):
        limiter = RateLimiter(min_delay=1.0, jitter_max=0.0)
        limiter._last_request_time = time.monotonic()
        assert limiter.seconds_since_last < 1.0
        limiter.reset()
        assert limiter.seconds_since_last == float("inf")


# ─── Proxy Manager ──────────────────────────────────────────────────────────


class TestProxyManager:
    def test_round_robin_rotation(self):
        manager = ProxyManager(proxy_urls=["proxy1", "proxy2", "proxy3"])
        p1 = manager.get_proxy()
        p2 = manager.get_proxy()
        p3 = manager.get_proxy()
        assert {p1, p2, p3} == {"proxy1", "proxy2", "proxy3"}

    def test_skips_retired_proxy(self):
        manager = ProxyManager(proxy_urls=["proxy1", "proxy2"])
        manager.retire("proxy1")
        # Should skip proxy1 and return proxy2
        proxy = manager.get_proxy()
        assert proxy == "proxy2"

    def test_all_retired_returns_none(self):
        manager = ProxyManager(proxy_urls=["proxy1"])
        manager.retire("proxy1")
        assert manager.get_proxy() is None

    def test_daily_limit_enforcement(self):
        manager = ProxyManager(proxy_urls=["proxy1", "proxy2"])
        for _ in range(DAILY_LIMIT):
            manager.record_use("proxy1")
        # proxy1 should be at limit
        assert manager._proxies["proxy1"].is_at_limit
        proxy = manager.get_proxy()
        # Should return proxy2 (skipping exhausted proxy1)
        assert proxy == "proxy2"

    def test_reset_daily_counts(self):
        manager = ProxyManager(proxy_urls=["proxy1"])
        for _ in range(100):
            manager.record_use("proxy1")
        assert manager._proxies["proxy1"].request_count == 100
        manager.reset_daily_counts()
        assert manager._proxies["proxy1"].request_count == 0

    def test_empty_pool_returns_none(self):
        manager = ProxyManager(proxy_urls=[])
        assert manager.get_proxy() is None

    def test_stats(self):
        manager = ProxyManager(proxy_urls=["proxy1", "proxy2", "proxy3"])
        manager.record_use("proxy1")
        manager.record_use("proxy1")
        manager.retire("proxy3")
        stats = manager.get_stats()
        assert stats["total"] == 3
        assert stats["available"] == 2  # proxy1 + proxy2
        assert stats["retired"] == 1
        assert stats["total_requests"] == 2

    def test_available_count(self):
        manager = ProxyManager(proxy_urls=["p1", "p2", "p3"])
        assert manager.available_count == 3
        manager.retire("p1")
        assert manager.available_count == 2


# ─── Browser Manager ────────────────────────────────────────────────────────


class TestBrowserManager:
    def test_user_agents_loaded(self):
        assert len(USER_AGENTS) >= 10

    def test_viewports_available(self):
        assert len(VIEWPORTS) == 3
        for vp in VIEWPORTS:
            assert "width" in vp
            assert "height" in vp

    def test_session_limit_constant(self):
        assert SESSION_LIMIT == 15

    @pytest.mark.asyncio
    async def test_request_counting(self):
        mock_pw = MagicMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        manager = BrowserManager(_playwright=mock_pw)
        await manager.get_page()
        assert manager.request_count == 0
        assert manager.remaining_requests == SESSION_LIMIT

        await manager.mark_request()
        assert manager.request_count == 1
        assert manager.remaining_requests == SESSION_LIMIT - 1

        await manager.close()


# ─── Result Parser ──────────────────────────────────────────────────────────


class TestResultParser:
    def test_parse_simple_fare_text(self):
        text = """
        Base fare: $450.00
        YQ  0.00
        YR  45.00
        US  32.50
        XF  4.50
        Total: $532.00
        """
        result = parse_fare_text(text)
        assert result.success is True
        assert result.base_fare_usd == 450.0
        assert result.yq_total_usd == 0.0
        assert result.yr_total_usd == 45.0
        assert result.total_price_usd == 532.0

    def test_parse_with_yq_present(self):
        """When YQ is charged, dump has failed."""
        text = """
        Base fare: $350.00
        YQ  580.00
        YR  45.00
        US  32.50
        Total: $1007.50
        """
        result = parse_fare_text(text)
        assert result.success is True
        assert result.yq_total_usd == 580.0
        assert result.is_dump_success is False

    def test_parse_dump_success(self):
        """When YQ is zero, dump is successful."""
        text = """
        Base fare: $450.00
        YQ  0.00
        YR  45.00
        Total: $495.00
        """
        result = parse_fare_text(text)
        assert result.is_dump_success is True
        assert result.yq_savings == 0.0

    def test_parse_no_total_calculates(self):
        """When Total is missing, it should be calculated from components."""
        text = """
        Base fare: $450.00
        YQ  0.00
        YR  45.00
        US  32.50
        """
        result = parse_fare_text(text)
        assert result.success is True
        assert result.total_price_usd == 450.0 + 0.0 + 45.0 + 32.5

    def test_parse_commas_in_amounts(self):
        text = """
        Base fare: $1,250.00
        YQ  0.00
        Total: $1,250.00
        """
        result = parse_fare_text(text)
        assert result.base_fare_usd == 1250.0

    def test_empty_text_returns_success_with_zeros(self):
        result = parse_fare_text("")
        assert result.success is True
        assert result.base_fare_usd == 0.0


class TestFareBreakdown:
    def test_to_dict(self):
        breakdown = FareBreakdown(
            success=True,
            base_fare_usd=450.0,
            yq_total_usd=0.0,
            yr_total_usd=45.0,
            total_price_usd=495.0,
            tax_lines=[TaxLine(code="YR", description="", amount_usd=45.0)],
            segments=[
                SegmentInfo(
                    origin="JFK",
                    destination="FRA",
                    operating_carrier="LH",
                    ticketing_carrier="LH",
                    fare_basis="YLOWUS",
                )
            ],
        )
        d = breakdown.to_dict()
        assert d["success"] is True
        assert d["base_fare_usd"] == 450.0
        assert len(d["tax_lines"]) == 1
        assert len(d["segments"]) == 1
        assert d["segments"][0]["origin"] == "JFK"

    def test_is_dump_success_threshold(self):
        """YQ under $1 counts as success."""
        b1 = FareBreakdown(success=True, yq_total_usd=0.0)
        assert b1.is_dump_success is True

        b2 = FareBreakdown(success=True, yq_total_usd=0.99)
        assert b2.is_dump_success is True

        b3 = FareBreakdown(success=True, yq_total_usd=1.0)
        assert b3.is_dump_success is False


# ─── ITAResult ──────────────────────────────────────────────────────────────


class TestITAResult:
    def test_default_values(self):
        result = ITAResult()
        assert result.success is False
        assert result.error_message is None
        assert result.fare_breakdown is None
        assert result.bot_detected is False

    def test_successful_result(self):
        breakdown = FareBreakdown(success=True, base_fare_usd=450.0, yq_total_usd=0.0)
        result = ITAResult(
            success=True,
            fare_breakdown=breakdown,
            proxy_used="http://proxy:8080",
            query_duration_seconds=12.5,
        )
        assert result.success is True
        assert result.fare_breakdown.is_dump_success is True
        assert result.proxy_used == "http://proxy:8080"

    def test_to_dict(self):
        breakdown = FareBreakdown(success=True, base_fare_usd=450.0)
        result = ITAResult(
            success=True,
            fare_breakdown=breakdown,
            query_duration_seconds=10.0,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert "fare_breakdown" in d
        assert d["fare_breakdown"]["base_fare_usd"] == 450.0
        assert d["query_duration_seconds"] == 10.0

    def test_to_dict_without_breakdown(self):
        result = ITAResult(success=False, error_message="Timeout")
        d = result.to_dict()
        assert d["success"] is False
        assert d["error_message"] == "Timeout"
        assert "fare_breakdown" not in d


# ─── ITAClient (Mocked) ────────────────────────────────────────────────────


class TestITAClientMocked:
    @pytest.mark.asyncio
    async def test_run_query_never_raises(self):
        """run_query must never raise, even on unexpected errors."""
        mock_pw = MagicMock()
        mock_browser_inst = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser_inst)
        mock_browser_inst.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)

        # Make page.goto raise an exception
        mock_page.goto = AsyncMock(side_effect=Exception("Network error"))
        mock_page.url = "about:blank"
        mock_page.close = AsyncMock()

        browser = BrowserManager(_playwright=mock_pw)
        proxies = ProxyManager(proxy_urls=["http://proxy:8080"])
        limiter = RateLimiter(min_delay=0.0, jitter_max=0.0)

        client = ITAClient(
            browser=browser,
            proxies=proxies,
            rate_limiter=limiter,
            max_retries=0,
        )

        # This should NOT raise
        result = await client.run_query(
            routing_code="FORCE LH:JFK-FRA",
            origin="JFK",
            destination="FRA",
        )

        assert result.success is False
        assert result.error_message is not None
        assert "Network error" in result.error_message

        await browser.close()

    @pytest.mark.asyncio
    async def test_bot_detection_retires_proxy(self):
        """When bot detected, proxy should be retired."""
        mock_pw = MagicMock()
        mock_browser_inst = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_pw.chromium.launch = AsyncMock(return_value=mock_browser_inst)
        mock_browser_inst.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_page.goto = AsyncMock()
        mock_page.url = "https://captcha.example.com"  # Not ITA Matrix
        mock_page.close = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)

        browser = BrowserManager(_playwright=mock_pw)
        proxies = ProxyManager(proxy_urls=["http://proxy1:8080", "http://proxy2:8080"])
        limiter = RateLimiter(min_delay=0.0, jitter_max=0.0)

        client = ITAClient(
            browser=browser,
            proxies=proxies,
            rate_limiter=limiter,
            max_retries=0,
        )

        result = await client.run_query(
            routing_code="FORCE LH:JFK-FRA",
            origin="JFK",
            destination="FRA",
        )

        assert result.success is False
        assert result.bot_detected is True
        # proxy1 should now be retired
        assert proxies._proxies["http://proxy1:8080"].is_retired

        await browser.close()
