"""
alert_service.py — Alert generation and webhook delivery.

Creates alert payloads and delivers them to configured webhook URLs
(Slack, Discord, or custom endpoints).

Alert types and severities:
    HIGH:   PATTERN_DEPRECATED, HIGH_VALUE_DUMP_FOUND, BOT_DETECTION
    MEDIUM: PATTERN_DEGRADING, YQ_SPIKE
    INFO:   PATTERN_RECOVERED, NEW_PATTERN_ACTIVE
"""

import enum
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


# ─── Alert types and severities ──────────────────────────────────────────

class AlertSeverity(str, enum.Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    INFO = "INFO"

    @property
    def priority(self) -> int:
        """Higher number = higher priority."""
        return {"HIGH": 3, "MEDIUM": 2, "INFO": 1}[self.value]


class AlertType(str, enum.Enum):
    # HIGH severity
    PATTERN_DEPRECATED = "PATTERN_DEPRECATED"
    HIGH_VALUE_DUMP_FOUND = "HIGH_VALUE_DUMP_FOUND"
    BOT_DETECTION = "BOT_DETECTION"

    # MEDIUM severity
    PATTERN_DEGRADING = "PATTERN_DEGRADING"
    YQ_SPIKE = "YQ_SPIKE"

    # INFO severity
    PATTERN_RECOVERED = "PATTERN_RECOVERED"
    NEW_PATTERN_ACTIVE = "NEW_PATTERN_ACTIVE"


# Severity mapping
ALERT_SEVERITY_MAP: dict[AlertType, AlertSeverity] = {
    AlertType.PATTERN_DEPRECATED: AlertSeverity.HIGH,
    AlertType.HIGH_VALUE_DUMP_FOUND: AlertSeverity.HIGH,
    AlertType.BOT_DETECTION: AlertSeverity.HIGH,
    AlertType.PATTERN_DEGRADING: AlertSeverity.MEDIUM,
    AlertType.YQ_SPIKE: AlertSeverity.MEDIUM,
    AlertType.PATTERN_RECOVERED: AlertSeverity.INFO,
    AlertType.NEW_PATTERN_ACTIVE: AlertSeverity.INFO,
}

# High-value threshold for HIGH_VALUE_DUMP_FOUND
HIGH_VALUE_SAVINGS_THRESHOLD = 400.0


# ─── Result types ──────────────────────────────────────────────────────────

@dataclass
class AlertPayload:
    """Structured alert payload for webhook delivery."""

    alert_type: str
    severity: str
    timestamp: str
    message: str
    pattern_id: str | None = None
    pattern_url: str | None = None
    last_savings_usd: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {
            "alert_type": self.alert_type,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "message": self.message,
        }
        if self.pattern_id:
            d["pattern_id"] = self.pattern_id
        if self.pattern_url:
            d["pattern_url"] = self.pattern_url
        if self.last_savings_usd is not None:
            d["last_savings_usd"] = self.last_savings_usd
        if self.extra:
            d.update(self.extra)
        return d


@dataclass
class DeliveryResult:
    """Result of webhook delivery attempt."""

    url: str
    success: bool
    status_code: int | None = None
    error: str | None = None


@dataclass
class AlertResult:
    """Result of alert creation and delivery."""

    alert_type: str
    severity: str
    delivered: bool
    payload: AlertPayload
    deliveries: list[DeliveryResult] = field(default_factory=list)
    suppressed: bool = False
    suppression_reason: str | None = None


# ─── Alert creation ──────────────────────────────────────────────────────

def create_alert(
    alert_type: AlertType,
    message: str,
    pattern_id: uuid.UUID | None = None,
    last_savings_usd: float | None = None,
    dashboard_base_url: str = "http://localhost:3000",
    extra: dict[str, Any] | None = None,
) -> AlertPayload:
    """
    Create a structured alert payload.

    Args:
        alert_type: Type of alert.
        message: Human-readable alert message.
        pattern_id: Related pattern UUID (if applicable).
        last_savings_usd: Last known savings for the pattern.
        dashboard_base_url: Base URL for pattern deep links.
        extra: Additional key-value pairs for the payload.

    Returns:
        AlertPayload ready for delivery.
    """
    severity = ALERT_SEVERITY_MAP.get(alert_type, AlertSeverity.INFO)
    pattern_url = None
    if pattern_id:
        pattern_url = f"{dashboard_base_url}/patterns/{pattern_id}"

    return AlertPayload(
        alert_type=alert_type.value,
        severity=severity.value,
        timestamp=datetime.now(timezone.utc).isoformat(),
        message=message,
        pattern_id=str(pattern_id) if pattern_id else None,
        pattern_url=pattern_url,
        last_savings_usd=last_savings_usd,
        extra=extra or {},
    )


def should_send_alert(
    severity: str,
    min_severity: str | None = None,
) -> bool:
    """
    Check if an alert should be sent based on minimum severity filter.

    Args:
        severity: Alert severity (HIGH, MEDIUM, INFO).
        min_severity: Minimum severity threshold from config.

    Returns:
        True if the alert should be sent.
    """
    if min_severity is None:
        settings = get_settings()
        min_severity = settings.ALERT_MIN_SEVERITY

    try:
        alert_sev = AlertSeverity(severity)
        min_sev = AlertSeverity(min_severity)
        return alert_sev.priority >= min_sev.priority
    except ValueError:
        # Unknown severity — send it to be safe
        return True


def get_webhook_urls() -> list[str]:
    """
    Get configured webhook URLs from settings.

    Returns:
        List of webhook URL strings. Empty list if none configured.
    """
    settings = get_settings()
    raw = settings.ALERT_WEBHOOK_URLS
    if not raw or not raw.strip():
        return []
    return [url.strip() for url in raw.split(",") if url.strip()]


# ─── Webhook delivery ───────────────────────────────────────────────────

async def deliver_webhook(
    url: str,
    payload: dict[str, Any],
    timeout: float = 10.0,
) -> DeliveryResult:
    """
    Deliver an alert payload to a single webhook URL.

    Args:
        url: Webhook endpoint URL.
        payload: JSON-serializable payload dict.
        timeout: Request timeout in seconds.

    Returns:
        DeliveryResult with success status.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                timeout=timeout,
                headers={"Content-Type": "application/json"},
            )
            success = 200 <= response.status_code < 300
            if not success:
                logger.warning(
                    "Webhook delivery failed: %s returned %d",
                    url, response.status_code,
                )
            return DeliveryResult(
                url=url,
                success=success,
                status_code=response.status_code,
            )
    except httpx.TimeoutException:
        logger.error("Webhook timeout: %s", url)
        return DeliveryResult(url=url, success=False, error="Timeout")
    except Exception as e:
        logger.error("Webhook error for %s: %s", url, e)
        return DeliveryResult(url=url, success=False, error=str(e))


async def deliver_alert(
    payload: AlertPayload,
    webhook_urls: list[str] | None = None,
) -> list[DeliveryResult]:
    """
    Deliver an alert to all configured webhook URLs.

    Args:
        payload: Alert payload to deliver.
        webhook_urls: Override webhook URLs (default: from settings).

    Returns:
        List of delivery results.
    """
    if webhook_urls is None:
        webhook_urls = get_webhook_urls()

    if not webhook_urls:
        logger.debug("No webhook URLs configured — skipping alert delivery")
        return []

    payload_dict = payload.to_dict()
    results = []

    for url in webhook_urls:
        result = await deliver_webhook(url, payload_dict)
        results.append(result)

    delivered = sum(1 for r in results if r.success)
    logger.info(
        "Alert %s delivered to %d/%d webhooks",
        payload.alert_type, delivered, len(results),
    )

    return results


async def send_alert(
    alert_type: AlertType,
    message: str,
    pattern_id: uuid.UUID | None = None,
    last_savings_usd: float | None = None,
    extra: dict[str, Any] | None = None,
) -> AlertResult:
    """
    Full alert pipeline: create payload → check severity → deliver.

    This is the main entry point for sending alerts from services.

    Args:
        alert_type: Type of alert.
        message: Human-readable message.
        pattern_id: Related pattern UUID.
        last_savings_usd: Last known savings.
        extra: Additional payload data.

    Returns:
        AlertResult with delivery details.
    """
    payload = create_alert(
        alert_type=alert_type,
        message=message,
        pattern_id=pattern_id,
        last_savings_usd=last_savings_usd,
        extra=extra,
    )

    # Check severity filter
    if not should_send_alert(payload.severity):
        return AlertResult(
            alert_type=payload.alert_type,
            severity=payload.severity,
            delivered=False,
            payload=payload,
            suppressed=True,
            suppression_reason=f"Below minimum severity threshold",
        )

    # Deliver
    deliveries = await deliver_alert(payload)
    any_delivered = any(d.success for d in deliveries)

    return AlertResult(
        alert_type=payload.alert_type,
        severity=payload.severity,
        delivered=any_delivered,
        payload=payload,
        deliveries=deliveries,
    )
