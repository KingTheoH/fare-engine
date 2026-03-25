# CLAUDE.md — Backend

## Overview

The backend is a **FastAPI** application. It serves the agent dashboard, exposes internal APIs for the automation and ingestion systems, and owns the database connection.

## Directory Structure

```
backend/
├── CLAUDE.md          ← you are here
├── pyproject.toml
├── alembic.ini
├── alembic/
│   └── versions/      ← migration files go here
└── app/
    ├── CLAUDE.md
    ├── main.py        ← FastAPI app entrypoint
    ├── config.py      ← env-based config (Pydantic BaseSettings)
    ├── models/        ← SQLAlchemy ORM models
    ├── schemas/       ← Pydantic request/response schemas
    ├── api/           ← route handlers
    ├── services/      ← business logic
    ├── db/            ← session management, base class
    └── tasks/         ← Celery task definitions
```

## Key Principles

- **Config via environment variables only** — use `pydantic-settings`. Never hardcode secrets or connection strings.
- **Thin routes, fat services** — API route handlers should do almost nothing except call a service and return a schema. All business logic lives in `services/`.
- **Async where it matters** — database queries use async SQLAlchemy. CPU-bound work goes to Celery tasks, not async handlers.
- **Alembic for all schema changes** — never modify tables directly. Every change = new migration.

## Auth

- API key authentication for the agent dashboard and any external callers.
- Keys are stored hashed in the database.
- No OAuth or SSO in MVP scope.
- Implementation: FastAPI `Security` dependency with `X-API-Key` header.

## Database Connection

- Use `asyncpg` driver with async SQLAlchemy.
- Connection pool managed by SQLAlchemy (min 5, max 20).
- One `AsyncSession` per request, via dependency injection.
- See `db/CLAUDE.md` for session management details.

## Error Handling

- All service exceptions bubble up as `HTTPException` at the route level.
- Use a custom exception hierarchy defined in `app/exceptions.py`.
- Never return raw SQLAlchemy or Python tracebacks to clients.

## Celery Integration

- Celery app is defined in `app/tasks/celery_app.py`.
- Tasks import services directly — they do NOT make HTTP calls to the FastAPI app.
- Task results are stored in Redis.
- All scheduled tasks are registered in `app/tasks/schedules.py`.
