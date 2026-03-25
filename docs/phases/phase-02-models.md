# Phase 02 — Core Domain Models (Python)

## Goal
Define all Pydantic schemas, enums, and service-layer data structures. By the end of this phase, the system has fully typed representations of every core concept, independent of the database layer.

## Deliverables

- [ ] `app/models/enums.py` — finalized with all enum values
- [ ] `app/schemas/` directory with all Pydantic schemas:
  - `carrier.py` — CarrierCreate, CarrierUpdate, CarrierResponse
  - `route.py` — RouteCreate, RouteResponse
  - `dump_pattern.py` — DumpPatternCreate, DumpPatternUpdate, DumpPatternResponse, DumpPatternSummary
  - `manual_input.py` — ManualInputBundle (the most critical schema — see below)
  - `validation_run.py` — ValidationRunCreate, ValidationRunResponse
  - `yq_schedule.py` — YQScheduleCreate, YQScheduleResponse
  - `community_post.py` — CommunityPostCreate, CommunityPostResponse, ExtractedPattern
- [ ] `app/schemas/common.py` — shared types (PaginatedResponse, ErrorResponse)
- [ ] Unit tests for all schemas (`tests/test_schemas/`)

## ManualInputBundle Schema (Critical)

This schema must exactly match what the frontend `ManualInputBundle` component renders. Define it in `app/schemas/manual_input.py`:

```python
class ManualInputBundle(BaseModel):
    routing_code_string: str
    # The exact string to paste into ITA Matrix routing codes field

    human_description: str
    # Plain English: "JFK → Frankfurt (LH) → Bangkok (LH) // Bangkok → JFK (AA)"

    ita_matrix_steps: list[str]
    # Numbered step-by-step instructions. Must be self-contained.

    expected_yq_savings_usd: float
    expected_yq_carrier: str  # The carrier whose YQ is being avoided

    validation_timestamp: datetime
    confidence_score: float  # 0.0–1.0

    backup_routing_code: str | None
    # Alternate routing code if primary fails (e.g., use LX instead of LH)

    notes: str | None
    # Free text: fare class hints, caveats, known booking windows
```

## Enum Definitions

```python
class DumpType(str, Enum):
    TP_DUMP = "TP_DUMP"
    CARRIER_SWITCH = "CARRIER_SWITCH"
    FARE_BASIS = "FARE_BASIS"
    ALLIANCE_RULE = "ALLIANCE_RULE"

class LifecycleState(str, Enum):
    DISCOVERED = "discovered"
    ACTIVE = "active"
    DEGRADING = "degrading"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"

class PatternSource(str, Enum):
    FLYERTALK = "FLYERTALK"
    MANUAL = "MANUAL"
    INTERNAL_DISCOVERY = "INTERNAL_DISCOVERY"

class FreshnessTier(int, Enum):
    HIGH = 1    # YQ savings > $200, validate every 24h
    MEDIUM = 2  # YQ savings $50–200, validate every 7 days
    LOW = 3     # YQ savings < $50, validate every 30 days

class ProcessingState(str, Enum):
    RAW = "raw"
    PROCESSED = "processed"
    FAILED = "failed"
```

## What This Phase Does NOT Include

- No actual service logic (just data shapes)
- No database queries
- No API endpoints

## Completion Check

```bash
cd backend && pytest tests/test_schemas/ -v
# All schema validation tests should pass
```

## Files Changed
- New: all files in `backend/app/schemas/`
- New: `backend/tests/test_schemas/`
- Modified: `app/models/enums.py` (if any adjustments needed after Phase 1)
