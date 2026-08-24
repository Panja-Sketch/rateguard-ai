import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from app.adapters.runtime_connector import BlackBoxRatingApiAdapter, RatingApiConnectionError
from app.agents.supervisor import AssuranceSupervisor
from app.api.assurance import resolve_demo_package
from app.models.mission import (
    AssuranceMission,
    ComparisonMode,
    MissionObjective,
    MissionStatus,
    PricingSourceRef,
    RuntimeConnectorConfig,
)
from app.services.validation_service import MissionValidationService
from app.storage import AssuranceRunStatus, get_run_store

router = APIRouter(prefix="/api/v1", tags=["assurance-missions-v2"])


class CreateMissionRequest(BaseModel):
    """Payload for creating and initiating an Assurance Mission V2."""
    name: str = Field(default="Pricing Release Assurance Mission")
    mode: ComparisonMode = Field(default=ComparisonMode.RELEASE_CONFORMANCE)
    product: str = Field(default="AZ_HO3")
    jurisdiction: str = Field(default="Arizona")
    effective_period_start: str = Field(default="2026-09-01")
    portfolio_dataset: str = Field(default="az_ho3_2026_synthetic_50k.csv")
    gating_policy: str = Field(default="STRICT_ZERO_DRIFT")
    
    source_a: PricingSourceRef = Field(
        default_factory=lambda: PricingSourceRef(
            source_id="AZ_HO3_2026_09",
            source_type="SAMPLE_RELEASE",
            name="Arizona HO3 Actuarial Spec (Canonical Filing Intent)",
        )
    )
    source_b: PricingSourceRef | None = Field(
        default_factory=lambda: PricingSourceRef(
            source_id="AZ_HO3_2026_09_DEFECTIVE",
            source_type="SAMPLE_RELEASE",
            name="Arizona HO3 Target Rating Engine Implementation",
        )
    )
    runtime_connector: RuntimeConnectorConfig | None = None
    disposable_sample_run: bool = Field(default=False)
    async_execution: bool = Field(default=False)


@router.post("/connectors/test")
def test_rating_api_connector(config: RuntimeConnectorConfig) -> dict[str, Any]:
    """Validates and tests connection to an external Black-Box Rating API endpoint."""
    issues = MissionValidationService.validate_runtime_connector(config)
    if issues:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Connector validation failed.", "issues": [i.dict() for i in issues]},
        )

    adapter = BlackBoxRatingApiAdapter(config)
    try:
        res = adapter.test_connection()
        return res
    except RatingApiConnectionError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Test connection failed: {err}",
        ) from err


@router.post("/missions")
def create_assurance_mission(req: CreateMissionRequest, response: Response) -> dict[str, Any]:
    """Creates and starts an Assurance Mission V2."""
    mission_id = f"MIS-{uuid.uuid4().hex[:8].upper()}"

    objective = MissionObjective(
        product=req.product,
        jurisdiction=req.jurisdiction,
        effective_period_start=req.effective_period_start,
        portfolio_dataset=req.portfolio_dataset,
        gating_policy=req.gating_policy,
    )

    mission = AssuranceMission(
        mission_id=mission_id,
        name=req.name,
        mode=req.mode,
        status=MissionStatus.QUEUED,
        objective=objective,
        source_a=req.source_a,
        source_b=req.source_b,
        runtime_connector=req.runtime_connector,
        disposable_sample_run=req.disposable_sample_run,
    )

    # Perform mission validations
    val_issues = MissionValidationService.validate_mission(mission)
    if val_issues:
        mission.status = MissionStatus.FAILED
        mission.validation_issues = val_issues
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Mission validation failed.", "issues": [i.dict() for i in val_issues]},
        )

    store = get_run_store()

    # Synchronous Execution via AssuranceSupervisor
    left_pkg = resolve_demo_package(req.source_a.source_id)
    right_pkg = resolve_demo_package(req.source_b.source_id) if req.source_b else None

    supervisor = AssuranceSupervisor(store)
    result = supervisor.run_mission(mission, left_pkg, right_pkg)

    return {
        "mission_id": mission_id,
        "status": mission.status.value,
        "mode": mission.mode.value,
        "decision": result.release_decision.data.status if result.release_decision.data else "UNKNOWN",
        "result": result.dict(),
    }


@router.get("/missions")
def list_assurance_missions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    mode_filter: str | None = Query(default=None, alias="mode"),
    decision_filter: str | None = Query(default=None, alias="decision"),
) -> dict[str, Any]:
    """Lists assurance missions with pagination and filtering."""
    store = get_run_store()
    records = store.list_runs(limit=limit + offset)

    mission_list = []
    for r in records:
        meta = r.metadata if isinstance(r.metadata, dict) else {}
        mode_val = meta.get("mode") or "RELEASE_CONFORMANCE"
        status_val = r.status.value if hasattr(r.status, "value") else str(r.status)

        if status_filter and status_val.upper() != status_filter.upper():
            continue
        if mode_filter and mode_val.upper() != mode_filter.upper():
            continue
        if decision_filter and (r.decision or "").upper() != decision_filter.upper():
            continue

        mission_list.append(
            {
                "mission_id": r.run_id,
                "name": meta.get("name") or f"Assurance Mission ({r.run_id})",
                "created_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
                "status": status_val,
                "workflow_stage": r.workflow_stage,
                "mode": mode_val,
                "source_a": r.left_package_id,
                "source_b": r.right_package_id,
                "decision": r.decision or "UNKNOWN",
                "summary": r.summary or "",
                "disposable_sample_run": meta.get("disposable_sample_run", False),
            }
        )

    paginated = mission_list[offset : offset + limit]

    return {
        "missions": paginated,
        "total_count": len(mission_list),
        "limit": limit,
        "offset": offset,
    }


@router.get("/missions/{mission_id}")
def get_assurance_mission(mission_id: str) -> dict[str, Any]:
    """Retrieves full mission state and AssuranceResultV2."""
    store = get_run_store()
    record = store.get_run(mission_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assurance mission '{mission_id}' not found.",
        )

    res_dict = record.report if isinstance(record.report, dict) else {}
    return {
        "mission_id": record.run_id,
        "status": record.status.value if hasattr(record.status, "value") else str(record.status),
        "decision": record.decision,
        "summary": record.summary,
        "metadata": record.metadata,
        "result": res_dict,
    }


@router.post("/missions/{mission_id}/archive")
def archive_assurance_mission(mission_id: str) -> dict[str, Any]:
    """Soft-archives a completed assurance mission audit record."""
    store = get_run_store()
    record = store.get_run(mission_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assurance mission '{mission_id}' not found.",
        )

    record.status = AssuranceRunStatus.COMPLETED
    record.workflow_stage = "ARCHIVED"
    if isinstance(record.metadata, dict):
        record.metadata["archived"] = True

    store.update_run(record)
    return {"mission_id": mission_id, "status": "ARCHIVED", "message": "Mission audit record soft-archived successfully."}


@router.delete("/missions/{mission_id}")
def delete_assurance_mission(mission_id: str) -> dict[str, Any]:
    """Permanently deletes disposable missions (DRAFT, FAILED sample runs, CANCELLED sample runs).
    Completed audit missions are protected against permanent deletion.
    """
    store = get_run_store()
    record = store.get_run(mission_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assurance mission '{mission_id}' not found.",
        )

    meta = record.metadata if isinstance(record.metadata, dict) else {}
    is_disposable = meta.get("disposable_sample_run", False) or record.run_id.startswith("RUN-DEMO") or record.run_id.startswith("MIS-SAMPLE")
    is_failed_or_cancelled = record.status in (AssuranceRunStatus.FAILED, AssuranceRunStatus.QUEUED)

    if not is_disposable and not is_failed_or_cancelled and record.status == AssuranceRunStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Mission '{mission_id}' is a completed audit record and cannot be permanently deleted. "
                "Use POST /api/v1/missions/{id}/archive to soft-archive audit records."
            ),
        )

    # Delete record from store if memory or supported
    if hasattr(store, "_runs") and mission_id in store._runs:
        del store._runs[mission_id]

    return {"mission_id": mission_id, "status": "DELETED", "message": f"Disposable mission '{mission_id}' permanently deleted."}
