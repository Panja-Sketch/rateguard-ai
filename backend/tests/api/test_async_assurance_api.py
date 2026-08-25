import base64

from fastapi.testclient import TestClient

from app.main import app
from app.messaging import AssuranceJob
from app.messaging.outcomes import ProcessingOutcome

client = TestClient(app)


def test_async_assurance_run_creation():
    """Tests POST /api/v1/assurance/runs returning 202 Accepted in async mode."""
    payload = {
        "left_package_id": "AZ_HO3_2026_09",
        "right_package_id": "AZ_HO3_2026_09_DEFECTIVE",
        "async_execution": True,
        "include_portfolio_analysis": False,
    }

    res = client.post("/api/v1/assurance/runs", json=payload)
    assert res.status_code == 202

    data = res.json()
    assert "run_id" in data
    assert data["status"] == "QUEUED"
    assert "job_id" in data

    run_id = data["run_id"]

    # Verify status endpoint
    res_status = client.get(f"/api/v1/assurance/runs/{run_id}")
    assert res_status.status_code == 200
    assert res_status.json()["status"] == "QUEUED"

    # Verify events endpoint
    res_events = client.get(f"/api/v1/assurance/runs/{run_id}/events")
    assert res_events.status_code == 200
    assert res_events.json()["event_count"] >= 1

    # Verify result endpoint returns 202 while QUEUED
    res_result = client.get(f"/api/v1/assurance/runs/{run_id}/result")
    assert res_result.status_code == 202
    assert res_result.json()["status"] == "QUEUED"


def test_internal_pubsub_worker_endpoint():
    """Tests POST /internal/pubsub/assurance decoding Pub/Sub push message."""
    job = AssuranceJob(
        job_id="JOB-TEST-001",
        run_id="RUN-TEST-001",
        left_package_id="AZ_HO3_2026_09",
        right_package_id="AZ_HO3_2026_09_DEFECTIVE",
        include_portfolio_analysis=False,
    )

    encoded_data = base64.b64encode(job.model_dump_json().encode("utf-8")).decode("utf-8")

    envelope = {
        "message": {
            "data": encoded_data,
            "message_id": "12345",
        },
        "subscription": "projects/rateguard-ai/subscriptions/assurance-worker",
    }

    res = client.post("/internal/pubsub/assurance", json=envelope)
    assert res.status_code == 200

    data = res.json()
    assert data["status"] in (
        ProcessingOutcome.SUCCEEDED.value,
        ProcessingOutcome.DUPLICATE_ALREADY_PROCESSED.value,
    )
    assert data["job_id"] == "JOB-TEST-001"
    assert data["run_id"] == "RUN-TEST-001"


def test_unknown_assurance_run_404():
    """Verifies 404 response for unknown run ID."""
    res = client.get("/api/v1/assurance/runs/RUN-NONEXISTENT")
    assert res.status_code == 404

    res_events = client.get("/api/v1/assurance/runs/RUN-NONEXISTENT/events")
    assert res_events.status_code == 404

    res_result = client.get("/api/v1/assurance/runs/RUN-NONEXISTENT/result")
    assert res_result.status_code == 404
