# CLAUDE.md — App Internals

## Entrypoint

`main.py` creates the FastAPI app, registers routers, and sets up lifespan events (DB pool init, Celery connection check).

## Config (`config.py`)

All configuration via `pydantic-settings` reading from environment:

```python
class Settings(BaseSettings):
    DATABASE_URL: str          # asyncpg connection string
    REDIS_URL: str
    CLAUDE_API_KEY: str        # for LLM-assisted ingestion
    ITA_PROXY_LIST: list[str]  # rotating residential proxies
    ITA_RATE_LIMIT_SECONDS: float = 3.5   # min seconds between ITA requests
    ITA_JITTER_MAX_SECONDS: float = 2.0   # random jitter added on top
    API_KEY_HEADER: str = "X-API-Key"
    LOG_LEVEL: str = "INFO"
```

## Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| `models/` | SQLAlchemy ORM table definitions |
| `schemas/` | Pydantic models for API input/output |
| `api/` | FastAPI route handlers (thin — delegate to services) |
| `services/` | All business logic |
| `db/` | DB session factory, base declarative class |
| `tasks/` | Celery task definitions + schedules |

## Naming Conventions

- ORM models: `PascalCase`, file named `snake_case.py` (e.g., `DumpPattern` in `dump_pattern.py`)
- Schemas: `PascalCase` with `Create`, `Update`, `Response` suffixes
- Services: `snake_case` functions in `snake_case.py` modules
- API routers: one router per domain, prefixed (e.g., `/patterns`, `/carriers`, `/validations`)
