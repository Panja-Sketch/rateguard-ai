from pathlib import Path

from app.ipir.package import IPIRPackage
from scripts.generate_synthetic_portfolio import generate_portfolio


def get_canonical_file_path() -> Path:
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    return root_dir / "data" / "implementations" / "canonical" / "AZ_HO3_2026_09_ipir.json"


def load_canonical_package() -> IPIRPackage:
    with open(get_canonical_file_path(), encoding="utf-8") as f:
        return IPIRPackage.model_validate_json(f.read())


def test_01_synthetic_portfolio_reproducibility_and_constraints() -> None:
    canonical = load_canonical_package()

    # Small 1,000 policy test generation for speed
    pols1, sum1 = generate_portfolio(canonical, seed=42, count=1000)
    pols2, sum2 = generate_portfolio(canonical, seed=42, count=1000)

    assert len(pols1) == 1000
    assert len(pols2) == 1000
    assert pols1[0]["policy_id"] == "POL-AZ-000001"
    assert pols1[0]["canonical_premium"] == pols2[0]["canonical_premium"]
    assert sum1["roof_band_21_30_population"] == sum2["roof_band_21_30_population"]

    # Verify no PII fields exist
    pii_keywords = ["name", "ssn", "address", "email", "phone", "first_name", "last_name"]
    for field in pols1[0].keys():
        assert field not in pii_keywords

