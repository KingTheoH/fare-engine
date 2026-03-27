"""
celery_app.py — Celery application instance.

This module creates the Celery app used by all task modules.
Import this in task files:
    from app.tasks.celery_app import celery_app

Running the worker:
    celery -A app.tasks.celery_app worker --loglevel=info --concurrency=5

Running the beat scheduler:
    celery -A app.tasks.celery_app beat --loglevel=info
"""

import logging

from celery import Celery

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# ─── Celery instance ──────────────────────────────────────────────────────

celery_app = Celery(
    "fare_engine",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Reliability: only ack AFTER task completes — prevents data loss on crash
    task_acks_late=True,

    # Don't prefetch — ITA tasks are slow and memory-heavy
    worker_prefetch_multiplier=1,

    # Result expiry: keep results for 24h
    result_expires=86400,

    # Task routes for queue separation
    task_routes={
        "app.tasks.validation_tasks.*": {"queue": "validation"},
        "app.tasks.yq_tasks.*": {"queue": "yq"},
        "app.tasks.ingestion_tasks.*": {"queue": "ingestion"},
        "app.tasks.alert_tasks.*": {"queue": "alerts"},
    },

    # Default queue for unrouted tasks
    task_default_queue="default",

    # Retry settings
    task_reject_on_worker_lost=True,

    # Worker settings
    worker_max_tasks_per_child=100,  # Recycle workers after 100 tasks (memory safety)
    worker_max_memory_per_child=512000,  # 512MB per worker max
)

# Auto-discover tasks in app.tasks package
celery_app.autodiscover_tasks(["app.tasks"])

# Import beat schedule
celery_app.conf.beat_schedule = {}  # Populated by schedules.py at import time


def configure_beat_schedule() -> None:
    """Load beat schedule from schedules module."""
    from app.tasks.schedules import BEAT_SCHEDULE
    celery_app.conf.beat_schedule = BEAT_SCHEDULE
    logger.info("Celery Beat schedule configured with %d tasks", len(BEAT_SCHEDULE))


# Configure on import
try:
    configure_beat_schedule()
except Exception as e:
    logger.warning("Failed to configure beat schedule: %s", e)
