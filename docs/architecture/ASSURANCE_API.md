# Autonomous Assurance API Specification

## 1. Overview
The RateGuard Autonomous Assurance API exposes REST endpoints for triggering agentic pricing assurance workflows, retrieving run status, and fetching evidence lineage records.

---

## 2. API Endpoints

### `GET /api/v1/demo/packages`
Returns allowed synthetic rate plan packages available for testing.

### `POST /api/v1/assurance/runs`
Initiates and synchronously executes an autonomous multi-agent assurance workflow run.

**Request Payload:**
```json
{
  "left_package_id": "AZ_HO3_2026_09",
  "right_package_id": "AZ_HO3_2026_09_DEFECTIVE",
  "include_portfolio_analysis": true
}
```

**Response Payload:**
```json
{
  "run_id": "RUN-33A1D1A0",
  "status": "BLOCK_DEPLOYMENT",
  "executive_summary": "...",
  "recommendation": "BLOCK DEPLOYMENT: Material pricing discrepancies...",
  "result": { ... }
}
```

### `GET /api/v1/assurance/runs/{run_id}`
Fetches persisted assurance run state from configured `RunStore`.

### `GET /api/v1/assurance/runs/{run_id}/evidence`
Fetches evidence lineage records associated with a specific run.

