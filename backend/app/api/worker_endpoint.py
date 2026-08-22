import base64
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.messaging import AssuranceJob, AssuranceWorker

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal/pubsub", tags=["internal-worker"])


class PubSubMessage(BaseModel):
    """Pub/Sub push message body format."""

    data: str = Field(description="Base64-encoded AssuranceJob JSON payload")
    message_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class PubSubPushEnvelope(BaseModel):
    """Envelope wrapper for Pub/Sub push subscription HTTP requests."""

    message: PubSubMessage
    subscription: str | None = None


@router.post("/assurance")
def process_pubsub_assurance_job(envelope: PubSubPushEnvelope) -> dict[str, Any]:
    """Internal endpoint for processing Cloud Pub/Sub push jobs via AssuranceWorker.

    Designed for authenticated invocation from Google Cloud Pub/Sub push subscriptions
    or Cloud Run service-to-service IAM invocation.
    """
    try:
        raw_bytes = base64.b64decode(envelope.message.data)
        job_dict = json.loads(raw_bytes.decode("utf-8"))
        job = AssuranceJob.model_validate(job_dict)
    except Exception as e:
        logger.error("Failed to decode Pub/Sub envelope data: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Pub/Sub job message payload: {e}",
        ) from e

    worker = AssuranceWorker()
    result = worker.process_job(job)

    return {
        "status": "ACKNOWLEDGED",
        "job_id": job.job_id,
        "run_id": job.run_id,
        "result": result,
    }
