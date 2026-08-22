# Source-Agnostic Pricing Assurance Demo Guide

## Story Overview

This demo demonstrates RateGuard AI's source-agnostic compilation and autonomous pricing assurance workflow:

1. **Source A (Canonical Intent)**: Arizona HO3 Rate Specification in **Excel Workbook (`.xlsx`)** format.
2. **Source B (Target Implementation)**: Defective Rating Engine configuration represented as **Platform Config JSON (`.json`)**.
3. **Compilation**: Both sources are compiled into IPIR packages using RateGuard's source-agnostic adapters (`ExcelPricingAdapter` and `PlatformConfigAdapter`).
4. **Autonomous Assurance Execution**: Google ADK multi-agent workflow runs semantic comparison, impact analysis, risk-directed test generation, target execution, premium reconciliation, and 50,000-policy portfolio financial blast-radius exposure analysis.
5. **Verdict**: System renders an evidence-backed decision (**`BLOCK_DEPLOYMENT`**) backed by 8 lineage records.

---

## Command Execution

Run the complete source-agnostic assurance demo script:

```bash
cd backend
python scripts/run_source_agnostic_assurance_demo.py
```

---

## Expected Output Summary

```text
========================================================
  RateGuard AI -- Source-Agnostic Assurance Workflow    
========================================================

1. Compiling Canonical Excel Actuarial Specification...
   [SUCCESS] Compiled IPIR Package: 'AZ_HO3_2026_09' (Confidence: 1.0)

2. Compiling Defective Target Platform Configuration...
   [SUCCESS] Compiled IPIR Package: 'AZ_HO3_2026_09_DEFECTIVE' (Confidence: 1.0)

3. Executing Google ADK Multi-Agent Autonomous Assurance Workflow...

Run ID:           RUN-DE2DBC73
Assurance Status: [BLOCK_DEPLOYMENT]

Agent Workflow Audit Steps:
  Step 1: [SemanticAssuranceAgent] -> COMPARE_IPIR_PACKAGES
  Step 2: [ImpactAgent] -> ANALYZE_PRICING_IMPACT
  Step 3: [TestPlannerAgent] -> GENERATE_TEST_PLAN
  Step 4: [InvestigationAgent] -> EXECUTE_PRICING_ASSURANCE
  Step 5: [PortfolioAgent] -> ANALYZE_PORTFOLIO_EXPOSURE
  Step 6: [AssuranceDecisionAgent] -> EVALUATE_ASSURANCE_DECISION

Evidence-Backed Executive Recommendation:
BLOCK DEPLOYMENT: Material pricing discrepancies, sequence order drifts, or portfolio financial exposures were behaviorally reproduced.
```

