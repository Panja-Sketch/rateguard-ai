from typing import Any

from fastapi import APIRouter, Response, status

from app.core.config import get_settings

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Health Check (legacy alias)")
async def health_check() -> dict[str, str]:
    """Backward-compatible alias for existing Cloud Run health probes. Equivalent to
    /health/live: process liveness only, zero external dependency calls."""
    return {"status": "healthy"}


@router.get("/health/live", summary="Liveness Check")
async def liveness_check() -> dict[str, str]:
    """Lightweight process liveness only. MUST NOT call Gemini, BigQuery, Firestore,
    Pub/Sub, or any other external/billable dependency — this is the fast probe Cloud
    Run uses to decide whether to keep routing traffic to this instance."""
    return {"status": "healthy"}


@router.get("/health/ready", summary="Readiness Check")
async def readiness_check(response: Response) -> dict[str, Any]:
    """Dependencies required for THIS instance to accept new work: durable run
    storage and the async execution queue. Each check uses a short timeout and
    reports a structured degraded reason on failure rather than raising. Gemini and
    BigQuery are intentionally NOT probed here (not required to accept a queued
    mission, and Gemini generation is billable) — see /api/v1/system/status for
    full diagnostics.
    """
    settings = get_settings()
    checks: dict[str, dict[str, Any]] = {}

    checks["run_store"] = _check_run_store()
    checks["message_queue"] = _check_message_queue(settings)

    overall_ready = all(c["status"] == "ok" for c in checks.values())
    if not overall_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if overall_ready else "degraded",
        "checks": checks,
    }


def _check_run_store() -> dict[str, Any]:
    try:
        from app.storage import get_run_store

        store = get_run_store()
        store_kind = type(store).__name__

        # A cheap, non-mutating reachability probe with an implicit short timeout:
        # list_runs(limit=1) already has its own try/except-with-fallback inside
        # FirestoreRunStore, so this never blocks long or raises for a real outage.
        store.list_runs(limit=1)

        db = getattr(store, "_db", "n/a")
        if store_kind == "FirestoreRunStore" and db is None:
            return {
                "status": "degraded",
                "detail": "FirestoreRunStore configured but Firestore client unavailable; "
                "falling back to in-memory store (not durable across instances).",
                "backend": store_kind,
            }
        return {"status": "ok", "backend": store_kind}
    except Exception as e:
        return {"status": "degraded", "detail": f"Run store check failed: {e}"}


def _check_message_queue(settings: Any) -> dict[str, Any]:
    if not settings.async_enabled or settings.execution_mode != "pubsub":
        return {"status": "ok", "detail": "Async Pub/Sub execution mode not enabled for this deployment."}

    if not settings.pubsub_topic or not settings.pubsub_subscription:
        return {
            "status": "degraded",
            "detail": "Pub/Sub topic/subscription not configured while execution_mode='pubsub'.",
        }

    try:
        from app.messaging import get_message_publisher

        publisher = get_message_publisher()
        return {
            "status": "ok",
            "backend": type(publisher).__name__,
            "topic": settings.pubsub_topic,
            "subscription": settings.pubsub_subscription,
        }
    except Exception as e:
        return {"status": "degraded", "detail": f"Message publisher construction failed: {e}"}
