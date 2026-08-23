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


def test_04_dict_backed_report_and_list_runs_api() -> None:
    from app.storage import AssuranceRunRecord, AssuranceRunStatus, get_run_store

    store = get_run_store()
    dict_report_run = AssuranceRunRecord(
        run_id="RUN-DICT-REPORT-001",
        status=AssuranceRunStatus.COMPLETED,
        workflow_stage="COMPLETED",
        decision="BLOCK_DEPLOYMENT",
        summary="Dict report test summary",
        report={
            "run_id": "RUN-DICT-REPORT-001",
            "status": "BLOCK_DEPLOYMENT",
            "decision": "BLOCK_DEPLOYMENT",
            "executive_summary": "Dict report executive summary",
        },
    )
    store.create_run(dict_report_run)

    # Test /result endpoint with dict report returns 200
    res = client.get("/api/v1/assurance/runs/RUN-DICT-REPORT-001/result")
    assert res.status_code == 200
    result_json = res.json()
    assert result_json["run_id"] == "RUN-DICT-REPORT-001"
    assert result_json["decision"] == "BLOCK_DEPLOYMENT"

    # Test GET /assurance/runs endpoint
    list_res = client.get("/api/v1/assurance/runs?limit=10")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert "runs" in list_data
    assert "count" in list_data
    assert list_data["count"] >= 1
    run_ids = [r["run_id"] for r in list_data["runs"]]
    assert "RUN-DICT-REPORT-001" in run_ids

    # Test 404 for missing run
    missing_res = client.get("/api/v1/assurance/runs/RUN-DOES-NOT-EXIST")
    assert missing_res.status_code == 404


def test_05_cors_origin_headers() -> None:
    res = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"},
    )
    assert res.status_code == 200
    assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
