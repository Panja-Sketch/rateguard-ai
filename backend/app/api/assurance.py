import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.agents import AgenticAssuranceRunner
from app.api.sources import _registered_sources
from app.core.config import get_data_dir, get_settings
from app.ipir.package import IPIRPackage
from app.messaging import AssuranceJob, get_message_publisher
from app.services.ingestion_service import PricingSourceIngestionService
from app.services.scenario_service import (
    DEMO_SCENARIOS_CATALOG,
    derive_scenario_package,
)
from app.storage import AssuranceRunRecord, AssuranceRunStatus, EvidenceRecord, get_run_store

router = APIRouter(prefix="/api/v1", tags=["assurance"])
_ingestion_service = PricingSourceIngestionService()
_ephemeral_packages: dict[str, IPIRPackage] = {}


class AssuranceRunRequest(BaseModel):
    """Request payload for starting an autonomous pricing assurance workflow."""

    left_package_id: str = Field(
        default="AZ_HO3_2026_09", description="Canonical spec/package identifier"
    )
    right_package_id: str = Field(
        default="AZ_HO3_2026_09_DEFECTIVE", description="Target spec/package identifier"
    )
    left_source_id: str | None = Field(
        default=None, description="Optional registered source ID for left pricing model"
    )
    right_source_id: str | None = Field(
        default=None, description="Optional registered source ID for right pricing model"
    )
    include_portfolio_analysis: bool = Field(
        default=True, description="Include 50K portfolio exposure analysis"
    )
    portfolio_csv_path: str | None = Field(
        default=None, description="Optional custom synthetic portfolio CSV path"
    )
    async_execution: bool | None = Field(
        default=None, description="Explicitly request async Pub/Sub execution mode"
    )


def resolve_demo_package(package_id: str) -> IPIRPackage:
    """Resolves allowed demo package IDs safely without exposing arbitrary filesystem paths."""
    if package_id in _ephemeral_packages:
        return _ephemeral_packages[package_id]

    data_dir = get_data_dir()
    canonical_file = (
        data_dir / "implementations" / "canonical" / "AZ_HO3_2026_09_ipir.json"
    )
    defective_file = (
        data_dir / "implementations" / "defective" / "AZ_HO3_2026_09_ipir.json"
    )

    if package_id == "AZ_HO3_2026_09":
        target_path = canonical_file
    elif package_id in ("AZ_HO3_2026_09_DEFECTIVE", "AZ_HO3_2026_09_defective"):
        target_path = defective_file
    elif package_id in (
        "AZ_HO3_2026_09_CLEAN",
        "AZ_HO3_2026_09_DEDUCTIBLE_DRIFT",
        "AZ_HO3_2026_09_EFFDATE_DRIFT",
        "AZ_HO3_2026_09_TERRITORY_DRIFT",
    ):
        if not canonical_file.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Canonical package file not found at {canonical_file}",
            )
        with open(canonical_file, encoding="utf-8") as f:
            canonical_pkg = IPIRPackage.model_validate_json(f.read())
        return derive_scenario_package(package_id, canonical_pkg)
    else:
        allowed = [
            "AZ_HO3_2026_09",
            "AZ_HO3_2026_09_DEFECTIVE",
            "AZ_HO3_2026_09_CLEAN",
            "AZ_HO3_2026_09_DEDUCTIBLE_DRIFT",
            "AZ_HO3_2026_09_EFFDATE_DRIFT",
            "AZ_HO3_2026_09_TERRITORY_DRIFT",
        ]
        err_msg = (
            f"Unsupported package_id '{package_id}'. "
            f"Allowed demo packages: {allowed}"
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


@router.get("/system/info")
def get_system_info() -> dict[str, Any]:
    """Returns runtime system and AI model information."""
    from app.agents.config import get_agent_config

    settings = get_settings()
    agent_config = get_agent_config()
    return {
        "gemini_model": agent_config.gemini_model,
        "gemini_model_display": "Gemini 3.7 Flash",
        "agent_framework": "Google GenAI SDK",
        "agent_provider": "Google Vertex AI",
        "agent_supervisor": "Google GenAI SDK Structured-Decision Supervisor",
        "ipir_version": "0.1",
        "cloud_project": settings.google_cloud_project,
        "region": settings.google_cloud_region,
        "run_store": agent_config.run_store,
        "bigquery_enabled": settings.bigquery_enabled,
    }


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
                "name": "Arizona Homeowners HO3 Rate Plan (Defective Multi-Defect Target)",
                "type": "DEFECTIVE_TARGET",
            },
            {
                "id": "AZ_HO3_2026_09_CLEAN",
                "name": "Arizona Homeowners HO3 Rate Plan (Compliant / Clean Target)",
                "type": "CLEAN_TARGET",
            },
            {
                "id": "AZ_HO3_2026_09_DEDUCTIBLE_DRIFT",
                "name": "Arizona Homeowners HO3 Rate Plan (Deductible Drift Target)",
                "type": "DEDUCTIBLE_DRIFT_TARGET",
            },
            {
                "id": "AZ_HO3_2026_09_EFFDATE_DRIFT",
                "name": "Arizona Homeowners HO3 Rate Plan (Effective Date Drift Target)",
                "type": "EFFDATE_DRIFT_TARGET",
            },
            {
                "id": "AZ_HO3_2026_09_TERRITORY_DRIFT",
                "name": "Arizona Homeowners HO3 Rate Plan (Territory Drift Target)",
                "type": "TERRITORY_DRIFT_TARGET",
            },
        ]
    }


@router.get("/demo/scenarios")
def list_demo_scenarios() -> dict[str, Any]:
    """Returns ready-to-run assurance scenarios for judge demonstration."""
    return {
        "scenarios": DEMO_SCENARIOS_CATALOG,
        "count": len(DEMO_SCENARIOS_CATALOG),
    }


@router.post("/assurance/scenario-lab")
def create_scenario_lab_run() -> dict[str, Any]:
    """Obsolete Scenario Lab endpoint retired in Assurance Mission V2."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Scenario Lab has been retired in RateGuard AI Assurance Mission V2. Use POST /api/v1/missions to create assurance missions.",
    )


@router.post("/assurance/runs")
def create_assurance_run(req: AssuranceRunRequest, response: Response) -> dict[str, Any]:
    """Initiates and executes an autonomous agentic pricing assurance workflow run."""
    is_async = req.async_execution is True

    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
    job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"

    if is_async:
        # Async mode: Publish job and return 202 Accepted immediately
        response.status_code = status.HTTP_202_ACCEPTED
        store = get_run_store()
        publisher = get_message_publisher()

        record = AssuranceRunRecord(
            run_id=run_id,
            status=AssuranceRunStatus.QUEUED,
            workflow_stage="QUEUED",
            metadata={"job_id": job_id},
        )
        store.save_run(record)
        store.log_event(
            run_id=run_id,
            stage="QUEUED",
            message=f"Assurance run queued as job '{job_id}'.",
        )

        job = AssuranceJob(
            job_id=job_id,
            run_id=run_id,
            left_source_id=req.left_source_id,
            right_source_id=req.right_source_id,
            left_package_id=req.left_package_id,
            right_package_id=req.right_package_id,
            include_portfolio_analysis=req.include_portfolio_analysis,
        )

        pub_msg_id = publisher.publish_assurance_job(job)

        return {
            "run_id": run_id,
            "status": "QUEUED",
            "job_id": job_id,
            "message_id": pub_msg_id,
            "message": "Assurance run queued successfully for asynchronous background execution.",
        }

    # Sync mode: Resolve packages & execute synchronously
    left_pkg: IPIRPackage | None = None
    right_pkg: IPIRPackage | None = None

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

    store = get_run_store()
    runner = AgenticAssuranceRunner(run_store=store)

    result = runner.run_assurance(
        left_package=left_pkg,
        right_package=right_pkg,
        run_id=run_id,
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


@router.get("/assurance/runs")
def list_assurance_runs(limit: int = 50) -> dict[str, Any]:
    """Lists assurance runs sorted newest first with summary information."""
    from datetime import datetime
    from enum import Enum

    store = get_run_store()
    records = store.list_runs(limit=limit)

    summary_list = []
    for r in records:
        status_val = r.status.value if isinstance(r.status, Enum) else str(r.status)
        created_str = (
            r.created_at.isoformat()
            if isinstance(r.created_at, datetime)
            else str(r.created_at)
        )
        updated_str = (
            r.updated_at.isoformat()
            if isinstance(r.updated_at, datetime)
            else str(r.updated_at)
        )

        summary_list.append(
            {
                "run_id": r.run_id,
                "created_at": created_str,
                "updated_at": updated_str,
                "status": status_val,
                "workflow_stage": r.workflow_stage,
                "left_package_id": r.left_package_id,
                "right_package_id": r.right_package_id,
                "decision": r.decision,
                "summary": r.summary,
            }
        )

    return {
        "runs": summary_list,
        "count": len(summary_list),
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


@router.get("/assurance/runs/{run_id}/events")
def get_assurance_run_events(run_id: str) -> dict[str, Any]:
    """Fetches ordered workflow event timeline for a specific assurance run."""
    store = get_run_store()
    record = store.get_run(run_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assurance run '{run_id}' not found.",
        )

    events = store.get_events(run_id)
    return {
        "run_id": run_id,
        "event_count": len(events),
        "events": [e.model_dump(mode="json") for e in events],
    }


@router.get("/assurance/runs/{run_id}/result")
def get_assurance_run_result(run_id: str, response: Response) -> dict[str, Any]:
    """Fetches structured final assurance report result."""
    store = get_run_store()
    record = store.get_run(run_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assurance run '{run_id}' not found.",
        )

    if record.status in (AssuranceRunStatus.QUEUED, AssuranceRunStatus.PROCESSING):
        response.status_code = status.HTTP_202_ACCEPTED
        return {
            "run_id": run_id,
            "status": record.status.value,
            "workflow_stage": record.workflow_stage,
            "message": "Assurance run is currently processing. Poll again shortly.",
        }

    if record.status == AssuranceRunStatus.FAILED:
        return {
            "run_id": run_id,
            "status": "FAILED",
            "error_summary": record.summary or "Assurance workflow failed.",
        }

    if not record.report:
        return {
            "run_id": run_id,
            "status": record.status.value,
            "decision": record.decision,
            "summary": record.summary,
        }

    if isinstance(record.report, dict):
        res_dict = dict(record.report)
    elif hasattr(record.report, "model_dump"):
        res_dict = record.report.model_dump(mode="json")
    else:
        res_dict = dict(record.report)

    # Ensure structured sections are available from run record if not already in report
    if not res_dict.get("semantic_diff") and record.semantic_diff_summary:
        res_dict["semantic_diff"] = record.semantic_diff_summary
    if not res_dict.get("semantic_differences") and record.semantic_diff_summary:
        res_dict["semantic_differences"] = record.semantic_diff_summary.get("differences", [])
    if not res_dict.get("impact") and record.impact_summary:
        res_dict["impact"] = record.impact_summary
    if not res_dict.get("impact_analysis") and record.impact_summary:
        res_dict["impact_analysis"] = record.impact_summary
    if not res_dict.get("test_plan") and record.test_plan_summary:
        res_dict["test_plan"] = record.test_plan_summary
    if not res_dict.get("reconciliation") and record.reconciliation_summary:
        res_dict["reconciliation"] = record.reconciliation_summary
    if not res_dict.get("portfolio") and record.portfolio_summary:
        res_dict["portfolio"] = record.portfolio_summary
    if not res_dict.get("portfolio_exposure") and record.portfolio_summary:
        res_dict["portfolio_exposure"] = record.portfolio_summary
    if not res_dict.get("agent_steps") and record.agent_activity:
        res_dict["agent_steps"] = record.agent_activity
    if not res_dict.get("decision") and record.decision:
        res_dict["decision"] = record.decision

    return res_dict


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
