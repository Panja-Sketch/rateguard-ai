from datetime import date, timedelta
from typing import Any

from app.engines.diff.enums import DifferenceType
from app.engines.diff.models import SemanticDiffResult
from app.engines.impact.models import ImpactAnalysis
from app.engines.testing.boundary_generator import generate_range_boundary_values
from app.engines.testing.models import PricingTestScenario, ScenarioClassification
from app.ipir.package import IPIRPackage


def generate_candidate_scenarios(
    diff_result: SemanticDiffResult,
    impact: ImpactAnalysis,
    package: IPIRPackage,
) -> list[PricingTestScenario]:
    """Generates an initial candidate set of risk-directed test scenarios.

    Systematically exercises range boundaries, interior values, control baseline scenarios,
    temporal effective date boundaries, and sequence order sensitivity.
    """
    candidates: list[PricingTestScenario] = []
    counter = 1
    pkg_start = package.effective_period.start

    # Base baseline risk dictionary
    base_risk: dict[str, Any] = {
        "territory": "T05",
        "roof_age": 10,
        "deductible": 1000,
        "protection_class": 3,
        "construction_type": "FRAME",
        "dwelling_limit": 350000,
        "multi_policy": True,
        "claims_free": True,
        "claims_free_years": 5,
    }

    # 1. Control Baseline Scenario
    candidates.append(
        PricingTestScenario(
            id=f"RG_CAND_{counter:03d}",
            name="Baseline Control Scenario",
            risk_values=dict(base_risk),
            effective_date=pkg_start + timedelta(days=20),
            classification=ScenarioClassification.CONTROL,
            target_difference_ids=[],
            target_node_ids=[],
            tags=["CONTROL"],
            purpose="Baseline control scenario to verify baseline pricing engine stability.",
        )
    )
    counter += 1

    # 2. Risk Predicate Boundary & Interior Scenarios
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
            inp_def = next((i for i in package.inputs if i.id == field_name), None)

            for label, b_val in bounds.items():
                if inp_def:
                    if inp_def.minimum is not None:
                        b_val = max(int(str(inp_def.minimum)), b_val)
                    if inp_def.maximum is not None:
                        b_val = min(int(str(inp_def.maximum)), b_val)

                risk = dict(base_risk)
                risk[field_name] = b_val
                eff_date = pkg_start + timedelta(days=20)

                is_control = label in ("just_below", "just_above")
                scenario_id = f"RG_CAND_{counter:03d}"
                counter += 1

                t_diff_ids = [
                    d.id
                    for d in diff_result.differences
                    if field_name in str(d.semantic_path)
                    or field_name in d.node_id
                    or field_name in d.description
                ]
                t_node_ids = [
                    d.node_id
                    for d in diff_result.differences
                    if field_name in str(d.semantic_path)
                    or field_name in d.node_id
                    or field_name in d.description
                ]

                classification = (
                    ScenarioClassification.CONTROL
                    if is_control
                    else ScenarioClassification.BOUNDARY
                )
                tag_label = "CONTROL" if is_control else "BOUNDARY"

                candidates.append(
                    PricingTestScenario(
                        id=scenario_id,
                        name=f"Predicate Boundary Scenario ({field_name}={b_val} [{label}])",
                        risk_values=risk,
                        effective_date=eff_date,
                        classification=classification,
                        target_difference_ids=t_diff_ids,
                        target_node_ids=t_node_ids,
                        tags=[tag_label, f"VAL_{b_val}"],
                        purpose=(
                            f"Test predicate boundary for {field_name} at "
                            f"value {b_val} ({label})."
                        ),
                    )
                )

    # 3. Temporal Effective Date Shift Scenarios
    date_diffs = [
        d
        for d in diff_result.differences
        if d.difference_type == DifferenceType.EFFECTIVE_DATE_CHANGE
    ]
    for diff in date_diffs:
        target_start = None
        if diff.right_value:
            try:
                target_start = date.fromisoformat(str(diff.right_value))
            except ValueError:
                pass

        if target_start and target_start > pkg_start:
            pre_drift_date = pkg_start + timedelta(days=5)
            post_drift_date = target_start + timedelta(days=5)

            candidates.append(
                PricingTestScenario(
                    id=f"RG_CAND_{counter:03d}",
                    name=f"Temporal Effective Date Drift Pre-Window ({diff.node_id})",
                    risk_values=dict(base_risk),
                    effective_date=pre_drift_date,
                    classification=ScenarioClassification.TEMPORAL,
                    target_difference_ids=[diff.id],
                    target_node_ids=[diff.node_id],
                    tags=["TEMPORAL", "PRE_WINDOW"],
                    purpose=(
                        f"Verify pricing behavior prior to delayed "
                        f"effective date {target_start}."
                    ),
                )
            )
            counter += 1

            candidates.append(
                PricingTestScenario(
                    id=f"RG_CAND_{counter:03d}",
                    name=f"Temporal Effective Date Drift Post-Window ({diff.node_id})",
                    risk_values=dict(base_risk),
                    effective_date=post_drift_date,
                    classification=ScenarioClassification.TEMPORAL,
                    target_difference_ids=[diff.id],
                    target_node_ids=[diff.node_id],
                    tags=["TEMPORAL", "POST_WINDOW"],
                    purpose=f"Verify pricing behavior after delayed effective date {target_start}.",
                )
            )
            counter += 1

    # 4. Calculation Sequence Order Mismatch Scenarios
    order_diffs = [
        d for d in diff_result.differences if d.difference_type == DifferenceType.ORDER_CHANGE
    ]
    if order_diffs:
        seq_risk = dict(base_risk)
        seq_risk["dwelling_limit"] = 700000
        seq_risk["multi_policy"] = False
        seq_risk["claims_free"] = False

        candidates.append(
            PricingTestScenario(
                id=f"RG_CAND_{counter:03d}",
                name="Sequence Order Pre-Minimum Floor Scenario",
                risk_values=seq_risk,
                effective_date=pkg_start + timedelta(days=20),
                classification=ScenarioClassification.CONSTRAINT_ORDER,
                target_difference_ids=[d.id for d in order_diffs],
                target_node_ids=[d.node_id for d in order_diffs],
                tags=["SEQUENCE", "ORDER_MISMATCH"],
                purpose="Isolate order dependency between minimum premium floor and fee addition.",
            )
        )
        counter += 1

    return candidates
