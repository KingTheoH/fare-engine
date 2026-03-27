# CLAUDE.md — Celery Tasks

## Overview

All background task definitions live here. Tasks are Celery-decorated functions that import and call services directly. They do NOT make HTTP calls to the FastAPI app.

## Directory Structure

```
tasks/
├── CLAUDE.md              ← you are here
├── celery_app.py          ← Celery application instance (Phase 08)
├── schedules.py           ← Celery Beat scheduled task definitions (Phase 08)
├── validation_tasks.py    ← Validation sweep + per-pattern validation (Phase 07, extended 08)
├── yq_tasks.py            ← YQ data update tasks (Phase 05, extended 08)
├── ingestion_tasks.py     ← Community forum scan + post processing (Phase 06, extended 08)
└── alert_tasks.py         ← Alert delivery tasks (Phase 08)
```

## Celery App Config (Key Settings)

```python
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,           # Only ack AFTER task completes — prevents data loss on crash
    worker_prefetch_multiplier=1,  # Don't prefetch — ITA tasks are slow and memory-heavy
)
```

## Task Conventions

### Do
- Always return a dict from tasks (serializable, stored in Redis)
- Use `max_retries=1` for ITA automation tasks — do NOT hammer ITA Matrix on failures
- Use `retry_backoff=True` where retries are allowed
- Pass `pattern_id` as a string (UUID → str), never as a Python UUID object
- Use Redis locks to prevent double-queuing the same pattern

### Do NOT
- Do not call `requests` or `httpx` to the local FastAPI app — call service functions directly
- Do not run async code inside tasks — use `asyncio.run()` if the service is async
- Do not raise exceptions from validation tasks — return `{"success": False, "error": "..."}`
- Do not prefetch more than 1 task per worker (ITA Matrix tasks are slow)

## Concurrency Controls

Max concurrent ITA Matrix tasks: **10** across all workers.

```python
ITA_CONCURRENCY_KEY = "ita_matrix_active_count"
# Redis semaphore — increment on task start, decrement on finish (even on failure)
# If at limit: task waits with retry_countdown backoff rather than exceeding
```

## Sweep Task Pattern

```python
@celery_app.task(name="app.tasks.validation_tasks.sweep_tier")
def sweep_tier(tier: int) -> dict:
    """
    Enqueues individual validate_pattern_task for each active/degrading pattern
    in the given freshness tier.
    Checks Redis lock before enqueuing to avoid double-queuing.
    Returns: {"queued": count, "skipped": count}
    """
```

## Scheduled Sweeps (from `schedules.py`)

| Task | Schedule | Notes |
|------|---------|-------|
| `sweep_tier(1)` | Every 24h | Tier 1: YQ savings > $200 |
| `sweep_tier(2)` | Mon + Thu 6am UTC | Tier 2: YQ savings $50–200 |
| `sweep_tier(3)` | 1st of month 6am UTC | Tier 3: YQ savings < $50 |
| `update_all_carrier_yq` | Every Sunday 5am UTC | Refreshes all carrier YQ data |
| `scan_all_forums` | Every 6h | FlyerTalk + configured forums |

## Alert Task

`alert_tasks.send_alert(alert_type, payload)` — posts to all configured webhook URLs.

Webhook payload format:
```json
{
  "alert_type": "PATTERN_DEPRECATED",
  "severity": "HIGH",
  "timestamp": "2026-03-25T10:30:00Z",
  "message": "Dump pattern JFK→BKK via LH/TP:FRA deprecated after 3 consecutive failures",
  "pattern_id": "uuid-here",
  "pattern_url": "http://dashboard/patterns/uuid-here",
  "last_savings_usd": 580.00
}
```

Delivery: `ALERT_WEBHOOK_URLS` env var (comma-separated Slack/Discord/custom URLs).
Filter: `ALERT_MIN_SEVERITY` env var — suppress alerts below threshold (default: MEDIUM).
