# CLAUDE.md — Tests

## Overview

All pytest tests live here. Tests are organized to mirror the module they're testing.

## Directory Structure

```
tests/
├── CLAUDE.md                      ← you are here
├── conftest.py                    ← shared fixtures (test DB, async client, factories)
├── fixtures/
│   ├── dump_patterns.json         ← 10+ example dump patterns (all 4 dump types)
│   └── flyertalk_posts.json       ← 10+ example forum posts for LLM extractor tests
├── test_schemas/                  ← Phase 02: Pydantic schema validation tests
│   ├── test_manual_input.py
│   ├── test_dump_pattern.py
│   └── ...
├── test_automation/               ← Phase 03 + 04: query builder + ITA client tests
│   ├── test_query_builder.py      ← unit tests, no network required
│   └── test_ita_client.py         ← integration tests, marked @pytest.mark.integration
├── test_ingestion/                ← Phase 05 + 06: scraper + LLM extraction tests
│   ├── test_yq_scrapers.py        ← unit tests with mock HTTP (httpx mock)
│   └── test_llm_extractor.py      ← unit tests with fixture posts
├── test_services/                 ← Phase 07: validation + scoring service tests
│   ├── test_validation_service.py ← ITA automation is mocked
│   └── test_scoring_service.py
├── test_tasks/                    ← Phase 08: Celery task tests
└── test_api/                      ← Phase 09: FastAPI integration tests
    ├── test_patterns.py
    ├── test_carriers.py
    ├── test_validations.py
    └── test_health.py
```

## Test Markers

Defined in `pyproject.toml`:
```
integration  — requires real network, proxies, or browser (always mark ITA client tests)
slow         — takes >5s to run (mark long-running integration tests)
```

Run unit tests only (CI default):
```bash
cd backend && pytest -v -m "not integration"
```

Run all tests including integration:
```bash
cd backend && pytest -v
```

## Conftest Fixtures

### `test_db` (session-scoped)
Creates a fresh test database using `TEST_DATABASE_URL`. Runs all migrations before the test session, drops all data after.

### `async_client` (function-scoped)
`httpx.AsyncClient` pointed at the FastAPI TestClient. Includes a valid `X-API-Key` header.

### `db_session` (function-scoped)
`AsyncSession` connected to the test database. Auto-rolls back after each test.

### Factories (using `factory_boy`)
- `CarrierFactory` — creates carrier records
- `DumpPatternFactory` — creates dump_pattern records in `discovered` state
- `ValidationRunFactory` — creates validation run records

## Key Testing Rules

### Unit Tests (no network, no DB)
- Schema tests: just instantiate the Pydantic model and assert field values
- Query builder tests: call `build_routing_code(pattern)` with fixture data, assert the output string
- Scoring service: mock `get_recent_validation_runs()`, assert confidence score math

### Service Tests (mock automation)
- Patch `ita_client.run_query` to return a fixed `ITAResult`
- Test that `validation_service.validate_pattern()` correctly writes `ValidationRun` records
- Test all lifecycle transition edge cases (discovered→active, active→degrading, degrading→deprecated)

### API Integration Tests (real FastAPI, test DB)
```python
async def test_get_patterns_returns_active_only(async_client, db_session):
    # Arrange: create one active pattern, one deprecated pattern
    # Act: GET /api/v1/patterns
    # Assert: only active pattern in response, deprecated not returned
```

### ITA Client Integration Tests (real network)
Always mark with `@pytest.mark.integration`. These run against the real ITA Matrix.
They can be skipped in CI by running `pytest -m "not integration"`.

## Fixture Data (`tests/fixtures/`)

### `dump_patterns.json`
10+ patterns covering all dump types. Used in query builder tests.
```json
[
  {
    "id": "...",
    "dump_type": "TP_DUMP",
    "origin_iata": "JFK",
    "destination_iata": "BKK",
    "ticketing_carrier_iata": "LH",
    "operating_carriers": ["LH", "AA"],
    "routing_points": ["FRA"],
    "fare_basis_hint": null
  }
]
```

### `flyertalk_posts.json`
10+ posts, some containing dump patterns, some not. Used in LLM extractor tests to verify two-pass filtering logic.

## What NOT to Do

- Do not share state between tests — each test must be self-contained
- Do not make real ITA Matrix requests in unit tests — always mock `ita_client`
- Do not use `asyncio.run()` in tests — use `pytest-asyncio` with `asyncio_mode = "auto"`
- Do not hardcode test data in test functions — use fixture files or factories
- Do not test FastAPI route handlers directly — use `async_client` (goes through full middleware stack)
