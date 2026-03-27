# CLAUDE.md — Pydantic Schemas

## Overview

All Pydantic models for API request/response validation live here. Schemas are the contract between the API layer and its consumers (dashboard, automation, tests). ORM models live in `models/` — schemas are separate.

## Directory Structure

```
schemas/
├── CLAUDE.md              ← you are here
├── common.py              ← PaginatedResponse, ErrorResponse (shared types)
├── carrier.py             ← CarrierCreate, CarrierUpdate, CarrierResponse
├── route.py               ← RouteCreate, RouteResponse
├── dump_pattern.py        ← DumpPatternCreate, DumpPatternUpdate, DumpPatternResponse, DumpPatternSummary
├── manual_input.py        ← ManualInputBundle (the most critical schema)
├── validation_run.py      ← ValidationRunCreate, ValidationRunResponse
├── yq_schedule.py         ← YQScheduleCreate, YQScheduleResponse
└── community_post.py      ← CommunityPostCreate, CommunityPostResponse, ExtractedPattern
```

## Naming Conventions

| Suffix | Purpose |
|--------|---------|
| `Create` | Input schema for POST requests (omit `id`, `created_at`) |
| `Update` | Input schema for PATCH requests (all fields Optional) |
| `Response` | Output schema (includes `id`, timestamps, computed fields) |
| `Summary` | Lightweight response for list views (omit heavy fields like `manual_input_bundle`) |

## ManualInputBundle — The Critical Schema

Defined in `manual_input.py`. This schema must match exactly what `ManualInputBundle.tsx` renders on the frontend.

```python
class ManualInputBundle(BaseModel):
    routing_code_string: str
    # The exact string to paste into ITA Matrix "Routing codes" field

    human_description: str
    # Plain English: "JFK → Frankfurt (LH) → Bangkok (LH) // Bangkok → JFK (AA)"

    ita_matrix_steps: list[str]
    # Numbered step-by-step instructions. Must be self-contained — usable with no prior context.
    # Example: ["1. Go to matrix.itasoftware.com", "2. Enter JFK as origin..."]

    expected_yq_savings_usd: float
    expected_yq_carrier: str          # The carrier whose YQ is being avoided

    validation_timestamp: datetime
    confidence_score: float           # 0.0–1.0

    backup_routing_code: str | None
    # Alternate routing if primary fails (e.g., use LX instead of LH)

    notes: str | None
    # Free text: fare class hints, caveats, known booking windows
```

## DumpPatternSummary vs DumpPatternResponse

`DumpPatternSummary` is used in list responses and **excludes** `manual_input_bundle` (too heavy for leaderboard).
`DumpPatternResponse` is used in detail responses and **includes** `manual_input_bundle`.

Always return `DumpPatternSummary` from `GET /api/v1/patterns`.
Return `DumpPatternResponse` from `GET /api/v1/patterns/{id}`.

## Common Types (`common.py`)

```python
class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int

class ErrorResponse(BaseModel):
    error: str        # machine-readable code, e.g. "pattern_not_found"
    message: str      # human-readable
    status_code: int
```

## Response Conventions

- All timestamps: ISO 8601 (`datetime` fields, FastAPI serializes automatically)
- Savings amounts: `float`, always in USD, 2 decimal places
- Confidence scores: `float`, 0.0–1.0
- Enums: return string values (e.g. `"TP_DUMP"`, `"active"`) not integers
- `manual_input_bundle` in responses: always complete and self-contained

## What NOT to Do

- Do not put business logic in schemas (no methods that call DB or services)
- Do not share ORM model instances as response — always serialize through a schema
- Do not use `orm_mode` directly — use `model_config = ConfigDict(from_attributes=True)` (Pydantic v2 style)
