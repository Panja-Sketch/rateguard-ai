import threading
from datetime import UTC, datetime

from app.storage.interfaces import BaseRunStore
from app.storage.models import AssuranceRunRecord, EvidenceRecord, RunEvent


class InMemoryRunStore(BaseRunStore):
    """Thread-safe in-memory store adapter for development and unit testing."""

    def __init__(self) -> None:
        self._runs: dict[str, AssuranceRunRecord] = {}
        self._events: dict[str, list[RunEvent]] = {}
        self._evidence: dict[str, list[EvidenceRecord]] = {}
        self._lock = threading.Lock()

    def create_run(self, record: AssuranceRunRecord) -> AssuranceRunRecord:
        with self._lock:
            self._runs[record.run_id] = record
            self._events[record.run_id] = []
            self._evidence[record.run_id] = []
            return record

    def get_run(self, run_id: str) -> AssuranceRunRecord | None:
        with self._lock:
            return self._runs.get(run_id)

    def update_run(self, record: AssuranceRunRecord) -> AssuranceRunRecord:
        with self._lock:
            record.updated_at = datetime.now(UTC)
            self._runs[record.run_id] = record
            return record

    def add_event(self, run_id: str, event: RunEvent) -> RunEvent:
        with self._lock:
            if run_id not in self._events:
                self._events[run_id] = []
            self._events[run_id].append(event)
            return event

    def get_events(self, run_id: str) -> list[RunEvent]:
        with self._lock:
            return list(self._events.get(run_id, []))

    def add_evidence(self, run_id: str, evidence: EvidenceRecord) -> EvidenceRecord:
        with self._lock:
            if run_id not in self._evidence:
                self._evidence[run_id] = []
            self._evidence[run_id].append(evidence)
            if run_id in self._runs:
                if evidence.evidence_id not in self._runs[run_id].evidence_refs:
                    self._runs[run_id].evidence_refs.append(evidence.evidence_id)
            return evidence

    def get_evidence(self, run_id: str) -> list[EvidenceRecord]:
        with self._lock:
            return list(self._evidence.get(run_id, []))
