from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.adapters.errors import SourceParsingError
from app.services.ingestion_service import PricingSourceIngestionService

router = APIRouter(prefix="/api/v1/sources", tags=["sources"])
ingestion_service = PricingSourceIngestionService()
_registered_sources: dict[str, Any] = {}


@router.post("")
async def upload_pricing_source(file: UploadFile = File(...)) -> dict[str, Any]:
    """Uploads and registers a pricing source file (.json, .xlsx, .pdf)."""
    try:
        content = await file.read()
        descriptor = ingestion_service.register_source(
            filename=file.filename or "uploaded_source",
            content_type=file.content_type or "application/octet-stream",
            content=content,
        )
        _registered_sources[descriptor.source_id] = descriptor
        return {
            "source_id": descriptor.source_id,
            "name": descriptor.name,
            "source_type": descriptor.source_type.value,
            "format": descriptor.format,
            "storage_uri": descriptor.storage_uri,
            "status": "REGISTERED",
        }
    except SourceParsingError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload pricing source: {e}",
        )


@router.post("/{source_id}/compile")
def compile_pricing_source(source_id: str) -> dict[str, Any]:
    """Compiles a registered source into a canonical IPIR package using its matching adapter."""
    desc = _registered_sources.get(source_id)
    if not desc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Registered source '{source_id}' not found.",
        )

    try:
        res = ingestion_service.compile_source(desc)
        return {
            "source_id": source_id,
            "adapter_id": res.adapter_id,
            "ipir_package_id": res.ipir_package.id,
            "mapping_coverage": res.mapping_coverage,
            "confidence": res.confidence,
            "warnings": res.warnings,
            "requires_human_review": res.requires_human_review,
            "ipir_package": res.ipir_package.model_dump(mode="json"),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Source compilation failed: {e}",
        )

