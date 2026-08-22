from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.assurance import router as assurance_router
from app.api.health import router as health_router
from app.api.sources import router as sources_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle context manager."""
    configure_logging()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

# Register API routers
app.include_router(health_router)
app.include_router(assurance_router)
app.include_router(sources_router)


@app.get("/", summary="Root Status Endpoint")
async def root() -> dict[str, str]:
    """Root endpoint returning service identification and status."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }
