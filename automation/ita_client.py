"""
ita_client.py — Main ITA Matrix interaction layer.

Orchestrates the full query flow:
1. Navigate to ITA Matrix
2. Fill search form (origin, destination, dates)
3. Enter routing codes via "More options"
4. Submit search
5. Wait for results
6. Click first fare to expand breakdown
7. Parse fare construction

IMPORTANT: run_query() NEVER raises exceptions.
Always returns an ITAResult with success=True/False.

Human-like behavior:
- page.type() with keystroke delays (30–120ms per char)
- Random pauses 1.5–3.5s between actions
- Mouse movement to elements before clicking
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from automation.browser import BrowserManager
from automation.proxy_manager import ProxyManager
from automation.rate_limiter import RateLimiter
from automation.result_parser import FareBreakdown, detect_bot_check, parse_fare_breakdown

logger = logging.getLogger(__name__)

ITA_MATRIX_URL = "https://matrix.itasoftware.com"


@dataclass
class ITAResult:
    """
    Structured result from an ITA Matrix query.

    run_query() always returns this — never raises.
    """

    success: bool = False
    error_message: str | None = None
    fare_breakdown: FareBreakdown | None = None
    proxy_used: str | None = None
    query_duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    bot_detected: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize for storage in validation_runs.raw_ita_response."""
        result: dict[str, Any] = {
            "success": self.success,
            "error_message": self.error_message,
            "proxy_used": self.proxy_used,
            "query_duration_seconds": self.query_duration_seconds,
            "timestamp": self.timestamp.isoformat(),
            "bot_detected": self.bot_detected,
        }
        if self.fare_breakdown:
            result["fare_breakdown"] = self.fare_breakdown.to_dict()
        return result


@dataclass
class ITAClient:
    """
    ITA Matrix automation client.

    Usage:
        client = ITAClient(browser_manager, proxy_manager, rate_limiter)
        result = await client.run_query(
            routing_code="FORCE LH:JFK-FRA / FORCE LH:FRA-BKK",
            origin="JFK",
            destination="BKK",
        )
    """

    browser: BrowserManager
    proxies: ProxyManager
    rate_limiter: RateLimiter
    max_retries: int = 1  # Only retry once — don't hammer ITA Matrix

    async def run_query(
        self,
        routing_code: str,
        origin: str,
        destination: str,
        outbound_date: str | None = None,
        return_date: str | None = None,
    ) -> ITAResult:
        """
        Execute an ITA Matrix query and return structured results.

        NEVER raises exceptions. Returns ITAResult(success=False) on any failure.

        Args:
            routing_code: ITA Matrix routing code string
            origin: 3-letter IATA origin airport
            destination: 3-letter IATA destination airport
            outbound_date: Optional date string (MM/DD/YYYY)
            return_date: Optional return date string (MM/DD/YYYY)
        """
        import time

        start = time.monotonic()
        proxy_url = self.proxies.get_proxy()
        attempts = 0

        while attempts <= self.max_retries:
            attempts += 1
            result = await self._attempt_query(
                routing_code=routing_code,
                origin=origin,
                destination=destination,
                outbound_date=outbound_date,
                return_date=return_date,
                proxy_url=proxy_url,
            )

            result.query_duration_seconds = time.monotonic() - start
            result.proxy_used = proxy_url

            if result.success:
                if proxy_url:
                    self.proxies.record_use(proxy_url)
                return result

            if result.bot_detected:
                # Rotate proxy immediately, don't retry with same one
                if proxy_url:
                    self.proxies.retire(proxy_url)
                    proxy_url = self.proxies.get_proxy()
                logger.warning("Bot detected, rotating proxy")

            if attempts <= self.max_retries:
                logger.info("Retrying query (attempt %d/%d)", attempts + 1, self.max_retries + 1)
                if proxy_url is None:
                    proxy_url = self.proxies.get_proxy()

        # All retries exhausted
        result.query_duration_seconds = time.monotonic() - start
        return result

    async def _attempt_query(
        self,
        routing_code: str,
        origin: str,
        destination: str,
        outbound_date: str | None,
        return_date: str | None,
        proxy_url: str | None,
    ) -> ITAResult:
        """Single query attempt. Returns ITAResult, never raises."""
        try:
            # Rate limit
            await self.rate_limiter.wait()

            # Get page
            page = await self.browser.get_page(proxy_url)

            # Navigate to ITA Matrix
            await page.goto(ITA_MATRIX_URL, wait_until="networkidle", timeout=30000)
            await _human_pause()

            # Check for bot detection after navigation
            if await detect_bot_check(page):
                return ITAResult(
                    success=False,
                    error_message="Bot detection on initial navigation",
                    bot_detected=True,
                    proxy_used=proxy_url,
                )

            # Fill origin
            origin_input = await page.wait_for_selector(
                "input[name*='origin'], input[aria-label*='origin'], "
                "input[placeholder*='origin'], #city1",
                timeout=10000,
            )
            if origin_input:
                await origin_input.click()
                await _human_pause(0.3, 0.8)
                await page.keyboard.press("Control+a")
                await _human_type(page, origin)
                await _human_pause(0.5, 1.5)
                await page.keyboard.press("Enter")
                await _human_pause()

            # Fill destination
            dest_input = await page.wait_for_selector(
                "input[name*='destination'], input[aria-label*='destination'], "
                "input[placeholder*='destination'], #city2",
                timeout=10000,
            )
            if dest_input:
                await dest_input.click()
                await _human_pause(0.3, 0.8)
                await page.keyboard.press("Control+a")
                await _human_type(page, destination)
                await _human_pause(0.5, 1.5)
                await page.keyboard.press("Enter")
                await _human_pause()

            # Fill dates if provided
            if outbound_date:
                date_input = await page.query_selector(
                    "input[name*='date'], input[aria-label*='depart'], #date1"
                )
                if date_input:
                    await date_input.click()
                    await _human_pause(0.3, 0.8)
                    await page.keyboard.press("Control+a")
                    await _human_type(page, outbound_date)
                    await _human_pause()

            if return_date:
                return_input = await page.query_selector(
                    "input[name*='return'], input[aria-label*='return'], #date2"
                )
                if return_input:
                    await return_input.click()
                    await _human_pause(0.3, 0.8)
                    await page.keyboard.press("Control+a")
                    await _human_type(page, return_date)
                    await _human_pause()

            # Open "More options" / advanced panel
            more_options = await page.query_selector(
                "button:has-text('More options'), a:has-text('More options'), "
                "[class*='advanced'], [class*='routing']"
            )
            if more_options:
                await more_options.click()
                await _human_pause()

            # Enter routing code
            routing_input = await page.wait_for_selector(
                "textarea[name*='routing'], input[name*='routing'], "
                "textarea[aria-label*='routing'], textarea[aria-label*='Routing'], "
                "[class*='routing'] textarea, [class*='routing'] input",
                timeout=10000,
            )
            if routing_input:
                await routing_input.click()
                await _human_pause(0.3, 0.8)
                await _human_type(page, routing_code)
                await _human_pause()
            else:
                return ITAResult(
                    success=False,
                    error_message="Could not find routing codes input field",
                    proxy_used=proxy_url,
                )

            # Submit search
            search_button = await page.query_selector(
                "button:has-text('Search'), input[type='submit'], "
                "button[type='submit'], [class*='search'] button"
            )
            if search_button:
                await search_button.click()
            else:
                await page.keyboard.press("Enter")

            # Wait for results
            await _human_pause(2.0, 5.0)

            try:
                await page.wait_for_selector(
                    "[class*='result'], [class*='fare'], [class*='itinerary']",
                    timeout=45000,
                )
            except Exception:
                # Check if bot detection triggered during search
                if await detect_bot_check(page):
                    return ITAResult(
                        success=False,
                        error_message="Bot detection during search",
                        bot_detected=True,
                        proxy_used=proxy_url,
                    )
                return ITAResult(
                    success=False,
                    error_message="Timeout waiting for search results (45s)",
                    proxy_used=proxy_url,
                )

            # Click first fare result to expand breakdown
            first_fare = await page.query_selector(
                "[class*='result-row'], [class*='fareRow'], "
                "tr[class*='fare'], [class*='itinerary']"
            )
            if first_fare:
                await first_fare.click()
                await _human_pause(1.0, 3.0)

            # Parse fare breakdown
            fare_breakdown = await parse_fare_breakdown(page)

            # Mark request
            await self.browser.mark_request()

            return ITAResult(
                success=fare_breakdown.success,
                error_message=fare_breakdown.error_message,
                fare_breakdown=fare_breakdown,
                proxy_used=proxy_url,
            )

        except asyncio.TimeoutError:
            return ITAResult(
                success=False,
                error_message="Page timeout",
                proxy_used=proxy_url,
            )
        except Exception as e:
            logger.error("Query failed: %s", e, exc_info=True)
            return ITAResult(
                success=False,
                error_message=f"Unexpected error: {str(e)}",
                proxy_used=proxy_url,
            )


async def _human_pause(min_seconds: float = 1.5, max_seconds: float = 3.5) -> None:
    """Random pause to simulate human interaction speed."""
    await asyncio.sleep(random.uniform(min_seconds, max_seconds))


async def _human_type(page: Any, text: str) -> None:
    """Type text with human-like keystroke delays (30–120ms per character)."""
    for char in text:
        await page.keyboard.type(char, delay=random.randint(30, 120))
