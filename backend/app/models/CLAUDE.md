# CLAUDE.md — Domain Models

## Core Tables (defined in Phase 1 & 2)

### `carriers`
Tracks every airline relevant to the system.
- `iata_code` (PK, e.g. "LH", "QR", "AA")
- `name`
- `alliance` (STAR, ONEWORLD, SKYTEAM, NONE)
- `charges_yq` (bool) — whether this carrier typically levies YQ
- `typical_yq_usd` — approximate YQ per intercontinental roundtrip (informational)
- `last_yq_updated` — when YQ data was last scraped
- `yq_scrape_url` — URL used to scrape current YQ schedule (nullable — some have no clean page)

### `routes`
A canonical origin-destination pair.
- `id` (UUID PK)
- `origin_iata` (3-letter airport code)
- `destination_iata`
- `is_intercontinental` (bool)

### `dump_patterns`
The core entity. One row = one known fuel dump construction.
- `id` (UUID PK)
- `dump_type` (enum: TP_DUMP, CARRIER_SWITCH, FARE_BASIS, ALLIANCE_RULE)
- `lifecycle_state` (enum: discovered, active, degrading, deprecated, archived)
- `origin_iata`
- `destination_iata`
- `ticketing_carrier_iata` — the carrier the ticket is issued on
- `operating_carriers` (array of IATA codes) — sequence of actual operating carriers
- `routing_points` (array of IATA codes) — via/TP points in order
- `fare_basis_hint` (nullable) — known fare basis code pattern that triggers the dump
- `ita_routing_code` — the exact routing code string for ITA Matrix automation
- `manual_input_bundle` (JSONB) — the 1:1 manual input package (see root CLAUDE.md)
- `expected_yq_savings_usd` — last known savings per roundtrip
- `confidence_score` (0.0–1.0)
- `freshness_tier` (1, 2, or 3) — controls validation frequency
- `source` (enum: FLYERTALK, MANUAL, INTERNAL_DISCOVERY)
- `source_url` (nullable) — link to original community post
- `source_post_weight` (0.0–1.0) — community credibility score of source post
- `backup_pattern_id` (FK → dump_patterns, nullable) — alternate routing if primary fails
- `created_at`, `updated_at`

### `validation_runs`
Every time we test a dump pattern against ITA Matrix.
- `id` (UUID PK)
- `pattern_id` (FK → dump_patterns)
- `ran_at` (timestamp)
- `success` (bool)
- `yq_charged_usd` — actual YQ returned by ITA Matrix on this run
- `yq_expected_usd` — what we expected
- `base_fare_usd` — base fare returned (informational)
- `raw_ita_response` (JSONB) — parsed fare breakdown from ITA
- `manual_input_snapshot` (JSONB) — manual input bundle as-of this run (so agents can replay)
- `error_message` (nullable) — if automation failed (timeout, parse error, etc.)
- `proxy_used` (nullable) — for debugging rate limit issues

### `yq_schedules`
Point-in-time snapshots of what a carrier charges for YQ on specific routes.
- `id` (UUID PK)
- `carrier_iata`
- `route_id` (FK → routes)
- `yq_amount_usd`
- `effective_date`
- `scraped_at`
- `source_url`

### `community_posts`
Raw community data before pattern extraction.
- `id` (UUID PK)
- `source` (FLYERTALK, etc.)
- `post_url`
- `post_author`
- `author_post_count` (nullable)
- `author_account_age_days` (nullable)
- `raw_text`
- `extracted_patterns` (JSONB array) — output of LLM extraction
- `processing_state` (enum: raw, processed, failed)
- `scraped_at`

## Important Constraints

- `dump_patterns.ita_routing_code` must be unique (no duplicate constructions)
- `validation_runs` should never be deleted — they are the audit trail
- When a pattern transitions to `deprecated`, keep all its validation_runs
- `manual_input_bundle` is always regenerated on each successful validation run (it must stay current)
