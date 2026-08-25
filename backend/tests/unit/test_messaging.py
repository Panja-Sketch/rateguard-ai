from unittest.mock import MagicMock, patch

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


def test_worker_routes_legacy_run_id_to_legacy_handler_regardless_of_job_type():
    """Legacy RUN-* jobs currently carry the AssuranceJob.job_type default
    ('ASSURANCE_MISSION_V2') because that field's default isn't legacy-aware — the
    run_id ID scheme, not job_type, must remain the authoritative dispatch key so
    these are NOT misrouted or rejected."""
    store = InMemoryRunStore()
    runner = MagicMock()
    mock_report = MagicMock()
    mock_report.status = "PASS"
    mock_report.executive_summary = "ok"
    mock_report.evidence_refs = []
    runner.run_assurance.return_value = mock_report

    worker = AssuranceWorker(run_store=store, runner=runner)
    job = AssuranceJob(job_id="JOB-LEGACY-1", run_id="RUN-LEGACY-1")  # job_type defaults to ASSURANCE_MISSION_V2

    res = worker.process_job(job)

    assert res["status"] == "COMPLETED"
    assert runner.run_assurance.called


def test_worker_rejects_mission_v2_id_with_mismatched_job_type():
    """A MIS-* run_id with a job_type other than 'ASSURANCE_MISSION_V2' is a genuine
    bug and must fail with a structured error — never silently dispatched to either
    pipeline."""
    store = InMemoryRunStore()
    store.save_run(AssuranceRunRecord(run_id="MIS-MISMATCH-1", status=AssuranceRunStatus.QUEUED))
    worker = AssuranceWorker(run_store=store, runner=MagicMock())

    job = AssuranceJob(job_id="JOB-MISMATCH-1", run_id="MIS-MISMATCH-1", job_type="SOME_OTHER_TYPE")

    res = worker.process_job(job)

    assert res["status"] == "FAILED"
    assert res["error"] == "JOB_ROUTING_MISMATCH"


def test_worker_dispatches_mission_v2_id_with_matching_job_type():
    store = InMemoryRunStore()
    store.save_run(AssuranceRunRecord(run_id="MIS-MATCH-1", status=AssuranceRunStatus.QUEUED))
    worker = AssuranceWorker(run_store=store, runner=MagicMock())

    job = AssuranceJob(job_id="JOB-MATCH-1", run_id="MIS-MATCH-1", job_type="ASSURANCE_MISSION_V2")

    with patch("app.services.mission_execution_service.MissionExecutionService.execute_job") as mock_exec:
        mock_exec.return_value = {"status": "RUNNING", "mission_id": "MIS-MATCH-1"}
        res = worker.process_job(job)

    mock_exec.assert_called_once_with(job)
    assert res["status"] == "RUNNING"


def test_factory_returns_memory_publisher_when_local():
    """Verifies factory returns InMemoryPublisher when execution_mode is local or async is disabled."""
    with patch("app.messaging.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.execution_mode = "local"
        mock_settings.async_enabled = False
        mock_get_settings.return_value = mock_settings

        pub = get_message_publisher()
        assert isinstance(pub, InMemoryPublisher)
