# Fare Construction Engine — Master Plan
> **Last updated:** 2026-03-25
> **Overall progress:** Phase 10 complete — All phases done

---

## What We're Building

A **fare arbitrage intelligence engine** for travel agents that:
1. Scrapes community forums (FlyerTalk) to discover fuel dump patterns via LLM extraction
2. Validates those patterns against ITA Matrix via Playwright browser automation
3. Tracks airline fuel surcharges (YQ) so agents know where savings opportunities are highest
4. Surfaces working patterns via an agent dashboard with confidence scores + lifecycle states
5. For every automated query, produces a **manual input bundle** so agents can replicate or fall back manually

**Target users:** Travel agents and ticketing professionals (not consumers)
**Data source:** Community-sourced (FlyerTalk) + self-validated via ITA Matrix automation

---

## Architecture

```
FlyerTalk / Community Forums
          │
          ▼
  Ingestion Pipeline          ← Phase 06
  (Playwright scraper + Claude API LLM extraction)
          │
          ▼
  Pattern Database            ← Phase 01–02
  (PostgreSQL)
          │                   ▲
          ▼                   │
  ITA Matrix Automation   Validation Engine   ← Phase 04, 07
  (Playwright + proxies)      │
          │                   │
          ▼                   │
  Fare Result Parser ─────────┘
          │
          ▼
  Background Scheduler        ← Phase 08
  (Celery + Redis)
          │
          ▼
  FastAPI REST API            ← Phase 09
          │
          ▼
  Agent Dashboard             ← Phase 10
  (Next.js 14 + Tailwind)
```

---

## Phase Status

| # | Phase | Status | Depends On |
|---|-------|--------|-----------|
| 01 | Foundation & DB Schema | ✅ Complete | — |
| 02 | Core Domain Models | ✅ Complete | 01 |
| 03 | ITA Query Builder | ✅ Complete | 02 |
| 04 | ITA Automation Engine | ✅ Complete | 03 |
| 05 | YQ Data Collection | ✅ Complete | 01, 02, 04 |
| 06 | Community Ingestion | ✅ Complete | 02, 03 |
| 07 | Validation Engine | ⏳ Planned | 04, 05, 06 |
| 08 | Background Jobs | ⏳ Planned | 07 |
| 09 | REST API | ⏳ Planned | 07, 08 |
| 10 | Agent Dashboard | ⏳ Planned | 09 |

**Status key:** ✅ Complete · 🔄 In Progress · ⏳ Planned

---

## Phase 01 — Foundation & DB Schema

**Goal:** Stand up Docker + PostgreSQL. At the end, `docker compose up` connects to a database with all tables created and seeded with carrier data.

**Status:** ✅ Complete

### Deliverables

| Item | Status |
|------|--------|
| `docker-compose.yml` (postgres + redis, others commented) | ✅ |
| `.env.example` with all env var names | ✅ |
| `backend/pyproject.toml` with all dependencies | ✅ |
| `backend/app/db/base.py` — SQLAlchemy declarative base + TimestampMixin | ✅ |
| `backend/app/db/session.py` — async session factory | ✅ |
| `backend/app/models/enums.py` — DumpType, LifecycleState, PatternSource, FreshnessTier, ProcessingState, Alliance | ✅ |
| Alembic initialized (`alembic init alembic/`) | ✅ |
| `app/models/carrier.py` | ✅ |
| `app/models/route.py` | ✅ |
| `app/models/dump_pattern.py` | ✅ |
| `app/models/validation_run.py` | ✅ |
| `app/models/yq_schedule.py` | ✅ |
| `app/models/community_post.py` | ✅ |
| Initial Alembic migration (all tables + indexes) | ✅ |
| `make db-migrate` and `make db-upgrade` in Makefile | ✅ |
| `seeds/carriers.json` (30+ carriers, high-YQ + low-YQ) | ✅ |
| `backend/scripts/seed_carriers.py` | ✅ |

### Key Indexes to Create in Migration
```sql
CREATE INDEX idx_patterns_lifecycle_tier ON dump_patterns(lifecycle_state, freshness_tier);
CREATE INDEX idx_patterns_route ON dump_patterns(origin_iata, destination_iata);
CREATE INDEX idx_patterns_savings ON dump_patterns(expected_yq_savings_usd DESC);
CREATE INDEX idx_validations_pattern_time ON validation_runs(pattern_id, ran_at DESC);
CREATE INDEX idx_carriers_charges_yq ON carriers(charges_yq);
```

### Completion Check
```bash
docker compose up -d postgres
cd backend && alembic upgrade head
python scripts/seed_carriers.py
psql $DATABASE_URL -c "SELECT COUNT(*) FROM carriers;"
# Expected: 30+
```

📄 Full spec: `docs/phases/phase-01-foundation.md`

---

## Phase 02 — Core Domain Models

**Goal:** Define all Pydantic schemas and shared Python types. Pure Python — no DB queries, no API endpoints yet.

**Status:** ✅ Complete

### Deliverables

| Item | Status |
|------|--------|
| `app/schemas/carrier.py` — CarrierCreate, CarrierUpdate, CarrierResponse | ✅ |
| `app/schemas/route.py` — RouteCreate, RouteResponse | ✅ |
| `app/schemas/dump_pattern.py` — DumpPatternCreate, DumpPatternUpdate, DumpPatternResponse, DumpPatternSummary | ✅ |
| `app/schemas/manual_input.py` — **ManualInputBundle** (critical schema) | ✅ |
| `app/schemas/validation_run.py` — ValidationRunCreate, ValidationRunResponse | ✅ |
| `app/schemas/yq_schedule.py` — YQScheduleCreate, YQScheduleResponse | ✅ |
| `app/schemas/community_post.py` — CommunityPostCreate, CommunityPostResponse, ExtractedPattern | ✅ |
| `app/schemas/common.py` — PaginatedResponse, ErrorResponse | ✅ |
| `tests/test_schemas/` — unit tests for all schemas | ✅ |

### Critical: ManualInputBundle Schema
```python
class ManualInputBundle(BaseModel):
    routing_code_string: str          # paste into ITA Matrix routing codes field
    human_description: str            # plain English: "JFK → Frankfurt (LH) → Bangkok"
    ita_matrix_steps: list[str]       # numbered, self-contained, agent-ready steps
    expected_yq_savings_usd: float
    expected_yq_carrier: str
    validation_timestamp: datetime
    confidence_score: float           # 0.0–1.0
    backup_routing_code: str | None
    notes: str | None
```

### Completion Check
```bash
cd backend && pytest tests/test_schemas/ -v
```

📄 Full spec: `docs/phases/phase-02-models.md`

---

## Phase 03 — ITA Matrix Query Builder

**Goal:** Pure Python module that translates a `DumpPattern` into an ITA Matrix routing code string + generates a complete ManualInputBundle. Zero external dependencies — fully unit-testable offline.

**Status:** ✅ Complete

### Deliverables

| Item | Status |
|------|--------|
| `automation/query_builder.py` — routing code DSL builder | ✅ |
| `automation/manual_input.py` — ManualInputBundle generator | ✅ |
| `docs/ita_routing_codes.md` — ITA routing code syntax reference | ✅ |
| `tests/test_automation/test_query_builder.py` | ✅ |
| `tests/fixtures/dump_patterns.json` (10+ patterns, all 4 dump types) | ✅ |

### Routing Code Logic by Dump Type
```
TP_DUMP:        FORCE LH:JFK-FRA / FORCE LH:FRA-BKK / FORCE AA:BKK-JFK
CARRIER_SWITCH: FORCE QR:JFK-DOH-BKK / FORCE AA:BKK-JFK
FARE_BASIS:     FORCE LH:JFK-FRA-BKK BC=YLOWUS / FORCE AA:BKK-JFK
ALLIANCE_RULE:  FORCE BA/AA:JFK-LHR-SYD / FORCE BA/AA:SYD-LHR-JFK
```

### Completion Check
```bash
cd backend && pytest tests/test_automation/test_query_builder.py -v
```

📄 Full spec: `docs/phases/phase-03-query-builder.md`

---

## Phase 04 — ITA Matrix Automation Engine

**Goal:** Playwright browser automation that executes ITA Matrix queries and parses fare breakdowns. Input: routing code string. Output: structured fare result with YQ amount.

**Status:** ✅ Complete

### Deliverables

| Item | Status |
|------|--------|
| `automation/browser.py` — browser/context lifecycle (recycle after 15 reqs) | ✅ |
| `automation/proxy_manager.py` — rotating proxy pool (Redis-backed, retire on bot detect) | ✅ |
| `automation/rate_limiter.py` — request throttling with jitter | ✅ |
| `automation/ita_client.py` — main ITA Matrix interaction | ✅ |
| `automation/result_parser.py` — fare breakdown parser | ✅ |
| `automation/data/user_agents.json` — pool of 10 real Chrome UAs | ✅ |
| `tests/test_automation/test_ita_client.py` (integration, marked slow) | ✅ |

### Key Behaviors
- Human-like: `page.type()` with keystroke delays, random pauses 1.5–3.5s between actions
- Session recycle: restart browser context after 15 requests
- Proxy: retire for 24h on bot detection, rotate before 200 daily requests
- Never raise from `run_query()` — always return `ITAResult(success=False, error=...)`

### Completion Check
```bash
cd backend && pytest tests/test_automation/test_ita_client.py -v -m integration
```

📄 Full spec: `docs/phases/phase-04-ita-automation.md`

---

## Phase 05 — YQ Data Collection

**Goal:** Scrapers that fetch current YQ (fuel surcharge) amounts via ITA Matrix automation. Populates `yq_schedules` table and keeps `carriers.typical_yq_usd` current.

**Status:** ✅ Complete

**Design decision:** Instead of per-airline booking page scrapers (fragile, break frequently), all 15 carriers use a unified ITA Matrix-based approach (Approach B). The Phase 04 ITA parsing engine is reused, making the scraping layer thin and reliable.

### Deliverables

| Item | Status |
|------|--------|
| `ingestion/scrapers/base.py` — abstract BaseYQScraper + YQScrapeResult | ✅ |
| `ingestion/scrapers/yq/ita_based.py` — unified ITA-based YQ scraper for all carriers | ✅ |
| `ingestion/scrapers/yq/carriers.py` — 15 carrier configs (10 high-YQ + 5 low-YQ reference) | ✅ |
| `ingestion/scrapers/yq_dispatcher.py` — sequential dispatcher with DispatchResult | ✅ |
| `backend/app/services/yq_service.py` — store/query YQ data, update carrier typical_yq | ✅ |
| `backend/app/tasks/yq_tasks.py` — Celery task stubs for weekly YQ updates | ✅ |
| `tests/test_ingestion/test_yq_scrapers.py` — 44 tests (mocked ITA client) | ✅ |

### Priority Carrier Order
LH → BA → LX → OS → SN → IB → CX → KE → OZ → AF

### Completion Check
```bash
cd backend && pytest tests/test_ingestion/test_yq_scrapers.py -v
```

📄 Full spec: `docs/phases/phase-05-yq-collection.md`

---

## Phase 06 — Community Data Ingestion

**Goal:** Pipeline that scrapes FlyerTalk, uses Claude API (haiku filter → sonnet extraction) to pull structured dump patterns from forum posts, scores credibility, queues for ITA validation.

**Status:** ✅ Complete

### Deliverables

| Item | Status |
|------|--------|
| `ingestion/scrapers/flyertalk.py` — FlyerTalk thread/post scraper with keyword matching | ✅ |
| `ingestion/extractors/llm_extractor.py` — two-pass Claude API extraction (haiku→sonnet) | ✅ |
| `ingestion/extractors/pattern_normalizer.py` — LLM output → DB-ready format | ✅ |
| `ingestion/weighting/post_credibility.py` — author reputation scoring (0.0–1.0) | ✅ |
| `backend/app/services/ingestion_service.py` — orchestration service (ingest_post, process_raw_posts) | ✅ |
| `backend/app/tasks/ingestion_tasks.py` — Celery task stubs (scan_all_forums, process_pending_posts) | ✅ |
| `tests/fixtures/flyertalk_posts.json` (10 example posts, all 4 dump types + negatives) | ✅ |
| `tests/test_ingestion/test_community_ingestion.py` — 76 tests (mocked LLM + HTTP) | ✅ |

### LLM Strategy (cost control)
- Pass 1 — `claude-haiku-4-5`: "Does this post describe a fuel dump? yes/no" (~$0.001/post)
- Pass 2 — `claude-sonnet-4-6`: Full structured JSON extraction (only "yes" posts, ~$0.01/post)

### Completion Check
```bash
cd backend && pytest tests/test_ingestion/test_llm_extractor.py -v
curl -X POST http://localhost:8000/api/v1/ingestion/submit \
  -H "X-API-Key: dev_key" -d '{"url": "https://www.flyertalk.com/forum/..."}'
```

📄 Full spec: `docs/phases/phase-06-community-ingestion.md`

---

## Phase 07 — Validation & Scoring Engine

**Goal:** Core validation loop — takes a `dump_pattern`, runs it through ITA Matrix, records the result, updates confidence scores, manages lifecycle state transitions. The heart of the system.

**Status:** ✅ Complete

### Deliverables

| Item | Status |
|------|--------|
| `backend/app/services/validation_service.py` | ✅ |
| `backend/app/services/scoring_service.py` | ✅ |
| `backend/app/services/pattern_service.py` | ✅ |
| `backend/app/db/repositories/validation_repository.py` | ✅ |
| `backend/app/db/repositories/pattern_repository.py` | ✅ |
| `backend/app/tasks/validation_tasks.py` | ✅ |
| `backend/app/api/validations.py` — trigger + history endpoints | ⏳ Deferred to Phase 09 |
| `tests/test_services/test_validation_service.py` | ✅ |
| `tests/test_services/test_scoring_service.py` | ✅ |

### Lifecycle Transition Logic
```
discovered → active       : first successful ITA validation
active → degrading        : success rate < 60% over last 5 runs
degrading → active        : 2 consecutive successes (recovery)
degrading → deprecated    : 3 consecutive failures
deprecated → archived     : manual agent action only
```

### Confidence Score Formula
```
confidence = (
    0.50 * recent_validation_success_rate   # last 10 runs, recency-weighted
  + 0.25 * source_post_weight               # community credibility of source
  + 0.15 * multi_source_bonus               # bonus if confirmed in >1 independent post
  + 0.10 * recency_factor                   # decays if not validated recently
)
```

### Completion Check
```bash
cd backend && pytest tests/test_services/ -v
curl -X POST http://localhost:8000/api/v1/validations/trigger/{pattern_id} -H "X-API-Key: dev_key"
```

📄 Full spec: `docs/phases/phase-07-validation-engine.md`

---

## Phase 08 — Background Job System

**Goal:** Celery + Redis wired up with scheduled tasks and webhook alert system. System runs validation sweeps and YQ updates automatically on schedule.

**Status:** ✅ Complete

### Deliverables

| Item | Status |
|------|--------|
| `backend/app/tasks/celery_app.py` — Celery instance | ✅ |
| `backend/app/tasks/schedules.py` — Celery Beat schedule definitions | ✅ |
| `backend/app/tasks/alert_tasks.py` | ✅ |
| `backend/app/services/alert_service.py` | ✅ |
| Celery worker + beat services added to `docker-compose.yml` | ✅ |
| Celery decorators wired onto existing task stubs (validation, yq, ingestion) | ✅ |
| `tests/test_tasks/test_celery_config.py` | ✅ |

### Scheduled Tasks
| Task | Schedule |
|------|---------|
| Validate Tier 1 patterns (>$200 YQ savings) | Every 24h |
| Validate Tier 2 patterns ($50–200 savings) | Mon + Thu at 6am UTC |
| Validate Tier 3 patterns (<$50 savings) | 1st of month at 6am UTC |
| Update all carrier YQ data | Every Sunday 5am UTC |
| Scan community forums for new posts | Every 6h |

### Alert Types
| Alert | Severity |
|-------|---------|
| `PATTERN_DEPRECATED` | HIGH |
| `HIGH_VALUE_DUMP_FOUND` (>$400 savings) | HIGH |
| `BOT_DETECTION` | HIGH |
| `PATTERN_DEGRADING` | MEDIUM |
| `YQ_SPIKE` (carrier YQ increases >20%) | MEDIUM |
| `PATTERN_RECOVERED` | INFO |
| `NEW_PATTERN_ACTIVE` | INFO |

### Completion Check
```bash
docker compose up -d
docker compose logs celery-worker
```

📄 Full spec: `docs/phases/phase-08-background-jobs.md`

---

## Phase 09 — REST API Layer

**Goal:** Complete FastAPI app with all endpoints, API key auth, auto-generated OpenAPI docs at `/docs`. Agent dashboard can retrieve patterns, trigger validations, get manual input bundles.

**Status:** ✅ Complete

### Deliverables

| Item | Status |
|------|--------|
| `backend/app/main.py` — FastAPI entrypoint | ✅ |
| `backend/app/dependencies.py` — auth + DB session DI | ✅ |
| `backend/app/exceptions.py` — custom exception hierarchy | ✅ |
| `backend/app/api/patterns.py` | ✅ |
| `backend/app/api/carriers.py` | ✅ |
| `backend/app/api/validations.py` | ✅ |
| `backend/app/api/ingestion.py` | ✅ |
| `backend/app/api/manual_inputs.py` | ✅ |
| `backend/app/api/health.py` | ✅ |
| `backend/app/db/repositories/carrier_repository.py` | ✅ |
| `tests/test_api/` — integration tests (49 tests) | ✅ |

### Key Endpoints
```
GET  /api/v1/patterns                         — leaderboard (filterable, paginated)
GET  /api/v1/patterns/{id}                    — full pattern detail + manual_input_bundle
GET  /api/v1/patterns/{id}/manual-input       — ManualInputBundle only
POST /api/v1/validations/trigger/{pattern_id} — enqueue validation task
GET  /api/v1/validations/{pattern_id}/history — validation run history
GET  /api/v1/carriers                         — YQ tracker, sorted by typical_yq_usd DESC
POST /api/v1/ingestion/submit                 — submit forum URL for ingestion
GET  /health                                  — health check (no auth required)
```

### Completion Check
```bash
cd backend && uvicorn app.main:app --reload
curl http://localhost:8000/health
open http://localhost:8000/docs
cd backend && pytest tests/test_api/ -v
```

📄 Full spec: `docs/phases/phase-09-api.md`

---

## Phase 10 — Agent Dashboard (UI)

**Goal:** Next.js 14 agent dashboard. Utility-first — agents browse working patterns, get manual input bundles, monitor validation health. `ManualInputBundle` component is the most important UI element.

**Status:** ⏳ Planned

### Deliverables

| Item | Status |
|------|--------|
| `frontend/app/patterns/page.tsx` — pattern leaderboard | ⏳ |
| `frontend/app/patterns/[id]/page.tsx` — pattern detail + manual input | ⏳ |
| `frontend/app/carriers/page.tsx` — YQ tracker | ⏳ |
| `frontend/app/validations/page.tsx` — validation history | ⏳ |
| `frontend/components/ManualInputBundle.tsx` — **critical** | ⏳ |
| `frontend/components/PatternCard.tsx` | ⏳ |
| `frontend/components/ValidationBadge.tsx` | ⏳ |
| `frontend/components/LifecycleBadge.tsx` | ⏳ |
| `frontend/components/ConfidenceBar.tsx` | ⏳ |
| `frontend/lib/api.ts` — typed API client | ⏳ |
| Frontend service added to `docker-compose.yml` | ⏳ |

### ManualInputBundle Component (Most Important)
1. Routing code in monospace block with one-click copy button
2. Human-readable route description
3. Numbered step-by-step checklist (interactive checkboxes agents can tick)
4. Expected YQ savings (large, prominent)
5. Validation timestamp + confidence bar
6. Collapsible "If this fails..." section with backup routing code
7. Notes field
8. Download as PDF / Print options (agents use printed cheat sheets)

### Completion Check
```bash
cd frontend && npm install && npm run dev
open http://localhost:3000/patterns
# Verify: ManualInputBundle loads, routing code copyable, steps checkboxable, print works
```

📄 Full spec: `docs/phases/phase-10-dashboard.md`

---

## Phase Sizing Guide

Each phase is scoped to be implementable in a single focused session. If a phase feels too large, split it into Phase Xa and Phase Xb and update this document.

---

## Implementation Instructions

When told **"implement phase N"**:
1. Read `docs/phases/phase-0N-*.md` for the full spec
2. Read all relevant `CLAUDE.md` files for the modules being touched
3. Read `docs/CONTEXT.md` for any recent requirement changes
4. Implement all deliverables listed in the phase doc
5. Run the completion check at the bottom of the phase doc
6. Update `docs/CONTEXT.md` with what changed and why
7. Update the status table and deliverable checkboxes in this file

---

## Key Design Decisions

### Why ITA Matrix (not an API)?
All fare data APIs (QPX, Amadeus) are dead or restricted. ITA Matrix is the most powerful public fare search tool available. Browser automation is the only feasible path.

### Why community-sourced patterns?
Fuel dump routes are discovered empirically by the travel hacking community. No authoritative database exists. FlyerTalk is the best aggregation of this knowledge.

### Why tiered freshness?
A $600 savings dump is worth checking every 24h. A $30 savings dump can wait 30 days. This keeps ITA Matrix automation load proportional to business value.

### Why separate YQ and YR?
YQ (carrier-imposed) is the target of fuel dumps. YR (government-imposed) cannot be eliminated by routing tricks. Conflating them produces incorrect dump success assessments.

### Why lifecycle states?
Patterns degrade gradually — success rates drop before they stop working entirely. The `degrading` state gives agents advance warning before a dump fully dies.

### Why immutable ValidationRun.manual_input_snapshot?
Agents need to replay exactly what worked on a specific date. If a pattern's routing code changes later, old validation records must preserve the original instructions. Critical for reproducing successful bookings.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend language | Python 3.12 |
| API framework | FastAPI |
| Database | PostgreSQL 16 |
| Cache / Queue broker | Redis 7 |
| Task queue | Celery 5 + Celery Beat |
| Browser automation | Playwright (async) |
| LLM extraction | Claude API (haiku filter + sonnet extraction) |
| Frontend | Next.js 14 + Tailwind CSS + React Query |
| Containerization | Docker Compose |
| Migrations | Alembic |
| Testing | pytest + pytest-asyncio + pytest-playwright |

---

## CLAUDE.md File Map

```
fare-engine/
├── CLAUDE.md                      ← root: project overview, constraints, phase index
├── docs/
│   ├── PLAN.md                    ← YOU ARE HERE — master plan with live status
│   ├── CONTEXT.md                 ← decision log, updated after every phase
│   └── phases/                    ← per-phase detailed specs
│       ├── phase-01-foundation.md
│       ├── phase-02-models.md
│       ├── phase-03-query-builder.md
│       ├── phase-04-ita-automation.md
│       ├── phase-05-yq-collection.md
│       ├── phase-06-community-ingestion.md
│       ├── phase-07-validation-engine.md
│       ├── phase-08-background-jobs.md
│       ├── phase-09-api.md
│       └── phase-10-dashboard.md
├── backend/
│   ├── CLAUDE.md                  ← backend principles, auth, error handling, Celery
│   ├── seeds/CLAUDE.md            ← seed data format, carrier list requirements
│   ├── scripts/CLAUDE.md          ← utility script conventions
│   └── app/
│       ├── CLAUDE.md              ← entrypoint, config schema, naming conventions
│       ├── models/CLAUDE.md       ← ORM table specs (all columns, constraints)
│       ├── schemas/CLAUDE.md      ← Pydantic schema conventions, ManualInputBundle
│       ├── api/CLAUDE.md          ← router organization, endpoint specs, auth
│       ├── services/CLAUDE.md     ← service layer, confidence formula, lifecycle rules
│       ├── db/CLAUDE.md           ← session pattern, migrations, repository pattern
│       └── tasks/CLAUDE.md        ← Celery task conventions, scheduling
├── automation/
│   └── CLAUDE.md                  ← ITA Matrix interaction, human-like behavior, rate limiting
├── ingestion/
│   └── CLAUDE.md                  ← FlyerTalk scraper, LLM extraction, credibility scoring
└── frontend/
    └── CLAUDE.md                  ← dashboard UI, ManualInputBundle component spec
```
