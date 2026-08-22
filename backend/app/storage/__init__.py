import os

from app.storage.firestore_store import FirestoreRunStore
from app.storage.interfaces import BaseRunStore
from app.storage.memory_store import InMemoryRunStore
from app.storage.models import (
    AssuranceRunRecord,
    AssuranceRunStatus,
    EvidenceRecord,
    EvidenceType,
    RunEvent,
)

_global_memory_store: InMemoryRunStore | None = None


def get_run_store() -> BaseRunStore:
    """Factory function returning the configured RunStore adapter instance."""
    global _global_memory_store
    store_type = os.getenv("RATEGUARD_RUN_STORE", "memory").lower()
    if store_type == "firestore":
        project_id = os.getenv("RATEGUARD_GOOGLE_CLOUD_PROJECT", "rateguard-ai")
        db_id = os.getenv("RATEGUARD_FIRESTORE_DATABASE")
        return FirestoreRunStore(project_id=project_id, database_id=db_id)

    if _global_memory_store is None:
        _global_memory_store = InMemoryRunStore()
    return _global_memory_store


__all__ = [
    "AssuranceRunRecord",
    "AssuranceRunStatus",
    "BaseRunStore",
    "EvidenceRecord",
    "EvidenceType",
    "FirestoreRunStore",
    "InMemoryRunStore",
    "RunEvent",
    "get_run_store",
]
