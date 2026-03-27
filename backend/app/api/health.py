"""
health.py — Health check endpoint.

No auth required. Used by load balancers and monitoring.
"""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    """Health check — returns OK if the app is running."""
    return {"status": "ok"}
