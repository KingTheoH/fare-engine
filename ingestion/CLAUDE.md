# CLAUDE.md — Community Data Ingestion

## Overview

This module scrapes and processes community forum data (primarily FlyerTalk) to extract dump pattern candidates. It uses Claude API for LLM-assisted extraction of structured fare constructions from unstructured forum text.

## Directory Structure

```
ingestion/
├── CLAUDE.md              ← you are here
├── scrapers/
│   ├── flyertalk.py       ← FlyerTalk thread/post scraper
│   └── base.py            ← Abstract base scraper
├── extractors/
│   ├── llm_extractor.py   ← Claude API extraction
│   └── pattern_normalizer.py  ← Converts LLM output to DB-ready format
└── weighting/
    └── post_credibility.py    ← Author reputation scoring
```

## Source Priority

| Source | Priority | Notes |
|--------|----------|-------|
| FlyerTalk — Business Class/Premium forum | HIGH | Best quality dump discussions |
| FlyerTalk — Mileage Run Deals | HIGH | Active community validation |
| FlyerTalk — Newbies thread | LOW | Often outdated or incorrect |
| Other forums (Boarding Area, etc.) | MEDIUM | Process if linked from FlyerTalk |

## FlyerTalk Scraper

- Scrapes thread lists from target forums (configurable list of forum URLs)
- Identifies threads likely to contain fuel dump info via keyword matching:
  - "fuel dump", "YQ", "YQ-free", "fuel surcharge", "routing trick", "TP dump", "ticketing point"
- For matching threads: scrape all posts, store in `community_posts`
- Pagination: follow "next page" links until all posts retrieved
- Rate limit: 1 request / 2 seconds, randomized ±0.5s
- Respect `robots.txt` — only scrape publicly accessible pages

## LLM Extraction (`llm_extractor.py`)

Uses Claude API to extract structured patterns from raw post text.

### Model Selection
- Use `claude-haiku-4-5` for initial pass (cheap, fast — most posts have nothing useful)
- Escalate to `claude-sonnet-4-6` only for posts that haiku flags as likely containing a dump construction

### Extraction Prompt Strategy
The prompt must ask for:
1. Whether the post describes a specific fuel dump construction (yes/no)
2. If yes: origin, destination, carrier sequence, ticketing point, dump mechanism type
3. Confidence the LLM has in its extraction (low/medium/high)
4. Any explicit confirmation language ("I just booked this", "still works as of [date]")
5. Any warning language ("no longer works", "airline fixed this")

### Output Schema (from LLM)
```json
{
  "contains_dump_pattern": true,
  "patterns": [
    {
      "origin": "JFK",
      "destination": "BKK",
      "carriers": ["LH", "AA"],
      "ticketing_point": "FRA",
      "dump_type": "TP_DUMP",
      "fare_basis_hint": null,
      "confidence": "high",
      "confirmation_signals": ["just booked this last week", "confirmed working March 2026"],
      "deprecation_signals": []
    }
  ],
  "extraction_confidence": "high"
}
```

### Handling Ambiguity
- If LLM returns `confidence: low` → store as `discovered` lifecycle state, do NOT auto-promote
- If post contains deprecation signals → still store but with `confidence_score` capped at 0.2
- Multiple patterns from one post → create one `dump_patterns` record per extracted pattern

## Post Credibility Scoring

`post_credibility.py` returns a float 0.0–1.0:

```python
def score_post(post: CommunityPost) -> float:
    score = 0.5  # baseline

    # Author experience signals
    if post.author_post_count > 1000: score += 0.15
    elif post.author_post_count > 200: score += 0.08

    if post.author_account_age_days > 1825:  # 5+ years
        score += 0.10
    elif post.author_account_age_days > 365:
        score += 0.05

    # Recency signals
    days_since_post = (now - post.posted_at).days
    if days_since_post < 7: score += 0.15
    elif days_since_post < 30: score += 0.08
    elif days_since_post > 180: score -= 0.15
    elif days_since_post > 365: score -= 0.25

    # Confirmation in thread
    if post.reply_confirms_count > 3: score += 0.10
    if post.reply_deprecates_count > 2: score -= 0.20

    return max(0.0, min(1.0, score))
```

## Pattern Normalization

`pattern_normalizer.py` converts raw LLM output to a format suitable for `dump_patterns` table insert:
- Validates IATA codes (3-letter airports, 2-letter carriers)
- Looks up carrier records to confirm they exist in DB
- Generates `ita_routing_code` from extracted carriers/routing points
- Sets `lifecycle_state = discovered` (never auto-set to active — validation must confirm)
- Sets `manual_input_bundle = None` until first successful ITA validation

## What NOT to Do

- Do not extract patterns from posts older than 2 years without a recent confirmation post in the same thread
- Do not mark a pattern as `active` based solely on community data — ITA validation is always required
- Do not store author usernames in the database (privacy) — only use account age and post count metrics
- Do not retry LLM extraction on the same post more than 3 times if it keeps failing
