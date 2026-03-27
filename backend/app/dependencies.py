"""
dependencies.py — FastAPI dependency injection.

Provides:
- get_db_session: Async database session (request-scoped)
- require_api_key: X-API-Key header auth
"""

import hashlib
import hmac
from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_session


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped database session."""
    async for session in get_session():
        yield session


async def require_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> str:
    """
    Validate X-API-Key header.

    Returns 403 Forbidden (not 401) on missing/invalid key
    to avoid leaking auth scheme info.
    """
    if x_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing API key",
        )

    settings = get_settings()

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(x_api_key, settings.INITIAL_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return x_api_key
