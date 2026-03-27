"""
validation_tasks.py — Celery tasks for pattern validation.

Task stubs wrapping the async validation service functions.
These are dispatched by the background job scheduler (Phase 08).

Tasks never raise — they return error dicts on failure.
"""

import asyncio
from app.tasks.celery_app import celery_app

import logging
import uuid
from typing import Any

logger = logging.getLogger(__name__)


# ─── Async implementations ────────────────────────────────────────────────

async def _run_single_validation(pattern_id_str: str) -> dict[str, Any]:
    """Run validation for a single pattern."""
    from app.db.session import async_session_factory
    from app.services import validation_service

    pattern_id = uuid.UUID(pattern_id_str)

    async with async_session_factory() as session:
        outcome = await validation_service.run_validation(
            session=session,
            pattern_id=pattern_id,
            ita_client=None,  # TODO: inject real ITA client in Phase 08
        )
        await session.commit()

    return {
        "pattern_id": pattern_id_str,
        "success": outcome.validation_success,
        "new_confidence": outcome.new_confidence_score,
        "old_confidence": outcome.old_confidence_score,
        "had_transition": outcome.had_transition,
        "error": outcome.error,
    }


async def _run_tier_validations(freshness_tier: int, limit: int = 50) -> dict[str, Any]:
    """Run validations for all patterns in a given freshness tier."""
    from app.db.session import async_session_factory
    from app.db.repositories import pattern_repository
    from app.services import validation_service

    async with async_session_factory() as session:
        patterns = await pattern_repository.get_patterns_needing_validation(
            session, freshness_tier=freshness_tier, limit=limit
        )

        results = []
        successes = 0
        failures = 0
        errors = 0

        for pattern in patterns:
            try:
                outcome = await validation_service.run_validation(
                    session=session,
                    pattern_id=pattern.id,
                    ita_client=None,  # TODO: inject real ITA client in Phase 08
                )
                await session.commit()

                if outcome.error:
                    errors += 1
                elif outcome.validation_success:
                    successes += 1
                else:
                    failures += 1

                results.append({
                    "pattern_id": str(pattern.id),
                    "success": outcome.validation_success,
                    "error": outcome.error,
                })
            except Exception as e:
                errors += 1
                results.append({
                    "pattern_id": str(pattern.id),
                    "success": False,
                    "error": str(e),
                })

    return {
        "tier": freshness_tier,
        "total_patterns": len(patterns),
        "successes": successes,
        "failures": failures,
        "errors": errors,
        "results": results,
    }


# ─── Celery task stubs ─────────────────────────────────────────────────────

@celery_app.task(
    name="app.tasks.validation_tasks.validate_single_pattern",
    queue="validation",
    max_retries=1,
)
def validate_single_pattern(pattern_id: str) -> dict[str, Any]:
    """
    Celery task: validate a single pattern.

    Args:
        pattern_id: UUID string of the pattern to validate.

    Returns:
        Dict with validation outcome summary. Never raises.
    """
    try:
        return asyncio.run(_run_single_validation(pattern_id))
    except Exception as e:
        logger.error(
            "Task validate_single_pattern failed for %s: %s",
            pattern_id, e, exc_info=True,
        )
        return {
            "pattern_id": pattern_id,
            "success": False,
            "error": f"Task error: {str(e)}",
        }


@celery_app.task(
    name="app.tasks.validation_tasks.validate_tier_patterns",
    queue="validation",
)
def validate_tier_patterns(freshness_tier: int, limit: int = 50) -> dict[str, Any]:
    """
    Celery task: validate all patterns in a given freshness tier.

    This is the main scheduled task dispatched by the job scheduler:
    - Tier 1 (HIGH): dispatched daily
    - Tier 2 (MEDIUM): dispatched weekly
    - Tier 3 (LOW): dispatched monthly

    Args:
        freshness_tier: 1, 2, or 3.
        limit: Max patterns to validate in one batch.

    Returns:
        Dict with batch validation summary. Never raises.
    """
    try:
        return asyncio.run(_run_tier_validations(freshness_tier, limit))
    except Exception as e:
        logger.error(
            "Task validate_tier_patterns failed for tier %d: %s",
            freshness_tier, e, exc_info=True,
        )
        return {
            "tier": freshness_tier,
            "total_patterns": 0,
            "successes": 0,
            "failures": 0,
            "errors": 1,
            "error": f"Task error: {str(e)}",
        }
