# Phase 07 — Validation & Scoring Engine

## Goal
Build the core validation loop: take a `dump_pattern`, run it through ITA Matrix automation, record the result, update confidence scores, and transition lifecycle states. This is the heart of the system.

## Deliverables

- [ ] `backend/app/services/validation_service.py` — full validation logic
- [ ] `backend/app/services/scoring_service.py` — confidence + tier calculation
- [ ] `backend/app/db/repositories/validation_repository.py`
- [ ] `backend/app/db/repositories/pattern_repository.py`
- [ ] Celery task: `app/tasks/validation_tasks.py`
- [ ] API endpoint: `POST /api/v1/validations/trigger/{pattern_id}`
- [ ] API endpoint: `GET /api/v1/validations/{pattern_id}/history`
- [ ] Unit tests: `tests/test_services/test_validation_service.py` (mock ITA automation)
- [ ] Unit tests: `tests/test_services/test_scoring_service.py`

## Validation Flow

```
validate_pattern(pattern_id)
    │
    ├── Load pattern from DB
    ├── Build routing code via query_builder
    ├── Select a travel date (3–6 weeks out — always use future dates)
    ├── Call ita_client.run_query(routing_code, origin, dest, date)
    │
    ├── If ITAResult.success == True:
    │   ├── Parse YQ from fare_breakdown
    │   ├── Determine success: yq_total_usd <= SUCCESS_THRESHOLD (default: $10)
    │   ├── Save ValidationRun record
    │   ├── Update manual_input_bundle on pattern (regenerate fresh)
    │   ├── Update expected_yq_savings_usd on pattern
    │   └── Call evaluate_validation_result(pattern_id, success=True/False)
    │
    └── If ITAResult.success == False:
        ├── Save ValidationRun record with success=False, error_message set
        └── Call evaluate_validation_result(pattern_id, success=False)
```

## Success Threshold

A validation is considered **successful** if:
```
yq_charged_usd <= SUCCESS_THRESHOLD
```
Where `SUCCESS_THRESHOLD = 10.0` (USD). This allows for minor rounding/currency differences without false negatives.

If `yq_charged_usd` is close to threshold (within $50 of expected), flag as `degrading` signal even if technically successful.

## Lifecycle Transition Logic

```python
async def evaluate_validation_result(pattern_id: UUID, success: bool) -> None:
    pattern = await get_pattern(pattern_id)
    recent_runs = await get_recent_validation_runs(pattern_id, limit=10)

    if success:
        if pattern.lifecycle_state == LifecycleState.DISCOVERED:
            # First success — promote to active
            await update_lifecycle_state(pattern_id, LifecycleState.ACTIVE)

        elif pattern.lifecycle_state == LifecycleState.DEGRADING:
            # Check for recovery: 2 consecutive successes
            if last_n_consecutive_successes(recent_runs, n=2):
                await update_lifecycle_state(pattern_id, LifecycleState.ACTIVE)

    else:  # failure
        if pattern.lifecycle_state == LifecycleState.ACTIVE:
            # Check success rate of last 5 runs
            if success_rate(recent_runs, last_n=5) < 0.60:
                await update_lifecycle_state(pattern_id, LifecycleState.DEGRADING)

        elif pattern.lifecycle_state in (LifecycleState.DEGRADING, LifecycleState.DISCOVERED):
            # Check for 3 consecutive failures
            if last_n_consecutive_failures(recent_runs, n=3):
                await update_lifecycle_state(pattern_id, LifecycleState.DEPRECATED)
                await alert_pattern_deprecated(pattern_id)  # notify agents
```

## Scoring Service (`scoring_service.py`)

### `calculate_confidence_score(pattern_id) -> float`

```python
# Component weights (see root CLAUDE.md)
recent_success_rate = weighted_success_rate(recent_runs, recency_weight=True)
source_weight = pattern.source_post_weight
multi_source = 0.1 if count_independent_sources(pattern_id) > 1 else 0.0
recency_decay = calculate_recency_decay(pattern.updated_at)

score = (
    0.50 * recent_success_rate
  + 0.25 * source_weight
  + 0.15 * multi_source
  + 0.10 * recency_decay
)
return max(0.0, min(1.0, score))
```

### `recalculate_freshness_tier(pattern_id) -> FreshnessTier`

```python
savings = pattern.expected_yq_savings_usd
if savings > 200: return FreshnessTier.HIGH
elif savings >= 50: return FreshnessTier.MEDIUM
else: return FreshnessTier.LOW
```

Run `recalculate_freshness_tier` after every successful validation (savings may have changed).

### `calculate_recency_decay(last_validated: datetime) -> float`

```python
days_since = (now - last_validated).days
if days_since <= 1: return 1.0
elif days_since <= 7: return 0.9
elif days_since <= 30: return 0.7
elif days_since <= 90: return 0.4
else: return 0.1
```

## ValidationRun Record

After each run, store:
- All `ITAResult` data
- `manual_input_snapshot` — the manual input bundle AS OF this run (so agents can replay exactly what worked)
- `yq_expected_usd` — what we expected going into the run
- Whether `success` was True/False
- `proxy_used` — for debugging

The `manual_input_snapshot` in ValidationRun is **immutable** after creation. Even if the pattern's manual_input_bundle changes later, old validation runs preserve the exact routing that was tested.

## Celery Task

```python
@celery_app.task(name="validate_pattern", max_retries=1, retry_backoff=True)
def validate_pattern_task(pattern_id: str) -> dict:
    """
    Wraps validation_service.validate_pattern().
    Returns dict with success, yq_result, lifecycle_change.
    Max 1 retry — don't hammer ITA Matrix on failures.
    """
```

## Completion Check

```bash
# Unit tests (mocked ITA automation)
cd backend && pytest tests/test_services/test_validation_service.py -v
cd backend && pytest tests/test_services/test_scoring_service.py -v

# Integration: trigger a validation via API
curl -X POST http://localhost:8000/api/v1/validations/trigger/{pattern_id} \
  -H "X-API-Key: test-key"
```

## Files Changed
- New: `backend/app/services/validation_service.py`
- New: `backend/app/services/scoring_service.py`
- New: `backend/app/db/repositories/validation_repository.py`
- New: `backend/app/db/repositories/pattern_repository.py`
- New: `backend/app/tasks/validation_tasks.py`
- New: `backend/app/api/validations.py` (route handlers)
- New: `tests/test_services/test_validation_service.py`
- New: `tests/test_services/test_scoring_service.py`
