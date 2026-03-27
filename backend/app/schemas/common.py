"""
common.py — Shared Pydantic types used across all schema modules.

PaginatedResponse is generic — use PaginatedResponse[DumpPatternSummary], etc.
ErrorResponse is the standard error shape returned by all API error handlers.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated list wrapper. All list endpoints return this shape."""

    items: list[T]
    total: int = Field(description="Total number of matching records")
    page: int = Field(ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(ge=1, le=100, description="Items per page")


class ErrorResponse(BaseModel):
    """Standard error response. Returned by all exception handlers."""

    error: str = Field(description="Machine-readable error code, e.g. 'pattern_not_found'")
    message: str = Field(description="Human-readable error message")
    status_code: int = Field(description="HTTP status code")
