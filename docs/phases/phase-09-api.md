# Phase 09 — REST API Layer

## Goal
Build the complete FastAPI application with all endpoints, authentication, and a proper `main.py` entrypoint. By the end of this phase, the agent dashboard can make API calls to retrieve patterns, trigger validations, and get manual input bundles.

## Deliverables

- [ ] `backend/app/main.py` — FastAPI app with all routers registered
- [ ] `backend/app/dependencies.py` — shared FastAPI dependencies (auth, DB session)
- [ ] All router files (see API CLAUDE.md for list)
- [ ] Pydantic response schemas (review and finalize from Phase 2)
- [ ] OpenAPI docs auto-generated at `/docs` and `/redoc`
- [ ] Integration tests: `tests/test_api/` (use `httpx.AsyncClient` against TestClient)

## App Entrypoint (`main.py`)

```python
from fastapi import FastAPI
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: init DB pool, verify Redis connection
    await init_db_pool()
    await verify_redis_connection()
    yield
    # Shutdown: close DB pool
    await close_db_pool()

app = FastAPI(
    title="Fare Construction Engine",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Register all routers
app.include_router(patterns_router, prefix="/api/v1")
app.include_router(carriers_router, prefix="/api/v1")
app.include_router(validations_router, prefix="/api/v1")
app.include_router(ingestion_router, prefix="/api/v1")
app.include_router(manual_inputs_router, prefix="/api/v1")
app.include_router(health_router)
```

## Auth Dependency (`dependencies.py`)

```python
async def verify_api_key(x_api_key: str = Security(api_key_header)) -> str:
    """
    FastAPI Security dependency.
    Looks up hashed key in DB. Returns the key string if valid.
    Raises HTTP 403 if invalid or missing.
    """
```

All routers except `/health` use `Depends(verify_api_key)`.

## Key Endpoint Specs

### `GET /api/v1/patterns`
Query params: `origin`, `destination`, `dump_type`, `min_confidence`, `min_savings_usd`, `carrier`, `page`, `page_size` (default 20, max 100)

Response:
```json
{
  "items": [DumpPatternSummary],
  "total": 142,
  "page": 1,
  "page_size": 20
}
```

`DumpPatternSummary` includes: id, route, dump_type, lifecycle_state, expected_yq_savings_usd, confidence_score, freshness_tier, ticketing_carrier, operating_carriers, last_validated_at.

### `GET /api/v1/patterns/{id}`
Full pattern detail. Includes `manual_input_bundle`.

### `GET /api/v1/patterns/{id}/manual-input`
Returns ONLY the `ManualInputBundle` JSON. Clean, self-contained, ready for the agent.

### `POST /api/v1/validations/trigger/{pattern_id}`
Enqueues validation task. Returns:
```json
{"task_id": "celery-task-uuid", "message": "Validation queued"}
```

### `GET /api/v1/validations/{pattern_id}/history`
Returns list of `ValidationRunResponse` in reverse chronological order.
Each item includes `manual_input_snapshot` — the exact manual input bundle as of that run.

### `GET /api/v1/carriers`
Returns all carriers, sorted by `typical_yq_usd DESC`.
Query param: `charges_yq=true` to filter to YQ-charging carriers only.

### `POST /api/v1/ingestion/submit`
Body: `{"url": "https://flyertalk.com/forum/..."}`
Returns: `{"task_id": "...", "message": "Ingestion queued"}`

## Error Response Format

All errors return:
```json
{
  "error": "pattern_not_found",
  "message": "No pattern found with id: abc-123",
  "status_code": 404
}
```

Use custom exception handler in `main.py` to catch `AppException` and format consistently.

## OpenAPI Schema Notes

- Mark `manual_input_bundle` fields with `example` values so the Swagger UI is useful
- Document all query params with descriptions
- Add response examples for key endpoints

## Integration Tests

Use `pytest` + `httpx.AsyncClient` with a test database (separate `TEST_DATABASE_URL`).

Test coverage required:
- Auth: valid key works, invalid key returns 403
- Pattern list: filtering by origin/destination, min_savings, dump_type
- Pattern detail: includes manual_input_bundle when pattern is active
- Validation trigger: returns task_id, task appears in Redis
- Manual input endpoint: returns self-contained bundle

## Completion Check

```bash
# Run API server
cd backend && uvicorn app.main:app --reload

# Check health
curl http://localhost:8000/health

# Check docs
open http://localhost:8000/docs

# Run integration tests
cd backend && pytest tests/test_api/ -v
```

## Files Changed
- New: `backend/app/main.py`
- New: `backend/app/dependencies.py`
- New: `backend/app/exceptions.py`
- New: all router files in `backend/app/api/`
- New: `tests/test_api/`
- Modified: `docker-compose.yml` (add backend service with uvicorn)
