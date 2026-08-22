from pathlib import Path

from app.engines.diff import compare_packages
from app.engines.impact import ImpactAnalyzer, PricingDependencyGraph
from app.ipir.enums import ComparisonOperator
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


def test_01_dependency_graph_edges_and_descendants() -> None:
    canonical = load_canonical_package()
    graph = PricingDependencyGraph(canonical)

    desc_roof_input = graph.get_descendants("roof_age")
    assert "roof_age_factor" in desc_roof_input
    assert "final_policy_premium" in desc_roof_input

    desc_roof_table = graph.get_descendants("roof_age_factor")
    assert "gross_risk_premium" in desc_roof_table
    assert "total_policy_premium" in desc_roof_table
    assert "final_policy_premium" in desc_roof_table

    anc_output = graph.get_ancestors("final_policy_premium")
    assert "base_rate" in anc_output
    assert "territory" in anc_output
    assert "roof_age" in anc_output


def test_02_2d_table_multi_input_connection() -> None:
    canonical = load_canonical_package()
    graph = PricingDependencyGraph(canonical)

    anc_2d = graph.get_ancestors("territory_construction_adjustment")
    assert "territory" in anc_2d
    assert "construction_type" in anc_2d


def test_03_impact_analysis_downstream_and_paths() -> None:
    canonical = load_canonical_package()
    defective = load_defective_package()

    diff_res = compare_packages(canonical, defective)
    analyzer = ImpactAnalyzer()
    impact = analyzer.analyze(diff_res, canonical)

    assert "roof_age_factor" in impact.changed_nodes
    assert "final_policy_premium" in impact.affected_outputs
    assert len(impact.dependency_paths) > 0

    roof_outputs = [p[-1] for p in impact.dependency_paths if p[0] == "roof_age_factor"]
    assert any(out in impact.affected_outputs for out in roof_outputs)


def test_04_impact_predicates_derived_correctly() -> None:
    canonical = load_canonical_package()
    defective = load_defective_package()

    diff_res = compare_packages(canonical, defective)
    analyzer = ImpactAnalyzer()
    impact = analyzer.analyze(diff_res, canonical)

    roof_pred = next(
        p for p in impact.candidate_risk_predicates
        if "roof_age_factor" in p.id or "21..30" in p.id or "roof_age" in p.description
    )
    assert roof_pred is not None
    assert len(roof_pred.clauses) == 2

    c_gte = next(c for c in roof_pred.clauses if c.operator == ComparisonOperator.GTE)
    c_lte = next(c for c in roof_pred.clauses if c.operator == ComparisonOperator.LTE)
    assert c_gte.field == "roof_age"
    assert c_gte.value == 21
    assert c_lte.field == "roof_age"
    assert c_lte.value == 30

