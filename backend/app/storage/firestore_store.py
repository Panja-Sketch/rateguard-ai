import logging
from typing import Any

from app.storage.interfaces import BaseRunStore
from app.storage.memory_store import InMemoryRunStore
from app.storage.models import AssuranceRunRecord, EvidenceRecord, RunEvent

logger = logging.getLogger(__name__)


class FirestoreRunStore(BaseRunStore):
    """Google Cloud Firestore adapter for persistent run state and evidence lineage."""

    def __init__(
        self,
        project_id: str = "rateguard-ai",
        database_id: str | None = None,
        fallback_on_error: bool = True,
    ) -> None:
        self.project_id = project_id
        self.database_id = database_id
        self.fallback_on_error = fallback_on_error
        self._fallback_store = InMemoryRunStore()
        self._db: Any = None

        try:
            from google.cloud import firestore

            kwargs: dict[str, Any] = {"project": project_id}
            if database_id:
                kwargs["database"] = database_id
            self._db = firestore.Client(**kwargs)
            logger.info("Successfully initialized Firestore client for project '%s'", project_id)
        except Exception as e:
            if fallback_on_error:
                logger.warning(
                    "Failed to initialize Firestore client (%s). Falling back to InMemoryRunStore.",
                    e,
                )
                self._db = None
            else:
                raise

    def create_run(self, record: AssuranceRunRecord) -> AssuranceRunRecord:
        self._fallback_store.create_run(record)
        if self._db is not None:
            try:
                doc_ref = self._db.collection("assurance_runs").document(record.run_id)
                doc_ref.set(record.model_dump(mode="json"))
            except Exception as e:
                logger.error("Firestore error in create_run: %s", e)
                if not self.fallback_on_error:
                    raise
        return record

    def get_run(self, run_id: str) -> AssuranceRunRecord | None:
        if self._db is not None:
            try:
                doc_ref = self._db.collection("assurance_runs").document(run_id)
                doc = doc_ref.get()
                if doc.exists:
                    return AssuranceRunRecord.model_validate(doc.to_dict())
            except Exception as e:
                logger.error("Firestore error in get_run: %s", e)
                if not self.fallback_on_error:
                    raise
        return self._fallback_store.get_run(run_id)

    def update_run(self, record: AssuranceRunRecord) -> AssuranceRunRecord:
        self._fallback_store.update_run(record)
        if self._db is not None:
            try:
                doc_ref = self._db.collection("assurance_runs").document(record.run_id)
                doc_ref.set(record.model_dump(mode="json"), merge=True)
            except Exception as e:
                logger.error("Firestore error in update_run: %s", e)
                if not self.fallback_on_error:
                    raise
        return record

    def add_event(self, run_id: str, event: RunEvent) -> RunEvent:
        self._fallback_store.add_event(run_id, event)
        if self._db is not None:
            try:
                doc_ref = (
                    self._db.collection("assurance_runs")
                    .document(run_id)
                    .collection("events")
                    .document(event.event_id)
                )
                doc_ref.set(event.model_dump(mode="json"))
            except Exception as e:
                logger.error("Firestore error in add_event: %s", e)
                if not self.fallback_on_error:
                    raise
        return event

    def get_events(self, run_id: str) -> list[RunEvent]:
        if self._db is not None:
            try:
                col_ref = (
                    self._db.collection("assurance_runs").document(run_id).collection("events")
                )
                docs = col_ref.stream()
                events = [RunEvent.model_validate(doc.to_dict()) for doc in docs]
                if events:
                    return events
            except Exception as e:
                logger.error("Firestore error in get_events: %s", e)
                if not self.fallback_on_error:
                    raise
        return self._fallback_store.get_events(run_id)

    def add_evidence(self, run_id: str, evidence: EvidenceRecord) -> EvidenceRecord:
        self._fallback_store.add_evidence(run_id, evidence)
        if self._db is not None:
            try:
                doc_ref = (
                    self._db.collection("assurance_runs")
                    .document(run_id)
                    .collection("evidence")
                    .document(evidence.evidence_id)
                )
                doc_ref.set(evidence.model_dump(mode="json"))
            except Exception as e:
                logger.error("Firestore error in add_evidence: %s", e)
                if not self.fallback_on_error:
                    raise
        return evidence

    def get_evidence(self, run_id: str) -> list[EvidenceRecord]:
        if self._db is not None:
            try:
                col_ref = (
                    self._db.collection("assurance_runs").document(run_id).collection("evidence")
                )
                docs = col_ref.stream()
                evidence_list = [EvidenceRecord.model_validate(doc.to_dict()) for doc in docs]
                if evidence_list:
                    return evidence_list
            except Exception as e:
                logger.error("Firestore error in get_evidence: %s", e)
                if not self.fallback_on_error:
                    raise
        return self._fallback_store.get_evidence(run_id)
