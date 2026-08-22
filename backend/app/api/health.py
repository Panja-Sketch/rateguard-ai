from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health Check")
async def health_check() -> dict[str, str]:
    """Endpoint verifying service health status."""
    return {"status": "healthy"}

