# RateGuard AI — Continuous Pricing Assurance for Insurance

## Problem Statement
Insurance pricing logic moves through multiple representations and disparate systems, such as regulatory filings, actuarial spreadsheets, rating engines (Guidewire, Duck Creek, Earnix, Akur8), custom REST APIs, and production policy runtimes. A pricing rule can be 100% correct at its source but mistranslated during implementation. Because technical code executes cleanly without runtime exceptions and passes traditional smoke tests, incorrect customer premiums silently slip into production.

## Solution Summary
RateGuard AI is a vendor-neutral, agentic insurance pricing assurance platform. By converting diverse pricing sources into a canonical Insurance Pricing Intermediate Representation (IPIR), RateGuard independently performs semantic diffing, constructs pricing dependency DAGs, executes deterministic expected premium calculations via an Independent Premium Oracle, generates risk-directed validation tests, pinpoints calculation root causes, and quantifies portfolio financial exposure—all backed by Google ADK agents and Gemini reasoning.

## Architecture Specification
The complete system design and authoritative architectural contract is defined in [`PROJECT_SPEC.md`](PROJECT_SPEC.md).

## Current Status
**Complete Backend & Multi-Agent Engine Core.**
IPIR data model, Arizona HO3 synthetic rate plan, Premium Oracle, Semantic Diff, Dependency Impact Engine, Risk-Directed Test Planner, Target Rating Engine, Premium Reconciliation & RCA, Synthetic 50k Policy Portfolio, Portfolio Blast Radius Exposure Analyzer, Google ADK Multi-Agent Orchestrator (Gemini 2.5/3.5/3.7), Firestore Run State & Evidence Lineage, and FastAPI Autonomous Assurance REST API are fully implemented and verified.

## Google ADK & Gemini Multi-Agent Architecture
RateGuard AI features a multi-agent orchestration architecture built on Google ADK and Gemini API (`gemini-2.5-flash` default):
- **RateGuard Orchestrator Agent:** Coordinates agent workflow, logs audit events (`RunEvent`), and persists run state.
- **Semantic Assurance Agent:** Interprets granular IPIR semantic diff results (`compare_ipir_packages_tool`).
- **Impact Agent:** Analyzes pricing DAG dependency paths and risk predicates (`analyze_pricing_impact_tool`).
- **Test Planner Agent:** Optimizes risk-directed validation scenario plans (`generate_assurance_test_plan_tool`).
- **Investigation Agent:** Analyzes trace step divergences, quote reconciliations, and RCA findings (`execute_pricing_assurance_tool`).
- **Portfolio Agent:** Analyzes 50,000 policy financial exposure metrics (`analyze_portfolio_exposure_tool`).
- **Assurance Decision Agent:** Enforces deterministic decision policy (`BLOCK_DEPLOYMENT`, `REVIEW`, `PASS`).

> **Architectural Guardrail:** Gemini reasons, synthesizes narratives, and orchestrates workflows. Deterministic Python software performs arithmetic, table lookups, graph traversal, scenario planning, target execution, reconciliation, and 50,000 policy portfolio analysis.

## High-Level Architecture Components
- **IPIR Core Engine:** Canonical intermediate representation for insurance pricing ASTs and logic.
- **Source Adapters:** Bidirectional adapters for filings (PDF), actuarial workbooks (Excel), JSON specs, and rating engines.
- **Semantic Diff & Dependency Graph:** Structural logic comparison and pricing DAG traversal.
- **Independent Premium Oracle:** Deterministic math and rate table execution engine.
- **Agentic Suite (Google ADK):** Multi-agent orchestrator, intent extractor, impact analyzer, test planner, RCA investigator, and assurance recommender.
- **Portfolio Analytics & Web Dashboard:** Financial risk exposure calculations and visual audit workspace.

## Quick Local Backend Setup

### 1. Prerequisites
- Python 3.12+
- `pip` / `virtualenv`

### 2. Environment & Dependencies Setup
```bash
cd backend
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

pip install -e .
```

### 3. Run Development Server
```bash
uvicorn app.main:app --reload --port 8080
```

### 4. Run Agentic Assurance Demos
```bash
# Verify Google ADK / Gemini connectivity
python scripts/test_agent_connectivity.py

# Run full multi-agent autonomous assurance demo
python scripts/run_agentic_assurance_demo.py
```

### 5. Run Tests & Linter
```bash
pytest
ruff check .
```
