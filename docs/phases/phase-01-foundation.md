# Phase 01 — Project Foundation & Database Schema

## Goal
Stand up the project skeleton, Docker environment, and full database schema with migrations. At the end of this phase, you can `docker compose up` and connect to a PostgreSQL database with all tables created.

## Deliverables

- [ ] `docker-compose.yml` with `postgres`, `redis`, `backend` (stub), `celery-worker` (stub) services
- [ ] `.env.example` with all required environment variable names
- [ ] `backend/pyproject.toml` with all dependencies declared
- [ ] Alembic initialized (`alembic init alembic/`)
- [ ] `backend/app/db/base.py` — SQLAlchemy declarative base
- [ ] `backend/app/db/session.py` — async session factory
- [ ] All ORM model files created with full column definitions:
  - `app/models/carrier.py`
  - `app/models/route.py`
  - `app/models/dump_pattern.py`
  - `app/models/validation_run.py`
  - `app/models/yq_schedule.py`
  - `app/models/community_post.py`
- [ ] `app/models/enums.py` — all enums (DumpType, LifecycleState, PatternSource, ProcessingState)
- [ ] Initial Alembic migration that creates all tables and indexes
- [ ] `make db-migrate` and `make db-upgrade` commands in `Makefile`

## Database Tables to Create

See `backend/app/models/CLAUDE.md` for full column specs.

Tables: `carriers`, `routes`, `dump_patterns`, `validation_runs`, `yq_schedules`, `community_posts`

Indexes (create in migration):
```sql
CREATE INDEX idx_patterns_lifecycle_tier ON dump_patterns(lifecycle_state, freshness_tier);
CREATE INDEX idx_patterns_route ON dump_patterns(origin_iata, destination_iata);
CREATE INDEX idx_patterns_savings ON dump_patterns(expected_yq_savings_usd DESC);
CREATE INDEX idx_validations_pattern_time ON validation_runs(pattern_id, ran_at DESC);
CREATE INDEX idx_carriers_charges_yq ON carriers(charges_yq);
```

## Seed Data

Create a `seeds/carriers.json` with the top 30 carriers that are relevant (mix of high-YQ carriers and known dump-friendly carriers). Include at minimum:
- High YQ: LH, LX, OS, SN (Lufthansa Group), BA, IB (IAG), CX, KE, OZ
- Low/No YQ: QR, EK, EY, TK, SQ (useful as dump vehicles)
- US carriers: AA, UA, DL (useful as operating carriers in dumps)

Seed script: `backend/scripts/seed_carriers.py`

## What This Phase Does NOT Include

- No FastAPI app yet (just DB + models)
- No business logic
- No automation
- No API endpoints

## Completion Check

```bash
docker compose up -d postgres
cd backend && alembic upgrade head
python scripts/seed_carriers.py
psql $DATABASE_URL -c "SELECT COUNT(*) FROM carriers;"
# Should return 30+
```

## Files Changed
- New: `docker-compose.yml`, `.env.example`, `Makefile`
- New: `backend/pyproject.toml`, `backend/alembic.ini`, `backend/alembic/env.py`
- New: all model files listed above
- New: initial migration in `backend/alembic/versions/`
- New: `backend/scripts/seed_carriers.py`
