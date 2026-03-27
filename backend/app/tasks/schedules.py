"""
schedules.py — Celery Beat schedule definitions.

All scheduled tasks are registered here. The schedule is loaded by celery_app.py.

Schedule overview:
| Task                      | Schedule              | Queue      |
|---------------------------|-----------------------|------------|
| Validate Tier 1 patterns  | Every 24h at midnight | validation |
| Validate Tier 2 patterns  | Mon + Thu at 6am UTC  | validation |
| Validate Tier 3 patterns  | 1st of month 6am UTC  | validation |
| Update carrier YQ data    | Every Sunday 5am UTC  | yq         |
| Scan community forums     | Every 6 hours         | ingestion  |
| Process pending posts     | Every 6h (offset 30m) | ingestion  |
"""

from celery.schedules import crontab

# ─── Beat Schedule ─────────────────────────────────────────────────────────

BEAT_SCHEDULE = {
    # ── Validation sweeps (tiered) ──────────────────────────────────────
    "validate-tier-1-daily": {
        "task": "app.tasks.validation_tasks.validate_tier_patterns",
        "schedule": crontab(hour=0, minute=0),  # Every day at midnight UTC
        "args": [1],  # freshness_tier=1 (HIGH, >$200 savings)
        "kwargs": {"limit": 100},
        "options": {"queue": "validation"},
    },
    "validate-tier-2-biweekly": {
        "task": "app.tasks.validation_tasks.validate_tier_patterns",
        "schedule": crontab(hour=6, minute=0, day_of_week="1,4"),  # Mon + Thu at 6am UTC
        "args": [2],  # freshness_tier=2 (MEDIUM, $50-200 savings)
        "kwargs": {"limit": 100},
        "options": {"queue": "validation"},
    },
    "validate-tier-3-monthly": {
        "task": "app.tasks.validation_tasks.validate_tier_patterns",
        "schedule": crontab(hour=6, minute=0, day_of_month=1),  # 1st of month at 6am UTC
        "args": [3],  # freshness_tier=3 (LOW, <$50 savings)
        "kwargs": {"limit": 200},
        "options": {"queue": "validation"},
    },

    # ── YQ data collection ──────────────────────────────────────────────
    "update-carrier-yq-weekly": {
        "task": "app.tasks.yq_tasks.update_all_carrier_yq",
        "schedule": crontab(hour=5, minute=0, day_of_week=0),  # Sunday 5am UTC
        "options": {"queue": "yq"},
    },

    # ── Community ingestion ─────────────────────────────────────────────
    "scan-forums-6h": {
        "task": "app.tasks.ingestion_tasks.scan_all_forums",
        "schedule": crontab(hour="*/6", minute=0),  # Every 6 hours
        "options": {"queue": "ingestion"},
    },
    "process-pending-posts-6h": {
        "task": "app.tasks.ingestion_tasks.process_pending_posts",
        "schedule": crontab(hour="*/6", minute=30),  # Every 6 hours, offset 30m from scan
        "kwargs": {"limit": 50},
        "options": {"queue": "ingestion"},
    },
}
