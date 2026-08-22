import logging
from typing import Any

from app.agents.runner import AgenticAssuranceRunner
from app.ipir.package import IPIRPackage
from app.messaging.models import AssuranceJob
from app.services.ingestion_service import PricingSourceIngestionService
from app.storage import AssuranceRunRecord, AssuranceRunStatus, BaseRunStore, get_run_store

logger = logging.getLogger(__name__)


class AssuranceWorker:
    """Idempotent background worker processing assurance jobs."""

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
        run_id = job.run_id
        record = self.run_store.get_run(run_id)

        if not record:
            # Create initial run record if not present
            record = AssuranceRunRecord(
                run_id=run_id,
                status=AssuranceRunStatus.QUEUED,
                workflow_stage="QUEUED",
                metadata={"job_id": job.job_id},
            )
            self.run_store.save_run(record)

        # Idempotency check: If run is already COMPLETED, skip re-execution
        if record.status == AssuranceRunStatus.COMPLETED:
            logger.info("Run '%s' is already COMPLETED. Skipping job '%s'.", run_id, job.job_id)
            self.run_store.log_event(
                run_id=run_id,
                stage="COMPLETED",
                message=f"Idempotency check: Job '{job.job_id}' received for completed run.",
                details={"job_id": job.job_id},
            )
            return {"status": "SKIPPED_ALREADY_COMPLETED", "run_id": run_id}

        # Transition to PROCESSING
        self.run_store.update_run_status(
            run_id=run_id,
            status=AssuranceRunStatus.PROCESSING,
            workflow_stage="PROCESSING",
        )
        self.run_store.log_event(
            run_id=run_id,
            stage="PROCESSING",
            message=f"Assurance Worker started processing job '{job.job_id}'.",
            details={"requested_model": job.requested_model},
        )

        try:
            # 1. Source Compilation / Package Resolution
            canonical_pkg: IPIRPackage | None = None
            defective_pkg: IPIRPackage | None = None

            if job.left_source_id:
                self.run_store.update_run_status(
                    run_id=run_id,
                    status=AssuranceRunStatus.PROCESSING,
                    workflow_stage="COMPILING_SOURCES",
                )
                self.run_store.log_event(
                    run_id=run_id,
                    stage="COMPILING_SOURCES",
                    message="Compiling canonical IPIR from ingested source ID.",
                    details={"source_id": job.left_source_id},
                )
                res_left = self.ingestion_service.compile_source(job.left_source_id)
                canonical_pkg = res_left.ipir_package
            elif job.left_package_id:
                from app.api.assurance import resolve_demo_package

                canonical_pkg = resolve_demo_package(job.left_package_id)

            if job.right_source_id:
                self.run_store.log_event(
                    run_id=run_id,
                    stage="COMPILING_SOURCES",
                    message="Compiling defective IPIR from ingested source ID.",
                    details={"source_id": job.right_source_id},
                )
                res_right = self.ingestion_service.compile_source(job.right_source_id)
                defective_pkg = res_right.ipir_package
            elif job.right_package_id:
                from app.api.assurance import resolve_demo_package

                defective_pkg = resolve_demo_package(job.right_package_id)

            # 2. Log workflow progression stages
            for stage in ["COMPARING", "PLANNING_TESTS", "EXECUTING_TESTS", "ANALYZING_PORTFOLIO"]:
                self.run_store.update_run_status(
                    run_id=run_id,
                    status=AssuranceRunStatus.PROCESSING,
                    workflow_stage=stage,
                )
                self.run_store.log_event(
                    run_id=run_id,
                    stage=stage,
                    message=f"Executing multi-agent assurance stage: {stage}",
                )

            # 3. Execute ADK Multi-Agent Assurance Workflow
            report = self.runner.run_assurance(
                left_package=canonical_pkg,
                right_package=defective_pkg,
                run_id=run_id,
                include_portfolio_analysis=job.include_portfolio_analysis,
            )

            # 4. Update final run record & state
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
                message=f"Assurance Run COMPLETED with decision [{report.status}].",
                details={
                    "total_differences": len(report.evidence_refs),
                    "confidence": report.confidence,
                },
            )

            return {
                "status": "COMPLETED",
                "run_id": run_id,
                "decision": report.status,
            }

        except Exception as e:
            logger.exception("Assurance worker failed for run '%s': %s", run_id, e)
            error_msg = f"Assurance Worker Failure: {e}"

            self.run_store.update_run_status(
                run_id=run_id,
                status=AssuranceRunStatus.FAILED,
                workflow_stage="FAILED",
                summary=error_msg,
            )
            self.run_store.log_event(
                run_id=run_id,
                stage="FAILED",
                message=error_msg,
                details={"error_type": type(e).__name__},
            )

            return {
                "status": "FAILED",
                "run_id": run_id,
                "error": str(e),
            }
