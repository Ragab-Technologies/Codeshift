"""FastAPI application for Codeshift billing API."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from codeshift import __version__
from codeshift.api.config import get_settings
from codeshift.api.routers import auth, billing, migrate, usage, webhooks


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    settings = get_settings()
    print(f"Codeshift API starting (environment: {settings.environment})")
    yield
    # Shutdown
    print("Codeshift API shutting down")


app = FastAPI(
    title="Codeshift API",
    description="Billing and authentication API for Codeshift CLI",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if not get_settings().is_production else None,
    redoc_url="/redoc" if not get_settings().is_production else None,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://codeshift.dev",
        "https://www.codeshift.dev",
        "http://localhost:3000",  # Local development
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(billing.router, prefix="/billing", tags=["Billing"])
app.include_router(migrate.router, tags=["Migration"])
app.include_router(usage.router, prefix="/usage", tags=["Usage"])
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])


@app.get("/")
async def root() -> dict:
    """API root endpoint."""
    return {
        "name": "Codeshift API",
        "version": __version__,
        "status": "healthy",
    }


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "version": __version__}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler."""
    settings = get_settings()

    # Log the error
    print(f"Unhandled exception: {exc}")

    # Return appropriate response based on environment
    if settings.is_production:
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
    else:
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "type": type(exc).__name__},
        )


# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "codeshift.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
