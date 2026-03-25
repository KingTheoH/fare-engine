# Phase 06 — Community Data Ingestion

## Goal
Build the pipeline that scrapes FlyerTalk (and similar forums), uses Claude API to extract structured dump pattern candidates from posts, scores them by credibility, and queues them for ITA validation.

## Deliverables

- [ ] `ingestion/scrapers/flyertalk.py` — FlyerTalk thread/post scraper
- [ ] `ingestion/extractors/llm_extractor.py` — Claude API extraction
- [ ] `ingestion/extractors/pattern_normalizer.py` — LLM output → DB record
- [ ] `ingestion/weighting/post_credibility.py` — author reputation scoring
- [ ] `backend/app/services/ingestion_service.py` — orchestration
- [ ] Celery task: `app/tasks/ingestion_tasks.py`
- [ ] API endpoint: `POST /api/v1/ingestion/submit` (submits a URL for ingestion)
- [ ] Unit tests: `tests/test_ingestion/test_llm_extractor.py` (with fixture posts)

## FlyerTalk Scraper (`flyertalk.py`)

### Target Forums
Configure as a list (so new forums can be added without code changes):

```json
{
  "forums": [
    {
      "name": "Business Class",
      "url": "https://www.flyertalk.com/forum/business-class-premium/",
      "priority": "high"
    },
    {
      "name": "Mileage Run Deals",
      "url": "https://www.flyertalk.com/forum/mileage-run-deals/",
      "priority": "high"
    },
    {
      "name": "Lufthansa Group",
      "url": "https://www.flyertalk.com/forum/miles-more/",
      "priority": "medium"
    }
  ]
}
```

### Scraping Logic
1. Fetch forum index page
2. Find thread links (pagination: follow "next page" until all threads fetched or `max_threads_per_forum` reached)
3. Filter to threads with keyword match: `fuel dump|YQ-free|YQ free|fuel surcharge|routing trick|ticketing point|TP dump|bypass surcharge`
4. For matching threads: fetch all pages of posts
5. Store each post as a `community_posts` record with `processing_state = "raw"`
6. Enqueue `process_community_post` Celery task per post

### Author Data Extraction
From the post HTML, extract:
- `post_author` — username (stored for deduplication, not for display)
- `author_post_count` — from profile badge if visible
- `author_account_age_days` — calculate from join date if visible
- `posted_at` — post timestamp

### Rate Limiting
- 1 request per 2 seconds ± 0.5s jitter
- Respect `robots.txt`
- Do NOT scrape more than 500 posts per run (configurable via `MAX_POSTS_PER_INGESTION_RUN`)

## LLM Extractor (`llm_extractor.py`)

### Two-Pass Strategy (cost control)

**Pass 1 — Haiku filter** (cheap, ~$0.001 per post):
```
Prompt: "Does this forum post describe a specific airline fuel dump or YQ-free fare construction technique? Answer ONLY 'yes' or 'no'."
```
If "no" → mark post as `processed`, skip Pass 2.

**Pass 2 — Sonnet extraction** (only for "yes" posts, ~$0.01 per post):
Full structured extraction. See prompt in `ingestion/CLAUDE.md` for schema.

### Extraction Prompt (Pass 2)

System prompt:
```
You are an expert airline fare construction analyst. Extract structured information about fuel dump techniques from the following forum post. A "fuel dump" is a fare construction technique where specific routing or ticketing arrangements eliminate or reduce YQ (carrier-imposed fuel surcharges).

Return a JSON object matching this schema:
{
  "contains_dump_pattern": boolean,
  "patterns": [
    {
      "origin": "3-letter IATA airport code or null",
      "destination": "3-letter IATA airport code or null",
      "carriers": ["list of 2-letter IATA carrier codes in sequence"],
      "ticketing_point": "3-letter IATA code or null",
      "dump_type": "TP_DUMP | CARRIER_SWITCH | FARE_BASIS | ALLIANCE_RULE | unknown",
      "fare_basis_hint": "fare basis code pattern or null",
      "confidence": "low | medium | high",
      "confirmation_signals": ["phrases from the post indicating it currently works"],
      "deprecation_signals": ["phrases from the post indicating it no longer works"],
      "yq_savings_estimate_usd": number or null,
      "notes": "any other relevant details"
    }
  ],
  "extraction_confidence": "low | medium | high"
}

If the post contains no dump pattern, return {"contains_dump_pattern": false, "patterns": []}.
```

### Handling LLM Failures
- If Claude API call fails (rate limit, timeout): retry once after 5s, then mark post as `failed`
- If JSON parsing fails: log raw response, mark as `failed`, do NOT crash the pipeline
- Failed posts can be manually re-queued via the API

## Pattern Normalizer (`pattern_normalizer.py`)

Converts LLM output to a `DumpPatternCreate` schema:
1. Validate all IATA codes (3-letter airport, 2-letter carrier) against the `carriers` table
2. If carrier not in DB: create a stub carrier record with `charges_yq = null` for later enrichment
3. Generate `ita_routing_code` using Phase 3's `query_builder`
4. Set `lifecycle_state = discovered`
5. Set `manual_input_bundle = null` (populated after first successful ITA validation)
6. Set `confidence_score = post_credibility_score * llm_confidence_multiplier`
   - `llm_confidence_multiplier`: high=1.0, medium=0.7, low=0.4
7. Attempt deduplication: check if `ita_routing_code` already exists in DB
   - If exists: update `source_post_weight` if new source has higher weight, don't duplicate

## Ingestion Service (`ingestion_service.py`)

```python
async def ingest_url(url: str) -> IngestResult:
    """
    Entry point for manual URL submission via API.
    Detects source type (FlyerTalk forum index vs single thread vs single post)
    and dispatches to appropriate scraper.
    """

async def process_community_post(post_id: UUID) -> list[UUID]:
    """
    Run LLM extraction on a stored community post.
    Returns list of new dump_pattern IDs created.
    Each new pattern is also enqueued for ITA validation.
    """
```

## Completion Check

```bash
# Unit tests with fixture posts
cd backend && pytest tests/test_ingestion/test_llm_extractor.py -v

# Integration test: submit a known FlyerTalk URL
curl -X POST http://localhost:8000/api/v1/ingestion/submit \
  -H "X-API-Key: test-key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.flyertalk.com/forum/..."}'
```

## Files Changed
- New: `ingestion/scrapers/flyertalk.py`
- New: `ingestion/extractors/llm_extractor.py`
- New: `ingestion/extractors/pattern_normalizer.py`
- New: `ingestion/weighting/post_credibility.py`
- New: `ingestion/data/forum_config.json`
- New: `backend/app/services/ingestion_service.py`
- New: `backend/app/tasks/ingestion_tasks.py`
- New: `backend/app/api/ingestion.py` (route handler)
- New: `tests/test_ingestion/test_llm_extractor.py`
- New: `tests/fixtures/flyertalk_posts.json` (10+ example posts for testing)
