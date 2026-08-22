from pathlib import Path

from app.engines.diff import compare_packages
from app.engines.impact import ImpactAnalyzer
from app.engines.testing import PricingTestPlanner, generate_range_boundary_values
from app.ipir.package import IPIRPackage


def get_canonical_file_path() -> Path:
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    return root_dir / "data" / "implementations" / "canonical" / "AZ_HO3_2026_09_ipir.json"


def get_defective_file_path() -> Path:
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    return root_dir / "data" / "implementations" / "defective" / "AZ_HO3_2026_09_ipir.json"


def load_canonical_package() -> IPIRPackage:
    with open(get_canonical_file_path(), encoding="utf-8") as f:
        return IPIRPackage.model_validate_json(f.read())


def load_defective_package() -> IPIRPackage:
    with open(get_defective_file_path(), encoding="utf-8") as f:
        return IPIRPackage.model_validate_json(f.read())


def test_01_boundary_values_generation() -> None:
    bounds = generate_range_boundary_values(21, 30)
    assert bounds["just_below"] == 20
    assert bounds["lower_bound"] == 21
    assert bounds["interior"] == 25
    assert bounds["upper_bound"] == 30
    assert bounds["just_above"] == 31


def test_02_test_plan_generation_and_optimization() -> None:
    canonical = load_canonical_package()
    defective = load_defective_package()

    diff_res = compare_packages(canonical, defective)
    impact = ImpactAnalyzer().analyze(diff_res, canonical)

    planner = PricingTestPlanner()
    plan = planner.generate_plan(canonical, diff_res, impact)

    assert plan.candidate_count > 0
    assert plan.selected_count > 0
    assert plan.selected_count <= plan.candidate_count
    assert plan.coverage_metrics["semantic_difference_coverage_pct"] == 100.0
    assert plan.coverage_metrics["candidate_reduction_pct"] >= 0.0

    # Verify roof boundary coverage scenarios exist in selected plan
    scenarios = plan.selected_scenarios
    roof_values = [s.risk_values.get("roof_age") for s in scenarios if "roof_age" in s.risk_values]
    assert 20 in roof_values
    assert 21 in roof_values
    assert 30 in roof_values or 31 in roof_values
