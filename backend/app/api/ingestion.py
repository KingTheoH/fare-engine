"""
ingestion.py — Community ingestion endpoints.

POST /api/v1/ingestion/submit — submit a forum URL for ingestion
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies import require_api_key

router = APIRouter(
    prefix="/api/v1/ingestion",
    tags=["ingestion"],
    dependencies=[Depends(require_api_key)],
)


class IngestionSubmitRequest(BaseModel):
    """Request body for submitting a URL for ingestion."""

    url: str = Field(
        min_length=1,
        description="Forum URL to scrape and process (e.g. FlyerTalk thread)",
    )


@router.post("/submit")
async def submit_for_ingestion(
    body: IngestionSubmitRequest,
) -> dict:
    """
    Submit a FlyerTalk or forum URL for ingestion.

    Enqueues a Celery task to scrape the URL and run the LLM
    extraction pipeline on all posts found.
    """
    from app.tasks.ingestion_tasks import scan_all_forums

    task = scan_all_forums.delay()

    return {
        "status": "queued",
        "task_id": task.id,
        "url": body.url,
    }
