"""
session.py — Async SQLAlchemy session factory.

Usage in FastAPI (Phase 9):
    async def get_session() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

Usage in Celery tasks (Phase 8) — tasks create their own sessions:
    async with async_session_factory() as session:
        ...

Design note: Connection pool min=5, max=20. asyncpg driver.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

# Module-level engine — created once on first import, reused across requests.
# The engine is NOT created at module load time; it's lazy via _get_engine()
# so tests can override DATABASE_URL before the engine is constructed.
_engine = None
_async_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=5,
            max_overflow=15,       # 5 + 15 = 20 total connections
            pool_pre_ping=True,    # verify connections before use
            echo=settings.LOG_LEVEL == "DEBUG",
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,  # avoid lazy-load errors after commit
        )
    return _async_session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency. Yields a session, commits on success, rolls back on error.
    Use via: session: AsyncSession = Depends(get_session)
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db_pool() -> None:
    """Called during FastAPI lifespan startup to warm the connection pool."""
    engine = _get_engine()
    async with engine.connect():
        pass  # just verify we can connect


async def close_db_pool() -> None:
    """Called during FastAPI lifespan shutdown."""
    global _engine, _async_session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
