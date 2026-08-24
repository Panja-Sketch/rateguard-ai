import logging
from datetime import UTC, datetime
from typing import Any

from app.agents.supervisor import AssuranceSupervisor
from app.api.assurance import resolve_demo_package
from app.messaging.models import AssuranceJob
from app.models.mission import AssuranceMission, MissionStatus
from app.storage import AssuranceRunStatus, get_run_store

logger = logging.getLogger(__name__)


class MissionExecutionService:
    """Authoritative execution service for Mission V2 10-stage assurance pipeline."""

    @staticmethod
    def execute_job(job: AssuranceJob) -> dict[str, Any]:
        """Executes a Mission V2 assurance job with atomic lease management and heartbeat tracking."""
        store = get_run_store()
        mission_id = job.run_id
        record = store.get_run(mission_id)

        if not record:
            logger.error("MISSION_LOADED_FAILED: Mission '%s' not found in store.", mission_id)
            return {"status": "FAILED", "mission_id": mission_id, "error": "MISSION_NOT_FOUND"}

        meta = record.metadata if isinstance(record.metadata, dict) else {}
        status_str = record.status.value if hasattr(record.status, "value") else str(record.status)

        # Idempotency / Execution Lease Check
        if status_str in ("COMPLETED", "NEEDS_REVIEW", "FAILED", "CANCELLED", "ARCHIVED"):
            logger.info("EXECUTION_LEASE_SKIPPED: Mission '%s' is in terminal status '%s'. Skipping job '%s'.", mission_id, status_str, job.job_id)
            store.log_event(
                run_id=mission_id,
                stage=status_str,
                message=f"Idempotency check: Job '{job.job_id}' received for terminal mission status [{status_str}].",
                details={"job_id": job.job_id},
            )
            res_status = "SKIPPED_ALREADY_COMPLETED" if status_str == "COMPLETED" else "SKIPPED_ALREADY_TERMINAL"
            return {"status": res_status, "mission_id": mission_id}

        # Concurrency lease: if actively RUNNING on another worker with recent heartbeat (< 120s), skip duplicate delivery
        last_hb = meta.get("last_heartbeat_at") or record.updated_at
        if status_str == "RUNNING" and last_hb:
            try:
                hb_dt = datetime.fromisoformat(last_hb) if isinstance(last_hb, str) else last_hb
                now_dt = datetime.now(UTC)
                if (now_dt - hb_dt).total_seconds() < 120:
                    logger.info("EXECUTION_LEASE_LOCKED: Mission '%s' is actively RUNNING on another worker.", mission_id)
                    return {"status": "RUNNING", "mission_id": mission_id, "locked": True}
            except Exception:
                pass

        # Acquire execution lease & transition status QUEUED -> RUNNING
        now_iso = datetime.now(UTC).isoformat()
        record.status = AssuranceRunStatus.RUNNING
        record.workflow_stage = "RUNNING"
        record.updated_at = datetime.now(UTC)
        if isinstance(record.metadata, dict):
            record.metadata["last_heartbeat_at"] = now_iso
            record.metadata["lease_owner"] = job.job_id
            record.metadata["job_type"] = job.job_type
        store.update_run(record)

        store.log_event(
            run_id=mission_id,
            stage="RUNNING",
            message=f"EXECUTION_LEASE_ACQUIRED: Worker acquired lease for job '{job.job_id}' (Correlation ID: {job.correlation_id}).",
            details={"job_id": job.job_id, "correlation_id": job.correlation_id},
        )

        mission_dict = meta.get("mission_object")
        if mission_dict and isinstance(mission_dict, dict):
            mission = AssuranceMission.model_validate(mission_dict)
        else:
            source_a_id = job.left_package_id or job.left_source_id or "AZ_HO3_2026_09"
            source_b_id = job.right_package_id or job.right_source_id
            mission = AssuranceMission(
                mission_id=mission_id,
                name=meta.get("name", "Assurance Mission"),
                mode=meta.get("mode", "RELEASE_CONFORMANCE"),
                status=MissionStatus.RUNNING,
                source_a={"source_id": source_a_id, "source_type": "SAMPLE_RELEASE", "name": "Source A"},
                source_b={"source_id": source_b_id, "source_type": "SAMPLE_RELEASE", "name": "Source B"} if source_b_id else None,
            )

        logger.info("SUPERVISOR_STARTED: Running AssuranceSupervisor for mission '%s'", mission_id)

        try:
            left_pkg = resolve_demo_package(mission.source_a.source_id)
            right_pkg = resolve_demo_package(mission.source_b.source_id) if mission.source_b else None

            supervisor = AssuranceSupervisor(store)
            result = supervisor.run_mission(mission, left_pkg, right_pkg)

            term_status = mission.status.value if hasattr(mission.status, "value") else str(mission.status)
            logger.info("MISSION_COMPLETED: Mission '%s' finished with status '%s'", mission_id, term_status)

            dec_val = (
                result.release_decision.data.status
                if result.release_decision and result.release_decision.data
                else "UNKNOWN"
            )

            return {
                "status": term_status,
                "mission_id": mission_id,
                "decision": dec_val,
            }
        except Exception as exc:
            logger.exception("SUPERVISOR_FAILED: Mission '%s' failed during execution: %s", mission_id, exc)
            record.status = AssuranceRunStatus.FAILED
            record.workflow_stage = "FAILED"
            record.summary = f"Supervisor Execution Failure: {exc}"
            if isinstance(record.metadata, dict):
                record.metadata["last_error"] = str(exc)
            store.update_run(record)
            store.log_event(
                run_id=mission_id,
                stage="FAILED",
                message=f"Mission execution failed: {exc}",
                details={"error": str(exc)},
            )
            return {"status": "FAILED", "mission_id": mission_id, "error": str(exc)}

