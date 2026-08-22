# Asynchronous Assurance Workflow Architecture

## 1. Overview
RateGuard AI supports production asynchronous execution via Cloud Pub/Sub and HTTP 202 Accepted status polling.

```text
Source Artifacts ──► Cloud Storage
                          │
                          ▼
                  Source Adapter ──► IPIR
                                       │
                                       ▼
                             POST /api/v1/assurance/runs
                                       │
                     ┌─────────────────┴─────────────────┐
                     ▼                                   ▼
             (Sync Mode: 200 OK)                 (Async Mode: 202 Accepted)
          Synchronous Workflow                     Pub/Sub AssuranceJob
                     │                                   │
                     └─────────────────┬─────────────────┘
                                       ▼
                            Assurance Worker Process
                                       │
                       ┌───────────────┼───────────────┐
                       ▼               ▼               ▼
                   Firestore       BigQuery      Cloud Storage
                  (State/Logs)    (Analytics)      (Artifacts)
```

## 2. API Endpoints

- `POST /api/v1/assurance/runs`: Starts run. Supports sync or async mode (returns HTTP 202 with `run_id` and `job_id`).
- `GET /api/v1/assurance/runs/{run_id}`: Returns run status, workflow stage, decision, and timestamps.
- `GET /api/v1/assurance/runs/{run_id}/events`: Returns chronological audit events timeline.
- `GET /api/v1/assurance/runs/{run_id}/result`: Returns HTTP 202 while processing, or full report when completed.
- `GET /api/v1/assurance/runs/{run_id}/evidence`: Returns evidence lineage references.

## 3. Configuration
- `RATEGUARD_ASYNC_ENABLED=true` enables async Pub/Sub execution.
- `RATEGUARD_PUBSUB_TOPIC=assurance-runs`
- `RATEGUARD_PUBSUB_SUBSCRIPTION=assurance-worker`

