"""
base.py — Abstract base scraper and shared types for YQ data collection.

All YQ scrapers inherit from BaseYQScraper and implement scrape_yq().
YQScrapeResult is the standard return type — never raise from scrapers.

Two scraping strategies:
- Approach A: Parse airline booking pages via httpx (fast, may break)
- Approach B: Run ITA Matrix query for a non-dumped route (slower, reliable)

All scrapers in this codebase use Approach B (ITA Matrix baseline) because
airline booking flows change frequently and break scrapers. ITA Matrix
parsing is already built (Phase 04) and is more stable.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class YQScrapeResult:
    """
    Result of a single YQ scrape attempt.

    yq_amount_usd is None if the scrape failed.
    error is set on failure, None on success.
    """

    carrier_iata: str
    origin: str
    destination: str
    yq_amount_usd: float | None = None
    yr_amount_usd: float | None = None
    base_fare_usd: float | None = None
    source_url: str = ""
    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.yq_amount_usd is not None and self.error is None


class BaseYQScraper(ABC):
    """
    Abstract base class for airline YQ scrapers.

    Subclasses implement scrape_yq() for their specific carrier.
    """

    carrier_iata: str = ""
    carrier_name: str = ""

    # Sample routes to test for YQ. Override per carrier.
    sample_routes: list[tuple[str, str]] = []

    @abstractmethod
    async def scrape_yq(self, origin: str, destination: str) -> YQScrapeResult:
        """
        Scrape the current YQ amount for this carrier on the given route.

        Must NEVER raise exceptions. Return YQScrapeResult with error set.

        Args:
            origin: 3-letter IATA origin airport
            destination: 3-letter IATA destination airport

        Returns:
            YQScrapeResult with yq_amount_usd set on success.
        """
        ...

    async def scrape_all_routes(self) -> list[YQScrapeResult]:
        """
        Scrape YQ for all sample routes defined for this carrier.

        Returns a list of results (some may have errors).
        """
        results = []
        for origin, destination in self.sample_routes:
            try:
                result = await self.scrape_yq(origin, destination)
                results.append(result)
            except Exception as e:
                logger.error(
                    "Unexpected error scraping %s %s-%s: %s",
                    self.carrier_iata,
                    origin,
                    destination,
                    e,
                )
                results.append(
                    YQScrapeResult(
                        carrier_iata=self.carrier_iata,
                        origin=origin,
                        destination=destination,
                        error=f"Unexpected error: {str(e)}",
                    )
                )
        return results

    def calculate_typical_yq(self, results: list[YQScrapeResult]) -> float | None:
        """
        Calculate the typical YQ amount from multiple scrape results.

        Returns the median of successful results, or None if no successes.
        """
        amounts = [r.yq_amount_usd for r in results if r.success and r.yq_amount_usd is not None]
        if not amounts:
            return None
        amounts.sort()
        mid = len(amounts) // 2
        if len(amounts) % 2 == 0:
            return (amounts[mid - 1] + amounts[mid]) / 2
        return amounts[mid]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} carrier={self.carrier_iata}>"
