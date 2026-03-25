# CLAUDE.md — API Layer

## Router Organization

One router file per domain:

| File | Prefix | Purpose |
|------|--------|---------|
| `patterns.py` | `/api/v1/patterns` | CRUD + search for dump patterns |
| `carriers.py` | `/api/v1/carriers` | Carrier list + YQ data |
| `validations.py` | `/api/v1/validations` | Validation run history + manual triggers |
| `ingestion.py` | `/api/v1/ingestion` | Submit community post URLs for processing |
| `manual_inputs.py` | `/api/v1/manual-inputs` | Export manual input bundles |
| `health.py` | `/health` | Health check (no auth) |

## Key Endpoints

### `GET /api/v1/patterns`
Returns paginated list of `active` dump patterns, sorted by `expected_yq_savings_usd DESC`.
Query params: `origin`, `destination`, `dump_type`, `min_confidence`, `min_savings_usd`, `carrier`.

### `GET /api/v1/patterns/{id}/manual-input`
Returns the full manual input bundle for a specific pattern. This is what agents copy-paste into ITA Matrix. Always returns the most recent `manual_input_snapshot` from the last successful validation run.

### `POST /api/v1/validations/trigger/{pattern_id}`
Manually trigger a validation run for a specific pattern. Enqueues a Celery task. Returns task ID.

### `GET /api/v1/validations/{pattern_id}/history`
Returns all validation runs for a pattern in reverse chronological order.

### `POST /api/v1/ingestion/submit`
Submit a FlyerTalk or forum URL for ingestion. Enqueues a Celery ingestion task.

## Response Conventions

- Always use ISO 8601 timestamps
- Savings amounts always in USD (float, 2 decimal places)
- Confidence scores as float 0.0–1.0
- Lifecycle state and dump type always returned as strings matching enum names
- `manual_input_bundle` in responses is always a complete, self-contained JSON object — agents should be able to use it with no other context

## Auth

All endpoints except `/health` require `X-API-Key` header.
Return `403 Forbidden` (not 401) on missing/invalid key to avoid leaking auth scheme info.
