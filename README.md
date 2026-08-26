# RateGuard AI — Continuous Pricing Assurance for Insurance

RateGuard AI is a vendor-neutral, agentic insurance pricing assurance platform. It independently verifies that insurance pricing logic stays semantically correct as it moves from a regulatory filing, through an actuarial spec, into a rating engine implementation — catching silent pricing defects before they reach production.

**Production URL:** https://rateguard-web-iqofutwtva-uc.a.run.app

---

## The Problem

Insurance pricing logic is written once (as an approved actuarial filing) and then re-implemented multiple times: in rating engines (Guidewire, Duck Creek, Earnix, custom REST APIs), in spreadsheets, in legacy systems. A rule that is 100% correct at its source can be silently mistranslated during implementation:

- **Approved filing:** `roof_age >= 21 → factor 1.35`
- **Implemented engine:** `roof_age >= 21 → factor 1.25`

The code runs cleanly, throws no exceptions, and passes ordinary smoke tests — so incorrect customer premiums ship to production undetected. There is no standard, vendor-neutral way to prove that a rating engine implementation actually matches the filing it's supposed to implement.

## The Innovation

RateGuard converts any pricing source — a filing PDF, an actuarial Excel workbook, a JSON spec, or a platform rating config — into a canonical **Insurance Pricing Intermediate Representation (IPIR)**: an executable AST and dependency graph. Because every source lands in the same representation, RateGuard can compare *any* two of them symmetrically, without treating any vendor or format as the privileged source of truth.

From there, a bounded, structured Gemini supervisor and a suite of deterministic engines work together to not just detect that two sources differ, but to prove *how much it matters*: which calculation nodes are affected, which of 50,000 real policies would be mispriced, and by how much money — then propose and verify a fix.

## Agentic Gemini Workflow

RateGuard runs a mandatory deterministic evidence pipeline unconditionally (validation → IPIR comparison → dependency impact → boundary-test generation → premium oracle → target execution → trace reconciliation), and consults **Gemini 3.7 Flash** (via the Google GenAI SDK against Vertex AI) at a small number of bounded, structured decision points inside `AssuranceSupervisor`:

| Decision point | What Gemini decides |
| :--- | :--- |
| `PRIORITIZE_DIFFERENCES` | Which already-detected semantic differences deserve focused boundary testing |
| `SELECT_BOUNDARY_TESTS` | Which deterministically-generated candidate boundary tests to execute |
| Evidence sufficiency | Whether one more bounded round of probes is worth running (capped at `MAX_PROBE_ROUNDS`) |
| Portfolio justification | How to frame the 50K-policy blast-radius narrative |
| Remediation proposal | What isolated patch would resolve a confirmed defect |
| Remediation revalidation selection | Which tests to re-run to prove the patch actually fixes it |

Every Gemini call is schema-validated structured output, and Gemini may **only select IDs from a candidate pool a deterministic engine already produced** — it can never invent a finding, a test scenario, or a dollar figure. Every mission is capped at `MAX_GEMINI_CALLS_PER_MISSION` calls. If Gemini is unavailable or returns an invalid response, every decision point has a deterministic fallback (e.g. "retain all differences," "use optimizer-selected tests") so a mission never stalls on an LLM outage — and the UI honestly reports which path was taken (`is_gemini_decision` / `is_fallback` on every logged action).

When two sources are found to be fully equivalent with **zero** AST diffs, Gemini is **never invoked** for that mission — the decision path never reaches a real judgment call, so there is nothing for it to decide. The UI reports this explicitly as "Gemini not invoked by design," not as a skipped or failed step.

## Architecture

```
User Browser / Client → Next.js 14 Frontend
  ↓ HTTP REST API
FastAPI Backend (Cloud Run API)
  ↓ Pub/Sub Async Queue
Private Worker Runtime (Cloud Run Worker, no public ingress)
  ↓ Agentic Assurance Supervisor
Google GenAI SDK Structured-Decision Supervisor ↔ Gemini 3.7 Flash (Vertex AI)
  ↕ Deterministic Boundary
Python Deterministic Engines (AST Diff, Dependency DAG, Premium Oracle, Test Generator, Reconciliation)
  ↓ Cloud Persistence
Firestore (mission/run state) | BigQuery (50K-policy portfolio SQL) | GCS (source & evidence artifacts)
  ↓ Release Decision
PASS / REVIEW_REQUIRED / BLOCK_DEPLOYMENT
```

The API validates a mission request synchronously (~2ms), persists it as `QUEUED` in Firestore, and publishes an `AssuranceJob` to a Pub/Sub topic. A push subscription delivers it to the private worker, which acquires an atomic Firestore execution lease (so duplicate Pub/Sub delivery can never double-execute a mission) and runs the full pipeline asynchronously — mission execution never runs in-process inside the public API.

## Key Features

- **Release Conformance** — verifies a target rating engine implementation conforms to an authoritative filing intent.
- **Symmetric Equivalence** — compares two sources with neither assumed authoritative; checked both A→B and B→A to prove the result is genuinely symmetric, not an artifact of comparison order.
- **Semantic diffing** — structural AST comparison classifying value, range, rule, order, effective-date, and rounding changes.
- **Dependency impact graph** — traces a diff through the pricing calculation DAG to every downstream affected node and output.
- **Risk-directed boundary testing** — generates targeted test scenarios at range boundaries and interaction points instead of brute-forcing the input space, and reports the real reduction (candidates pruned vs. selected) achieved.
- **Independent Premium Oracle** — a deterministic pricing engine that computes expected premiums directly from IPIR; the LLM never performs pricing arithmetic.
- **Premium reconciliation & root-cause analysis** — pinpoints the first divergent calculation node and explains why.
- **50,000-policy blast-radius analysis** — runs the confirmed defect's boundary predicate against a synthetic Arizona HO3 portfolio in BigQuery to quantify affected-policy count and net financial exposure.
- **Remediation & revalidation** — proposes an isolated patch and re-runs targeted + regression tests to prove the fix eliminates the exposure before recommending deployment.
- **Full evidence lineage** — every stage's evidence (semantic diff results, Gemini invocation metadata, reconciliation traces) is persisted to Firestore/GCS and inspectable from the mission detail UI.

## Supported Source Formats

| Format | Adapter |
| :--- | :--- |
| Structured JSON (native IPIR or simple JSON specs) | `structured_json` |
| Excel workbooks (actuarial rate spec exports) | `excel` |
| PDF (regulatory filing documents) | `pdf` |
| Platform rating configs (Guidewire/Duck Creek-style exports) | `platform_config` |

Deterministic extractors run first; Gemini-assisted extraction is used only for genuinely ambiguous PDF/Excel sources, and every extraction below `LOW_CONFIDENCE_REVIEW_THRESHOLD` (60%) is flagged for human review rather than silently accepted.

## The Deterministic Boundary

This is the architectural guarantee the whole system is built around: **Gemini reasons, plans, and explains — it never computes a premium, a financial exposure figure, or a policy count.** All arithmetic (rate table lookups, expression evaluation, rounding, DAG traversal, SQL aggregation over the 50K portfolio) is untouched deterministic Python. Gemini's only discretion is *which* deterministically-generated candidate (a difference, a test scenario, a remediation option) gets investigated next — every ID it returns is validated against the candidate pool before anything executes, and a hallucinated ID is simply rejected, falling back to the deterministic default.

## Google Cloud Services

| Service | Role |
| :--- | :--- |
| **Cloud Run** | Hosts the public API (`rateguard-api`), the private worker (`rateguard-worker`, no public ingress), and the web frontend (`rateguard-web`) |
| **Vertex AI (Gemini 3.7 Flash)** | Structured-decision reasoning via the Google GenAI SDK, authenticated via the runtime service account (no API key) |
| **Cloud Pub/Sub** | Durable async job queue between the API and worker, with a bounded retry policy and a dead-letter topic/subscription for poison messages |
| **Firestore** | Mission/run state, per-stage event log, and evidence records |
| **BigQuery** | The 50,000-synthetic-policy portfolio dataset and blast-radius exposure queries |
| **Cloud Storage (GCS)** | Uploaded source files and compiled IPIR artifacts |
| **Cloud Build** | Builds and pushes container images for the API/worker and web services |
| **Artifact Registry** | Stores built container images |

## Setup & Local Development

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows; use `source .venv/bin/activate` on Linux/macOS
pip install -e .
uvicorn app.main:app --reload --port 8000
```

Run tests and lint:

```bash
pytest
ruff check .
```

### Frontend

```bash
cd frontend
npm install
npm run dev      # local dev server
npm run typecheck
npm run lint
npm test
```

### Deployment

Deployment to Google Cloud Run follows a staged pipeline, implemented in `infrastructure/`:

1. `deploy_candidate.sh --deploy-candidate` builds an immutable image and deploys it as a `--no-traffic --tag candidate` revision against fully isolated staging Pub/Sub/Firestore/BigQuery/GCS resources.
2. `backend/scripts/verify_candidate.py --yes-test-candidate` exercises the candidate end-to-end (mission lifecycle, structured validation, CORS) against those isolated resources.
3. `deploy_release.sh --deploy-release --image-digest=<verified digest>` promotes the exact verified image to `--no-traffic --tag release` revisions using production resource names, still at 0% traffic.
4. Traffic is shifted deliberately via targeted `gcloud run services update-traffic` commands, gated by a staging-name guard (`infrastructure/check_production_config.sh`) that refuses to proceed if a revision resolves to any staging-named resource.

## Demo Steps

1. Open the [production site](https://rateguard-web-iqofutwtva-uc.a.run.app).
2. Visit **Missions → New Mission**, pick **Release Conformance**, and run the bundled Arizona HO3 canonical-vs-defective scenario — expect a `BLOCK_DEPLOYMENT` decision with a quantified financial exposure and a proposed remediation.
3. Run the same wizard again with the **clean control** target — expect `PASS` with zero diffs, and note the "Gemini not invoked by design" messaging.
4. Pick **Equivalence** mode and run it both A→B and B→A — confirm the decision is identical in both directions.
5. Visit **Sources**, upload your own `.json`/`.xlsx`/`.pdf` pricing spec for Source A and B, compile them, and launch a mission from real uploaded sources.
6. Open the mission detail page and walk the tabs: Material Findings, Dependency DAG, Boundary Experiments, Reconciliation & RCA, Blast Radius, Remediation & Revalidation, Evidence Lineage, and the Gemini Action Timeline.

## Screenshots & Video

_Add links to a demo video and screenshots here before final submission._

## Test Results

- **Backend:** 386 tests passing (`pytest`), covering mission lifecycle, validation, the Gemini supervisor's decision points and fallback paths, Pub/Sub worker delivery/idempotency, cross-process artifact storage, and API-level contract tests.
- **Frontend:** clean `tsc --noEmit` typecheck across the app.
- **Deployed acceptance tests** (`scripts/verify_deployed_system.py`, `docs/demo/DEPLOYED_ACCEPTANCE_TEST.md`): clean `RELEASE_CONFORMANCE` run → `PASS`; defective `RELEASE_CONFORMANCE` run → `BLOCK_DEPLOYMENT` with a quantified blast radius; symmetric `EQUIVALENCE` run in both directions → matching `PASS`.

## Repository Structure

```
backend/            FastAPI application, agents, deterministic engines, tests
  app/
    agents/          AssuranceSupervisor + Gemini decision client
    api/             REST endpoints (missions, sources, assurance, health)
    adapters/        Source format adapters (JSON, Excel, PDF, platform config)
    engines/         Deterministic diff, impact, oracle, testing, reconciliation, portfolio engines
    ipir/            IPIR schema, package model, validation
    models/           Pydantic domain models
    services/        Validation, remediation, mission transition services
    storage/         Firestore/BigQuery/GCS/Pub/Sub adapters
  scripts/            Fixture generators, demo runners, deploy-time verification scripts
  tests/              Unit, API, and agent test suites
frontend/            Next.js 14 (App Router) + TypeScript + Tailwind web UI
  src/app/            Pages (missions, sources, architecture)
  src/components/     Assurance UI components (diff viewer, impact graph, evidence lineage, ...)
  src/lib/            API client and shared types
infrastructure/      Deploy/rollback/promotion scripts and production runtime config
docs/
  architecture/       Per-subsystem architecture specifications
  demo/               Demo kit and acceptance test guide
data/                 Synthetic Arizona HO3 demo/test fixtures (rate spec, IPIR packages, 50K portfolio)
scripts/              Deployed-system verification script
```
