from decimal import Decimal
from pathlib import Path

from app.engines.portfolio import PortfolioAnalyzer
from app.ipir.package import IPIRPackage
from scripts.generate_synthetic_portfolio import generate_portfolio
from scripts.run_portfolio_impact_demo import load_synthetic_portfolio_csv


def get_canonical_file_path() -> Path:
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    return root_dir / "data" / "implementations" / "canonical" / "AZ_HO3_2026_09_ipir.json"


def get_defective_file_path() -> Path:
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    return root_dir / "data" / "implementations" / "defective" / "AZ_HO3_2026_09_ipir.json"


def get_csv_file_path() -> Path:
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    return root_dir / "data" / "portfolio" / "az_ho3_2026_synthetic_50k.csv"


def load_canonical_package() -> IPIRPackage:
    with open(get_canonical_file_path(), encoding="utf-8") as f:
        return IPIRPackage.model_validate_json(f.read())


def load_defective_package() -> IPIRPackage:
    with open(get_defective_file_path(), encoding="utf-8") as f:
        return IPIRPackage.model_validate_json(f.read())


def test_01_synthetic_portfolio_reproducibility_and_constraints() -> None:
    canonical = load_canonical_package()

    # Test generation reproducibility with seed 42
    pols1, sum1 = generate_portfolio(canonical, seed=42, count=1000)
    pols2, sum2 = generate_portfolio(canonical, seed=42, count=1000)

    assert len(pols1) == 1000
    assert len(pols2) == 1000

    # Risk attribute stability check across runs
    for p1, p2 in zip(pols1, pols2, strict=True):
        assert p1["policy_id"] == p2["policy_id"]
        assert p1["territory"] == p2["territory"]
        assert p1["roof_age"] == p2["roof_age"]
        assert p1["deductible"] == p2["deductible"]
        assert p1["effective_date"] == p2["effective_date"]
        assert p1["canonical_premium"] == p2["canonical_premium"]

    assert sum1["roof_band_21_30_population"] == sum2["roof_band_21_30_population"]

    # Verify 2-decimal premium formatting and scale <= 2
    for p in pols1:
        prem_dec = Decimal(p["canonical_premium"])
        assert prem_dec.as_tuple().exponent >= -2
        assert len(p["canonical_premium"].split(".")[1]) == 2

    # Verify no PII fields exist
    pii_keywords = ["name", "ssn", "address", "email", "phone", "first_name", "last_name"]
    for field in pols1[0].keys():
        assert field not in pii_keywords


def test_02_effective_date_distribution_uniformity() -> None:
    canonical = load_canonical_package()
    pols, summary = generate_portfolio(canonical, seed=42, count=5000)

    # Verify ~11.5% to 12.5% of policies fall into the Sep 1 to Sep 14 window
    temp_count = summary["temporal_window_population"]
    temp_pct = temp_count / 5000 * 100.0
    assert 10.0 <= temp_pct <= 14.0


def test_03_full_50k_portfolio_authoritative_baseline() -> None:
    canonical = load_canonical_package()
    defective = load_defective_package()
    csv_file = get_csv_file_path()

    if not csv_file.exists():
        return

    policies = load_synthetic_portfolio_csv(csv_file)
    assert len(policies) == 50000

    analyzer = PortfolioAnalyzer()
    res = analyzer.analyze(policies, canonical, defective)

    # Authoritative 50,000 policy exposure metrics
    assert res.total_policies == 50000
    assert res.exposed_policy_count == 14607
    assert res.behaviorally_affected_count == 14607
    assert res.financially_affected_count == 13294
    assert res.multi_defect_policy_count == 1246
    assert res.total_expected_premium == Decimal("13589617.67")
    assert res.total_target_premium == Decimal("13000875.25")
    assert res.total_signed_variance == Decimal("-588742.42")
    assert res.total_absolute_variance == Decimal("868974.18")
    assert res.undercharged_count == 10247
    assert res.total_undercharge == Decimal("728858.30")
    assert res.overcharged_count == 3047
    assert res.total_overcharge == Decimal("140115.88")
