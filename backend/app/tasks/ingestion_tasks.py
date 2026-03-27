"""
ingestion_tasks.py — Celery tasks for community data ingestion.

Tasks:
- scan_all_forums: Scrape configured FlyerTalk forums for new posts
- process_pending_posts: Run LLM extraction on unprocessed community_posts
"""
from app.tasks.celery_app import celery_app

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def _run_forum_scan(
    forum_urls: list[str] | None = None,
) -> dict[str, Any]:
    """
    Async implementation of forum scanning.

    Scrapes configured FlyerTalk forums, stores new posts,
    and returns scan statistics.
    """
    from ingestion.scrapers.flyertalk import FlyerTalkScraper

    scraper = FlyerTalkScraper()
    if forum_urls:
        scraper.forum_urls = forum_urls

    try:
        scan_result = await scraper.scan_forums()

        return {
            "success": True,
            "threads_scanned": scan_result.threads_scanned,
            "threads_matched": scan_result.threads_matched,
            "posts_scraped": scan_result.posts_scraped,
            "error_count": len(scan_result.errors),
            "errors": scan_result.errors[:10],
        }
    finally:
        await scraper.close()


async def _run_post_processing(
    limit: int = 50,
    api_key: str = "",
) -> dict[str, Any]:
    """
    Async implementation of LLM post processing.

    Fetches unprocessed community_posts and runs them through the
    two-pass LLM extraction pipeline. Inserts valid patterns into
    dump_patterns for ITA Matrix validation.
    """
    from app.config import get_settings
    from app.db.session import get_session_factory
    from app.services.ingestion_service import process_raw_posts
    from ingestion.extractors.llm_extractor import LLMExtractor

    settings = get_settings()
    effective_api_key = api_key or settings.CLAUDE_API_KEY

    extractor = LLMExtractor(api_key=effective_api_key)

    factory = get_session_factory()
    async with factory() as session:
        try:
            batch = await process_raw_posts(
                session=session,
                llm_extractor=extractor,
                limit=limit,
            )
            await session.commit()
            return {
                "success": True,
                **batch.summary(),
            }
        except Exception as e:
            await session.rollback()
            logger.error("process_raw_posts failed: %s", e, exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }


@celery_app.task(
    name="app.tasks.ingestion_tasks.scan_all_forums",
    queue="ingestion",
)
def scan_all_forums(
    forum_urls: list[str] | None = None,
) -> dict[str, Any]:
    """
    Synchronous entry point for Celery.

    Scrapes all configured FlyerTalk forums for new posts.
    Called every 6h by Celery Beat.

    Args:
        forum_urls: Optional list of forum URLs to scan.
                   Defaults to DEFAULT_FORUM_URLS in the scraper.

    Returns:
        Dict with scan stats.
    """
    try:
        return asyncio.run(_run_forum_scan(forum_urls))
    except Exception as e:
        logger.error("scan_all_forums failed: %s", e, exc_info=True)
        return {
            "success": False,
            "error": f"Task failed: {str(e)}",
        }


@celery_app.task(
    name="app.tasks.ingestion_tasks.process_pending_posts",
    queue="ingestion",
)
def process_pending_posts(
    limit: int = 50,
    api_key: str = "",
) -> dict[str, Any]:
    """
    Synchronous entry point for Celery.

    Processes unprocessed community_posts through the LLM pipeline.
    Extracts patterns, hard-validates IATA codes and YQ savings,
    and inserts valid patterns into dump_patterns for ITA validation.
    Called after scan_all_forums completes.

    Args:
        limit: Max posts to process in this batch.
        api_key: Anthropic API key for LLM calls (falls back to settings).

    Returns:
        Dict with processing stats including patterns_stored count.
    """
    try:
        return asyncio.run(_run_post_processing(limit, api_key))
    except Exception as e:
        logger.error("process_pending_posts failed: %s", e, exc_info=True)
        return {
            "success": False,
            "error": f"Task failed: {str(e)}",
        }
