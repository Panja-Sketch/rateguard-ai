from datetime import timedelta
from typing import Any

from app.engines.diff.enums import DifferenceType
from app.engines.diff.models import SemanticDiffResult
from app.engines.impact.models import ImpactAnalysis
from app.engines.testing.boundary_generator import generate_range_boundary_values
from app.engines.testing.models import PricingTestScenario, ScenarioClassification
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

    if package.product.id == "AZ_HO3":
        base.update({
            "territory": "T07",
            "roof_age": 5,
            "deductible": 1000,
            "protection_class": 5,
            "construction_type": "MASONRY",
            "dwelling_limit": 400000,
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

    group_roof = "ISSUE_ROOF_FACTOR"
    group_temporal = "ISSUE_CLAIMS_FREE_EFFECTIVE_DATE"
    group_order = "ISSUE_PREMIUM_SEQUENCE_ORDER"

    # 1. Range Boundary Candidates for roof_age_factor
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
                eff_date = pkg_start + timedelta(days=20)

                is_control = label in ("just_below", "just_above")
                scenario_id = f"RG_CAND_{counter:03d}"
                counter += 1

                t_diff_ids = [
                    d.id for d in diff_result.differences if field_name in d.semantic_path
                ]
                t_node_ids = [
                    d.node_id for d in diff_result.differences if field_name in d.semantic_path
                ]

                classification = (
                    ScenarioClassification.CONTROL
                    if is_control
                    else ScenarioClassification.BOUNDARY
                )

                candidates.append(
                    PricingTestScenario(
                        id=scenario_id,
                        name=f"Roof Range Boundary Test ({field_name}={b_val} [{label}])",
                        risk_values=risk,
                        effective_date=eff_date,
                        transaction_type=TransactionType.NEW_BUSINESS,
                        purpose=f"Test roof boundary '{label}' for {field_name}={b_val}",
                        classification=classification,
                        target_difference_ids=t_diff_ids,
                        target_issue_group_ids=[group_roof] if not is_control else [],
                        target_node_ids=t_node_ids,
                        tags=["BOUNDARY", "CONTROL" if is_control else "SINGLE_DEFECT", field_name],
                    )
                )

        # 2. Temporal Discrepancy Window Candidates
        if pred.temporal_start and pred.temporal_end:
            win_start = max(pkg_start, pred.temporal_start)

            temporal_risk = dict(base_risk)
            temporal_risk.update({
                "dwelling_limit": 700000,
                "roof_age": 5,
                "multi_policy": True,
                "claims_free": True,
            })

            cls_temp = ScenarioClassification.TEMPORAL
            cls_ctrl = ScenarioClassification.CONTROL

            dates = [
                (win_start + timedelta(days=5), "inside_window", cls_temp, True),
                (pred.temporal_end, "window_end", cls_ctrl, False),
                (pred.temporal_end + timedelta(days=10), "after_window", cls_ctrl, False),
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

            for t_date, label, cls, is_target in dates:
                scenario_id = f"RG_CAND_{counter:03d}"
                counter += 1

                candidates.append(
                    PricingTestScenario(
                        id=scenario_id,
                        name=f"Claims-Free Temporal Drift Test ({label} date={t_date})",
                        risk_values=temporal_risk,
                        effective_date=t_date,
                        transaction_type=TransactionType.NEW_BUSINESS,
                        purpose=f"Isolate claims-free discount temporal drift on date {t_date}",
                        classification=cls,
                        target_difference_ids=t_eff_diffs if is_target else [],
                        target_issue_group_ids=[group_temporal] if is_target else [],
                        target_node_ids=t_eff_nodes if is_target else [],
                        tags=["TEMPORAL", "SINGLE_DEFECT" if is_target else "CONTROL"],
                    )
                )

    # 3. Minimum / Fee Sequence Order Exposure Candidate
    order_risk = dict(base_risk)
    order_risk.update({
        "territory": "T07",
        "roof_age": 5,
        "deductible": 1000,
        "protection_class": 5,
        "construction_type": "MASONRY",
        "dwelling_limit": 300000,
        "multi_policy": False,
        "claims_free": False,
    })
    order_date = pkg_start + timedelta(days=20)
    t_order_diffs = [
        d.id for d in diff_result.differences if d.difference_type == DifferenceType.ORDER_CHANGE
    ]

    candidates.append(
        PricingTestScenario(
            id=f"RG_CAND_{counter:03d}",
            name="Policy Minimum vs Fee Execution Order Test",
            risk_values=order_risk,
            effective_date=order_date,
            transaction_type=TransactionType.NEW_BUSINESS,
            purpose="Expose minimum premium constraint vs policy fee sequence order execution",
            classification=ScenarioClassification.CONSTRAINT_ORDER,
            target_difference_ids=t_order_diffs,
            target_issue_group_ids=[group_order],
            target_node_ids=["policy_minimum", "policy_fee"],
            tags=["CONSTRAINT_ORDER", "SINGLE_DEFECT"],
        )
    )
    counter += 1

    # 4. Multi-Factor Interaction Candidate
    risk_interaction = dict(base_risk)
    risk_interaction.update({
        "roof_age": 24,
        "territory": "T17",
        "construction_type": "FRAME",
        "dwelling_limit": 400000,
    })

    candidates.append(
        PricingTestScenario(
            id=f"RG_CAND_{counter:03d}",
            name="Multi-Factor Interaction Test (Roof 24 + T17 + FRAME)",
            risk_values=risk_interaction,
            effective_date=pkg_start + timedelta(days=20),
            transaction_type=TransactionType.NEW_BUSINESS,
            purpose="Test 2D interaction adjustment combined with changed roof age factor",
            classification=ScenarioClassification.INTERACTION,
            target_difference_ids=[d.id for d in diff_result.differences],
            target_issue_group_ids=[group_roof],
            target_node_ids=list({d.node_id for d in diff_result.differences}),
            tags=["INTERACTION", "SINGLE_DEFECT"],
        )
    )
    counter += 1

    # 5. True Control Candidate 1 (Unaffected Low-Risk Minimum Capped)
    ctrl_1_risk = dict(base_risk)
    ctrl_1_risk.update({
        "dwelling_limit": 150000,
        "roof_age": 5,
        "territory": "T01",
        "deductible": 5000,
        "multi_policy": True,
        "claims_free": True,
    })
    candidates.append(
        PricingTestScenario(
            id=f"RG_CAND_{counter:03d}",
            name="Unaffected Low-Risk Control (Minimum Premium Capped)",
            risk_values=ctrl_1_risk,
            effective_date=pkg_start + timedelta(days=20),
            transaction_type=TransactionType.NEW_BUSINESS,
            purpose="Verify unaffected low-risk profile where both engines floor at minimum",
            classification=ScenarioClassification.CONTROL,
            target_difference_ids=[],
            target_issue_group_ids=[],
            target_node_ids=[],
            tags=["CONTROL", "LOW_RISK"],
        )
    )
    counter += 1

    # 6. True Control Candidate 2 (Unaffected High-Premium Uncapped)
    ctrl_2_risk = dict(base_risk)
    ctrl_2_risk.update({
        "dwelling_limit": 500000,
        "roof_age": 5,
        "territory": "T07",
        "multi_policy": False,
        "claims_free": False,
    })
    candidates.append(
        PricingTestScenario(
            id=f"RG_CAND_{counter:03d}",
            name="Unaffected High-Premium Control (Uncapped)",
            risk_values=ctrl_2_risk,
            effective_date=pkg_start + timedelta(days=20),
            transaction_type=TransactionType.NEW_BUSINESS,
            purpose="Verify unaffected high-premium policy profile matches perfectly",
            classification=ScenarioClassification.CONTROL,
            target_difference_ids=[],
            target_issue_group_ids=[],
            target_node_ids=[],
            tags=["CONTROL", "HIGH_PREMIUM"],
        )
    )

    return candidates
