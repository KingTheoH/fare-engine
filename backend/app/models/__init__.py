"""
models/__init__.py — Import all ORM models so Alembic can discover them.

Alembic's env.py imports Base.metadata, which only contains tables that
have been registered by importing their model classes. This file ensures
all models are imported when the package is loaded.
"""

from app.models.carrier import Carrier
from app.models.community_post import CommunityPost
from app.models.dump_candidate import DumpCandidate
from app.models.dump_pattern import DumpPattern
from app.models.enums import (
    Alliance,
    DumpType,
    FreshnessTier,
    LifecycleState,
    PatternSource,
    ProcessingState,
)
from app.models.route import Route
from app.models.scan_target import ScanTarget
from app.models.validation_run import ValidationRun
from app.models.yq_schedule import YQSchedule

__all__ = [
    "Carrier",
    "CommunityPost",
    "DumpCandidate",
    "DumpPattern",
    "Route",
    "ScanTarget",
    "ValidationRun",
    "YQSchedule",
    "Alliance",
    "DumpType",
    "FreshnessTier",
    "LifecycleState",
    "PatternSource",
    "ProcessingState",
]
