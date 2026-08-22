from fastapi.testclient import TestClient


def test_root_endpoint(client: TestClient) -> None:
    """Verify that root GET / returns expected metadata and running status."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "RateGuard AI"
    assert data["version"] == "0.1.0"
    assert data["status"] == "running"


def test_health_endpoint(client: TestClient) -> None:
    """Verify that health GET /health returns status healthy."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "healthy"}

