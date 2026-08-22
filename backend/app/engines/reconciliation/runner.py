from app.engines.diff import compare_packages
from app.engines.impact import ImpactAnalyzer
from app.engines.oracle import PremiumOracle, RiskInput
from app.engines.reconciliation.comparator import ReconciliationEngine
from app.engines.reconciliation.models import PricingAssuranceRun, RootCauseFinding
from app.engines.target.ipir_target import IPIRRatingTarget
from app.engines.testing.planner import PricingTestPlanner
from app.ipir.package import IPIRPackage


class PricingAssuranceRunner:
    """End-to-end deterministic runner executing full RateGuard pricing assurance pipeline."""

    def run_assurance(
        self, canonical_package: IPIRPackage, target_package: IPIRPackage
    ) -> PricingAssuranceRun:
        """Executes full assurance pipeline: diff -> impact -> testing -> target -> recon."""
        # 1. Semantic Diff
        diff_result = compare_packages(canonical_package, target_package)

        # 2. Impact Analysis
        impact = ImpactAnalyzer().analyze(diff_result, canonical_package)

        # 3. Test Planning
        test_plan = PricingTestPlanner().generate_plan(canonical_package, diff_result, impact)

        # 4. Engine Execution & Reconciliation
        oracle = PremiumOracle()
        target_engine = IPIRRatingTarget(target_id=target_package.id)
        reconciler = ReconciliationEngine()

        recon_results = []
        matched_count = 0
        mismatch_count = 0
        unique_root_causes: dict[str, RootCauseFinding] = {}
        exercised_diff_ids: set[str] = set()

        for scenario in test_plan.selected_scenarios:
            risk = RiskInput(values=scenario.risk_values)

            # Execute Oracle (Expected)
            expected_res = oracle.calculate(
                package=canonical_package,
                risk=risk,
                effective_date=scenario.effective_date,
                transaction_type=scenario.transaction_type,
            )

            # Execute Target Engine (Actual)
            actual_res = target_engine.quote(
                package=target_package,
                risk=risk,
                effective_date=scenario.effective_date,
                transaction_type=scenario.transaction_type,
            )

            # Reconcile Results
            recon = reconciler.reconcile(
                scenario=scenario,
                expected=expected_res,
                actual=actual_res,
                diff_result=diff_result,
                package=canonical_package,
            )
            recon_results.append(recon)

            if recon.premium_matches:
                matched_count += 1
            else:
                mismatch_count += 1
                if recon.root_cause:
                    unique_root_causes[recon.root_cause.node_id] = recon.root_cause
                    if recon.root_cause.evidence.get("semantic_difference_id"):
                        exercised_diff_ids.add(recon.root_cause.evidence["semantic_difference_id"])

        # Calculate defect reproduction rate (% of semantic diffs reproduced behaviorally)
        total_diff_count = len(diff_result.differences)
        reproduced_diff_count = len(exercised_diff_ids)
        defect_repro_rate = (
            (reproduced_diff_count / total_diff_count * 100.0) if total_diff_count else 100.0
        )

        overall_status = "FAIL" if mismatch_count > 0 else "PASS"

        cand_red_pct = test_plan.coverage_metrics.get("candidate_reduction_pct", 0.0)
        sem_cov_pct = test_plan.coverage_metrics.get("semantic_difference_coverage_pct", 0.0)

        return PricingAssuranceRun(
            test_plan=test_plan,
            execution_results=recon_results,
            passed_count=matched_count,
            failed_count=mismatch_count,
            matched_count=matched_count,
            mismatch_count=mismatch_count,
            candidate_reduction_pct=cand_red_pct,
            semantic_difference_coverage_pct=sem_cov_pct,
            defect_reproduction_rate_pct=round(defect_repro_rate, 2),
            discovered_root_causes=list(unique_root_causes.values()),
            overall_status=overall_status,
            run_metadata={
                "canonical_id": canonical_package.id,
                "target_id": target_package.id,
                "diff_count": total_diff_count,
            },
        )

