from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_system_status_reports_diagnostics_without_secrets():
    """Proves /api/v1/system/status reports configuration diagnostics and never
    exposes secret values, credentials, or auth headers."""
    res = client.get("/api/v1/system/status")
    assert res.status_code == 200
    data = res.json()

    for key in ("run_store", "message_queue", "worker_heartbeat", "gemini", "bigquery", "artifact_storage"):
        assert key in data

    assert data["message_queue"]["worker_push_route"] == "/internal/pubsub/assurance"
    assert "invoked" in data["gemini"]
    assert data["gemini"]["invoked"] is False

    # Never expose secret-shaped values anywhere in the response.
    serialized = str(data).lower()
    for forbidden in ("secret", "authorization", "bearer ", "api_key", "private_key"):
        assert forbidden not in serialized


def test_system_status_does_not_invoke_gemini_generation():
    """Proves the diagnostics endpoint reports the configured model id without
    performing a billable generation call (no 'generate_content'/response fields)."""
    res = client.get("/api/v1/system/status")
    assert res.status_code == 200
    gemini = res.json()["gemini"]
    assert "configured_model_id" in gemini
    assert "response" not in gemini
    assert "generated_text" not in gemini
