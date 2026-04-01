"""
enums.py — All shared enumerations for the fare construction engine.

Design note (from planning session):
- DumpType taxonomy was added during design to distinguish HOW a dump works,
  not just that it works. This affects query_builder logic in Phase 3.
- LifecycleState includes 'degrading' as an early-warning state before full
  deprecation — gives agents advance notice before a dump dies.
- YQ and YR are intentionally kept separate throughout the entire codebase.
  Never conflate them. YQ = carrier fuel surcharge (target). YR = govt tax (untouchable).
- FreshnessTier drives validation scheduling: Tier 1 daily, Tier 2 weekly, Tier 3 monthly.
"""

import enum


class DumpType(str, enum.Enum):
    """
    How the dump eliminates YQ. Critical for query_builder (Phase 3) to generate
    the correct ITA Matrix routing code syntax per dump mechanism.
    """
    TP_DUMP = "TP_DUMP"            # Ticketing Point manipulation — most common
    CARRIER_SWITCH = "CARRIER_SWITCH"  # No-YQ carrier on the surcharge-bearing sector
    FARE_BASIS = "FARE_BASIS"      # Specific fare basis code structurally excludes YQ
    ALLIANCE_RULE = "ALLIANCE_RULE"  # Interline agreement waives YQ between specific pairs
    STRIKE_SEGMENT = "STRIKE_SEGMENT"  # Throwaway segment appended to end of routing — no-YQ carrier zeroes surcharges on full ticket


class LifecycleState(str, enum.Enum):
    """
    Pattern lifecycle: discovered → active → degrading → deprecated → archived
    'degrading' = success rate < 60% over last 5 runs (early warning)
    'deprecated' = 3 consecutive failures
    'archived' = manual action only, never surfaced to agents
    """
    DISCOVERED = "discovered"
    ACTIVE = "active"
    DEGRADING = "degrading"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class PatternSource(str, enum.Enum):
    """Where the dump pattern was originally discovered."""
    FLYERTALK = "FLYERTALK"
    MANUAL = "MANUAL"
    INTERNAL_DISCOVERY = "INTERNAL_DISCOVERY"


class FreshnessTier(int, enum.Enum):
    """
    Controls how often a pattern is validated. Recalculated dynamically
    after every successful validation based on expected_yq_savings_usd:
    - Tier 1: > $200 savings → validate every 24h
    - Tier 2: $50–200 savings → validate every 7 days
    - Tier 3: < $50 savings  → validate every 30 days
    """
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class ProcessingState(str, enum.Enum):
    """State of a community post through the LLM extraction pipeline (Phase 6)."""
    RAW = "raw"
    PROCESSED = "processed"
    FAILED = "failed"


class Alliance(str, enum.Enum):
    """Carrier alliance membership. Used for ALLIANCE_RULE dump type logic."""
    STAR = "STAR"
    ONEWORLD = "ONEWORLD"
    SKYTEAM = "SKYTEAM"
    NONE = "NONE"
