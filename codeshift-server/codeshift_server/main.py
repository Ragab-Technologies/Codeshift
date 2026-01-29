"""Main FastAPI application for Codeshift Server.

This module sets up the FastAPI application with all routes, middleware,
and exception handlers for the Codeshift backend service.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from codeshift_server.middleware.rate_limit import get_rate_limiter, rate_limit_exceeded_handler
from codeshift_server.routers import migrate
from codeshift_server.utils.usage_tracker import run_cleanup_task

logger = logging.getLogger(__name__)

# Initialize the rate limiter
limiter = get_rate_limiter()

# Cleanup task interval in seconds (5 minutes)
CLEANUP_INTERVAL_SECONDS = 300.0
# Maximum age for pending usage records (15 minutes)
MAX_PENDING_AGE_SECONDS = 900.0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager for startup and shutdown events.

    Starts the usage cleanup background task on startup and
    cancels it gracefully on shutdown.
    """
    # Startup: Create and start the cleanup task
    logger.info("Starting usage cleanup background task")
    cleanup_task = asyncio.create_task(
        run_cleanup_task(
            interval_seconds=CLEANUP_INTERVAL_SECONDS,
            max_age_seconds=MAX_PENDING_AGE_SECONDS,
        )
    )

    yield

    # Shutdown: Cancel the cleanup task
    logger.info("Shutting down usage cleanup background task")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        logger.info("Usage cleanup task cancelled successfully")


# Create FastAPI application
app = FastAPI(
    title="Codeshift Server",
    description="API backend for authentication, billing, and server-side LLM migrations",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Store limiter in app state for access in route handlers
app.state.limiter = limiter

# Add SlowAPI middleware for rate limiting
app.add_middleware(SlowAPIMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handler for rate limit exceeded
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Include routers
app.include_router(migrate.router, prefix="/api/v1", tags=["migrate"])


@app.get("/health")
@limiter.limit("120/minute")
async def health_check(request: Request) -> dict[str, str]:
    """Health check endpoint for monitoring.

    Args:
        request: The incoming request (required for rate limiting).

    Returns:
        Status indicating the service is healthy.
    """
    return {"status": "healthy", "service": "codeshift-server"}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with API information.

    Returns:
        Basic API information and documentation links.
    """
    return {
        "service": "Codeshift Server",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
