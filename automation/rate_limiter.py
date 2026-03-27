"""
rate_limiter.py — Request throttling with jitter for ITA Matrix automation.

Enforces minimum delays between requests to avoid bot detection.
Adds random jitter to make request patterns less predictable.

Settings come from app config:
- ITA_RATE_LIMIT_SECONDS (default 3.5)
- ITA_JITTER_MAX_SECONDS (default 2.0)
"""

import asyncio
import random
import time
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    """
    Async rate limiter with jitter.

    Usage:
        limiter = RateLimiter(min_delay=3.5, jitter_max=2.0)
        await limiter.wait()  # blocks until safe to proceed
    """

    min_delay: float = 3.5
    jitter_max: float = 2.0
    _last_request_time: float = field(default=0.0, init=False)

    async def wait(self) -> float:
        """
        Wait until it's safe to make the next request.

        Returns the actual delay in seconds (for logging/metrics).
        """
        now = time.monotonic()
        elapsed = now - self._last_request_time

        # Calculate required delay with jitter
        jitter = random.uniform(0, self.jitter_max)
        required_delay = self.min_delay + jitter

        if elapsed < required_delay:
            sleep_time = required_delay - elapsed
            await asyncio.sleep(sleep_time)
        else:
            sleep_time = 0.0

        self._last_request_time = time.monotonic()
        return sleep_time + (required_delay - max(elapsed, required_delay - sleep_time))

    def reset(self) -> None:
        """Reset the limiter (e.g., after a long pause or proxy switch)."""
        self._last_request_time = 0.0

    @property
    def seconds_since_last(self) -> float:
        """Seconds since the last request."""
        if self._last_request_time == 0.0:
            return float("inf")
        return time.monotonic() - self._last_request_time
