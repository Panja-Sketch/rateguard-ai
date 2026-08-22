from abc import ABC, abstractmethod
from typing import Any

from app.storage.models import AssuranceRunRecord, AssuranceRunStatus, EvidenceRecord, RunEvent


class BaseRunStore(ABC):
    """Abstract interface for assurance run storage adapters."""

    @abstractmethod
    def create_run(self, record: AssuranceRunRecord) -> AssuranceRunRecord:
        """Creates a new assurance run record."""
        pass

    def save_run(self, record: AssuranceRunRecord) -> AssuranceRunRecord:
        """Alias/convenience for create_run/update_run."""
        if self.get_run(record.run_id):
            return self.update_run(record)
        return self.create_run(record)

    @abstractmethod
    def get_run(self, run_id: str) -> AssuranceRunRecord | None:
        """Fetches an assurance run record by ID."""
        pass

    @abstractmethod
    def update_run(self, record: AssuranceRunRecord) -> AssuranceRunRecord:
        """Updates an existing assurance run record."""
        pass

    def update_run_status(
        self,
        run_id: str,
        status: AssuranceRunStatus | str,
        workflow_stage: str | None = None,
        decision: str | None = None,
        summary: str | None = None,
        report: Any = None,
    ) -> AssuranceRunRecord:
        """Updates status and metadata for a run."""
        record = self.get_run(run_id)
        if not record:
            record = AssuranceRunRecord(run_id=run_id)

        if isinstance(status, str):
            status = AssuranceRunStatus(status)
        record.status = status

        if workflow_stage is not None:
            record.workflow_stage = workflow_stage
        if decision is not None:
            record.decision = decision
        if summary is not None:
            record.summary = summary
        if report is not None:
            record.report = report

        return self.update_run(record)

    @abstractmethod
    def add_event(self, run_id: str, event: RunEvent) -> RunEvent:
        """Appends an audit log event to a run."""
        pass

    def log_event(
        self,
        run_id: str,
        stage: str,
        message: str,
        agent_name: str = "AssuranceWorker",
        details: dict[str, Any] | None = None,
    ) -> RunEvent:
        """Logs a structured workflow milestone event."""
        import uuid
        event = RunEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:8].upper()}",
            run_id=run_id,
            stage=stage,
            agent_name=agent_name,
            action=message,
            details=details or {},
        )
        return self.add_event(run_id, event)

    @abstractmethod
    def get_events(self, run_id: str) -> list[RunEvent]:
        """Retrieves all audit events for a run."""
        pass

    @abstractmethod
    def add_evidence(self, run_id: str, evidence: EvidenceRecord) -> EvidenceRecord:
        """Persists a typed evidence lineage record."""
        pass

    @abstractmethod
    def get_evidence(self, run_id: str) -> list[EvidenceRecord]:
        """Retrieves all evidence lineage records for a run."""
        pass
