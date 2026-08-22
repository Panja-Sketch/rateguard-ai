from unittest.mock import MagicMock

from app.messaging import (
    AssuranceJob,
    AssuranceWorker,
    InMemoryPublisher,
    PubSubPublisher,
    get_message_publisher,
)
from app.storage import AssuranceRunRecord, AssuranceRunStatus, InMemoryRunStore


def test_assurance_job_serialization():
    """Tests AssuranceJob serialization and deserialization."""
    job = AssuranceJob(
        job_id="JOB-12345",
        run_id="RUN-99999",
        left_package_id="AZ_HO3_2026_09",
        right_package_id="AZ_HO3_2026_09_DEFECTIVE",
    )

    json_data = job.model_dump_json()
    deserialized = AssuranceJob.model_validate_json(json_data)

    assert deserialized.job_id == "JOB-12345"
    assert deserialized.run_id == "RUN-99999"
    assert deserialized.left_package_id == "AZ_HO3_2026_09"


def test_in_memory_publisher():
    """Tests InMemoryPublisher publishing and tracking."""
    pub = InMemoryPublisher()
    job = AssuranceJob(job_id="JOB-01", run_id="RUN-01")

    msg_id = pub.publish_assurance_job(job)
    assert msg_id.startswith("MSG-MEM-")
    assert len(pub.published_jobs) == 1
    assert pub.published_jobs[0][1].job_id == "JOB-01"


def test_pubsub_publisher_mocked():
    """Tests PubSubPublisher using a mocked Pub/Sub client."""
    mock_client = MagicMock()
    mock_future = MagicMock()
    mock_future.result.return_value = "1234567890"
    mock_client.publish.return_value = mock_future

    pub = PubSubPublisher(publisher_client=mock_client)
    job = AssuranceJob(job_id="JOB-02", run_id="RUN-02")

    msg_id = pub.publish_assurance_job(job)
    assert msg_id == "1234567890"
    assert mock_client.publish.called


def test_assurance_worker_execution():
    """Tests AssuranceWorker processing an assurance job."""
    store = InMemoryRunStore()
    runner = MagicMock()
    mock_report = MagicMock()
    mock_report.status = "BLOCK_DEPLOYMENT"
    mock_report.executive_summary = "Defects found"
    mock_report.evidence_refs = []
    mock_report.confidence = 1.0
    runner.run_assurance.return_value = mock_report

    worker = AssuranceWorker(run_store=store, runner=runner)
    job = AssuranceJob(
        job_id="JOB-100",
        run_id="RUN-100",
        left_package_id="AZ_HO3_2026_09",
        right_package_id="AZ_HO3_2026_09_DEFECTIVE",
    )

    res = worker.process_job(job)

    assert res["status"] == "COMPLETED"
    assert res["decision"] == "BLOCK_DEPLOYMENT"

    run_record = store.get_run("RUN-100")
    assert run_record is not None
    assert run_record.status == AssuranceRunStatus.COMPLETED

    events = store.get_events("RUN-100")
    assert len(events) >= 5


def test_assurance_worker_idempotency_skips_completed():
    """Verifies AssuranceWorker skips execution if run is already COMPLETED."""
    store = InMemoryRunStore()
    runner = MagicMock()

    # Pre-populate run record as COMPLETED
    record = AssuranceRunRecord(
        run_id="RUN-200",
        status=AssuranceRunStatus.COMPLETED,
        workflow_stage="COMPLETED",
    )
    store.save_run(record)

    worker = AssuranceWorker(run_store=store, runner=runner)
    job = AssuranceJob(job_id="JOB-200", run_id="RUN-200")

    res = worker.process_job(job)

    assert res["status"] == "SKIPPED_ALREADY_COMPLETED"
    assert not runner.run_assurance.called


def test_factory_returns_memory_publisher_by_default():
    """Verifies factory returns InMemoryPublisher when async is disabled."""
    pub = get_message_publisher()
    assert isinstance(pub, InMemoryPublisher)
