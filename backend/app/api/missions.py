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
    ValidationIssue,
)
from app.services.mission_transitions import (
    MAX_RETRY_ATTEMPTS,
    apply_transition,
    eligible_actions,
    is_deletable,
    is_retryable,
)
from app.services.validation_service import MissionValidationService
from app.storage import AssuranceRunRecord, AssuranceRunStatus, get_run_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["assurance-missions-v2"])


class CreateMissionRequest(BaseModel):
    """Payload for creating and initiating an Assurance Mission V2.

    Source selection is never silently defaulted: `source_a` is required, and
    `source_b` must be explicitly provided (or explicitly omitted/null for
    RUNTIME_VERIFICATION mode) — mode-specific requirements are enforced by
    MissionValidationService.validate_mission, not by a payload default.
    """

    name: str = Field(default="Pricing Release Assurance Mission")
    mode: ComparisonMode = Field(default=ComparisonMode.RELEASE_CONFORMANCE)
    product: str = Field(default="AZ_HO3")
    jurisdiction: str = Field(default="Arizona")
    effective_period_start: str = Field(default="2026-09-01")
    portfolio_dataset: str = Field(default="az_ho3_2026_synthetic_50k.csv")
    gating_policy: str = Field(default="STRICT_ZERO_DRIFT")

    source_a: PricingSourceRef | None = Field(
        default=None,
        description="Authoritative pricing intent source. Required for all modes; must be explicitly selected by the user.",
    )
    source_b: PricingSourceRef | None = Field(
        default=None,
        description="Target/comparison source. Required for RELEASE_CONFORMANCE and EQUIVALENCE; must be null for RUNTIME_VERIFICATION.",
    )
    runtime_connector: RuntimeConnectorConfig | None = None
    disposable_sample_run: bool = Field(default=False)
    is_demo_sample: bool = Field(
        default=False,
        description="Set only when the user explicitly opted into a built-in demo/sample source or rating connector.",
    )


def _validation_error(message: str, issues: list) -> HTTPException:
    """Structured 422 validation error: field, code, and actionable message per issue."""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "message": message,
            "issues": [i.model_dump(mode="json") if hasattr(i, "model_dump") else i for i in issues],
        },
    )


@router.post("/connectors/test")
def test_rating_api_connector(config: RuntimeConnectorConfig) -> dict[str, Any]:
    """Validates and tests connection to an external Black-Box Rating API endpoint."""
    issues = MissionValidationService.validate_runtime_connector(config)
    if issues:
        raise _validation_error("Connector validation failed.", issues)

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

    Source selection is never silently substituted with a demo/sample package: `source_a`
    is required for every mode, and mode-specific requirements for `source_b` /
    `runtime_connector` are enforced below by MissionValidationService — not by payload
    defaults.
    """
    if req.source_a is None:
        raise _validation_error(
            "Mission validation failed.",
            [
                ValidationIssue(
                    field="source_a",
                    code="REQUIRED",
                    message="Authoritative Pricing Intent (Source A) must be explicitly selected.",
                )
            ],
        )

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
        is_demo_sample=req.is_demo_sample,
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
        raise _validation_error("Mission validation failed.", val_issues)

    store = get_run_store()
    now = datetime.now(UTC)

    # Persist QUEUED mission state
    record = AssuranceRunRecord(
        run_id=mission_id,
        status=AssuranceRunStatus.QUEUED,
        workflow_stage="QUEUED",
        left_package_id=req.source_a.source_id,
        right_package_id=req.source_b.source_id if req.source_b else None,
        created_at=now,
        updated_at=now,
        queued_at=now,
        attempt_number=1,
        metadata={
            "name": mission.name,
            "mode": mission.mode.value,
            "correlation_id": correlation_id,
            "disposable_sample_run": mission.disposable_sample_run,
            "is_demo_sample": mission.is_demo_sample,
            "record_type": "ASSURANCE_MISSION_V2",
            "schema_version": 2,
            "mission_object": mission.model_dump(mode="json"),
            "source_a": req.source_a.source_id,
            "source_b": req.source_b.source_id if req.source_b else None,
            "attempt_number": 1,
            "cancellation_requested": False,
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
                "status_reason": r.status_reason,
                "current_stage": r.current_stage,
                "workflow_stage": r.workflow_stage,
                "attempt_number": r.attempt_number,
                "mode": mode_val,
                # No hidden defaults: a mission with no source_b (e.g. Runtime Verification)
                # displays as null, never as the bundled defective sample package.
                "source_a": r.left_package_id or meta.get("source_a"),
                "source_b": r.right_package_id or meta.get("source_b"),
                "runtime_connector_name": (
                    (meta.get("mission_object") or {}).get("runtime_connector") or {}
                ).get("connector_name")
                if isinstance(meta.get("mission_object"), dict)
                else None,
                "decision": r.decision or "UNKNOWN",
                "summary": r.summary or "",
                "disposable_sample_run": meta.get("disposable_sample_run", False),
                "is_demo_sample": meta.get("is_demo_sample", meta.get("disposable_sample_run", False)),
                "eligible_actions": eligible_actions(r),
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
    meta = record.metadata if isinstance(record.metadata, dict) else {}
    return {
        "mission_id": record.run_id,
        "status": record.status.value if hasattr(record.status, "value") else str(record.status),
        "status_reason": record.status_reason,
        "current_stage": record.current_stage,
        "workflow_stage": record.workflow_stage,
        "attempt_number": record.attempt_number,
        "cancellation_requested": record.cancellation_requested,
        "queued_at": record.queued_at.isoformat() if record.queued_at else None,
        "started_at": record.started_at.isoformat() if record.started_at else None,
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
        "decision": record.decision,
        "summary": record.summary,
        "updated_at": record.updated_at.isoformat() if hasattr(record.updated_at, "isoformat") else str(record.updated_at),
        "metadata": meta,
        "is_demo_sample": meta.get("is_demo_sample", meta.get("disposable_sample_run", False)),
        "eligible_actions": eligible_actions(record),
        "result": res_dict,
    }


@router.post("/missions/{mission_id}/cancel")
def cancel_assurance_mission(mission_id: str) -> dict[str, Any]:
    """Cancels a mission. QUEUED/VALIDATING/WAITING_RETRY/DRAFT transition directly to
    CANCELLED. RUNNING missions instead set `cancellation_requested`, which the worker/
    supervisor checks cooperatively between stages before continuing. Idempotent: a
    duplicate cancel request on an already-CANCELLED mission returns the current state
    rather than erroring.
    """
    from app.services.mission_transitions import (
        CANCELLABLE_STATUSES,
        COOPERATIVE_CANCELLABLE_STATUSES,
        DIRECT_CANCELLABLE_STATUSES,
    )

    store = get_run_store()
    record = store.get_run(mission_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assurance mission '{mission_id}' not found.",
        )

    status_str = record.status.value if hasattr(record.status, "value") else str(record.status)

    if status_str == "CANCELLED":
        # Idempotent: return current state rather than erroring on a duplicate request.
        return {"mission_id": mission_id, "status": "CANCELLED", "message": "Mission is already cancelled."}

    if status_str not in CANCELLABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "MISSION_NOT_CANCELLABLE",
                "message": f"Mission '{mission_id}' in status '{status_str}' cannot be cancelled.",
            },
        )

    if status_str in DIRECT_CANCELLABLE_STATUSES:
        result = apply_transition(
            store,
            mission_id,
            AssuranceRunStatus.CANCELLED,
            status_reason="Cancelled by user request.",
            workflow_stage="CANCELLED",
        )
        if not result.ok:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result.error)
        store.log_event(run_id=mission_id, stage="CANCELLED", message="Mission cancelled by user request.")
        return {"mission_id": mission_id, "status": "CANCELLED", "message": "Mission cancelled successfully."}

    # RUNNING: cooperative cancellation — request only, worker/supervisor honors it
    # between stages and never overwrites CANCELLED with a later COMPLETED result.
    assert status_str in COOPERATIVE_CANCELLABLE_STATUSES
    if not isinstance(record.metadata, dict):
        record.metadata = {}
    record.metadata["cancellation_requested"] = True
    record.cancellation_requested = True
    record.status_reason = "Cancellation requested; awaiting cooperative stop by worker."
    store.update_run(record)
    store.log_event(run_id=mission_id, stage=status_str, message="Cancellation requested for running mission.")
    return {
        "mission_id": mission_id,
        "status": status_str,
        "cancellation_requested": True,
        "message": "Cancellation requested. Mission will stop at the next checkpoint between stages.",
    }


@router.post("/missions/{mission_id}/retry")
def retry_assurance_mission(mission_id: str) -> dict[str, Any]:
    """Retries an eligible FAILED or WAITING_RETRY mission: increments attempt_number,
    preserves prior evidence/failure history, and re-queues via Pub/Sub with the same
    idempotent job dispatch used for the original mission (worker leasing prevents
    duplicate concurrent execution)."""
    store = get_run_store()
    record = store.get_run(mission_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assurance mission '{mission_id}' not found.",
        )

    if not is_retryable(record):
        status_str = record.status.value if hasattr(record.status, "value") else str(record.status)
        meta = record.metadata if isinstance(record.metadata, dict) else {}
        attempt_number = int(meta.get("attempt_number", record.attempt_number) or 1)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "MISSION_NOT_RETRYABLE",
                "message": (
                    f"Mission '{mission_id}' in status '{status_str}' (attempt {attempt_number}/"
                    f"{MAX_RETRY_ATTEMPTS}) is not eligible for retry."
                ),
            },
        )

    meta = record.metadata if isinstance(record.metadata, dict) else {}
    next_attempt = int(meta.get("attempt_number", record.attempt_number) or 1) + 1
    correlation_id = meta.get("correlation_id") or f"CORR-{uuid.uuid4().hex[:8].upper()}"
    observed_status = record.status.value if hasattr(record.status, "value") else str(record.status)

    # Compare-and-set on the status this handler observed: if a concurrent retry
    # request already moved the mission off that status, refuse rather than
    # double-publish a duplicate Pub/Sub job with the same bumped attempt number.
    result = apply_transition(
        store,
        mission_id,
        AssuranceRunStatus.QUEUED,
        status_reason=f"Retry attempt {next_attempt} queued by user request.",
        workflow_stage="QUEUED",
        extra_metadata={"attempt_number": next_attempt, "cancellation_requested": False},
        expected_current_status=observed_status,
    )
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result.error)

    record = result.record
    record.attempt_number = next_attempt
    record.cancellation_requested = False
    record.queued_at = datetime.now(UTC)
    store.update_run(record)

    store.log_event(
        run_id=mission_id,
        stage="QUEUED",
        message=f"Mission retry attempt {next_attempt} queued (Correlation ID: {correlation_id}).",
        details={"attempt_number": next_attempt},
    )

    left_source_id = meta.get("source_a") or record.left_package_id
    right_source_id = meta.get("source_b") or record.right_package_id

    publisher = get_message_publisher()
    job = AssuranceJob(
        job_id=f"JOB-{mission_id}-RETRY{next_attempt}",
        run_id=mission_id,
        job_type="ASSURANCE_MISSION_V2",
        schema_version=2,
        correlation_id=correlation_id,
        left_source_id=left_source_id,
        right_source_id=right_source_id,
        left_package_id=left_source_id,
        right_package_id=right_source_id,
        include_portfolio_analysis=True,
    )

    try:
        publisher.publish_assurance_job(job)
    except Exception as pub_err:
        logger.error("Failed to publish retry job for mission '%s': %s", mission_id, pub_err)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "MISSION_QUEUE_UNAVAILABLE",
                "message": f"Retry was recorded but could not be queued for execution: {pub_err}",
                "mission_id": mission_id,
            },
        ) from pub_err

    return {
        "mission_id": mission_id,
        "status": "QUEUED",
        "attempt_number": next_attempt,
        "message": f"Mission retry attempt {next_attempt} queued for execution.",
    }


@router.post("/missions/{mission_id}/archive")
def archive_assurance_mission(mission_id: str) -> dict[str, Any]:
    """Soft-archives a terminal (COMPLETED/FAILED/CANCELLED/NEEDS_REVIEW) assurance
    mission audit record. Does not force COMPLETED on missions that failed or were
    cancelled — the underlying status is preserved and only `archived`/ARCHIVED
    bookkeeping is applied."""
    store = get_run_store()
    record = store.get_run(mission_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assurance mission '{mission_id}' not found.",
        )

    status_str = record.status.value if hasattr(record.status, "value") else str(record.status)
    from app.services.mission_transitions import ARCHIVABLE_STATUSES

    meta = record.metadata if isinstance(record.metadata, dict) else {}
    if status_str not in ARCHIVABLE_STATUSES or meta.get("archived"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "MISSION_ARCHIVE_NOT_ALLOWED",
                "message": f"Mission '{mission_id}' in status '{status_str}' cannot be archived.",
            },
        )

    result = apply_transition(
        store,
        mission_id,
        AssuranceRunStatus.ARCHIVED,
        workflow_stage="ARCHIVED",
        extra_metadata={"archived": True},
    )
    if not result.ok:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=result.error)

    return {"mission_id": mission_id, "status": "ARCHIVED", "message": "Mission audit record archived successfully."}


@router.delete("/missions/{mission_id}")
def delete_assurance_mission(mission_id: str) -> dict[str, Any]:
    """Permanently deletes eligible disposable missions only: DRAFT, CANCELLED, or
    FAILED demo/sample missions. Completed or otherwise compliance-retained missions
    must be archived instead (409). Historical legacy RUN-* records are never deleted
    through this endpoint. Success is reported only after the backing store confirms
    the record no longer exists.
    """
    store = get_run_store()
    record = store.get_run(mission_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assurance mission '{mission_id}' not found.",
        )

    if mission_id.startswith("RUN-") and not mission_id.startswith("RUN-DEMO"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "MISSION_DELETE_NOT_ALLOWED",
                "message": f"Historical legacy run '{mission_id}' is retained for compliance auditability.",
            },
        )

    if not is_deletable(record):
        status_str = record.status.value if hasattr(record.status, "value") else str(record.status)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "MISSION_DELETE_NOT_ALLOWED",
                "message": (
                    f"Mission '{mission_id}' in status '{status_str}' is retained for compliance "
                    f"auditability. Only disposable DRAFT/CANCELLED missions or eligible FAILED demo "
                    f"missions may be deleted. Use POST /api/v1/missions/{mission_id}/archive instead."
                ),
            },
        )

    deleted = store.delete_run(mission_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "MISSION_DELETE_FAILED",
                "message": f"Mission '{mission_id}' could not be confirmed deleted by the backing store.",
            },
        )

    return {"mission_id": mission_id, "status": "DELETED", "message": f"Disposable mission '{mission_id}' deleted successfully."}
