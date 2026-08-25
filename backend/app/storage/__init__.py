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
_global_strict_run_store: BaseRunStore | None = None


def get_run_store(*, strict: bool = False) -> BaseRunStore:
    """Factory function returning the configured RunStore adapter singleton.

    `strict=True` returns a Firestore-backed store constructed with
    `fallback_on_error=False`: a storage-layer failure raises instead of being
    silently absorbed by falling back to an empty, process-local in-memory
    store. That silent-fallback behavior is the right default for read paths
    (the public API degrading gracefully during a transient Firestore blip is
    preferable to a hard error) but is actively dangerous for the
    asynchronous worker's write path — a Firestore outage would otherwise be
    misreported as "run not found", the worker would classify a fully
    retryable failure as an unrecoverable one, and Pub/Sub push delivery would
    still be acknowledged as if processing had succeeded. See
    `app.messaging.outcomes` and `app.services.mission_execution_service` for
    the full rationale; this is the fix for the missions-stuck-in-QUEUED
    incident traced to exactly this silent-fallback pattern.

    Legacy historical read access (the lenient, `strict=False` singleton) is
    unchanged and still used by every other caller (public API routes,
    tests, demo/dev in-memory mode).

    Non-Firestore backends (`InMemoryRunStore`) have no distinct
    failure-fallback behavior to strict-ify, so both modes intentionally
    share the exact same singleton instance for that backend — otherwise a
    strict variant would be a second, independently-empty in-memory store
    that never observes state written through the lenient one, which would
    break local/dev/test usage rather than fix anything.
    """
    global _global_run_store, _global_strict_run_store

    store_type = os.getenv("RATEGUARD_RUN_STORE", "memory").lower()

    if store_type != "firestore":
        if _global_run_store is None:
            _global_run_store = InMemoryRunStore()
        return _global_run_store

    if strict:
        if _global_strict_run_store is None:
            project_id = os.getenv("RATEGUARD_GOOGLE_CLOUD_PROJECT", "rateguard-ai")
            db_id = os.getenv("RATEGUARD_FIRESTORE_DATABASE")
            _global_strict_run_store = FirestoreRunStore(
                project_id=project_id, database_id=db_id, fallback_on_error=False
            )
        return _global_strict_run_store

    if _global_run_store is None:
        project_id = os.getenv("RATEGUARD_GOOGLE_CLOUD_PROJECT", "rateguard-ai")
        db_id = os.getenv("RATEGUARD_FIRESTORE_DATABASE")
        _global_run_store = FirestoreRunStore(project_id=project_id, database_id=db_id)
    return _global_run_store


def reset_run_store() -> None:
    """Testing helper to reset global singleton store(s)."""
    global _global_run_store, _global_strict_run_store
    _global_run_store = None
    _global_strict_run_store = None


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
