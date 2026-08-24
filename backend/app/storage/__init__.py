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

_global_run_store: BaseRunStore | None = None


def get_run_store() -> BaseRunStore:
    """Factory function returning the configured RunStore adapter singleton instance."""
    global _global_run_store
    if _global_run_store is not None:
        return _global_run_store

    store_type = os.getenv("RATEGUARD_RUN_STORE", "memory").lower()
    if store_type == "firestore":
        project_id = os.getenv("RATEGUARD_GOOGLE_CLOUD_PROJECT", "rateguard-ai")
        db_id = os.getenv("RATEGUARD_FIRESTORE_DATABASE")
        _global_run_store = FirestoreRunStore(project_id=project_id, database_id=db_id)
    else:
        _global_run_store = InMemoryRunStore()

    return _global_run_store


def reset_run_store() -> None:
    """Testing helper to reset global singleton store."""
    global _global_run_store
    _global_run_store = None


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
    "reset_run_store",
]
