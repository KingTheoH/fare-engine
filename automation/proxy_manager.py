"""
proxy_manager.py — Rotating residential proxy pool for ITA Matrix automation.

Manages proxy lifecycle:
- Tracks usage count per proxy (rotate before daily limit)
- Retires proxies for 24h on bot detection
- Rotates to next available proxy when limits hit
- Health checks (placeholder for Phase 08 integration)

Proxy strings format: "http://user:pass@host:port" or "socks5://host:port"
"""

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Limits from spec
DAILY_LIMIT = 200  # Max requests per proxy per day
RETIREMENT_SECONDS = 24 * 60 * 60  # 24h retirement on bot detection


@dataclass
class ProxyState:
    """Tracks usage and health of a single proxy."""

    url: str
    request_count: int = 0
    retired_until: float = 0.0  # monotonic timestamp
    last_used: float = 0.0
    bot_detection_count: int = 0

    @property
    def is_retired(self) -> bool:
        return time.monotonic() < self.retired_until

    @property
    def is_at_limit(self) -> bool:
        return self.request_count >= DAILY_LIMIT

    @property
    def is_available(self) -> bool:
        return not self.is_retired and not self.is_at_limit


@dataclass
class ProxyManager:
    """
    Rotating proxy pool.

    Usage:
        manager = ProxyManager(["http://proxy1:8080", "http://proxy2:8080"])
        proxy = manager.get_proxy()      # returns best available proxy URL
        manager.record_use(proxy)         # increment usage counter
        manager.retire(proxy)             # retire on bot detection
    """

    proxy_urls: list[str] = field(default_factory=list)
    _proxies: dict[str, ProxyState] = field(default_factory=dict, init=False)
    _current_index: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        for url in self.proxy_urls:
            self._proxies[url] = ProxyState(url=url)

    def get_proxy(self) -> str | None:
        """
        Get the next available proxy URL.

        Returns None if all proxies are retired or at their daily limit.
        Rotates through proxies in round-robin order, skipping unavailable ones.
        """
        if not self._proxies:
            return None

        urls = list(self._proxies.keys())
        checked = 0

        while checked < len(urls):
            idx = self._current_index % len(urls)
            self._current_index += 1
            checked += 1

            proxy = self._proxies[urls[idx]]
            if proxy.is_available:
                return proxy.url

        logger.warning("All proxies exhausted — all retired or at daily limit")
        return None

    def record_use(self, proxy_url: str) -> None:
        """Record a successful request through a proxy."""
        if proxy_url in self._proxies:
            self._proxies[proxy_url].request_count += 1
            self._proxies[proxy_url].last_used = time.monotonic()

    def retire(self, proxy_url: str) -> None:
        """
        Retire a proxy for 24 hours (bot detection).

        The proxy will not be returned by get_proxy() until the
        retirement period expires.
        """
        if proxy_url in self._proxies:
            proxy = self._proxies[proxy_url]
            proxy.retired_until = time.monotonic() + RETIREMENT_SECONDS
            proxy.bot_detection_count += 1
            logger.warning(
                "Proxy %s retired for 24h (bot detection #%d)",
                proxy_url,
                proxy.bot_detection_count,
            )

    def reset_daily_counts(self) -> None:
        """Reset all daily request counters. Call once per day."""
        for proxy in self._proxies.values():
            proxy.request_count = 0
        logger.info("Reset daily proxy counts for %d proxies", len(self._proxies))

    def get_stats(self) -> dict:
        """Get proxy pool statistics."""
        total = len(self._proxies)
        available = sum(1 for p in self._proxies.values() if p.is_available)
        retired = sum(1 for p in self._proxies.values() if p.is_retired)
        at_limit = sum(1 for p in self._proxies.values() if p.is_at_limit)
        return {
            "total": total,
            "available": available,
            "retired": retired,
            "at_limit": at_limit,
            "total_requests": sum(p.request_count for p in self._proxies.values()),
        }

    @property
    def available_count(self) -> int:
        return sum(1 for p in self._proxies.values() if p.is_available)
