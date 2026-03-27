# CLAUDE.md — Service Layer

## Principles

- Services are plain async Python functions (not classes unless state is needed)
- Services call repositories (db queries) and other services — never call API routes
- Services are the only place business rules live
- Services are unit-testable without spinning up FastAPI

## Key Services

### `pattern_service.py`
- `get_active_patterns(filters)` → list of dump patterns in active/degrading state
- `update_lifecycle_state(pattern_id, new_state)` → transitions pattern through lifecycle
- `recalculate_freshness_tier(pattern_id)` → reassigns tier 1/2/3 based on current savings
- `build_manual_input_bundle(pattern)` → constructs the manual input package from a pattern record
- `merge_community_pattern(extracted_data)` → upserts a pattern discovered from community ingestion

### `validation_service.py`
- `run_validation(pattern_id)` → triggers ITA Matrix automation, records result, updates pattern state
- `evaluate_validation_result(pattern_id, result)` → updates confidence score, checks if lifecycle state needs to change
- `get_consecutive_failure_count(pattern_id)` → used to trigger `deprecated` transition

### `scoring_service.py`
- `calculate_confidence_score(pattern_id)` → weighted combination of:
  - Recent validation success rate (last 10 runs, recency-weighted)
  - Community source weight of original post
  - Age of pattern (older patterns decay slightly)
  - Number of independent community confirmations
- `score_community_post(post)` → returns 0.0–1.0 credibility weight for a FlyerTalk post

### `yq_service.py`
- `get_current_yq(carrier_iata, route_id)` → latest known YQ for a carrier/route combo
- `update_yq_schedule(carrier_iata)` → triggers scraper + stores new yq_schedule record
- `get_highest_yq_carriers(limit=10)` → sorted list of carriers by average YQ (used to prioritize which routes to hunt)

### `ingestion_service.py`
- `ingest_community_post(url)` → scrape + LLM extract + store patterns
- `extract_patterns_from_text(text)` → calls Claude API to extract structured dump patterns from raw forum text
- `normalize_extracted_pattern(raw)` → converts LLM output to a valid `dump_patterns` insert

## Confidence Score Formula

```
confidence = (
    0.50 * recent_validation_success_rate   # last 10 runs, weighted toward recent
  + 0.25 * source_post_weight               # community credibility of original source
  + 0.15 * multi_source_bonus               # bonus if confirmed in >1 independent post
  + 0.10 * recency_factor                   # decays if not validated recently
)
```

All components clamped to [0.0, 1.0]. Final score also clamped.

## Lifecycle Transition Rules (updated 2026-03)

Infrastructure errors (proxy timeout, bot detection, etc.) are now filtered out
in `validation_service.py` and do NOT count toward lifecycle transitions. Only
genuine pattern failures (ITA returned results but YQ wasn't reduced) affect state.

| From | To | Trigger |
|------|----|---------|
| discovered | active | First successful validation |
| active | degrading | Success rate < 40% over last 10 runs (was 60%/5) |
| degrading | active | 2 consecutive successes (pattern recovered) |
| degrading | deprecated | 5 consecutive pattern failures (was 3) |
| deprecated | discovered | Manual resurrection by agent (re-enters validation queue) |
| deprecated | archived | Manual action only (agents review before archiving) |

## YQ Success Evaluation (updated 2026-03)

Two-pronged test (either passing = success):
1. **Absolute**: YQ charged < $20 (was $10)
2. **Relative**: YQ reduced by ≥75% from expected baseline

This prevents partial dumps saving $400+ from being marked as failures.
