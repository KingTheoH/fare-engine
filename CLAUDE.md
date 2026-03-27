# CLAUDE.md — Fare Construction Engine (Root)

## Project Summary

A **fare arbitrage intelligence engine** for travel agents and ticketing professionals that:
- Automates ITA Matrix queries to discover and validate fuel dump fare constructions
- Maintains a community-sourced + internally-validated database of working dump patterns
- Tracks which airlines charge high YQ (fuel surcharges) so agents know where to focus
- Updates at least weekly (tiered: high-value routes daily, medium weekly, low monthly)
- For every automated ITA Matrix output, generates a **1:1 manual input string** so agents can replicate or fallback manually

## Key Constraints (READ BEFORE CODING)

- **No Amadeus API** — Amadeus removed public API access. Do not attempt to integrate it.
- **No external fare data APIs** — QPX/QPX Express is dead. Duffel is not in scope. All fare data comes from ITA Matrix automation.
- **ITA Matrix is scraped via Playwright** — we accept the ToS risk. Build with human-like interaction patterns (realistic delays, mouse movement). Use rotating residential proxies.
- **All data is community-sourced or self-validated** — no authoritative feed exists. Confidence scoring is essential.
- **No ATPCO direct access** — fuel surcharge data is scraped from airline booking pages, not from GDS tariff tables.

## Architecture Overview

```
Community Sources (FlyerTalk etc.)
        │
        ▼
  Ingestion Pipeline (LLM-assisted NLP extraction)
        │
        ▼
  Pattern Database (PostgreSQL)
        │                   ▲
        ▼                   │
  ITA Matrix Automation  Validation Engine
  (Playwright + proxies)    │
        │                   │
        ▼                   │
  Fare Result Parser ───────┘
        │
        ▼
  Background Job Scheduler (Celery + Redis)
        │
        ▼
  FastAPI REST Layer
        │
        ▼
  Agent Dashboard (Next.js)
```

## Logic Decisions (from design discussions)

### Dump Type Taxonomy
Not all fuel dumps work the same. The system MUST distinguish these types:
- `TP_DUMP` — Ticketing Point manipulation (most common). A specific routing point causes YQ to not be applied.
- `CARRIER_SWITCH` — Using a no-YQ carrier on a specific sector breaks the surcharge chain.
- `FARE_BASIS` — Certain fare basis codes structurally exclude YQ.
- `ALLIANCE_RULE` — Interline agreements between specific carrier pairs waive YQ under certain conditions.

This taxonomy affects how patterns are stored, matched, and validated.

### YQ vs YR — Keep Separate
- **YQ** = carrier-imposed fuel surcharge (target of fuel dumps)
- **YR** = government-imposed surcharge (cannot be dumped, do not confuse)
The system tracks both. Dump success = YQ reduced to 0 or near-0. YR is informational only.

### Tiered Freshness (not just weekly)
- **Tier 1 (High-value)**: YQ savings > $200 per trip → validate every 24h
- **Tier 2 (Medium-value)**: YQ savings $50–200 → validate every 7 days
- **Tier 3 (Low-value)**: YQ savings < $50 → validate every 30 days
- Tier assignment is dynamic and recalculates on every validation run.

### Pattern Lifecycle States
```
discovered → active → degrading → deprecated → archived
```
- `degrading`: pattern succeeds < 60% of recent validation attempts
- `deprecated`: pattern fails > 3 consecutive validations
- `archived`: kept for historical analysis, never surfaced to agents

### Manual Input Format
Every automated ITA Matrix query MUST produce a parallel manual input bundle:
1. **ITA routing code string** (paste directly into ITA Matrix routing codes field)
2. **Human-readable route description** (plain English carrier/city sequence)
3. **Expected YQ savings** (based on last successful validation)
4. **Validation timestamp** and confidence score
5. **Backup routing** if primary fails (stored as secondary pattern variant)

### Community Source Weighting
FlyerTalk posts are not equal. Weight by:
- Poster account age (older = more trusted)
- Post count in relevant forums (Business Travel, Mileage Run Deals)
- Recency of confirmation posts in the same thread
- Downvotes / moderator flags reduce confidence

## Phase Index

| Phase | Name | Status |
|-------|------|--------|
| 01 | Project Foundation & Database Schema | ✅ Complete |
| 02 | Core Domain Models (Python) | ✅ Complete |
| 03 | ITA Matrix Query Builder | ✅ Complete |
| 04 | ITA Matrix Automation Engine | ✅ Complete |
| 05 | YQ Data Collection (Airline Scrapers) | ✅ Complete |
| 06 | Community Data Ingestion | ✅ Complete |
| 07 | Validation & Scoring Engine | ✅ Complete |
| 08 | Background Job System | ✅ Complete |
| 09 | REST API Layer | ✅ Complete |
| 10 | Agent Dashboard (UI) | ✅ Complete |

**Phase 01:** ✅ Complete — 6 tables, 5 indexes, 32 carriers seeded, all migrations passing

See `docs/phases/` for detailed specs on each phase.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend language | Python 3.12 |
| API framework | FastAPI |
| Database | PostgreSQL 16 |
| Cache / Queue broker | Redis |
| Task queue | Celery |
| Browser automation | Playwright |
| LLM (community parsing) | Claude API (claude-3-5-haiku for cost, claude-sonnet for complex extractions) |
| Frontend | Next.js 14 + Tailwind CSS |
| Containerization | Docker Compose |
| Migrations | Alembic |
| Testing | pytest + playwright pytest plugin |

## Repository Structure

```
fare-engine/
├── CLAUDE.md                    ← you are here (project overview + phase index)
├── docs/
│   ├── PLAN.md                  ← master plan with live phase status (read this first)
│   ├── CONTEXT.md               ← decision log, updated after every phase
│   └── phases/                  ← per-phase detailed specs (phase-01 through phase-10)
├── backend/
│   ├── CLAUDE.md                ← backend principles, auth, error handling, Celery
│   ├── seeds/CLAUDE.md          ← seed data format + carrier list requirements
│   ├── scripts/CLAUDE.md        ← utility script conventions
│   └── app/
│       ├── CLAUDE.md            ← entrypoint, config schema, naming conventions
│       ├── models/CLAUDE.md     ← ORM table specs (all columns, constraints)
│       ├── schemas/CLAUDE.md    ← Pydantic schema conventions, ManualInputBundle spec
│       ├── api/CLAUDE.md        ← router organization, endpoint specs, auth
│       ├── services/CLAUDE.md   ← service layer, confidence formula, lifecycle rules
│       ├── db/CLAUDE.md         ← session pattern, migrations, repository pattern
│       └── tasks/CLAUDE.md      ← Celery task conventions, scheduling, concurrency
├── automation/
│   └── CLAUDE.md                ← ITA Matrix interaction, human-like behavior, rate limiting
├── ingestion/
│   └── CLAUDE.md                ← FlyerTalk scraper, LLM extraction, credibility scoring
├── backend/tests/
│   └── CLAUDE.md                ← test organization, fixtures, mocking strategy
└── frontend/
    └── CLAUDE.md                ← dashboard UI, ManualInputBundle component spec
```

## What NOT to Do

- Do not hardcode carrier lists — all carriers are database records
- Do not assume a dump pattern that worked once will always work — every query needs fresh validation
- Do not store raw HTML from scraped pages long-term — extract and discard
- Do not make ITA Matrix requests in tight loops — always use rate limiting + jitter
- Do not conflate YQ and YR in any calculation or display
- Do not surface `deprecated` or `archived` patterns to agents
