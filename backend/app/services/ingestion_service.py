import uuid
from typing import Any

from app.adapters import AdapterResult, SourceDescriptor, SourceFormat, get_adapter_registry
from app.adapters.errors import SourceParsingError
from app.storage.artifacts import ArtifactCategory, ArtifactDescriptor, get_artifact_store


class PricingSourceIngestionService:
    """Service orchestrating source upload, artifact storage, adapter compilation, and IPIR lineage."""

    def __init__(self) -> None:
        self.artifact_store = get_artifact_store()
        self.registry = get_adapter_registry()

    def register_source(
        self,
        filename: str,
        content_type: str,
        content: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> SourceDescriptor:
        """Validates, stores, and registers a source file artifact."""
        if len(content) > 20 * 1024 * 1024:
            raise SourceParsingError("File size exceeds maximum allowed 20MB limit.")

        ext = filename.split(".")[-1].lower()
        if ext == "json":
            fmt = SourceFormat.STRUCTURED_JSON
            cat = ArtifactCategory.SOURCE_JSON
        elif ext in ("xlsx", "xls"):
            fmt = SourceFormat.EXCEL
            cat = ArtifactCategory.SOURCE_WORKBOOK
        elif ext == "pdf":
            fmt = SourceFormat.PDF
            cat = ArtifactCategory.SOURCE_DOCUMENT
        else:
            raise SourceParsingError(f"Unsupported file extension '.{ext}'. Allowed: .json, .xlsx, .pdf")

        source_id = f"SRC-{uuid.uuid4().hex[:8].upper()}"
        art_desc = ArtifactDescriptor(
            artifact_id=source_id,
            category=cat,
            filename=filename,
            content_type=content_type or "application/octet-stream",
            size_bytes=len(content),
            storage_uri="",
            metadata=metadata or {},
        )
        saved_desc = self.artifact_store.save_artifact(art_desc, content)

        return SourceDescriptor(
            source_id=source_id,
            name=filename,
            source_type=fmt,
            format=ext,
            storage_uri=saved_desc.storage_uri,
            metadata=metadata or {},
        )

    def compile_source(self, source_descriptor: SourceDescriptor) -> AdapterResult:
        """Selects adapter, compiles source bytes to IPIR, and saves compiled IPIR artifact."""
        content = self.artifact_store.get_artifact_content(source_descriptor.source_id)
        if not content:
            raise SourceParsingError(f"Artifact content for source '{source_descriptor.source_id}' not found.")

        adapter = self.registry.get_adapter(source_descriptor.source_type)
        result = adapter.to_ipir(source_descriptor, content)

        # Save compiled IPIR artifact
        ipir_json = result.ipir_package.model_dump_json(indent=2).encode("utf-8")
        ipir_art = ArtifactDescriptor(
            artifact_id=f"IPIR-{source_descriptor.source_id}",
            category=ArtifactCategory.IPIR_PACKAGE,
            filename=f"{result.ipir_package.id}.json",
            content_type="application/json",
            size_bytes=len(ipir_json),
            storage_uri="",
            metadata={"source_id": source_descriptor.source_id},
        )
        self.artifact_store.save_artifact(ipir_art, ipir_json)

        return result

