# PROJECT_SPEC.md — RateGuard AI Architecture & Engineering Specification

**Project Name:** RateGuard AI — Continuous Pricing Assurance for Insurance  
**Target Track:** Taskmaster  
**Status:** Canonical Project Specification (Phase 0: Bootstrap & Architecture)  

---

## 1. Executive Summary & Core Problem

Insurance pricing logic is written, approved, translated, and executed across multiple representations and disparate systems, including:
- Regulatory filings (PDFs, word documents)
- Actuarial spreadsheets (Excel workbooks)
- Actuarial/pricing models (Python, R, SAS)
- Core rating engines (Guidewire PolicyCenter/Rating, Duck Creek Rating, Earnix, Akur8, hyperexponential)
- Custom rating engines & REST APIs
- Legacy rating systems & production policy admin runtimes

A pricing rule can be 100% correct at its source but mistranslated or corrupted during technical implementation.

**Example Defect:**
- **Approved Regulatory / Actuarial Factor:** `roof_age >= 21 → 1.35`
- **Implemented Technical Factor:** `roof_age >= 21 → 1.25`

Because the software runs cleanly without runtime exceptions and passes standard technical smoke/unit tests, customer premiums are silently miscalculated in production.

**RateGuard AI** is a vendor-neutral, agentic insurance pricing assurance platform built to independently verify that insurance pricing intent remains semantically equivalent across every representation and runtime implementation.

---

## 2. Core Architectural Principles

### 2.1 Vendor-Neutral, Source-Agnostic, and Bidirectional
RateGuard MUST NOT be designed around or tightly coupled to Guidewire or any single vendor ecosystem. Guidewire, Duck Creek, Excel, and custom REST APIs are treated as equal adapters into a unified intermediate representation.

Any supported pricing representation MUST be comparable with any other supported pricing representation:
- Regulatory Filing ↔ Actuarial Workbook
- Actuarial Workbook ↔ Guidewire Configuration
- Guidewire Configuration ↔ Custom REST Rating Engine
- Legacy Rating Engine ↔ Modern Rating Engine
- Canonical Pricing Model ↔ Production Runtime Behavior

There is **no mandatory single source of truth** hardcoded into the system architecture.

---

## 3. Core Abstraction — IPIR (Insurance Pricing Intermediate Representation)

The core architectural foundation of RateGuard is **IPIR**: a canonical, executable, vendor-neutral, and source-agnostic schema for insurance pricing semantics.

### 3.1 IPIR Conceptual Schema Scope
IPIR represents insurance pricing logic as a structured, executable AST and dependency graph. Key entities include:

- **Metadata & Context:** Jurisdiction (e.g., State/ISO code), Product Line, Effective Dates, Expiration Dates, Transaction Types (New Business, Renewal, Endorsement).
- **Inputs & Variables:** Policy & Risk Inputs (numeric, categorical, boolean, date).
- **Constants & Rate Tables:**
  - 1D Lookup Tables (e.g., Territory → Base Factor)
  - 2D Multidimensional Tables (e.g., Construction Type x Protection Class)
  - Range-based Tables (e.g., `roof_age` brackets)
- **Calculation Nodes & Logic:**
  - Mathematical Expressions (`+`, `-`, `*`, `/`, exponentiation, min/max bounds)
  - Conditional Logic & Rules (`IF/THEN/ELSE`, range conditions)
  - Modifiers, Surcharges, and Discounts
  - Calculation Dependencies & Execution Ordering
- **Rounding & Financial Constraints:** Per-node rounding rules (decimal precision, rounding direction), minimum premiums, maximum premiums, fee structures.
- **Outputs & Provenance:** Final base premium, coverage premiums, total policy premium, node-level source lineage, confidence scores.

### 3.2 Bidirectional Comparability
IPIR models pricing semantics such that two distinct IPIR instances ($IPIR_A$ and $IPIR_B$) can be deterministically and semantically compared regardless of their origin.

---

## 4. RateGuard Core Capabilities

### 4.1 Intent Extraction
Extracts pricing logic from unstructured or semi-structured sources (regulatory PDFs, actuarial workbooks, JSON specs) and maps them into valid IPIR definitions using agentic intent extraction paired with validation tools.

### 4.2 Source Adapters
Extensible adapter architecture converting vendor-specific representations to/from IPIR:
- **MVP Adapters:** Structured Actuarial Source, Excel Workbook Adapter, Regulatory PDF Adapter, Guidewire-like Configuration Adapter, Generic REST Rating Engine Adapter.
- **Future Adapters:** Duck Creek, Earnix, Akur8, hyperexponential, legacy/custom engines.

### 4.3 Semantic Diff Engine
Performs semantic structural and value diffing between two IPIR models. Supported difference classifications:
- `VALUE_CHANGE`: Numeric factor or rate mismatch
- `RANGE_CHANGE`: Bracket boundary altered (e.g., `>= 21` vs `> 20`)
- `RULE_CHANGE`: Condition logic altered or swapped
- `ORDER_CHANGE`: Sequence of calculations modified affecting intermediate values
- `EFFECTIVE_DATE_CHANGE`: Variance in effective date logic or rate application dates
- `ROUNDING_CHANGE`: Rounding precision or method difference
- `MISSING_RULE`: Rule present in Source A but absent in Source B
- `EXTRA_RULE`: Rule present in Source B but absent in Source A
- `TABLE_COVERAGE_GAP`: Uncovered input domain in lookup table
- `OVERLAPPING_RULES`: Conflicting or ambiguous rule coverage

### 4.4 Pricing Dependency Graph
Constructs a Directed Acyclic Graph (DAG) of calculation steps (`Factor → Sub-Calculation → Coverage Premium → Total Premium`). Supports:
- Blast-radius estimation
- Root-cause analysis tracing
- Targeted test selection
- Human-readable pricing explanation

### 4.5 Independent Premium Oracle
RateGuard includes a **deterministic pricing execution engine** that executes IPIR models directly.
- Calculates exact expected premiums independently of target engines.
- Produces full, step-by-step intermediate calculation worksheets / audit traces.
- **STRICT MANDATE:** The LLM MUST NOT perform authoritative premium arithmetic.

### 4.6 Risk-Directed Test Generation
Analyzes semantic diffs and dependency graphs to generate targeted, high-value risk validation test cases:
- Range boundaries (e.g., `roof_age = 20`, `21`, `22`)
- Changed values and interaction points
- Effective date boundaries
- Minimum/maximum premium bounds
- Optimizes test portfolios to avoid brute-force combinatorial explosion.

### 4.7 Target Engine Execution & Adapter Dispatch
Executes generated validation risks against target rating engines (e.g., via REST endpoints or mock engines). Includes an intentionally defective target engine for hackathon validation.

### 4.8 Premium Reconciliation
Reconciles expected premiums from the IPIR Premium Oracle against actual premiums returned by target rating engines, comparing both final premiums and intermediate calculation nodes where exposed.

### 4.9 Root-Cause Analysis (RCA)
Pinpoints the exact first divergent calculation node in the execution trace (e.g., `base_rate` MATCH → `territory_factor` MATCH → `roof_age_factor` MISMATCH). Identifies the exact implementation artifact responsible.

### 4.10 Portfolio Blast Radius Analysis
Derives population predicates from identified pricing defects (e.g., `state = 'AZ' AND product = 'HO3' AND roof_age >= 21 AND effective_date >= '2026-09-01'`) and queries synthetic portfolio datasets to compute:
- Total affected policies
- Total expected vs implemented premium
- Net financial variance (undercharged / overcharged amounts)

### 4.11 Financial Exposure Metrics
Computes quantitative business impact metrics dynamically from portfolio dataset queries.

### 4.12 Pricing Lineage & Audit Provenance
Tracks lineage across the lifecycle:
`Regulatory Filing → Actuarial Model → IPIR → Implementation Artifact → Generated Test Case → Runtime Calculation Node → Final Premium`.

### 4.13 Assurance Decision
Generates automated release recommendations: `PASS`, `REVIEW`, or `BLOCK_DEPLOYMENT`, supported by evidence and severity metrics. Human approval remains authoritative.

---

## 5. Agentic Architecture (Google ADK & Gemini)

The application utilizes **Google ADK (Agent Development Kit)** with **Gemini** for multi-agent reasoning and orchestration.

```
                   +-----------------------+
                   |  Orchestrator Agent   |
                   +-----------+-----------+
                               |
      +------------------------+------------------------+
      |                        |                        |
+-----v------------+  +--------v-------+      +---------v----------+
|   Intent Agent   |  | Adapter Agent  |      |   Impact Agent     |
+------------------+  +----------------+      +--------------------+
      |                        |                        |
+-----v------------+  +--------v-------+      +---------v----------+
|Test Planner Agent|  | RCA Agent      |      |  Assurance Agent   |
+------------------+  +----------------+      +--------------------+
```

### 5.1 Agent Roles & Responsibilities
1. **Orchestrator Agent:** Coordinates the end-to-end assurance workflow across agents and tools.
2. **Intent Agent:** Interprets pricing documentation/filings and proposes structured IPIR mappings.
3. **Adapter Agent:** Coordinates conversion of vendor/source configurations into IPIR.
4. **Impact Agent:** Reasons over semantic diffs and pricing dependency graphs to evaluate severity.
5. **Test Planner Agent:** Selects boundary and interaction test vectors based on deterministic candidate seeds and Gemini reasoning.
6. **Investigation / RCA Agent:** Analyzes calculation node mismatches to explain root causes in plain language.
7. **Assurance Agent:** Synthesizes evidence, risk exposure, and compliance checks into a final release recommendation (`BLOCK_DEPLOYMENT` / `REVIEW` / `PASS`).

### 5.2 Division of Responsibilities: AI vs. Deterministic

| Domain | AI / Gemini / ADK Agents | Deterministic Python Core |
| :--- | :--- | :--- |
| **Document Understanding** | Parse unstructured filings/specs into candidate structures | N/A |
| **Semantic Mapping** | Propose IPIR element mappings | Validate schema & types |
| **Orchestration & Planning** | Workflow sequencing, test selection guidance | Execution of pipeline steps |
| **Arithmetic & Rates** | NEVER handle math | Execute rate tables, expressions, rounding |
| **Diffing & Graphing** | Explain semantic differences | Compute structural diffs & DAG traversals |
| **Portfolio Exposure** | Summarize financial risk narrative | Execute SQL / BigQuery aggregations |
| **Decisioning** | Draft release recommendations | Enforce hard boundary thresholds |

---

## 6. Technology Stack & Infrastructure

- **Frontend:** Next.js / React (TypeScript, Tailwind CSS)
- **Backend:** Python 3.12+ with FastAPI & Pydantic v2
- **Agentic Framework:** Google ADK (Agent Development Kit)
- **LLM / Foundation Models:** Gemini 3.5 / 3.6 Flash & Pro via Google GenAI SDK / Vertex AI (configurable)
- **Cloud Infrastructure & Storage:**
  - **Runtime:** Cloud Run (Docker containers)
  - **State & Workflow Metadata:** Cloud Firestore
  - **Portfolio Analytics:** BigQuery
  - **Evidence & Document Storage:** Cloud Storage (GCS)
  - **Async Processing:** Cloud Pub/Sub
- **Version Control:** GitHub

---

## 7. Hackathon Track & Core MVP Demo Flow

### Track
**Taskmaster Track** — Demonstrating autonomous multi-step execution with minimal human intervention.

### Demo Scenario
**State / Product:** US Property & Casualty — Homeowners 3 (HO3) Arizona synthetic rate plan.

**Scenario:**
- Approved Filing: `roof_age >= 21 → factor 1.35`
- Implemented Defective Engine: `roof_age >= 21 → factor 1.25`

**17-Step Autonomous Workflow:**
1. Ingest pricing intent document.
2. Convert intent into Source IPIR.
3. Convert target implementation into Target IPIR.
4. Run Semantic Diff Engine.
5. Detect pricing drift (`VALUE_CHANGE` on `roof_age >= 21`).
6. Build Pricing Dependency Graph.
7. Generate targeted boundary & interaction tests (e.g., `roof_age = 20`, `21`, `22`).
8. Execute IPIR Premium Oracle for expected values.
9. Execute target defective rating engine for actual values.
10. Reproduce premium mismatch on test case `roof_age = 21`.
11. Perform Node-level Reconciliation & find first divergent calculation node (`roof_age_factor`).
12. Identify likely root cause in target implementation artifact.
13. Formulate population predicate (`state='AZ', product='HO3', roof_age>=21`).
14. Query synthetic BigQuery portfolio dataset.
15. Calculate affected policy count and premium financial variance.
16. Generate evidence pack & provenance graph.
17. Issue recommended decision: `BLOCK_DEPLOYMENT`.

---

## 8. MVP Scope (IPIR 0.1) & Explicit Non-Goals

### Supported in IPIR 0.1 Scope:
- Constants, numeric inputs, categorical inputs, boolean inputs
- 1D & 2D rate tables, range brackets, exact lookups
- Basic arithmetic expressions, conditional rules, percentage discounts/surcharges
- Minimum premiums, explicit calculation dependencies, effective dates
- Per-node rounding, transaction contexts (New Business, Renewal), fees
- Provenance tracking, semantic diffing, dependency graphing
- Independent premium execution trace, targeted test generation, portfolio exposure calculation, assurance recommendations.

### Explicit Non-Goals for IPIR 0.1:
- Workers compensation experience rating & retrospective rating
- Catastrophe modeling & telematics integration
- Credit scoring models & machine-learning-based pricing models
- Complex commercial package policies & reinsurance modeling
- Full tax regimes, out-of-sequence endorsement processing, underwriting judgment scoring.

---

## 9. Safety, Governance, and Engineering Guidelines

### 9.1 Safety & Enterprise Guardrails
- **Provenance & Lineage:** Maintain source traceability for every pricing node.
- **Uncertainty & Confidence:** Expose confidence scores on AI mappings; never silently infer missing factors.
- **No Hallucinated Math:** Enforce strict separation between AI reasoning and deterministic arithmetic.
- **Explainable Audit Trail:** Preserve all intermediate traces and evidence for regulatory compliance.
- **Security:** Zero hardcoded secrets/credentials; strict environment variable management.

### 9.2 Code & Architecture Guidelines
- Clean, modular Python 3.12+ with strong typing and strict Pydantic models.
- Dependency inversion around source adapters.
- Deterministic seeded synthetic data generation for reproducible testing.
- Structured logging and explicit error handling throughout.

---

## 10. Development Governance Rule

> [!IMPORTANT]
> Before implementing any future RateGuard feature, developers and agents MUST read `PROJECT_SPEC.md`.
> If a requested implementation conflicts with this specification, explicitly identify the conflict before modifying code or architecture.
> Do NOT silently weaken the vendor-neutral, source-agnostic, bidirectional IPIR design.

---
*Phase 0 Architecture Specification complete. Proceed to next phase upon explicit instruction.*

