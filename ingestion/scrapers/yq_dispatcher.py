"""
yq_dispatcher.py — Runs all configured YQ scrapers in sequence.

Orchestrates the scraping of YQ data across all carriers.
Results are collected and returned as a flat list of YQScrapeResults.

The dispatcher runs scrapers sequentially (not parallel) to avoid
overwhelming ITA Matrix rate limits.
"""

import logging
from dataclasses import dataclass, field

from ingestion.scrapers.base import BaseYQScraper, YQScrapeResult

logger = logging.getLogger(__name__)


@dataclass
class DispatchResult:
    """Aggregate result from running all scrapers."""

    results: list[YQScrapeResult] = field(default_factory=list)
    carriers_scraped: int = 0
    carriers_failed: int = 0
    total_routes: int = 0
    successful_routes: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_routes == 0:
            return 0.0
        return self.successful_routes / self.total_routes

    def summary(self) -> dict:
        return {
            "carriers_scraped": self.carriers_scraped,
            "carriers_failed": self.carriers_failed,
            "total_routes": self.total_routes,
            "successful_routes": self.successful_routes,
            "success_rate": round(self.success_rate, 2),
        }


async def dispatch_all(
    scrapers: list[BaseYQScraper],
    carrier_filter: list[str] | None = None,
) -> DispatchResult:
    """
    Run all scrapers in sequence and collect results.

    Args:
        scrapers: List of scraper instances to run.
        carrier_filter: Optional list of carrier IATA codes to limit scraping to.
                       If None, all scrapers are run.

    Returns:
        DispatchResult with all results and summary stats.
    """
    dispatch = DispatchResult()

    for scraper in scrapers:
        if carrier_filter and scraper.carrier_iata not in carrier_filter:
            continue

        logger.info("Scraping YQ for %s (%s)", scraper.carrier_name, scraper.carrier_iata)

        try:
            results = await scraper.scrape_all_routes()
            dispatch.results.extend(results)
            dispatch.carriers_scraped += 1

            successes = sum(1 for r in results if r.success)
            dispatch.total_routes += len(results)
            dispatch.successful_routes += successes

            if successes == 0:
                dispatch.carriers_failed += 1
                logger.warning(
                    "All routes failed for %s (%s)", scraper.carrier_name, scraper.carrier_iata
                )
            else:
                typical_yq = scraper.calculate_typical_yq(results)
                logger.info(
                    "%s: %d/%d routes succeeded, typical YQ: $%.2f",
                    scraper.carrier_iata,
                    successes,
                    len(results),
                    typical_yq or 0.0,
                )

        except Exception as e:
            dispatch.carriers_failed += 1
            dispatch.carriers_scraped += 1
            logger.error("Scraper failed for %s: %s", scraper.carrier_iata, e)

    logger.info(
        "Dispatch complete: %d carriers, %d/%d routes succeeded (%.0f%%)",
        dispatch.carriers_scraped,
        dispatch.successful_routes,
        dispatch.total_routes,
        dispatch.success_rate * 100,
    )

    return dispatch
