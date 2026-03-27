# CLAUDE.md — Scripts

## Overview

One-off utility scripts that run outside the FastAPI app. These are CLI tools for setup, maintenance, and debugging — not production code paths.

## Files

```
scripts/
├── CLAUDE.md              ← you are here
└── seed_carriers.py       ← populates carriers table from seeds/carriers.json (Phase 01)
```

## Script Conventions

- All scripts use `asyncio.run()` at the bottom — they can call async service functions
- All scripts read config from environment (same `.env` as the main app)
- All scripts print meaningful output: what was done, counts, any errors
- All scripts exit with code 0 on success, 1 on error
- All scripts are idempotent — safe to run multiple times

## `seed_carriers.py` (Phase 01)

Loads `seeds/carriers.json` and upserts all carrier records.

```python
# Usage
python scripts/seed_carriers.py

# Expected output
Loading 32 carriers from seeds/carriers.json...
Seeded 32 carriers (27 inserted, 5 updated, 0 errors)
Done.
```

## Future Scripts (as phases are implemented)

| Script | Phase | Purpose |
|--------|-------|---------|
| `create_api_key.py` | 09 | Generate and store a hashed API key for agent access |
| `backfill_freshness_tiers.py` | 07 | Recalculate freshness tiers for all patterns |
| `export_patterns.py` | 09 | Export all active patterns to JSON for backup |
| `retire_proxy.py` | 04 | Manually mark a proxy as retired (when known-bad) |
| `requeue_failed_posts.py` | 06 | Re-enqueue community posts that failed LLM extraction |

## Makefile Integration

All scripts should be accessible via `make` commands:
```makefile
db-seed:
    cd backend && python scripts/seed_carriers.py

create-api-key:
    cd backend && python scripts/create_api_key.py
```

## What NOT to Do

- Do not use scripts to make schema changes — use Alembic migrations
- Do not put business logic in scripts that duplicates service functions — call the service
- Do not hardcode connection strings in scripts — always use `get_settings()` from `app.config`
