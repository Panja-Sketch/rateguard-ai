from datetime import timedelta
from typing import Any

from app.engines.diff.enums import DifferenceType
from app.engines.diff.models import SemanticDiffResult
from app.engines.impact.models import ImpactAnalysis
from app.engines.testing.boundary_generator import generate_range_boundary_values
from app.engines.testing.models import PricingTestScenario
from app.ipir.enums import TransactionType
from app.ipir.package import IPIRPackage


def get_default_base_risk(package: IPIRPackage) -> dict[str, Any]:
    """Derives baseline risk input values matching package constraints."""
    base: dict[str, Any] = {}
    for inp in package.inputs:
        if inp.allowed_values:
            base[inp.id] = inp.allowed_values[0]
        elif inp.data_type.value in ("INTEGER", "DECIMAL", "MONEY"):
            base[inp.id] = inp.minimum if inp.minimum is not None else 10
        elif inp.data_type.value == "BOOLEAN":
            base[inp.id] = False
        elif inp.data_type.value == "DATE":
            base[inp.id] = package.effective_period.start
        else:
            base[inp.id] = "DEFAULT"

    # Specific clean baseline for Arizona HO3 synthetic rate plan
    if package.product.id == "AZ_HO3":
        base.update({
            "territory": "T07",
            "roof_age": 5,
            "deductible": 1000,
            "protection_class": 5,
            "construction_type": "MASONRY",
            "dwelling_limit": 300000,
            "multi_policy": True,
            "claims_free": True,
        })

    return base


def generate_candidate_scenarios(
    diff_result: SemanticDiffResult, impact: ImpactAnalysis, package: IPIRPackage
) -> list[PricingTestScenario]:
    """Generates candidate test scenarios derived from semantic diffs and impact predicates."""
    candidates: list[PricingTestScenario] = []
    base_risk = get_default_base_risk(package)
    pkg_start = package.effective_period.start
    counter = 1

    # 1. Generate Boundary Candidates for Range Table Differences
    for pred in impact.candidate_risk_predicates:
        min_val = None
        max_val = None
        field_name = None

        for clause in pred.clauses:
            field_name = clause.field
            if clause.operator.value in ("GTE", "GT"):
                min_val = clause.value
            elif clause.operator.value in ("LTE", "LT"):
                max_val = clause.value

        if field_name and (min_val is not None or max_val is not None):
            bounds = generate_range_boundary_values(min_val, max_val)
            for label, b_val in bounds.items():
                risk = dict(base_risk)
                risk[field_name] = b_val

                is_control = label in ("just_below", "just_above")
                scenario_id = f"RG_CAND_{counter:03d}"
                counter += 1

                t_diff_ids = [
                    d.id for d in diff_result.differences if field_name in d.semantic_path
                ]
                t_node_ids = [
                    d.node_id for d in diff_result.differences if field_name in d.semantic_path
                ]

                candidates.append(
                    PricingTestScenario(
                        id=scenario_id,
                        name=f"Range Boundary Test ({field_name}={b_val} [{label}])",
                        risk_values=risk,
                        effective_date=pkg_start,
                        transaction_type=TransactionType.NEW_BUSINESS,
                        purpose=f"Test boundary condition '{label}' for {field_name}={b_val}",
                        target_difference_ids=t_diff_ids,
                        target_node_ids=t_node_ids,
                        tags=["BOUNDARY", "CONTROL" if is_control else "TARGETED", field_name],
                    )
                )

        # 2. Generate Temporal Discrepancy Candidates
        if pred.temporal_start and pred.temporal_end:
            win_start = max(pkg_start, pred.temporal_start)
            dates = [
                (win_start, "window_start", "TARGETED"),
                (win_start + timedelta(days=5), "inside_window", "TARGETED"),
                (pred.temporal_end - timedelta(days=1), "inside_window_end", "TARGETED"),
                (pred.temporal_end, "window_end", "CONTROL"),
                (pred.temporal_end + timedelta(days=5), "after_window", "CONTROL"),
            ]
            t_eff_diffs = [
                d.id
                for d in diff_result.differences
                if d.difference_type == DifferenceType.EFFECTIVE_DATE_CHANGE
            ]
            t_eff_nodes = [
                d.node_id
                for d in diff_result.differences
                if d.difference_type == DifferenceType.EFFECTIVE_DATE_CHANGE
            ]

            for t_date, label, tag in dates:
                risk = dict(base_risk)
                scenario_id = f"RG_CAND_{counter:03d}"
                counter += 1

                candidates.append(
                    PricingTestScenario(
                        id=scenario_id,
                        name=f"Temporal Drift Test ({label} date={t_date})",
                        risk_values=risk,
                        effective_date=t_date,
                        transaction_type=TransactionType.NEW_BUSINESS,
                        purpose=(
                            f"Test temporal discrepancy window condition '{label}' on date {t_date}"
                        ),
                        target_difference_ids=t_eff_diffs,
                        target_node_ids=t_eff_nodes,
                        tags=["TEMPORAL", tag],
                    )
                )

    # 3. Generate Interaction Candidate
    risk_interaction = dict(base_risk)
    risk_interaction["roof_age"] = 24
    risk_interaction["territory"] = "T17"
    risk_interaction["construction_type"] = "FRAME"

    candidates.append(
        PricingTestScenario(
            id=f"RG_CAND_{counter:03d}",
            name="Multi-Factor Interaction Test (Roof 24 + T17 + FRAME)",
            risk_values=risk_interaction,
            effective_date=pkg_start,
            transaction_type=TransactionType.NEW_BUSINESS,
            purpose="Test 2D interaction adjustment combined with changed roof age factor",
            target_difference_ids=[d.id for d in diff_result.differences],
            target_node_ids=list({d.node_id for d in diff_result.differences}),
            tags=["INTERACTION", "HIGH_RISK"],
        )
    )
    counter += 1

    # 4. Generate Minimum Premium Exposure Candidate
    risk_min_exposure = dict(base_risk)
    risk_min_exposure.update({
        "territory": "T01",
        "roof_age": 2,
        "deductible": 5000,
        "protection_class": 1,
        "construction_type": "SUPERIOR",
        "dwelling_limit": 150000,
        "multi_policy": True,
        "claims_free": True,
    })

    t_order_diffs = [
        d.id for d in diff_result.differences if d.difference_type == DifferenceType.ORDER_CHANGE
    ]

    candidates.append(
        PricingTestScenario(
            id=f"RG_CAND_{counter:03d}",
            name="Policy Minimum Premium Exposure Test",
            risk_values=risk_min_exposure,
            effective_date=pkg_start,
            transaction_type=TransactionType.NEW_BUSINESS,
            purpose="Expose minimum premium constraint and policy fee sequence order execution",
            target_difference_ids=t_order_diffs,
            target_node_ids=["policy_minimum", "policy_fee"],
            tags=["MINIMUM_PREMIUM", "SEQUENCE_ORDER"],
        )
    )
    counter += 1

    # 5. Renewal Transaction Candidate
    risk_renewal = dict(base_risk)
    candidates.append(
        PricingTestScenario(
            id=f"RG_CAND_{counter:03d}",
            name="Renewal Transaction Control Test",
            risk_values=risk_renewal,
            effective_date=pkg_start,
            transaction_type=TransactionType.RENEWAL,
            purpose="Verify renewal policy transaction context execution",
            target_difference_ids=[],
            target_node_ids=[],
            tags=["RENEWAL", "CONTROL"],
        )
    )

    return candidates

