# CLAUDE.md — Database Layer

## Connection Setup

- Driver: `asyncpg`
- ORM: SQLAlchemy 2.x async
- Session factory in `db/session.py`
- Base declarative class in `db/base.py`

## Session Pattern

Use FastAPI dependency injection for request-scoped sessions:

```python
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

Celery tasks create their own sessions directly (not via FastAPI DI).

## Migration Rules

- Every schema change = new Alembic migration
- Migration files are named with a timestamp prefix and descriptive slug
- Never use `--autogenerate` blindly — always review generated migrations before committing
- Migrations must be reversible (implement `downgrade()`)

## Index Strategy

Pre-create indexes for the most common query patterns (Phase 1):
- `dump_patterns(lifecycle_state, freshness_tier)` — for validation scheduler
- `dump_patterns(origin_iata, destination_iata)` — for agent route search
- `dump_patterns(expected_yq_savings_usd DESC)` — for leaderboard sorting
- `validation_runs(pattern_id, ran_at DESC)` — for history queries
- `carriers(charges_yq)` — for filtering to YQ-charging carriers

## Repository Pattern

Each domain has a corresponding repository module in `db/repositories/`:
- `pattern_repository.py`
- `carrier_repository.py`
- `validation_repository.py`
- `yq_repository.py`
- `community_repository.py`

Repositories handle raw DB queries. Services call repositories, never raw SQLAlchemy sessions directly.
