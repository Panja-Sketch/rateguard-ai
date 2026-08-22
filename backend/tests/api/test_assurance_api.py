from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_01_list_demo_packages() -> None:
    res = client.get("/api/v1/demo/packages")
    assert res.status_code == 200
    data = res.json()
    assert "packages" in data
    assert len(data["packages"]) >= 2
    ids = [p["id"] for p in data["packages"]]
    assert "AZ_HO3_2026_09" in ids
    assert "AZ_HO3_2026_09_DEFECTIVE" in ids


def test_02_create_assurance_run_endpoint() -> None:
    res = client.post(
        "/api/v1/assurance/runs",
        json={
            "left_package_id": "AZ_HO3_2026_09",
            "right_package_id": "AZ_HO3_2026_09_DEFECTIVE",
            "include_portfolio_analysis": False,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert "run_id" in data
    assert data["status"] == "BLOCK_DEPLOYMENT"
    run_id = data["run_id"]

    # Fetch run details
    get_res = client.get(f"/api/v1/assurance/runs/{run_id}")
    assert get_res.status_code == 200
    run_data = get_res.json()
    assert run_data["status"] == "COMPLETED"

    # Fetch evidence records
    ev_res = client.get(f"/api/v1/assurance/runs/{run_id}/evidence")
    assert ev_res.status_code == 200
    ev_data = ev_res.json()
    assert ev_data["evidence_count"] >= 5


def test_03_create_assurance_run_invalid_package_rejected() -> None:
    res = client.post(
        "/api/v1/assurance/runs",
        json={
            "left_package_id": "UNSUPPORTED_PACKAGE",
            "right_package_id": "AZ_HO3_2026_09_DEFECTIVE",
        },
    )
    assert res.status_code == 400
    assert "Unsupported package_id" in res.json()["detail"]

