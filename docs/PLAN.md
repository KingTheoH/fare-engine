# Fare Construction Engine — Master Plan

## What We're Building

A fare arbitrage intelligence engine for travel agents that:
1. Scrapes community forum data (FlyerTalk) to discover fuel dump patterns
2. Validates those patterns against ITA Matrix via browser automation
3. Tracks airline fuel surcharges (YQ) to know where savings opportunities are highest
4. Surfaces working patterns to agents via a dashboard
5. For every automated query, produces a **manual input bundle** so agents can replicate or fallback to manual

## Constraints (Set in Stone)

- No Amadeus API (removed public access)
- No QPX/external fare APIs
- All fare data: ITA Matrix browser automation only
- All surcharge data: airline website scraping
- Community data: FlyerTalk scraping + LLM extraction

## Phase Overview

| # | Phase | What Gets Built | Depends On |
|---|-------|-----------------|-----------|
| 01 | Foundation & DB Schema | Docker, PostgreSQL, Alembic, all ORM models | — |
| 02 | Core Domain Models | Pydantic schemas, enums, shared types | 01 |
| 03 | ITA Query Builder | Routing code DSL, manual input generator | 02 |
| 04 | ITA Automation Engine | Playwright scraper, fare parser, proxy management | 03 |
| 05 | YQ Data Collection | Airline scrapers, YQ schedule storage | 01, 02 |
| 06 | Community Ingestion | FlyerTalk scraper, LLM extraction, pattern normalizer | 02, 03 |
| 07 | Validation Engine | Validation loop, scoring, lifecycle management | 04, 05, 06 |
| 08 | Background Jobs | Celery setup, scheduled sweeps, alert system | 07 |
| 09 | REST API | FastAPI app, all endpoints, auth | 07, 08 |
| 10 | Agent Dashboard | Next.js UI, manual input display | 09 |

## Phase Sizing Guide

Each phase is intentionally scoped to be implementable in a single focused session. If a phase feels too large during implementation, split it — add a "Phase Xa" and "Phase Xb" and update this document.

## Implementation Instructions

When told "implement phase N":
1. Read `docs/phases/phase-0N-*.md` for full spec
2. Read all relevant `CLAUDE.md` files for the modules being touched
3. Read `docs/CONTEXT.md` for any recent changes to requirements
4. Implement all deliverables listed in the phase doc
5. Run the completion check at the bottom of the phase doc
6. Update `docs/CONTEXT.md` with what changed and why

## Key Design Decisions

### Why ITA Matrix (and not an API)?
All fare data APIs (QPX, Amadeus) are either dead or restricted. ITA Matrix is the most powerful fare search tool available to the public. The browser automation approach is the only feasible path.

### Why community-sourced patterns?
Fuel dump routes are discovered empirically by the travel hacking community. There is no authoritative database. FlyerTalk is the best aggregation of this knowledge.

### Why tiered freshness?
Not all patterns need daily validation. A $600 savings dump is worth checking every 24h. A $30 savings dump can wait 30 days. This keeps ITA Matrix automation load proportional to business value.

### Why separate YQ and YR?
YQ (carrier-imposed) is the target of fuel dumps. YR (government-imposed) cannot be eliminated by routing tricks. Conflating them leads to incorrect "dump success" assessment.

### Why lifecycle states?
Patterns don't simply "work or not." They degrade gradually — success rates drop before they stop working entirely. The `degrading` state gives agents advance warning and triggers more frequent validation.

### Why immutable ValidationRun.manual_input_snapshot?
Agents need to replay exactly what worked on a specific date. If the pattern's routing code changes after a successful validation, old validation records must preserve the original instructions. This is critical for reproducing successful bookings.
