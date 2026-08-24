import logging
from typing import Any

from app.agents.runner import AgenticAssuranceRunner
from app.ipir.package import IPIRPackage
from app.messaging.models import AssuranceJob
from app.services.ingestion_service import PricingSourceIngestionService
from app.storage import AssuranceRunRecord, AssuranceRunStatus, BaseRunStore, get_run_store

logger = logging.getLogger(__name__)


class AssuranceWorker:
    """Idempotent background worker dispatcher processing assurance jobs."""

    def __init__(
        self,
        run_store: BaseRunStore | None = None,
        runner: AgenticAssuranceRunner | None = None,
        ingestion_service: PricingSourceIngestionService | None = None,
    ) -> None:
        self.run_store = run_store or get_run_store()
        self.runner = runner or AgenticAssuranceRunner()
        self.ingestion_service = ingestion_service or PricingSourceIngestionService()

    def process_job(self, job: AssuranceJob) -> dict[str, Any]:
        """Processes an assurance job with strict idempotency and event timeline tracking."""
        logger.info("PUBSUB_RECEIVED: Worker received job '%s' (Run ID: %s, Job Type: %s)", job.job_id, job.run_id, job.job_type)

        # Route Mission V2 jobs vs Legacy RUN-* jobs
        if job.run_id.startswith("MIS-") or job.job_type == "ASSURANCE_MISSION_V2":
            if job.run_id.startswith("MIS-"):
                from app.services.mission_execution_service import MissionExecutionService

                return MissionExecutionService.execute_job(job)

        # Legacy Assurance Run Path
        return self._process_legacy_job(job)

    def _process_legacy_job(self, job: AssuranceJob) -> dict[str, Any]:
        """Handles legacy RUN-* jobs for backward compatibility."""
        run_id = job.run_id
        record = self.run_store.get_run(run_id)

        if not record:
            record = AssuranceRunRecord(
                run_id=run_id,
                status=AssuranceRunStatus.QUEUED,
                workflow_stage="QUEUED",
                metadata={"job_id": job.job_id},
            )
            self.run_store.save_run(record)

        status_str = record.status.value if hasattr(record.status, "value") else str(record.status)

        if status_str in ("COMPLETED", "FAILED", "NEEDS_REVIEW", "CANCELLED", "ARCHIVED"):
            logger.info("Legacy Run '%s' is already in terminal status '%s'. Skipping job '%s'.", run_id, status_str, job.job_id)
            res_status = "SKIPPED_ALREADY_COMPLETED" if status_str == "COMPLETED" else "SKIPPED_ALREADY_TERMINAL"
            return {"status": res_status, "run_id": run_id}

        self.run_store.update_run_status(
            run_id=run_id,
            status=AssuranceRunStatus.PROCESSING,
            workflow_stage="RUNNING",
        )

        try:
            canonical_pkg: IPIRPackage | None = None
            defective_pkg: IPIRPackage | None = None

            if job.left_source_id:
                res_left = self.ingestion_service.compile_source(job.left_source_id)
                canonical_pkg = res_left.ipir_package
            elif job.left_package_id:
                from app.api.assurance import resolve_demo_package

                canonical_pkg = resolve_demo_package(job.left_package_id)

            if job.right_source_id:
                res_right = self.ingestion_service.compile_source(job.right_source_id)
                defective_pkg = res_right.ipir_package
            elif job.right_package_id:
                from app.api.assurance import resolve_demo_package

                defective_pkg = resolve_demo_package(job.right_package_id)

            for stage in ["COMPARING", "PLANNING_TESTS", "EXECUTING_TESTS", "ANALYZING_PORTFOLIO"]:
                self.run_store.update_run_status(
                    run_id=run_id,
                    status=AssuranceRunStatus.PROCESSING,
                    workflow_stage=stage,
                )
                self.run_store.log_event(
                    run_id=run_id,
                    stage=stage,
                    message=f"Executing legacy assurance stage: {stage}",
                )

            report = self.runner.run_assurance(
                left_package=canonical_pkg,
                right_package=defective_pkg,
                run_id=run_id,
                include_portfolio_analysis=job.include_portfolio_analysis,
            )

            self.run_store.update_run_status(
                run_id=run_id,
                status=AssuranceRunStatus.COMPLETED,
                workflow_stage="COMPLETED",
                decision=report.status,
                summary=report.executive_summary,
                report=report,
            )
            self.run_store.log_event(
                run_id=run_id,
                stage="COMPLETED",
                message=f"Legacy Assurance Run COMPLETED with decision [{report.status}].",
            )

            return {
                "status": "COMPLETED",
                "run_id": run_id,
                "decision": report.status,
            }

        except Exception as e:
            logger.exception("Legacy assurance worker failed for run '%s': %s", run_id, e)
            error_msg = f"Assurance Worker Failure: {e}"

            self.run_store.update_run_status(
                run_id=run_id,
                status=AssuranceRunStatus.FAILED,
                workflow_stage="FAILED",
                summary=error_msg,
            )

            return {
                "status": "FAILED",
                "run_id": run_id,
                "error": str(e),
            }
