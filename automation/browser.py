"""
browser.py — Playwright browser/context lifecycle manager.

Manages browser sessions with automatic recycling after SESSION_LIMIT requests.
Uses realistic viewports and randomized user agents to avoid bot detection.

Key behaviors:
- Recycle browser context after 15 requests
- Random viewport selection from 3 realistic sizes
- Random user agent from a pool of 10 real Chrome UAs
- Proxy support per context
"""

import json
import logging
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SESSION_LIMIT = 15  # Restart browser context after this many requests

VIEWPORTS = [
    {"width": 1280, "height": 800},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
]

# Load user agents from data file
_UA_FILE = Path(__file__).parent / "data" / "user_agents.json"


def _load_user_agents() -> list[str]:
    try:
        with open(_UA_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("User agents file not found, using fallback")
        return [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ]


USER_AGENTS = _load_user_agents()


@dataclass
class BrowserManager:
    """
    Manages Playwright browser and context lifecycle.

    Usage:
        async with BrowserManager(playwright) as manager:
            page = await manager.get_page(proxy_url="http://proxy:8080")
            # ... use page ...
            await manager.mark_request()  # track request count

    The context is automatically recycled after SESSION_LIMIT requests.
    """

    _playwright: Any = None  # playwright.async_api.Playwright
    _browser: Any = field(default=None, init=False)
    _context: Any = field(default=None, init=False)
    _page: Any = field(default=None, init=False)
    _request_count: int = field(default=0, init=False)
    _current_proxy: str | None = field(default=None, init=False)

    async def __aenter__(self) -> "BrowserManager":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def get_page(self, proxy_url: str | None = None) -> Any:
        """
        Get a Playwright Page, creating or recycling the browser context as needed.

        Args:
            proxy_url: Optional proxy to use for this context.

        Returns:
            A Playwright Page instance.
        """
        needs_new_context = (
            self._page is None
            or self._request_count >= SESSION_LIMIT
            or proxy_url != self._current_proxy
        )

        if needs_new_context:
            await self._create_context(proxy_url)

        return self._page

    async def mark_request(self) -> None:
        """
        Increment request counter. Call after each ITA Matrix query.

        Triggers context recycle on next get_page() call when limit is hit.
        """
        self._request_count += 1
        if self._request_count >= SESSION_LIMIT:
            logger.info(
                "Session limit reached (%d/%d) — will recycle on next request",
                self._request_count,
                SESSION_LIMIT,
            )

    async def close(self) -> None:
        """Close browser and all contexts."""
        if self._page:
            try:
                await self._page.close()
            except Exception:
                pass
            self._page = None

        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

    async def _create_context(self, proxy_url: str | None = None) -> None:
        """Create a fresh browser context with randomized fingerprint."""
        # Close existing
        if self._page:
            try:
                await self._page.close()
            except Exception:
                pass
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass

        # Launch browser if needed
        if self._browser is None:
            launch_opts: dict[str, Any] = {"headless": True}
            self._browser = await self._playwright.chromium.launch(**launch_opts)

        # Randomize fingerprint
        viewport = random.choice(VIEWPORTS)
        user_agent = random.choice(USER_AGENTS)

        context_opts: dict[str, Any] = {
            "viewport": viewport,
            "user_agent": user_agent,
            "locale": "en-US",
            "timezone_id": "America/New_York",
        }

        if proxy_url:
            context_opts["proxy"] = {"server": proxy_url}
            self._current_proxy = proxy_url

        self._context = await self._browser.new_context(**context_opts)
        self._page = await self._context.new_page()
        self._request_count = 0

        logger.info(
            "New browser context: viewport=%s, UA=...%s, proxy=%s",
            f"{viewport['width']}x{viewport['height']}",
            user_agent[-30:],
            proxy_url or "direct",
        )

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def remaining_requests(self) -> int:
        return max(0, SESSION_LIMIT - self._request_count)
