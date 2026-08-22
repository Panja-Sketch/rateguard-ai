# RateGuard AI — Continuous Pricing Assurance for Insurance

## Problem Statement
Insurance pricing logic moves through multiple representations and disparate systems, such as regulatory filings, actuarial spreadsheets, rating engines (Guidewire, Duck Creek, Earnix, Akur8), custom REST APIs, and production policy runtimes. A pricing rule can be 100% correct at its source but mistranslated during implementation. Because technical code executes cleanly without runtime exceptions and passes traditional smoke tests, incorrect customer premiums silently slip into production.

## Solution Summary
RateGuard AI is a vendor-neutral, agentic insurance pricing assurance platform. By converting diverse pricing sources into a canonical Insurance Pricing Intermediate Representation (IPIR), RateGuard independently performs semantic diffing, constructs pricing dependency DAGs, executes deterministic expected premium calculations via an Independent Premium Oracle, generates risk-directed validation tests, pinpoints calculation root causes, and quantifies portfolio financial exposure—all backed by Google ADK agents and Gemini reasoning.

## Architecture Specification
The complete system design and authoritative architectural contract is defined in [`PROJECT_SPEC.md`](PROJECT_SPEC.md).

## Current Status
**Phase 1: Repository Foundation & Core Framework Setup.**  
The repository structure, configuration management, logging foundation, FastAPI application scaffolding, and package boundaries have been established.

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

### 4. Run Tests & Linter
```bash
pytest
ruff check .
```

