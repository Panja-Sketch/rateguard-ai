from abc import ABC, abstractmethod

from app.storage.models import AssuranceRunRecord, EvidenceRecord, RunEvent


class BaseRunStore(ABC):
    """Abstract interface for assurance run storage adapters."""

    @abstractmethod
    def create_run(self, record: AssuranceRunRecord) -> AssuranceRunRecord:
        """Creates a new assurance run record."""
        pass

    @abstractmethod
    def get_run(self, run_id: str) -> AssuranceRunRecord | None:
        """Fetches an assurance run record by ID."""
        pass

    @abstractmethod
    def update_run(self, record: AssuranceRunRecord) -> AssuranceRunRecord:
        """Updates an existing assurance run record."""
        pass

    @abstractmethod
    def add_event(self, run_id: str, event: RunEvent) -> RunEvent:
        """Appends an audit log event to a run."""
        pass

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

