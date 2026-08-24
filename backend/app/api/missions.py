import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from app.adapters.runtime_connector import BlackBoxRatingApiAdapter, RatingApiConnectionError
from app.messaging import AssuranceJob, get_message_publisher
from app.models.mission import (
    AssuranceMission,
    ComparisonMode,
    MissionObjective,
    MissionStatus,
    PricingSourceRef,
    RuntimeConnectorConfig,
)
from app.services.validation_service import MissionValidationService
from app.storage import AssuranceRunRecord, AssuranceRunStatus, get_run_store

logger = logging.getLogger(__name__)
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


@router.post("/connectors/test")
def test_rating_api_connector(config: RuntimeConnectorConfig) -> dict[str, Any]:
    """Validates and tests connection to an external Black-Box Rating API endpoint."""
    issues = MissionValidationService.validate_runtime_connector(config)
    if issues:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Connector validation failed.", "issues": [i.model_dump(mode="json") for i in issues]},
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


@router.post("/missions", status_code=status.HTTP_202_ACCEPTED)
def create_assurance_mission(
    req: CreateMissionRequest,
    response: Response,
) -> dict[str, Any]:
    """Validates request synchronously, persists mission as QUEUED, publishes Pub/Sub job, and returns HTTP 202 Accepted.
    Production mission execution NEVER runs in-process inside the API Cloud Run service.
    """
    mission_id = f"MIS-{uuid.uuid4().hex[:8].upper()}"
    correlation_id = f"CORR-{uuid.uuid4().hex[:8].upper()}"

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
        created_at=datetime.now(UTC).isoformat(),
        updated_at=datetime.now(UTC).isoformat(),
        metadata={
            "correlation_id": correlation_id,
            "record_type": "ASSURANCE_MISSION_V2",
            "schema_version": 2,
        },
    )

    # Synchronous request validation (~2ms)
    val_issues = MissionValidationService.validate_mission(mission)
    if val_issues:
        mission.status = MissionStatus.FAILED
        mission.validation_issues = val_issues
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Mission validation failed.", "issues": [i.model_dump(mode="json") for i in val_issues]},
        )

    store = get_run_store()

    # Persist QUEUED mission state
    record = AssuranceRunRecord(
        run_id=mission_id,
        status=AssuranceRunStatus.QUEUED,
        workflow_stage="QUEUED",
        left_package_id=req.source_a.source_id,
        right_package_id=req.source_b.source_id if req.source_b else None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata={
            "name": mission.name,
            "mode": mission.mode.value,
            "correlation_id": correlation_id,
            "disposable_sample_run": mission.disposable_sample_run,
            "record_type": "ASSURANCE_MISSION_V2",
            "schema_version": 2,
            "mission_object": mission.model_dump(mode="json"),
            "source_a": req.source_a.source_id,
            "source_b": req.source_b.source_id if req.source_b else None,
        },
    )
    store.save_run(record)
    store.log_event(
        run_id=mission_id,
        stage="QUEUED",
        message=f"Mission accepted and queued for worker execution (Correlation ID: {correlation_id}).",
        details={"mission_id": mission_id, "correlation_id": correlation_id},
    )

    # Dispatch to Pub/Sub message publisher
    publisher = get_message_publisher()
    job = AssuranceJob(
        job_id=f"JOB-{mission_id}",
        run_id=mission_id,
        job_type="ASSURANCE_MISSION_V2",
        schema_version=2,
        correlation_id=correlation_id,
        left_source_id=req.source_a.source_id,
        right_source_id=req.source_b.source_id if req.source_b else None,
        left_package_id=req.source_a.source_id,
        right_package_id=req.source_b.source_id if req.source_b else None,
        include_portfolio_analysis=True,
    )

    try:
        publisher.publish_assurance_job(job)
    except Exception as pub_err:
        logger.error(
            "Failed to publish assurance job for mission '%s' (Correlation ID: %s): %s",
            mission_id,
            correlation_id,
            pub_err,
        )
        record.status = AssuranceRunStatus.QUEUED
        record.workflow_stage = "QUEUE_FAILED"
        if isinstance(record.metadata, dict):
            record.metadata["last_error"] = str(pub_err)
            record.metadata["error_code"] = "MISSION_QUEUE_UNAVAILABLE"
        store.update_run(record)
        store.log_event(
            run_id=mission_id,
            stage="QUEUE_FAILED",
            message=f"PubSub queue publishing failed: {pub_err}",
            details={"error": str(pub_err), "correlation_id": correlation_id},
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "MISSION_QUEUE_UNAVAILABLE",
                "message": f"The assurance mission was created but could not be queued for execution: {pub_err}",
                "mission_id": mission_id,
                "correlation_id": correlation_id,
            },
        ) from pub_err

    response.status_code = status.HTTP_202_ACCEPTED
    return {
        "mission_id": mission_id,
        "status": "QUEUED",
        "workflow_stage": "QUEUED",
        "correlation_id": correlation_id,
        "status_url": f"/api/v1/missions/{mission_id}",
    }


@router.get("/missions")
def list_assurance_missions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status_filter: str | None = Query(default=None, alias="status"),
    mode_filter: str | None = Query(default=None, alias="mode"),
    decision_filter: str | None = Query(default=None, alias="decision"),
    include_legacy: bool = Query(default=False),
) -> dict[str, Any]:
    """Lists Mission V2 assurance records with pagination and filtering."""
    store = get_run_store()
    records = store.list_runs(limit=limit + offset + 50)

    mission_list = []
    for r in records:
        meta = r.metadata if isinstance(r.metadata, dict) else {}
        is_v2 = (
            r.run_id.startswith("MIS-")
            or meta.get("record_type") == "ASSURANCE_MISSION_V2"
            or meta.get("schema_version") == 2
        )
        if not include_legacy and not is_v2:
            continue

        status_val = r.status.value if hasattr(r.status, "value") else str(r.status)
        mode_val = meta.get("mode") or "RELEASE_CONFORMANCE"

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
                "updated_at": r.updated_at.isoformat() if hasattr(r.updated_at, "isoformat") else str(r.updated_at),
                "status": status_val,
                "workflow_stage": r.workflow_stage,
                "mode": mode_val,
                "source_a": r.left_package_id or meta.get("source_a", "AZ_HO3_2026_09"),
                "source_b": r.right_package_id or meta.get("source_b", "AZ_HO3_2026_09_DEFECTIVE"),
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
        "workflow_stage": record.workflow_stage,
        "decision": record.decision,
        "summary": record.summary,
        "updated_at": record.updated_at.isoformat() if hasattr(record.updated_at, "isoformat") else str(record.updated_at),
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
    Completed audit missions are protected against permanent deletion and return HTTP 409 CONFLICT.
    """
    store = get_run_store()
    record = store.get_run(mission_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assurance mission '{mission_id}' not found.",
        )

    meta = record.metadata if isinstance(record.metadata, dict) else {}
    status_str = record.status.value if hasattr(record.status, "value") else str(record.status)

    is_disposable = (
        meta.get("disposable_sample_run", False)
        or record.run_id.startswith("RUN-DEMO")
        or record.run_id.startswith("MIS-SAMPLE")
        or status_str in ("DRAFT", "CANCELLED")
    )

    if status_str == "COMPLETED" and not is_disposable:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "MISSION_DELETE_NOT_ALLOWED",
                "message": f"Completed assurance mission '{mission_id}' is retained for compliance auditability. Use POST /api/v1/missions/{mission_id}/archive to soft-archive audit records.",
            },
        )

    # Safely remove record from store
    if hasattr(store, "_runs") and mission_id in store._runs:
        del store._runs[mission_id]

    return {"mission_id": mission_id, "status": "DELETED", "message": f"Disposable mission '{mission_id}' deleted successfully."}
