import uuid

from app.messaging.interfaces import BaseMessagePublisher
from app.messaging.models import AssuranceJob


class InMemoryPublisher(BaseMessagePublisher):
    """In-memory message publisher for unit testing and local development."""

    def __init__(self) -> None:
        self.published_jobs: list[tuple[str, AssuranceJob]] = []

    def publish_assurance_job(self, job: AssuranceJob) -> str:
        msg_id = f"MSG-MEM-{uuid.uuid4().hex[:8].upper()}"
        self.published_jobs.append((msg_id, job))
        return msg_id
