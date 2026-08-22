# Google ADK + Gemini Multi-Agent Architecture Specification

## 1. Overview & Vision
RateGuard AI integrates Google ADK (Agent Development Kit) and Gemini models (configured via `RATEGUARD_GEMINI_MODEL`, defaulting to `gemini-2.5-flash`) to orchestrate multi-step pricing assurance workflows across insurance rate plan representations.

---

## 2. Fundamental Architectural Guardrail
> **Non-Negotiable Rule:** Gemini reasons, synthesizes natural language narratives, and orchestrates workflows. Deterministic Python software performs arithmetic, rate table lookups, dependency graph traversal, test scenario planning, target engine execution, reconciliation, and 50,000 policy portfolio exposure calculations.

Gemini prompt variance cannot override strict deterministic decision policy outcomes (`BLOCK_DEPLOYMENT`, `REVIEW`, `PASS`).

---

## 3. Agent Topology & Tool Boundaries

```text
User / API Request
        ↓
RateGuard Orchestrator Agent
        ↓
inspect source/package context
        ↓
Semantic Assurance Agent   ───> calls compare_ipir_packages_tool()
        ↓
Impact Agent              ───> calls analyze_pricing_impact_tool()
        ↓
Test Planning Agent       ───> calls generate_assurance_test_plan_tool()
        ↓
Investigation Agent       ───> calls execute_pricing_assurance_tool()
        ↓
Portfolio Impact Agent    ───> calls analyze_portfolio_exposure_tool()
        ↓
Assurance Decision Agent  ───> enforces deterministic decision policy
        ↓
Structured AgenticAssuranceResult
```

### Specialized Agents & Roles
1. **Orchestrator Agent (`RateGuardOrchestrator`):** Manages step execution, passes structured payloads, logs audit events, and maintains run state in `RunStore`.
2. **Semantic Assurance Agent (`SemanticAssuranceAgent`):** Analyzes semantic diff outputs (`compare_ipir_packages_tool`).
3. **Impact Agent (`ImpactAgent`):** Interprets DAG dependency paths and risk predicates (`analyze_pricing_impact_tool`).
4. **Test Planner Agent (`TestPlannerAgent`):** Reviews candidate/selected risk-directed scenario plans (`generate_assurance_test_plan_tool`).
5. **Investigation Agent (`InvestigationAgent`):** Reviews trace divergences, reconciliation mismatches, and RCA findings (`execute_pricing_assurance_tool`).
6. **Portfolio Agent (`PortfolioAgent`):** Synthesizes 50,000 policy financial exposure metrics (`analyze_portfolio_exposure_tool`).
7. **Assurance Decision Agent (`AssuranceDecisionAgent`):** Synthesizes findings across subagents and enforces deterministic status blocking policy.

---

## 4. Hackathon Track Alignment
- **Track:** Taskmaster (Autonomous Multi-Step AI Agent System).
- **AI Platform:** Google ADK + Gemini API / Vertex AI SDK.
- **Persistence:** Google Cloud Firestore (`rateguard-ai` project).

