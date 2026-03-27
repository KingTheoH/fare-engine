# CONTEXT.md — Change Log & Discussion Notes

This file is updated every time a phase is implemented or a significant decision is made.
Format: `## [Date] — [Phase or Topic]` with bullet points explaining what changed and why.

---

## [2026-03-25] — Initial Planning Session

**Session summary**: Explored product concept with user. Designed full architecture. Key decisions made:

### What the user confirmed:
- **Target users**: Travel agents / ticketing professionals (not consumers)
- **Data source**: Community-sourced from scratch (FlyerTalk + self-validated). No existing dataset.
- **ITA Matrix integration**: Browser automation via Playwright. User accepts ToS risk.
- **No Amadeus API**: Explicitly excluded. Amadeus removed public API access.
- **Manual input requirement**: For every automated ITA Matrix query, produce a 1:1 manual input bundle. If automation fails, agents must be able to replicate manually with zero additional context.
- **Development approach**: Phase by phase (backend → DB → automation → ingestion → UI). Small phases. Incremental.

### Logic changes made vs. initial design:
- **Added dump type taxonomy** (TP_DUMP, CARRIER_SWITCH, FARE_BASIS, ALLIANCE_RULE) — not in original concept but essential for correct pattern matching and validation
- **Changed "weekly updates" to tiered freshness** — Tier 1 (>$200 savings) validated daily, Tier 2 ($50–200) weekly, Tier 3 (<$50) monthly. Weekly was the floor, not the target.
- **Added pattern lifecycle states** (discovered → active → degrading → deprecated → archived) — gives agents advance warning before a dump stops working
- **Separated YQ and YR** — original concept mentioned "fuel costs" generically; explicitly separated carrier-imposed (YQ, target of dumps) from government-imposed (YR, cannot be dumped)
- **Community source weighting** added — not all FlyerTalk posts are equal; author reputation + recency + confirmation posts all factor into confidence scoring
- **Backup routing** added to manual input bundle — if primary routing fails, agents get an alternate carrier-substituted routing
- **Immutable ValidationRun.manual_input_snapshot** — each validation run stores the exact manual input bundle as-of that run, so agents can replay specific successful bookings even if the pattern changes later

### Architecture decisions:
- PostgreSQL (not SQLite or MongoDB) — structured relational data with complex queries needed
- Celery + Redis — background jobs with Redis broker/backend already in stack
- Claude API for LLM extraction (haiku filter → sonnet for extraction) — cost-controlled two-pass approach
- Next.js for dashboard — SSR allows API key to stay server-side

---

*Add new entries below as phases are implemented.*

## Template for future entries:

```
## [YYYY-MM-DD] — Phase N Implementation

### What was built:
-

### Deviations from spec:
- [List any places where the implementation differed from the phase doc, and why]

### Issues encountered:
- [Bugs, unexpected behavior, API changes, DOM changes in ITA Matrix, etc.]

### Decisions made during implementation:
-

### What to watch for in next phase:
-
```

---

## [2026-03-25] — Phase 01 Implementation

### What was built:
- `app/config.py` — Pydantic BaseSettings with all environment variables
- `app/models/carrier.py` — Carrier ORM model (PK: iata_code string, not UUID)
- `app/models/route.py` — Route ORM model (UUID PK, unique constraint on origin+destination)
- `app/models/dump_pattern.py` — DumpPattern ORM model (core entity, self-FK for backup_pattern, uses TimestampMixin)
- `app/models/validation_run.py` — ValidationRun ORM model (immutable manual_input_snapshot)
- `app/models/yq_schedule.py` — YQSchedule ORM model (FK to carriers + routes)
- `app/models/community_post.py` — CommunityPost ORM model (unique on post_url for dedup)
- `app/models/__init__.py` — exports all models for Alembic metadata discovery
- Alembic initialized with async-aware `env.py` (reads DATABASE_URL from app.config)
- Initial migration `001_initial_schema` — creates all 6 tables, 5 indexes, all FK constraints
- `seeds/carriers.json` — 32 carriers (16 high-YQ, 7 low/no-YQ, 3 US, 6 additional)
- `scripts/seed_carriers.py` — idempotent upsert using INSERT ON CONFLICT DO UPDATE
- All `__init__.py` files for clean package structure

### Deviations from spec:
- Added `Alliance` enum in Phase 01 (spec implied Phase 02) — needed by carrier model
- Used Homebrew PostgreSQL 16 instead of Docker (Docker Desktop not available). Docker Compose config still correct for deployment.
- Added `[tool.hatch.build.targets.wheel] packages = ["app"]` to pyproject.toml — hatchling auto-detection fix
- Added VS (Virgin Atlantic, $450 YQ) and QF (Qantas, $320 YQ) to carrier seed data

### Issues encountered:
- System Python was 3.9.6 — installed Python 3.12 via Homebrew
- Docker Desktop not installed — used local PostgreSQL 16 instead
- Hatch build system needed explicit `packages` directive

### Decisions made during implementation:
- Carrier PK is `iata_code` (String(2)) not UUID — IATA codes are globally unique, avoids unnecessary joins
- `gen_random_uuid()` used as server_default for UUID PKs (PostgreSQL 13+ native)
- Seed script uses raw SQL INSERT ON CONFLICT for reliability
- Hand-written Alembic migration (not autogenerate) — more reliable and reviewable

### What to watch for in next phase:
- Phase 02 schemas must use `ConfigDict(from_attributes=True)` for ORM serialization
- `ManualInputBundle` schema structure must match JSONB column in `dump_patterns.manual_input_bundle`
- `FreshnessTier` enum uses integers (1, 2, 3) — verify Pydantic handles correctly
- UI note: user wants **Google Flights aesthetic** for Phase 10 dashboard

---

## [2026-03-25] — Phase 02 Implementation

### What was built:
- `app/schemas/common.py` — PaginatedResponse (generic), ErrorResponse
- `app/schemas/carrier.py` — CarrierCreate, CarrierUpdate, CarrierResponse
- `app/schemas/route.py` — RouteCreate, RouteResponse
- `app/schemas/manual_input.py` — ManualInputBundle (the critical schema, with full validation)
- `app/schemas/dump_pattern.py` — DumpPatternCreate, DumpPatternUpdate, DumpPatternSummary, DumpPatternResponse
- `app/schemas/validation_run.py` — ValidationRunCreate, ValidationRunResponse
- `app/schemas/yq_schedule.py` — YQScheduleCreate, YQScheduleResponse
- `app/schemas/community_post.py` — CommunityPostCreate, CommunityPostResponse, ExtractedPattern
- `app/schemas/__init__.py` — exports all 17 schemas
- `tests/test_schemas/` — 7 test files, 70 tests covering all schemas

### Deviations from spec:
- None — all deliverables from the phase spec were implemented as specified

### Issues encountered:
- None — pure Python phase with no external dependencies to worry about

### Decisions made during implementation:
- `ManualInputBundle` has strict validation: confidence_score [0.0, 1.0], carrier codes exactly 2 chars, ita_matrix_steps requires at least 1 step, savings must be >= 0
- `DumpPatternSummary` deliberately excludes `fare_basis_hint`, `ita_routing_code`, `source_post_weight`, and `manual_input_bundle` — keeps list responses lightweight
- `ValidationRunResponse.manual_input_snapshot` typed as `dict[str, Any] | None` (not ManualInputBundle) since it's stored as JSONB and may contain historical formats
- `ExtractedPattern` schema added for LLM output structure — gives Phase 06 a clear contract
- `PaginatedResponse` generic type allows `PaginatedResponse[DumpPatternSummary]`, `PaginatedResponse[CarrierResponse]`, etc.
- All Response schemas use `ConfigDict(from_attributes=True)` for ORM → schema serialization

### What to watch for in next phase:
- Phase 03 (ITA Query Builder) needs to generate `ManualInputBundle` instances — import from `app.schemas.manual_input`
- The query builder should output routing code strings matching the format validated by `DumpPatternCreate.ita_routing_code`
- Test fixtures in `tests/fixtures/dump_patterns.json` (Phase 03) should use the same field shapes as `DumpPatternCreate`

---

## [2026-03-25] — Phase 03 Implementation

### What was built:
- `automation/query_builder.py` — Routing code builder with dispatch table for all 4 dump types (TP_DUMP, CARRIER_SWITCH, FARE_BASIS, ALLIANCE_RULE). Includes sister carrier map for backup routing generation and carrier hub lookup.
- `automation/manual_input.py` — ManualInputBundle generator with human-readable descriptions, numbered step-by-step ITA Matrix instructions, and dump mechanism notes. Includes city name and carrier name lookup tables.
- `docs/ita_routing_codes.md` — Complete ITA Matrix routing code syntax reference covering FORCE, BC=, NONSTOP, MINCONNECT, all 4 dump pattern types, common pitfalls, and tax code reference.
- `tests/fixtures/dump_patterns.json` — 11 test fixtures covering all 4 dump types (3 TP_DUMP, 3 CARRIER_SWITCH, 2 FARE_BASIS, 2 ALLIANCE_RULE), including one with expected backup code.
- `tests/test_automation/test_query_builder.py` — 28 tests covering routing code generation, backup routing, manual input bundle generation, error cases, and fixture-driven validation.

### Deviations from spec:
- `automation/` is a top-level package (not inside `backend/`) — this matches the repo structure in CLAUDE.md. Tests import it via sys.path manipulation since it's outside the backend package.

### Issues encountered:
- None — pure Python with no external dependencies

### Decisions made during implementation:
- Used `PatternInput` dataclass (not ORM model) as input to query_builder — keeps the module fully decoupled from SQLAlchemy/database
- Sister carrier substitution map covers Star Alliance, oneworld, SkyTeam, and Middle East carriers
- Backup routing substitutes both the carrier and hub city (LH/FRA → LX/ZRH, OS/VIE → LH/FRA, etc.)
- ALLIANCE_RULE requires 2 distinct operating carriers (raises ValueError otherwise)
- FARE_BASIS requires fare_basis_hint to be set (raises ValueError otherwise)
- Manual input steps are always numbered starting from 1, with backup step conditionally added at the end
- Bundle dict output matches ManualInputBundle Pydantic schema shape — validated in test_bundle_validates_as_schema

### What to watch for in next phase:
- Phase 04 (ITA Automation Engine) will call `build_routing_code()` to get the string to type into ITA Matrix
- The `PatternInput` dataclass should be constructed from ORM `DumpPattern` records in the service layer
- `generate_manual_input_bundle()` returns a dict — service layer should validate with `ManualInputBundle.model_validate()` before storing as JSONB

---

## [2026-03-25] — Phase 04 Implementation

### What was built:
- `automation/browser.py` — Playwright browser/context lifecycle manager. Recycles after 15 requests. Randomizes viewport (3 sizes), user agent (10 UAs), locale, and timezone per context. Proxy support per context.
- `automation/proxy_manager.py` — Rotating residential proxy pool. Round-robin rotation, daily limit (200/proxy), 24h retirement on bot detection, stats/monitoring, daily count reset.
- `automation/rate_limiter.py` — Async rate limiter with configurable min delay + random jitter. Prevents ITA Matrix rate limit trips.
- `automation/result_parser.py` — Fare breakdown text parser. Extracts base fare, YQ, YR, other taxes, total price from ITA Matrix fare construction text. Includes bot detection checker (CAPTCHA, redirect detection). `parse_fare_text()` separated for unit testing without Playwright.
- `automation/ita_client.py` — Main ITA Matrix interaction. Full query flow: navigate → fill search → enter routing codes → submit → wait → parse. Human-like behavior (keystroke delays 30-120ms, random pauses 1.5-3.5s). NEVER raises — always returns ITAResult.
- `automation/data/user_agents.json` — Pool of 10 real Chrome user agents (versions 120-123)
- `tests/test_automation/test_ita_client.py` — 30 unit tests covering rate limiter, proxy manager, browser manager, result parser, fare breakdown, ITAResult, and mocked ITAClient (never-raise guarantee, bot detection proxy retirement)

### Deviations from spec:
- `automation/data/user_agents.json` uses Chrome 120-123 UAs (spec said 10 UAs, delivered exactly 10)
- Screenshots directory created with .gitkeep but no screenshots integration test yet (requires live ITA Matrix access)

### Issues encountered:
- None — all Playwright interactions are mocked in unit tests, so no browser needed for test suite

### Decisions made during implementation:
- `parse_fare_text()` is a standalone sync function for unit testability — the async `parse_fare_breakdown()` calls it after extracting text from the page
- `ITAResult.to_dict()` format matches `validation_runs.raw_ita_response` JSONB column shape
- `FareBreakdown.is_dump_success` uses $1.00 threshold (not strict $0) to handle rounding
- `_human_type()` uses `page.keyboard.type()` with per-character delay (30-120ms random)
- `_human_pause()` defaults to 1.5-3.5s between actions
- Max retries set to 1 — spec says don't hammer ITA Matrix on failures
- Bot detection checks both CAPTCHA selectors and URL redirects away from matrix.itasoftware.com

### What to watch for in next phase:
- Phase 05 (YQ Data Collection) will use similar Playwright scraping but for airline booking pages, not ITA Matrix
- The `FareBreakdown` result feeds directly into `ValidationRunCreate` schema via service layer
- `ITAResult.to_dict()` is stored in `validation_runs.raw_ita_response` JSONB column

---

## [2026-03-25] — Phase 05: YQ Data Collection

**What was built:**
- `ingestion/scrapers/base.py` — Abstract BaseYQScraper + YQScrapeResult dataclass
- `ingestion/scrapers/yq/ita_based.py` — Unified ITABasedYQScraper for all carriers
- `ingestion/scrapers/yq/carriers.py` — 15 carrier configs (10 high-YQ + 5 low-YQ reference)
- `ingestion/scrapers/yq_dispatcher.py` — Sequential dispatcher with DispatchResult aggregation
- `backend/app/services/yq_service.py` — DB service layer (store_yq_result, update_carrier_typical_yq, get_highest_yq_carriers, get_current_yq)
- `backend/app/tasks/yq_tasks.py` — Celery task stubs (update_all_carrier_yq, update_single_carrier_yq)
- `backend/tests/test_ingestion/test_yq_scrapers.py` — 44 tests, all passing

**Key design decision — Unified ITA-based approach (Approach B):**
The original plan specified per-airline booking page scrapers (lufthansa.py, british_airways.py, etc.). Instead, all 15 carriers use a single ITABasedYQScraper class that runs a standard (non-dumped) ITA Matrix query. Rationale:
1. Airline booking flows change frequently and break scrapers
2. ITA Matrix parsing is already built and tested (Phase 04)
3. One scraper class to maintain instead of 10+
4. Consistent data format across all carriers

**Carrier coverage:**
- High-YQ (5 sample routes each): LH, BA, LX, OS, SN, IB, CX, KE, OZ, AF
- Low-YQ reference (3 routes each): QR, EK, EY, TK, SQ
- Total: 15 carriers, 65 sample routes

**YQ service fallback logic:**
`get_current_yq()` first checks route-specific YQ data in yq_schedules, then falls back to carrier-level typical_yq_usd. This allows both granular and aggregate YQ tracking.

**Typical YQ calculation:**
Uses median (not mean) of successful scrape results to resist outliers from parsing errors or unusual fare constructions.

**Test count:** 44 tests in test_yq_scrapers.py covering YQScrapeResult, BaseYQScraper, ITABasedYQScraper (with mocked ITA client), carrier configs, dispatcher, task wrappers, and CarrierYQSummary.

---

## [2026-03-25] — Phase 06: Community Data Ingestion

**What was built:**
- `ingestion/scrapers/flyertalk.py` — FlyerTalk forum scraper with keyword matching, thread listing parsing, post extraction, pagination, rate limiting (1.5-2.5s between requests), and deduplication
- `ingestion/extractors/llm_extractor.py` — Two-pass Claude API extraction:
  - Pass 1 (Filter): claude-haiku-4-5 for cheap relevance check (~$0.001/post)
  - Pass 2 (Extract): claude-sonnet-4-6 for full structured JSON extraction (~$0.01/post)
  - Includes JSON response parser that handles markdown code blocks and embedded JSON
- `ingestion/extractors/pattern_normalizer.py` — Converts LLM output to DB-ready format with IATA validation, routing code generation, initial confidence scoring, and freshness tier assignment
- `ingestion/weighting/post_credibility.py` — Post scoring (0.0–1.0) based on author post count, account age, recency, thread confirmations/deprecations (formula from CLAUDE.md spec)
- `backend/app/services/ingestion_service.py` — Orchestration service: ingest_post() (full pipeline), process_raw_posts() (batch), store_scraped_post() (with dedup)
- `backend/app/tasks/ingestion_tasks.py` — Celery task stubs: scan_all_forums, process_pending_posts
- `backend/tests/fixtures/flyertalk_posts.json` — 10 fixture posts covering all 4 dump types + negative cases + deprecated pattern + multiple patterns in one post
- `backend/tests/test_ingestion/test_community_ingestion.py` — 76 tests, all passing

**Key design decisions:**
1. **Regex-based HTML parsing** instead of BeautifulSoup — FlyerTalk has predictable vBulletin structure, avoids heavy dependency
2. **httpx for HTTP** instead of Playwright for forum scraping — forum pages are static HTML, no JS rendering needed. Playwright reserved for ITA Matrix
3. **Forum URLs configurable** — DEFAULT_FORUM_URLS in flyertalk.py, overridable at scraper and task level
4. **Deprecation signal handling** — posts with deprecation signals still get stored but confidence is hard-capped at 0.2
5. **API endpoint deferred** — POST /api/v1/ingestion/submit moved to Phase 09 (REST API layer). Phase 06 focuses on the pipeline internals
6. **Forum config file deferred** — forum URLs stored as constants in flyertalk.py instead of separate JSON config file. Simpler, and Celery tasks can override

**Normalization pipeline:**
- Validates dump_type against DumpType enum values
- Uppercases and validates IATA codes (3-letter airports, 2-letter carriers)
- Generates initial ITA routing code from extracted components
- Sets lifecycle_state = "discovered" (never auto-promotes)
- Sets manual_input_bundle = None (populated after first ITA validation in Phase 07)
- Computes initial confidence from LLM confidence level × source weight + confirmation/deprecation adjustments
- Assigns freshness tier based on estimated savings (>$200 = T1, $50-200 = T2, <$50 = T3)

**Test count:** 76 tests covering FlyerTalk scraper (keyword matching, HTML parsing, dedup), LLM extractor (filter, extract, full pipeline with mocked Claude API), pattern normalizer (validation, routing code gen, confidence scoring, freshness), post credibility (baseline, experience, recency, confirmations, deprecations), Celery tasks, and fixture integration.

---

## [2026-03-25] — Phase 07: Validation & Scoring Engine

**What was built:**
- `backend/app/services/scoring_service.py` — Confidence score calculation with weighted formula:
  - 50% validation success rate (recency-weighted exponential decay, last 10 runs)
  - 25% source post weight (community credibility)
  - 15% multi-source bonus (0.0 for 1 source, 0.5 for 2, 1.0 for 3+)
  - 10% recency factor (exponential decay with 14-day half-life)
  - Returns `ConfidenceBreakdown` with full component breakdown
- `backend/app/services/pattern_service.py` — Lifecycle state management:
  - `evaluate_lifecycle()` — automatic transitions based on validation results
  - `archive_pattern()` — manual deprecated → archived (only transition requiring agent action)
  - `compute_freshness_tier()` / `recalculate_freshness_tier()` — tier assignment based on YQ savings
  - Valid transition map enforced: discovered→active, active→degrading, degrading→active/deprecated, deprecated→archived
- `backend/app/services/validation_service.py` — Full validation orchestration:
  - `run_validation()` — query ITA Matrix → record run → evaluate (score + lifecycle + freshness)
  - `evaluate_validation_result()` — post-run scoring pipeline
  - `record_validation_run()` — stores raw result in validation_runs table
  - Skips archived/deprecated patterns automatically
  - YQ < $10 = dump success threshold
- `backend/app/db/repositories/validation_repository.py` — Query layer for validation_runs (recent runs, consecutive failures/successes, success rate, last validation time, paginated history)
- `backend/app/db/repositories/pattern_repository.py` — Query layer for dump_patterns (active patterns with filters, patterns needing validation, state/score/tier updates)
- `backend/app/tasks/validation_tasks.py` — Celery task stubs: validate_single_pattern, validate_tier_patterns (dispatched by tier for tiered scheduling)
- `backend/tests/test_services/test_scoring_service.py` — 45 tests
- `backend/tests/test_services/test_validation_service.py` — 50 tests

**Key design decisions:**
1. **Scoring is pure calculation** — `scoring_service.py` has zero database dependencies, making it trivially testable
2. **Recency-weighted validation rate** — uses 0.9^i exponential decay so recent runs matter more than old ones
3. **14-day recency half-life** — patterns not validated in 14 days lose half their recency score
4. **YQ < $10 = success** — not strict $0, allows for rounding and minor surcharges
5. **API endpoints deferred** — POST /api/v1/validations/trigger moved to Phase 09 (REST API layer)
6. **Pattern service separates lifecycle logic** — evaluate_lifecycle is distinct from scoring so each can be tested independently
7. **Repository pattern** — introduced `db/repositories/` for clean data access separation from business logic
8. **ITA client injected** — validation_service accepts ita_client parameter for easy mocking/testing, real client wired in Phase 08

**Lifecycle transition thresholds:**
- active → degrading: success rate < 60% over last 5 runs
- degrading → active: 2 consecutive successes
- degrading → deprecated: 3 consecutive failures
- deprecated → archived: manual only

**Test count:** 95 tests (45 scoring + 50 validation/lifecycle) — all passing, all mocked (no DB required)

---

## [2026-03-25] — Phase 08: Background Job System

**What was built:**
- `backend/app/tasks/celery_app.py` — Celery application instance with:
  - JSON serialization, UTC timezone, late ack (crash safety)
  - Prefetch multiplier = 1 (ITA tasks are slow/memory-heavy)
  - Queue-based task routing: validation, yq, ingestion, alerts queues
  - Worker memory cap 512MB, recycle after 100 tasks
  - Auto-discovers tasks in `app.tasks` package
- `backend/app/tasks/schedules.py` — Celery Beat schedule with 6 scheduled tasks:
  - Tier 1 validation: daily at midnight UTC
  - Tier 2 validation: Mon + Thu at 6am UTC
  - Tier 3 validation: 1st of month at 6am UTC
  - YQ update: Sunday 5am UTC
  - Forum scan: every 6 hours
  - Post processing: every 6 hours (offset 30m from scan)
- `backend/app/services/alert_service.py` — Alert system with:
  - 7 alert types across 3 severities (HIGH, MEDIUM, INFO)
  - Webhook delivery via httpx with timeout handling
  - Severity-based filtering (ALERT_MIN_SEVERITY env var)
  - Comma-separated webhook URLs (ALERT_WEBHOOK_URLS env var)
  - Full pipeline: create_alert → should_send_alert → deliver_webhook
- `backend/app/tasks/alert_tasks.py` — Celery alert tasks:
  - `send_alert_task` — generic alert delivery
  - `send_pattern_deprecated_alert` — convenience for deprecated patterns
  - `send_high_value_alert` — convenience for high-value discoveries
  - `send_bot_detection_alert` — convenience for bot detection events
- Wired `@celery_app.task` decorators onto existing task stubs:
  - `validation_tasks.py` — validate_single_pattern, validate_tier_patterns
  - `yq_tasks.py` — update_all_carrier_yq, update_single_carrier_yq
  - `ingestion_tasks.py` — scan_all_forums, process_pending_posts
- `docker-compose.yml` — Uncommented and configured celery-worker and celery-beat services
- `backend/tests/test_tasks/test_celery_config.py` — 58 tests

**Key design decisions:**
1. **Queue separation** — 4 queues (validation, yq, ingestion, alerts) allow independent scaling and priority
2. **Worker listens to all queues** — single worker config with `-Q default,validation,yq,ingestion,alerts`, can be split later for scaling
3. **No django_celery_beat** — replaced DatabaseScheduler with plain celery beat (simpler, no Django dependency)
4. **Alert severity filtering** — suppresses low-priority alerts without code changes (env var toggle)
5. **Post processing offset** — 30 minutes after forum scan to ensure scraped posts are committed to DB before LLM processing
6. **httpx for webhooks** — already a dependency (used by flyertalk scraper), async-native, timeout handling built-in
7. **Convenience alert tasks** — `send_pattern_deprecated_alert()` etc. wrap the generic `send_alert_task()` with proper message formatting

**Test count:** 58 tests covering Celery app config (7), beat schedule (8), alert severity (2), alert type mapping (8), alert creation (4), payload serialization (2), severity filtering (7), webhook URLs (4), webhook delivery (4), full send pipeline (3), alert task stubs (4), task decorator verification (4), and threshold constants (1)

---

## [2026-03-25] — Phase 09: REST API Layer

**What was built:**
- `backend/app/main.py` — FastAPI entrypoint with lifespan hooks (DB pool init/shutdown), CORS middleware (dev-only), custom exception handlers for all FareEngineError subtypes, and 6 routers registered
- `backend/app/dependencies.py` — DI for DB sessions (request-scoped via get_session) and API key auth (X-API-Key header, constant-time comparison, 403 on failure)
- `backend/app/exceptions.py` — Custom exception hierarchy: FareEngineError base, NotFoundError, ValidationError, DuplicateError, AuthenticationError, LifecycleError
- `backend/app/api/health.py` — GET /health (no auth)
- `backend/app/api/patterns.py` — GET /api/v1/patterns (leaderboard with filters: origin, destination, dump_type, carrier, min_confidence, min_savings_usd, pagination), GET /api/v1/patterns/{id} (full detail), GET /api/v1/patterns/{id}/manual-input (ManualInputBundle only)
- `backend/app/api/carriers.py` — GET /api/v1/carriers (sorted by typical_yq_usd DESC, filterable by charges_yq), GET /api/v1/carriers/{iata_code}
- `backend/app/api/validations.py` — POST /api/v1/validations/trigger/{pattern_id} (enqueues Celery task, rejects archived/deprecated), GET /api/v1/validations/{pattern_id}/history (paginated)
- `backend/app/api/ingestion.py` — POST /api/v1/ingestion/submit (enqueues forum scan task)
- `backend/app/api/manual_inputs.py` — GET /api/v1/manual-inputs/{pattern_id} (convenience alias)
- `backend/app/db/repositories/carrier_repository.py` — get_all_carriers (with charges_yq filter), get_carrier_by_iata, count_carriers
- `backend/tests/test_api/test_api_endpoints.py` — 49 tests, all passing

**Key design decisions:**
1. **Thin routes, fat services** — all routes delegate to repositories/services, no business logic in routes
2. **403 not 401** — auth failures return 403 Forbidden to avoid leaking auth scheme info
3. **Post-filters for confidence/savings** — applied in route handler after DB query (could be pushed to repo query for optimization later)
4. **Lazy Celery imports** — validation and ingestion tasks imported inside route functions to avoid circular import issues and allow easy mocking
5. **TestClient with mocked dependencies** — all 49 tests run without a database using FastAPI dependency overrides and patched repository functions
6. **Docker Compose backend service deferred** — docker-compose.yml update deferred since app runs fine with uvicorn directly

**Endpoints implemented:**
- `GET /health` — no auth
- `GET /api/v1/patterns` — leaderboard (filterable, paginated)
- `GET /api/v1/patterns/{id}` — full detail + manual_input_bundle
- `GET /api/v1/patterns/{id}/manual-input` — ManualInputBundle only
- `POST /api/v1/validations/trigger/{pattern_id}` — enqueue validation
- `GET /api/v1/validations/{pattern_id}/history` — run history
- `GET /api/v1/carriers` — YQ tracker
- `GET /api/v1/carriers/{iata_code}` — carrier detail
- `POST /api/v1/ingestion/submit` — submit URL for ingestion
- `GET /api/v1/manual-inputs/{pattern_id}` — export bundle

**Test count:** 49 tests — health (2), auth (6), patterns list (7), pattern detail (2), manual input (3), carriers list (3), carrier detail (2), validation trigger (4), validation history (3), ingestion submit (3), manual inputs endpoint (3), exception handlers (1), OpenAPI docs (2), dependencies (2), exceptions module (6)
