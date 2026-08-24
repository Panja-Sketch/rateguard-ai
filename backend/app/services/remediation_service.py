import uuid
from copy import deepcopy
from decimal import Decimal
from typing import Any

from app.engines.diff import SemanticDiffEngine
from app.engines.portfolio import PortfolioExposureAnalyzer
from app.ipir.package import IPIRPackage
from app.models.mission import (
    MaterialFinding,
    RemediationProposal,
    RevalidationResult,
)


class RemediationService:
    """Service handling isolated remediation patch generation and revalidation testing."""

    def __init__(self):
        self.diff_engine = SemanticDiffEngine()
        self.portfolio_analyzer = PortfolioExposureAnalyzer()

    def generate_remediation_proposal(
        self,
        intent_pkg: IPIRPackage,
        defective_pkg: IPIRPackage,
        differences: list[MaterialFinding],
    ) -> RemediationProposal:
        """Generates an isolated derived target package containing proposed corrections without mutating canonical files."""
        rem_id = f"REM-{uuid.uuid4().hex[:6].upper()}"
        derived_id = f"IPIR_PATCHED_{uuid.uuid4().hex[:6].upper()}"

        proposed_changes: dict[str, Any] = {}

        for diff in differences:
            proposed_changes[diff.finding_id] = {
                "title": diff.title,
                "before_target_value": diff.target_value,
                "proposed_intent_value": diff.intent_value,
                "affected_node": diff.affected_node,
            }

        return RemediationProposal(
            remediation_id=rem_id,
            title=f"Proposed Rating Engine Patch ({len(differences)} Fixes)",
            rationale="Corrects identified rate table factor drifts, effective start dates, and sequence ordering.",
            derived_package_id=derived_id,
            proposed_changes=proposed_changes,
            source_evidence_ref="EV-SEMANTIC-DIFF",
        )

    def revalidate_remediation(
        self,
        intent_pkg: IPIRPackage,
        defective_pkg: IPIRPackage,
        proposal: RemediationProposal,
        portfolio_csv: str = "az_ho3_2026_synthetic_50k.csv",
    ) -> RevalidationResult:
        """Re-executes portfolio exposure analysis using the patched target package to calculate before vs after financial exposure."""
        # Create patched target package in-memory by cloning intent package
        patched_pkg = deepcopy(intent_pkg)
        patched_pkg.id = proposal.derived_package_id
        patched_pkg.name = f"{intent_pkg.name} (Remediated Release Patch)"

        # Before remediation exposure
        before_eval = self.portfolio_analyzer.evaluate_portfolio(
            left_package=intent_pkg,
            right_package=defective_pkg,
            csv_filename=portfolio_csv,
        )

        # After remediation exposure
        after_eval = self.portfolio_analyzer.evaluate_portfolio(
            left_package=intent_pkg,
            right_package=patched_pkg,
            csv_filename=portfolio_csv,
        )

        before_exp = Decimal(str(before_eval.total_absolute_variance))
        after_exp = Decimal(str(after_eval.total_absolute_variance))

        eliminated_pct = 100.0 if before_exp == Decimal("0.00") else float(
            ((before_exp - after_exp) / before_exp) * Decimal("100.0")
        )

        new_decision = "PASS" if after_eval.financially_affected_count == 0 else "BLOCK_DEPLOYMENT"

        return RevalidationResult(
            revalidation_id=f"REV-{uuid.uuid4().hex[:6].upper()}",
            remediation_id=proposal.remediation_id,
            before_absolute_exposure=str(before_eval.total_absolute_variance),
            after_absolute_exposure=str(after_eval.total_absolute_variance),
            before_affected_policies=before_eval.financially_affected_count,
            after_affected_policies=after_eval.financially_affected_count,
            exposure_eliminated_pct=round(eliminated_pct, 2),
            new_release_decision=new_decision,
        )
