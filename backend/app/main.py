"""
main.py — FastAPI application entrypoint.

Creates the app, registers routers, and sets up lifespan events.
Run with: uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db.session import close_db_pool, init_db_pool
from app.exceptions import (
    AuthenticationError,
    DuplicateError,
    FareEngineError,
    LifecycleError,
    NotFoundError,
    ValidationError,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO))

    logger.info("Starting Fare Construction Engine API")
    try:
        await init_db_pool()
        logger.info("Database pool initialized")
    except Exception as e:
        logger.warning("Database not available at startup: %s", e)

    yield

    await close_db_pool()
    logger.info("Fare Construction Engine API shutdown complete")


app = FastAPI(
    title="Fare Construction Engine",
    description="Fare arbitrage intelligence engine for travel agents",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow all origins in development
settings = get_settings()
if settings.ENVIRONMENT == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# ─── Exception handlers ──────────────────────────────────────────────────

@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=404,
        content={"error": "not_found", "message": exc.message, "status_code": 404},
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "message": exc.message, "status_code": 422},
    )


@app.exception_handler(DuplicateError)
async def duplicate_handler(request: Request, exc: DuplicateError):
    return JSONResponse(
        status_code=409,
        content={"error": "duplicate", "message": exc.message, "status_code": 409},
    )


@app.exception_handler(AuthenticationError)
async def auth_handler(request: Request, exc: AuthenticationError):
    return JSONResponse(
        status_code=403,
        content={"error": "forbidden", "message": exc.message, "status_code": 403},
    )


@app.exception_handler(LifecycleError)
async def lifecycle_handler(request: Request, exc: LifecycleError):
    return JSONResponse(
        status_code=400,
        content={"error": "lifecycle_error", "message": exc.message, "status_code": 400},
    )


@app.exception_handler(FareEngineError)
async def generic_handler(request: Request, exc: FareEngineError):
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": exc.message, "status_code": 500},
    )


# ─── Register routers ────────────────────────────────────────────────────

from app.api.health import router as health_router
from app.api.patterns import router as patterns_router
from app.api.carriers import router as carriers_router
from app.api.validations import router as validations_router
from app.api.ingestion import router as ingestion_router
from app.api.manual_inputs import router as manual_inputs_router
from app.api.scan_targets import router as scan_targets_router
from app.api.dump_candidates import router as dump_candidates_router

app.include_router(health_router)
app.include_router(patterns_router)
app.include_router(carriers_router)
app.include_router(validations_router)
app.include_router(ingestion_router)
app.include_router(manual_inputs_router)
app.include_router(scan_targets_router)
app.include_router(dump_candidates_router)
