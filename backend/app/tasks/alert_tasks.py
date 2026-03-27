"""
alert_tasks.py — Celery tasks for alert delivery.

Wraps the async alert_service functions for Celery execution.
Tasks never raise — they return error dicts on failure.
"""

import asyncio
import logging
import uuid
from typing import Any

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


# ─── Async implementation ────────────────────────────────────────────────

async def _send_alert_async(
    alert_type: str,
    message: str,
    pattern_id: str | None = None,
    last_savings_usd: float | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send an alert via the alert service."""
    from app.services.alert_service import AlertType, send_alert

    parsed_type = AlertType(alert_type)
    parsed_id = uuid.UUID(pattern_id) if pattern_id else None

    result = await send_alert(
        alert_type=parsed_type,
        message=message,
        pattern_id=parsed_id,
        last_savings_usd=last_savings_usd,
        extra=extra,
    )

    return {
        "alert_type": result.alert_type,
        "severity": result.severity,
        "delivered": result.delivered,
        "suppressed": result.suppressed,
        "suppression_reason": result.suppression_reason,
        "webhook_count": len(result.deliveries),
        "successful_deliveries": sum(1 for d in result.deliveries if d.success),
    }


# ─── Celery tasks ─────────────────────────────────────────────────────────

@celery_app.task(
    name="app.tasks.alert_tasks.send_alert",
    queue="alerts",
    max_retries=2,
    default_retry_delay=30,
)
def send_alert_task(
    alert_type: str,
    message: str,
    pattern_id: str | None = None,
    last_savings_usd: float | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Celery task: send an alert via webhooks.

    Args:
        alert_type: AlertType enum value string.
        message: Human-readable alert message.
        pattern_id: UUID string of related pattern.
        last_savings_usd: Last known savings.
        extra: Additional payload data.

    Returns:
        Dict with delivery summary. Never raises.
    """
    try:
        return asyncio.run(_send_alert_async(
            alert_type=alert_type,
            message=message,
            pattern_id=pattern_id,
            last_savings_usd=last_savings_usd,
            extra=extra,
        ))
    except Exception as e:
        logger.error("send_alert_task failed: %s", e, exc_info=True)
        return {
            "alert_type": alert_type,
            "delivered": False,
            "error": f"Task error: {str(e)}",
        }


@celery_app.task(
    name="app.tasks.alert_tasks.send_pattern_deprecated_alert",
    queue="alerts",
)
def send_pattern_deprecated_alert(
    pattern_id: str,
    route_description: str,
    last_savings_usd: float | None = None,
) -> dict[str, Any]:
    """Convenience task for pattern deprecated alerts."""
    return send_alert_task(
        alert_type="PATTERN_DEPRECATED",
        message=f"Dump pattern {route_description} deprecated after 3 consecutive failures",
        pattern_id=pattern_id,
        last_savings_usd=last_savings_usd,
    )


@celery_app.task(
    name="app.tasks.alert_tasks.send_high_value_alert",
    queue="alerts",
)
def send_high_value_alert(
    pattern_id: str,
    route_description: str,
    savings_usd: float,
) -> dict[str, Any]:
    """Convenience task for high-value dump discovery alerts."""
    return send_alert_task(
        alert_type="HIGH_VALUE_DUMP_FOUND",
        message=f"High-value dump found: {route_description} — ${savings_usd:.0f} YQ savings",
        pattern_id=pattern_id,
        last_savings_usd=savings_usd,
    )


@celery_app.task(
    name="app.tasks.alert_tasks.send_bot_detection_alert",
    queue="alerts",
)
def send_bot_detection_alert(
    proxy_used: str | None = None,
    error_details: str = "",
) -> dict[str, Any]:
    """Convenience task for bot detection alerts."""
    msg = "ITA Matrix bot detection triggered"
    if proxy_used:
        msg += f" on proxy {proxy_used}"
    return send_alert_task(
        alert_type="BOT_DETECTION",
        message=msg,
        extra={"proxy_used": proxy_used, "error_details": error_details},
    )
