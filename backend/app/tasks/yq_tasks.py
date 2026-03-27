"""
yq_tasks.py — Celery tasks for YQ data collection.

Phase 05 stub: defines the task signatures for weekly YQ updates.
Full Celery integration (celery_app, beat schedule) is wired in Phase 08.

Tasks:
- update_all_carrier_yq: dispatches YQ scrapes for all configured carriers
- update_single_carrier_yq: scrapes YQ for one carrier, stores results
"""
from app.tasks.celery_app import celery_app


import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def _run_all_carrier_yq_update(
    carrier_filter: list[str] | None = None,
) -> dict[str, Any]:
    """
    Async implementation of full YQ update sweep.

    Creates scrapers, dispatches them, and stores results via yq_service.
    """
    from ingestion.scrapers.yq.carriers import create_all_scrapers, create_scraper
    from ingestion.scrapers.yq_dispatcher import dispatch_all

    if carrier_filter:
        scrapers = []
        for iata in carrier_filter:
            s = create_scraper(iata)
            if s:
                scrapers.append(s)
    else:
        scrapers = create_all_scrapers()

    if not scrapers:
        return {
            "success": False,
            "error": "No scrapers configured",
            "carriers_scraped": 0,
        }

    dispatch_result = await dispatch_all(scrapers, carrier_filter=carrier_filter)

    return {
        "success": True,
        "carriers_scraped": dispatch_result.carriers_scraped,
        "total_results": len(dispatch_result.results),
        "success_rate": round(dispatch_result.success_rate, 3),
        "errors": [
            {
                "carrier": r.carrier_iata,
                "origin": r.origin,
                "destination": r.destination,
                "error": r.error,
            }
            for r in dispatch_result.results
            if r.error
        ],
    }


async def _run_single_carrier_yq_update(carrier_iata: str) -> dict[str, Any]:
    """
    Async implementation of single-carrier YQ update.

    Scrapes all configured routes for one carrier and computes typical YQ.
    """
    from ingestion.scrapers.yq.carriers import create_scraper

    scraper = create_scraper(carrier_iata)
    if not scraper:
        return {
            "success": False,
            "carrier": carrier_iata,
            "error": f"No scraper configured for carrier {carrier_iata}",
        }

    results = await scraper.scrape_all_routes()
    typical_yq = scraper.calculate_typical_yq(results)

    successful = [r for r in results if r.error is None]
    failed = [r for r in results if r.error is not None]

    return {
        "success": len(successful) > 0,
        "carrier": carrier_iata,
        "routes_scraped": len(results),
        "routes_successful": len(successful),
        "routes_failed": len(failed),
        "typical_yq_usd": typical_yq,
        "errors": [
            {"origin": r.origin, "destination": r.destination, "error": r.error}
            for r in failed
        ],
    }


@celery_app.task(
    name="app.tasks.yq_tasks.update_all_carrier_yq",
    queue="yq",
)
def update_all_carrier_yq(
    carrier_filter: list[str] | None = None,
) -> dict[str, Any]:
    """
    Synchronous entry point for Celery.

    Dispatches YQ scraping for all (or filtered) carriers.
    Called weekly by Celery Beat (Phase 08 wiring).


    Args:
        carrier_filter: Optional list of IATA codes to limit scraping.

    Returns:
        Dict with success status, counts, and any errors.
    """
    try:
        return asyncio.run(_run_all_carrier_yq_update(carrier_filter))
    except Exception as e:
        logger.error("update_all_carrier_yq failed: %s", e, exc_info=True)
        return {
            "success": False,
            "error": f"Task failed: {str(e)}",
            "carriers_scraped": 0,
        }


@celery_app.task(
    name="app.tasks.yq_tasks.update_single_carrier_yq",
    queue="yq",
)
def update_single_carrier_yq(carrier_iata: str) -> dict[str, Any]:
    """
    Synchronous entry point for Celery.

    Scrapes YQ for a single carrier across all configured routes.


    Args:
        carrier_iata: 2-letter IATA code.

    Returns:
        Dict with success status, typical_yq_usd, and any errors.
    """
    try:
        return asyncio.run(_run_single_carrier_yq_update(carrier_iata))
    except Exception as e:
        logger.error(
            "update_single_carrier_yq(%s) failed: %s",
            carrier_iata,
            e,
            exc_info=True,
        )
        return {
            "success": False,
            "carrier": carrier_iata,
            "error": f"Task failed: {str(e)}",
        }
