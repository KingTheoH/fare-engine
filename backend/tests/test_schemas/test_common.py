"""Tests for common shared schemas."""

import pytest
from pydantic import ValidationError

from app.schemas.common import ErrorResponse, PaginatedResponse


class TestPaginatedResponse:
    def test_basic_pagination(self):
        resp = PaginatedResponse[str](
            items=["a", "b", "c"],
            total=10,
            page=1,
            page_size=3,
        )
        assert resp.items == ["a", "b", "c"]
        assert resp.total == 10
        assert resp.page == 1
        assert resp.page_size == 3

    def test_empty_items(self):
        resp = PaginatedResponse[int](items=[], total=0, page=1, page_size=10)
        assert resp.items == []
        assert resp.total == 0

    def test_page_must_be_positive(self):
        with pytest.raises(ValidationError):
            PaginatedResponse[str](items=[], total=0, page=0, page_size=10)

    def test_page_size_max_100(self):
        with pytest.raises(ValidationError):
            PaginatedResponse[str](items=[], total=0, page=1, page_size=101)


class TestErrorResponse:
    def test_basic_error(self):
        err = ErrorResponse(
            error="pattern_not_found",
            message="No pattern with that ID exists",
            status_code=404,
        )
        assert err.error == "pattern_not_found"
        assert err.status_code == 404

    def test_serialization(self):
        err = ErrorResponse(
            error="validation_error",
            message="Invalid input",
            status_code=422,
        )
        data = err.model_dump()
        assert data["error"] == "validation_error"
        assert data["status_code"] == 422
