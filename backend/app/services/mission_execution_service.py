import logging
from typing import Any

from app.agents.supervisor import AssuranceSupervisor
from app.api.assurance import resolve_demo_package
from app.messaging.models import AssuranceJob
from app.models.mission import AssuranceMission, MissionStatus
from app.services.mission_transitions import apply_transition
from app.storage import AssuranceRunStatus, get_run_store
from app.storage.interfaces import LeaseOutcome

logger = logging.getLogger(__name__)


class MissionExecutionService:
    """Authoritative execution service for Mission V2 10-stage assurance pipeline."""

    @staticmethod
    def execute_job(job: AssuranceJob) -> dict[str, Any]:
        """Executes a Mission V2 assurance job using an atomic store-level lease so
        duplicate Pub/Sub delivery (or two workers racing on the same mission) can
        never both begin executing it concurrently."""
        store = get_run_store()
        mission_id = job.run_id

        outcome, record = store.acquire_lease(mission_id, job.job_id)

        if outcome == LeaseOutcome.NOT_FOUND:
            logger.error("MISSION_LOADED_FAILED: Mission '%s' not found in store.", mission_id)
            return {"status": "FAILED", "mission_id": mission_id, "error": "MISSION_NOT_FOUND"}

        if outcome == LeaseOutcome.ALREADY_TERMINAL:
            status_str = record.status.value if hasattr(record.status, "value") else str(record.status)
            logger.info(
                "EXECUTION_LEASE_SKIPPED: Mission '%s' is in terminal status '%s'. Skipping job '%s'.",
                mission_id,
                status_str,
                job.job_id,
            )
            store.log_event(
                run_id=mission_id,
                stage=status_str,
                message=f"Idempotency check: Job '{job.job_id}' received for terminal mission status [{status_str}].",
                details={"job_id": job.job_id},
            )
            res_status = "SKIPPED_ALREADY_COMPLETED" if status_str == "COMPLETED" else "SKIPPED_ALREADY_TERMINAL"
            return {"status": res_status, "mission_id": mission_id}

        if outcome == LeaseOutcome.ALREADY_LEASED:
            logger.info("EXECUTION_LEASE_LOCKED: Mission '%s' is actively leased by another worker delivery.", mission_id)
            return {"status": "RUNNING", "mission_id": mission_id, "locked": True}

        if outcome == LeaseOutcome.INVALID_TRANSITION:
            logger.error("EXECUTION_LEASE_INVALID_TRANSITION: Mission '%s' could not transition to RUNNING.", mission_id)
            return {"status": "FAILED", "mission_id": mission_id, "error": "INVALID_TRANSITION"}

        assert outcome == LeaseOutcome.ACQUIRED
        assert record is not None

        meta = record.metadata if isinstance(record.metadata, dict) else {}
        meta["job_type"] = job.job_type
        record.metadata = meta
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

        def _cancellation_requested() -> bool:
            """Re-reads the mission record so cooperative cancellation requested via
            POST /missions/{id}/cancel while the supervisor is mid-flight is honored
            between stages."""
            current = store.get_run(mission_id)
            if current is None:
                return False
            current_meta = current.metadata if isinstance(current.metadata, dict) else {}
            return bool(current.cancellation_requested or current_meta.get("cancellation_requested"))

        try:
            left_pkg = resolve_demo_package(mission.source_a.source_id)
            right_pkg = resolve_demo_package(mission.source_b.source_id) if mission.source_b else None

            supervisor = AssuranceSupervisor(store)
            result = supervisor.run_mission(mission, left_pkg, right_pkg, cancellation_check=_cancellation_requested)

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
            # Routed through apply_transition so a mission already CANCELLED (e.g. a
            # cancel request that raced in during execution) is never overwritten with
            # FAILED by this late-arriving worker error.
            transition = apply_transition(
                store,
                mission_id,
                AssuranceRunStatus.FAILED,
                status_reason=f"Supervisor Execution Failure: {exc}",
                workflow_stage="FAILED",
                extra_metadata={"last_error": str(exc)},
            )
            store.log_event(
                run_id=mission_id,
                stage="FAILED",
                message=f"Mission execution failed: {exc}",
                details={"error": str(exc), "status_write_applied": transition.ok},
            )
            return {"status": "FAILED", "mission_id": mission_id, "error": str(exc)}

