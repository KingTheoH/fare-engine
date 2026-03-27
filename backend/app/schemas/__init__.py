"""
Pydantic schemas — API request/response contracts.

All schemas are imported here for convenient access.
"""

from app.schemas.carrier import CarrierCreate, CarrierResponse, CarrierUpdate
from app.schemas.common import ErrorResponse, PaginatedResponse
from app.schemas.community_post import (
    CommunityPostCreate,
    CommunityPostResponse,
    ExtractedPattern,
)
from app.schemas.dump_pattern import (
    DumpPatternCreate,
    DumpPatternResponse,
    DumpPatternSummary,
    DumpPatternUpdate,
)
from app.schemas.manual_input import ManualInputBundle
from app.schemas.route import RouteCreate, RouteResponse
from app.schemas.validation_run import ValidationRunCreate, ValidationRunResponse
from app.schemas.yq_schedule import YQScheduleCreate, YQScheduleResponse

__all__ = [
    "ErrorResponse",
    "PaginatedResponse",
    "CarrierCreate",
    "CarrierUpdate",
    "CarrierResponse",
    "RouteCreate",
    "RouteResponse",
    "ManualInputBundle",
    "DumpPatternCreate",
    "DumpPatternUpdate",
    "DumpPatternSummary",
    "DumpPatternResponse",
    "ValidationRunCreate",
    "ValidationRunResponse",
    "YQScheduleCreate",
    "YQScheduleResponse",
    "CommunityPostCreate",
    "CommunityPostResponse",
    "ExtractedPattern",
]
