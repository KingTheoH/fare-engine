# Phase 08 — Background Job System

## Goal
Wire up Celery with Redis as broker, define all scheduled tasks, and build the alert system. By the end of this phase, the system can run validation sweeps and YQ updates automatically on schedule.

## Deliverables

- [ ] `backend/app/tasks/celery_app.py` — Celery application instance
- [ ] `backend/app/tasks/schedules.py` — Celery Beat schedule definitions
- [ ] `backend/app/tasks/validation_tasks.py` — validation sweep tasks (extended from Phase 7)
- [ ] `backend/app/tasks/yq_tasks.py` — YQ update tasks (extended from Phase 5)
- [ ] `backend/app/tasks/ingestion_tasks.py` — community ingestion tasks (extended from Phase 6)
- [ ] `backend/app/tasks/alert_tasks.py` — NEW: alert notifications
- [ ] `backend/app/services/alert_service.py` — alert logic
- [ ] Alert config: webhook URL(s) in env vars
- [ ] Unit tests: `tests/test_tasks/`

## Celery App (`celery_app.py`)

```python
from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "fare_engine",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.validation_tasks",
        "app.tasks.yq_tasks",
        "app.tasks.ingestion_tasks",
        "app.tasks.alert_tasks",
    ]
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,          # Only ack after task completes (prevent data loss)
    worker_prefetch_multiplier=1, # Don't prefetch — ITA tasks are slow
)
```

## Scheduled Tasks (`schedules.py`)

```python
from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    # Tier 1 patterns: validate every 24h
    "validate-tier-1-patterns": {
        "task": "app.tasks.validation_tasks.sweep_tier",
        "schedule": crontab(hour="*/24"),
        "args": (1,),
    },
    # Tier 2 patterns: validate every Monday + Thursday
    "validate-tier-2-patterns": {
        "task": "app.tasks.validation_tasks.sweep_tier",
        "schedule": crontab(hour=6, day_of_week="1,4"),
        "args": (2,),
    },
    # Tier 3 patterns: validate first day of each month
    "validate-tier-3-patterns": {
        "task": "app.tasks.validation_tasks.sweep_tier",
        "schedule": crontab(hour=6, day_of_month=1),
        "args": (3,),
    },
    # YQ data: update every Sunday at 5am UTC
    "update-yq-data": {
        "task": "app.tasks.yq_tasks.update_all_carrier_yq",
        "schedule": crontab(hour=5, day_of_week=0),
    },
    # Community ingestion: scan configured forums every 6h
    "ingest-community-posts": {
        "task": "app.tasks.ingestion_tasks.scan_all_forums",
        "schedule": crontab(hour="*/6"),
    },
}
```

## Sweep Task (`sweep_tier`)

```python
@celery_app.task(name="app.tasks.validation_tasks.sweep_tier")
def sweep_tier(tier: int) -> dict:
    """
    Enqueues individual validate_pattern_task for each active/degrading pattern
    in the given freshness tier.
    Respects concurrency limits: max 10 validation tasks running simultaneously.
    Returns: {"queued": count, "skipped": count (already in queue)}
    """
```

**Important**: Before enqueuing, check if a validation task is already running for that pattern (use Redis lock with pattern_id as key). Don't double-queue.

## Alert System

### Alert Types

| Alert | Trigger | Severity |
|-------|---------|---------|
| `PATTERN_DEPRECATED` | Pattern transitions to deprecated | HIGH |
| `PATTERN_DEGRADING` | Pattern transitions to degrading | MEDIUM |
| `PATTERN_RECOVERED` | Pattern transitions from degrading back to active | INFO |
| `NEW_PATTERN_ACTIVE` | New pattern transitions from discovered to active | INFO |
| `HIGH_VALUE_DUMP_FOUND` | New active pattern with savings > $400 | HIGH |
| `BOT_DETECTION` | ITA Matrix bot detection triggered | HIGH |
| `YQ_SPIKE` | A carrier's YQ increases by >20% | MEDIUM |

### Delivery Mechanism

In MVP: **webhook** only. POST to configured webhook URLs (can be Slack incoming webhook, Discord webhook, custom endpoint).

```python
class AlertService:
    async def send_alert(self, alert_type: AlertType, payload: dict) -> None:
        """
        Sends alert to all configured webhook URLs.
        Payload includes alert_type, timestamp, human-readable message, and relevant IDs.
        """
```

Webhook payload format:
```json
{
  "alert_type": "PATTERN_DEPRECATED",
  "severity": "HIGH",
  "timestamp": "2026-03-24T10:30:00Z",
  "message": "Dump pattern JFK→BKK via LH/TP:FRA has been deprecated after 3 consecutive failures",
  "pattern_id": "uuid-here",
  "pattern_url": "http://dashboard/patterns/uuid-here",
  "last_savings_usd": 580.00
}
```

Config:
```
ALERT_WEBHOOK_URLS=https://hooks.slack.com/...,https://discord.com/api/webhooks/...
ALERT_MIN_SEVERITY=MEDIUM  # don't send INFO alerts unless configured
```

## Concurrency Controls

- Max 5 Celery workers (configurable)
- Max 10 concurrent ITA Matrix tasks across all workers
- Implement using Redis semaphore: `ITA_CONCURRENCY_KEY = "ita_matrix_active_count"`
- Each validation task increments on start, decrements on finish (even on failure)
- If semaphore is at limit: task waits (retry with backoff) rather than exceeding

## Completion Check

```bash
# Start all services
docker compose up -d

# Verify Celery workers started
docker compose logs celery-worker

# Manually trigger a sweep
docker compose exec celery-worker celery -A app.tasks.celery_app call \
  app.tasks.validation_tasks.sweep_tier --args='[1]'

# Check Redis for results
docker compose exec redis redis-cli KEYS "celery*"
```

## Files Changed
- New: `backend/app/tasks/celery_app.py`
- New: `backend/app/tasks/schedules.py`
- New: `backend/app/tasks/alert_tasks.py`
- New: `backend/app/services/alert_service.py`
- Modified: `docker-compose.yml` (add celery-worker + celery-beat services)
- Modified: `backend/app/tasks/validation_tasks.py` (add sweep_tier)
- Modified: `backend/app/tasks/yq_tasks.py` (add update_all_carrier_yq)
- Modified: `backend/app/tasks/ingestion_tasks.py` (add scan_all_forums)
- New: `tests/test_tasks/`
