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
