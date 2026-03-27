"""
test_celery_config.py — Tests for Celery app configuration and schedule.

Tests celery_app.py config, schedules.py beat schedule, and
alert_service.py / alert_tasks.py.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.alert_service import (
    ALERT_SEVERITY_MAP,
    AlertPayload,
    AlertResult,
    AlertSeverity,
    AlertType,
    DeliveryResult,
    HIGH_VALUE_SAVINGS_THRESHOLD,
    create_alert,
    deliver_webhook,
    get_webhook_urls,
    send_alert,
    should_send_alert,
)
from app.tasks.schedules import BEAT_SCHEDULE


# ─── Celery app config ──────────────────────────────────────────────────

class TestCeleryAppConfig:
    def test_celery_app_importable(self):
        from app.tasks.celery_app import celery_app
        assert celery_app is not None
        assert celery_app.main == "fare_engine"

    def test_serialization_json(self):
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.result_serializer == "json"

    def test_timezone_utc(self):
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.timezone == "UTC"
        assert celery_app.conf.enable_utc is True

    def test_acks_late(self):
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.task_acks_late is True

    def test_prefetch_multiplier(self):
        from app.tasks.celery_app import celery_app
        assert celery_app.conf.worker_prefetch_multiplier == 1

    def test_task_routes_configured(self):
        from app.tasks.celery_app import celery_app
        routes = celery_app.conf.task_routes
        assert "app.tasks.validation_tasks.*" in routes
        assert "app.tasks.yq_tasks.*" in routes
        assert "app.tasks.ingestion_tasks.*" in routes
        assert "app.tasks.alert_tasks.*" in routes

    def test_task_routes_queues(self):
        from app.tasks.celery_app import celery_app
        routes = celery_app.conf.task_routes
        assert routes["app.tasks.validation_tasks.*"]["queue"] == "validation"
        assert routes["app.tasks.yq_tasks.*"]["queue"] == "yq"
        assert routes["app.tasks.ingestion_tasks.*"]["queue"] == "ingestion"
        assert routes["app.tasks.alert_tasks.*"]["queue"] == "alerts"


# ─── Beat schedule ───────────────────────────────────────────────────────

class TestBeatSchedule:
    def test_schedule_has_all_tasks(self):
        expected_keys = {
            "validate-tier-1-daily",
            "validate-tier-2-biweekly",
            "validate-tier-3-monthly",
            "update-carrier-yq-weekly",
            "scan-forums-6h",
            "process-pending-posts-6h",
        }
        assert expected_keys == set(BEAT_SCHEDULE.keys())

    def test_tier_1_daily(self):
        task = BEAT_SCHEDULE["validate-tier-1-daily"]
        assert task["task"] == "app.tasks.validation_tasks.validate_tier_patterns"
        assert task["args"] == [1]
        assert task["options"]["queue"] == "validation"

    def test_tier_2_biweekly(self):
        task = BEAT_SCHEDULE["validate-tier-2-biweekly"]
        assert task["args"] == [2]
        # Mon=1, Thu=4
        schedule = task["schedule"]
        assert schedule.hour == {6}
        assert schedule.minute == {0}

    def test_tier_3_monthly(self):
        task = BEAT_SCHEDULE["validate-tier-3-monthly"]
        assert task["args"] == [3]
        schedule = task["schedule"]
        assert schedule.day_of_month == {1}

    def test_yq_weekly_sunday(self):
        task = BEAT_SCHEDULE["update-carrier-yq-weekly"]
        assert task["task"] == "app.tasks.yq_tasks.update_all_carrier_yq"
        schedule = task["schedule"]
        assert schedule.day_of_week == {0}  # Sunday
        assert schedule.hour == {5}

    def test_forum_scan_6h(self):
        task = BEAT_SCHEDULE["scan-forums-6h"]
        assert task["task"] == "app.tasks.ingestion_tasks.scan_all_forums"

    def test_process_posts_offset_30m(self):
        task = BEAT_SCHEDULE["process-pending-posts-6h"]
        assert task["task"] == "app.tasks.ingestion_tasks.process_pending_posts"
        schedule = task["schedule"]
        assert schedule.minute == {30}

    def test_all_tasks_have_valid_task_names(self):
        for key, entry in BEAT_SCHEDULE.items():
            assert "task" in entry, f"{key} missing 'task'"
            assert entry["task"].startswith("app.tasks."), f"{key} has invalid task name"


# ─── AlertSeverity ──────────────────────────────────────────────────────

class TestAlertSeverity:
    def test_priority_ordering(self):
        assert AlertSeverity.HIGH.priority > AlertSeverity.MEDIUM.priority
        assert AlertSeverity.MEDIUM.priority > AlertSeverity.INFO.priority

    def test_all_severities_have_priority(self):
        for sev in AlertSeverity:
            assert isinstance(sev.priority, int)


# ─── AlertType severity mapping ─────────────────────────────────────────

class TestAlertTypeSeverityMap:
    def test_deprecated_is_high(self):
        assert ALERT_SEVERITY_MAP[AlertType.PATTERN_DEPRECATED] == AlertSeverity.HIGH

    def test_high_value_dump_is_high(self):
        assert ALERT_SEVERITY_MAP[AlertType.HIGH_VALUE_DUMP_FOUND] == AlertSeverity.HIGH

    def test_bot_detection_is_high(self):
        assert ALERT_SEVERITY_MAP[AlertType.BOT_DETECTION] == AlertSeverity.HIGH

    def test_degrading_is_medium(self):
        assert ALERT_SEVERITY_MAP[AlertType.PATTERN_DEGRADING] == AlertSeverity.MEDIUM

    def test_yq_spike_is_medium(self):
        assert ALERT_SEVERITY_MAP[AlertType.YQ_SPIKE] == AlertSeverity.MEDIUM

    def test_recovered_is_info(self):
        assert ALERT_SEVERITY_MAP[AlertType.PATTERN_RECOVERED] == AlertSeverity.INFO

    def test_new_active_is_info(self):
        assert ALERT_SEVERITY_MAP[AlertType.NEW_PATTERN_ACTIVE] == AlertSeverity.INFO

    def test_all_alert_types_mapped(self):
        for alert_type in AlertType:
            assert alert_type in ALERT_SEVERITY_MAP


# ─── create_alert ───────────────────────────────────────────────────────

class TestCreateAlert:
    def test_creates_payload(self):
        pid = uuid.uuid4()
        payload = create_alert(
            alert_type=AlertType.PATTERN_DEPRECATED,
            message="Pattern deprecated",
            pattern_id=pid,
            last_savings_usd=580.0,
        )
        assert payload.alert_type == "PATTERN_DEPRECATED"
        assert payload.severity == "HIGH"
        assert payload.message == "Pattern deprecated"
        assert payload.pattern_id == str(pid)
        assert payload.last_savings_usd == 580.0
        assert str(pid) in payload.pattern_url

    def test_no_pattern_id(self):
        payload = create_alert(
            alert_type=AlertType.BOT_DETECTION,
            message="Bot detected",
        )
        assert payload.pattern_id is None
        assert payload.pattern_url is None

    def test_timestamp_present(self):
        payload = create_alert(
            alert_type=AlertType.PATTERN_RECOVERED,
            message="Pattern recovered",
        )
        assert payload.timestamp is not None
        # Should be ISO format
        datetime.fromisoformat(payload.timestamp)

    def test_extra_fields(self):
        payload = create_alert(
            alert_type=AlertType.BOT_DETECTION,
            message="Bot",
            extra={"proxy_used": "proxy1.example.com"},
        )
        assert payload.extra["proxy_used"] == "proxy1.example.com"


# ─── AlertPayload.to_dict ──────────────────────────────────────────────

class TestAlertPayloadToDict:
    def test_basic_dict(self):
        payload = AlertPayload(
            alert_type="TEST",
            severity="HIGH",
            timestamp="2026-03-25T10:00:00Z",
            message="Test message",
        )
        d = payload.to_dict()
        assert d["alert_type"] == "TEST"
        assert d["severity"] == "HIGH"
        assert d["message"] == "Test message"
        assert "pattern_id" not in d
        assert "pattern_url" not in d

    def test_full_dict(self):
        payload = AlertPayload(
            alert_type="TEST",
            severity="HIGH",
            timestamp="2026-03-25T10:00:00Z",
            message="Test",
            pattern_id="abc-123",
            pattern_url="http://localhost/patterns/abc-123",
            last_savings_usd=500.0,
            extra={"key": "value"},
        )
        d = payload.to_dict()
        assert d["pattern_id"] == "abc-123"
        assert d["pattern_url"] == "http://localhost/patterns/abc-123"
        assert d["last_savings_usd"] == 500.0
        assert d["key"] == "value"


# ─── should_send_alert ──────────────────────────────────────────────────

class TestShouldSendAlert:
    def test_high_passes_medium_filter(self):
        assert should_send_alert("HIGH", "MEDIUM") is True

    def test_medium_passes_medium_filter(self):
        assert should_send_alert("MEDIUM", "MEDIUM") is True

    def test_info_blocked_by_medium_filter(self):
        assert should_send_alert("INFO", "MEDIUM") is False

    def test_high_passes_high_filter(self):
        assert should_send_alert("HIGH", "HIGH") is True

    def test_medium_blocked_by_high_filter(self):
        assert should_send_alert("MEDIUM", "HIGH") is False

    def test_info_passes_info_filter(self):
        assert should_send_alert("INFO", "INFO") is True

    def test_unknown_severity_passes(self):
        assert should_send_alert("UNKNOWN", "MEDIUM") is True


# ─── get_webhook_urls ───────────────────────────────────────────────────

class TestGetWebhookUrls:
    def test_empty_returns_empty(self):
        with patch("app.services.alert_service.get_settings") as mock:
            mock.return_value.ALERT_WEBHOOK_URLS = ""
            assert get_webhook_urls() == []

    def test_single_url(self):
        with patch("app.services.alert_service.get_settings") as mock:
            mock.return_value.ALERT_WEBHOOK_URLS = "https://hooks.slack.com/test"
            assert get_webhook_urls() == ["https://hooks.slack.com/test"]

    def test_multiple_urls(self):
        with patch("app.services.alert_service.get_settings") as mock:
            mock.return_value.ALERT_WEBHOOK_URLS = "https://slack.com/hook1,https://discord.com/hook2"
            urls = get_webhook_urls()
            assert len(urls) == 2
            assert "https://slack.com/hook1" in urls

    def test_whitespace_trimmed(self):
        with patch("app.services.alert_service.get_settings") as mock:
            mock.return_value.ALERT_WEBHOOK_URLS = "  https://hook1.com , https://hook2.com  "
            urls = get_webhook_urls()
            assert urls == ["https://hook1.com", "https://hook2.com"]


# ─── deliver_webhook ────────────────────────────────────────────────────

class TestDeliverWebhook:
    @pytest.mark.asyncio
    async def test_successful_delivery(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("app.services.alert_service.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await deliver_webhook("https://hook.example.com", {"test": True})

            assert result.success
            assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_failed_delivery(self):
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("app.services.alert_service.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__ = AsyncMock(return_value=instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await deliver_webhook("https://hook.example.com", {"test": True})

            assert not result.success
            assert result.status_code == 500

    @pytest.mark.asyncio
    async def test_timeout_handled(self):
        import httpx

        with patch("app.services.alert_service.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await deliver_webhook("https://hook.example.com", {"test": True})

            assert not result.success
            assert result.error == "Timeout"

    @pytest.mark.asyncio
    async def test_connection_error_handled(self):
        with patch("app.services.alert_service.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post = AsyncMock(side_effect=ConnectionError("refused"))
            mock_client.return_value.__aenter__ = AsyncMock(return_value=instance)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await deliver_webhook("https://hook.example.com", {"test": True})

            assert not result.success
            assert "refused" in result.error


# ─── send_alert (full pipeline) ─────────────────────────────────────────

class TestSendAlert:
    @pytest.mark.asyncio
    async def test_suppressed_below_min_severity(self):
        with patch("app.services.alert_service.get_settings") as mock:
            mock.return_value.ALERT_MIN_SEVERITY = "HIGH"
            mock.return_value.ALERT_WEBHOOK_URLS = "https://hook.com"

            result = await send_alert(
                alert_type=AlertType.PATTERN_RECOVERED,  # INFO severity
                message="Pattern recovered",
            )

            assert result.suppressed
            assert not result.delivered

    @pytest.mark.asyncio
    async def test_no_webhooks_configured(self):
        with patch("app.services.alert_service.get_settings") as mock:
            mock.return_value.ALERT_MIN_SEVERITY = "INFO"
            mock.return_value.ALERT_WEBHOOK_URLS = ""

            result = await send_alert(
                alert_type=AlertType.PATTERN_DEPRECATED,
                message="Pattern deprecated",
            )

            assert not result.delivered
            assert not result.suppressed
            assert len(result.deliveries) == 0

    @pytest.mark.asyncio
    async def test_successful_send(self):
        with (
            patch("app.services.alert_service.get_settings") as mock_settings,
            patch("app.services.alert_service.deliver_webhook") as mock_deliver,
        ):
            mock_settings.return_value.ALERT_MIN_SEVERITY = "INFO"
            mock_settings.return_value.ALERT_WEBHOOK_URLS = "https://hook1.com,https://hook2.com"

            mock_deliver.return_value = DeliveryResult(
                url="https://hook.com", success=True, status_code=200
            )

            result = await send_alert(
                alert_type=AlertType.PATTERN_DEPRECATED,
                message="Deprecated",
                pattern_id=uuid.uuid4(),
                last_savings_usd=500.0,
            )

            assert result.delivered
            assert not result.suppressed
            assert len(result.deliveries) == 2


# ─── Alert task stubs ──────────────────────────────────────────────────

class TestAlertTasks:
    def test_send_alert_task_error_handling(self):
        from app.tasks.alert_tasks import send_alert_task

        with patch("app.tasks.alert_tasks._send_alert_async") as mock:
            mock.side_effect = RuntimeError("async failed")

            result = send_alert_task("PATTERN_DEPRECATED", "test msg")

            assert result["delivered"] is False
            assert "error" in result

    def test_send_pattern_deprecated_alert(self):
        from app.tasks.alert_tasks import send_pattern_deprecated_alert

        with patch("app.tasks.alert_tasks.send_alert_task") as mock:
            mock.return_value = {"delivered": True}

            result = send_pattern_deprecated_alert(
                pattern_id="abc-123",
                route_description="JFK→BKK via LH",
                last_savings_usd=580.0,
            )

            mock.assert_called_once()
            assert mock.call_args[1]["alert_type"] == "PATTERN_DEPRECATED"

    def test_send_high_value_alert(self):
        from app.tasks.alert_tasks import send_high_value_alert

        with patch("app.tasks.alert_tasks.send_alert_task") as mock:
            mock.return_value = {"delivered": True}

            result = send_high_value_alert(
                pattern_id="abc-123",
                route_description="JFK→BKK via LH",
                savings_usd=650.0,
            )

            mock.assert_called_once()
            assert mock.call_args[1]["alert_type"] == "HIGH_VALUE_DUMP_FOUND"

    def test_send_bot_detection_alert(self):
        from app.tasks.alert_tasks import send_bot_detection_alert

        with patch("app.tasks.alert_tasks.send_alert_task") as mock:
            mock.return_value = {"delivered": True}

            result = send_bot_detection_alert(
                proxy_used="proxy1.example.com",
                error_details="CAPTCHA detected",
            )

            mock.assert_called_once()
            assert mock.call_args[1]["alert_type"] == "BOT_DETECTION"


# ─── High-value threshold ──────────────────────────────────────────────

class TestHighValueThreshold:
    def test_threshold_is_400(self):
        assert HIGH_VALUE_SAVINGS_THRESHOLD == 400.0


# ─── Task decorator verification ──────────────────────────────────────

class TestTaskDecorators:
    def test_validation_tasks_are_registered(self):
        from app.tasks.celery_app import celery_app
        from app.tasks import validation_tasks

        # Check that the tasks have been registered with the celery app
        assert hasattr(validation_tasks.validate_single_pattern, 'delay')
        assert hasattr(validation_tasks.validate_tier_patterns, 'delay')

    def test_yq_tasks_are_registered(self):
        from app.tasks import yq_tasks

        assert hasattr(yq_tasks.update_all_carrier_yq, 'delay')
        assert hasattr(yq_tasks.update_single_carrier_yq, 'delay')

    def test_ingestion_tasks_are_registered(self):
        from app.tasks import ingestion_tasks

        assert hasattr(ingestion_tasks.scan_all_forums, 'delay')
        assert hasattr(ingestion_tasks.process_pending_posts, 'delay')

    def test_alert_tasks_are_registered(self):
        from app.tasks import alert_tasks

        assert hasattr(alert_tasks.send_alert_task, 'delay')
        assert hasattr(alert_tasks.send_pattern_deprecated_alert, 'delay')
        assert hasattr(alert_tasks.send_high_value_alert, 'delay')
        assert hasattr(alert_tasks.send_bot_detection_alert, 'delay')
