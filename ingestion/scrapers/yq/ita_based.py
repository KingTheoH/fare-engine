"""
ita_based.py — ITA Matrix-based YQ scraper (Approach B).

Instead of scraping individual airline booking pages (fragile),
this scraper runs a standard (non-dumped) ITA Matrix query for the
carrier on a representative route, then reads the YQ from the
fare breakdown.

This is the fallback strategy described in Phase 05 spec:
"For carriers where booking page scraping is too fragile, run a
standard ITA Matrix query and parse yq_total_usd from the result."

Since all airline booking flows change frequently and break scrapers,
we use this approach for ALL carriers. ITA Matrix parsing is already
built (Phase 04) and is more stable.
"""

import logging
from datetime import datetime, timezone

from ingestion.scrapers.base import BaseYQScraper, YQScrapeResult

logger = logging.getLogger(__name__)


class ITABasedYQScraper(BaseYQScraper):
    """
    Generic YQ scraper that uses ITA Matrix to determine a carrier's YQ.

    Runs a simple non-dumped query (no routing code manipulation) to see
    what YQ the carrier normally charges on a given route.

    This requires the ITA automation engine (Phase 04) to be available.
    In unit tests, the ita_client is mocked.
    """

    def __init__(
        self,
        carrier_iata: str,
        carrier_name: str,
        sample_routes: list[tuple[str, str]],
        ita_client: object | None = None,
    ):
        self.carrier_iata = carrier_iata
        self.carrier_name = carrier_name
        self.sample_routes = sample_routes
        self._ita_client = ita_client

    async def scrape_yq(self, origin: str, destination: str) -> YQScrapeResult:
        """
        Query ITA Matrix for a non-dumped fare on this carrier and extract YQ.

        Uses a simple FORCE <carrier>:<origin>-<destination> routing code
        (non-manipulated) to see what YQ the carrier normally charges.
        """
        now = datetime.now(timezone.utc)
        routing_code = f"FORCE {self.carrier_iata}:{origin}-{destination}"
        source_url = f"https://matrix.itasoftware.com (route: {origin}-{destination})"

        if self._ita_client is None:
            return YQScrapeResult(
                carrier_iata=self.carrier_iata,
                origin=origin,
                destination=destination,
                source_url=source_url,
                scraped_at=now,
                error="ITA client not configured — cannot scrape YQ",
            )

        try:
            result = await self._ita_client.run_query(
                routing_code=routing_code,
                origin=origin,
                destination=destination,
            )

            if not result.success:
                return YQScrapeResult(
                    carrier_iata=self.carrier_iata,
                    origin=origin,
                    destination=destination,
                    source_url=source_url,
                    scraped_at=now,
                    error=result.error_message or "ITA query failed",
                )

            breakdown = result.fare_breakdown
            if breakdown is None:
                return YQScrapeResult(
                    carrier_iata=self.carrier_iata,
                    origin=origin,
                    destination=destination,
                    source_url=source_url,
                    scraped_at=now,
                    error="No fare breakdown in ITA result",
                )

            return YQScrapeResult(
                carrier_iata=self.carrier_iata,
                origin=origin,
                destination=destination,
                yq_amount_usd=breakdown.yq_total_usd,
                yr_amount_usd=breakdown.yr_total_usd,
                base_fare_usd=breakdown.base_fare_usd,
                source_url=source_url,
                scraped_at=now,
            )

        except Exception as e:
            logger.error("ITA scrape failed for %s %s-%s: %s", self.carrier_iata, origin, destination, e)
            return YQScrapeResult(
                carrier_iata=self.carrier_iata,
                origin=origin,
                destination=destination,
                source_url=source_url,
                scraped_at=now,
                error=f"ITA scrape error: {str(e)}",
            )
