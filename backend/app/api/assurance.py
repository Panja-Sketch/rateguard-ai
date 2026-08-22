from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.agents import AgenticAssuranceRunner
from app.api.sources import _registered_sources
from app.ipir.package import IPIRPackage
from app.services.ingestion_service import PricingSourceIngestionService
from app.storage import EvidenceRecord, get_run_store

router = APIRouter(prefix="/api/v1", tags=["assurance"])
_ingestion_service = PricingSourceIngestionService()


class AssuranceRunRequest(BaseModel):
    """Request payload for starting an autonomous pricing assurance workflow."""

    left_package_id: str | None = Field(
        default="AZ_HO3_2026_09", description="Canonical IPIR rate plan ID"
    )
    right_package_id: str | None = Field(
        default="AZ_HO3_2026_09_DEFECTIVE", description="Target engine implementation ID"
    )
    left_source_id: str | None = Field(
        default=None, description="Optional registered source ID for left pricing model"
    )
    right_source_id: str | None = Field(
        default=None, description="Optional registered source ID for right pricing model"
    )
    include_portfolio_analysis: bool = Field(
        default=True, description="Enable 50,000 policy portfolio blast radius analysis"
    )
    portfolio_csv_path: str | None = Field(
        default=None, description="Optional custom synthetic portfolio CSV path"
    )


def resolve_demo_package(package_id: str) -> IPIRPackage:
    """Resolves allowed demo package IDs safely without exposing arbitrary filesystem paths."""
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    canonical_file = (
        root_dir / "data" / "implementations" / "canonical" / "AZ_HO3_2026_09_ipir.json"
    )
    defective_file = (
        root_dir / "data" / "implementations" / "defective" / "AZ_HO3_2026_09_ipir.json"
    )

    if package_id == "AZ_HO3_2026_09":
        target_path = canonical_file
    elif package_id in ("AZ_HO3_2026_09_DEFECTIVE", "AZ_HO3_2026_09_defective"):
        target_path = defective_file
    else:
        err_msg = (
            f"Unsupported package_id '{package_id}'. "
            "Allowed demo packages: ['AZ_HO3_2026_09', 'AZ_HO3_2026_09_DEFECTIVE']"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )

    if not target_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Package file for '{package_id}' not found at {target_path}",
        )

    with open(target_path, encoding="utf-8") as f:
        return IPIRPackage.model_validate_json(f.read())


@router.get("/demo/packages")
def list_demo_packages() -> dict[str, Any]:
    """Returns available synthetic demo packages for testing."""
    return {
        "packages": [
            {
                "id": "AZ_HO3_2026_09",
                "name": "Arizona Homeowners HO3 Rate Plan (Canonical Filing Intent)",
                "type": "CANONICAL",
            },
            {
                "id": "AZ_HO3_2026_09_DEFECTIVE",
                "name": "Arizona Homeowners HO3 Rate Plan (Defective Implementation)",
                "type": "DEFECTIVE_TARGET",
            },
        ]
    }


@router.post("/assurance/runs")
def create_assurance_run(req: AssuranceRunRequest) -> dict[str, Any]:
    """Initiates and executes an autonomous agentic pricing assurance workflow run."""
    if req.left_source_id:
        desc_l = _registered_sources.get(req.left_source_id)
        if not desc_l:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Left source_id '{req.left_source_id}' not found.",
            )
        left_pkg = _ingestion_service.compile_source(desc_l).ipir_package
    elif req.left_package_id:
        left_pkg = resolve_demo_package(req.left_package_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either left_package_id or left_source_id must be provided.",
        )

    if req.right_source_id:
        desc_r = _registered_sources.get(req.right_source_id)
        if not desc_r:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Right source_id '{req.right_source_id}' not found.",
            )
        right_pkg = _ingestion_service.compile_source(desc_r).ipir_package
    elif req.right_package_id:
        right_pkg = resolve_demo_package(req.right_package_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either right_package_id or right_source_id must be provided.",
        )

    store = get_run_store()
    runner = AgenticAssuranceRunner(run_store=store)

    result = runner.run_assurance(
        left_package=left_pkg,
        right_package=right_pkg,
        include_portfolio_analysis=req.include_portfolio_analysis,
        portfolio_csv_path=req.portfolio_csv_path,
    )

    return {
        "run_id": result.run_id,
        "status": result.status,
        "executive_summary": result.executive_summary,
        "recommendation": result.recommendation,
        "result": result.model_dump(mode="json"),
    }


@router.get("/assurance/runs/{run_id}")
def get_assurance_run(run_id: str) -> dict[str, Any]:
    """Fetches persisted assurance run state by run ID."""
    store = get_run_store()
    record = store.get_run(run_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assurance run '{run_id}' not found.",
        )
    return record.model_dump(mode="json")


@router.get("/assurance/runs/{run_id}/evidence")
def get_assurance_run_evidence(run_id: str) -> dict[str, Any]:
    """Fetches evidence lineage records for a specific assurance run."""
    store = get_run_store()
    record = store.get_run(run_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assurance run '{run_id}' not found.",
        )

    evidence_list: list[EvidenceRecord] = store.get_evidence(run_id)
    return {
        "run_id": run_id,
        "evidence_count": len(evidence_list),
        "evidence": [ev.model_dump(mode="json") for ev in evidence_list],
    }
