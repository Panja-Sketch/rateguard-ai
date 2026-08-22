import csv
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

# Ensure backend root is in sys.path when script is executed directly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.engines.portfolio import PortfolioAnalyzer, SyntheticPolicy  # noqa: E402
from app.ipir.enums import TransactionType  # noqa: E402
from app.ipir.package import IPIRPackage  # noqa: E402


def load_synthetic_portfolio_csv(csv_path: Path) -> list[SyntheticPolicy]:
    """Loads synthetic CSV portfolio into strongly typed SyntheticPolicy list."""
    policies: list[SyntheticPolicy] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            policies.append(
                SyntheticPolicy(
                    policy_id=row["policy_id"],
                    product_id=row.get("product_id", "AZ_HO3"),
                    state=row.get("state", "AZ"),
                    form=row.get("form", "HO3"),
                    transaction_type=TransactionType(row["transaction_type"]),
                    effective_date=date.fromisoformat(row["effective_date"]),
                    territory=row["territory"],
                    roof_age=int(row["roof_age"]),
                    deductible=int(row["deductible"]),
                    protection_class=int(row["protection_class"]),
                    construction_type=row["construction_type"],
                    dwelling_limit=int(row["dwelling_limit"]),
                    multi_policy=row["multi_policy"].lower() == "true",
                    claims_free=row["claims_free"].lower() == "true",
                    claims_free_years=int(row.get("claims_free_years", 3)),
                    canonical_premium=Decimal(row.get("canonical_premium", row.get("expected_canonical_premium", "0"))),
                )
            )
    return policies


def main() -> None:
    root_dir = Path(__file__).resolve().parent.parent.parent
    canonical_file = (
        root_dir / "data" / "implementations" / "canonical" / "AZ_HO3_2026_09_ipir.json"
    )
    defective_file = (
        root_dir / "data" / "implementations" / "defective" / "AZ_HO3_2026_09_ipir.json"
    )
    csv_file = root_dir / "data" / "portfolio" / "az_ho3_2026_synthetic_50k.csv"

    print("\n========================================================")
    print("      RateGuard AI -- 50,000 Policy Portfolio Analyzer  ")
    print("========================================================\n")

    with open(canonical_file, encoding="utf-8") as f:
        canonical_pkg = IPIRPackage.model_validate_json(f.read())

    with open(defective_file, encoding="utf-8") as f:
        defective_pkg = IPIRPackage.model_validate_json(f.read())

    print(f"Loading synthetic portfolio from: {csv_file}")
    policies = load_synthetic_portfolio_csv(csv_file)
    print(f"Loaded {len(policies):,} synthetic policy records.")

    print("\nExecuting Portfolio Analyzer across 50,000 policies...")
    analyzer = PortfolioAnalyzer()
    res = analyzer.analyze(policies, canonical_pkg, defective_pkg)

    print("\n--------------------------------------------------------")
    print("PORTFOLIO BLAST RADIUS & FINANCIAL EXPOSURE RESULTS")
    print("--------------------------------------------------------")
    print(f"Total Portfolio Policies:      {res.total_policies:,}")
    print(f"Exposed Policies (in DAG):    {res.exposed_policy_count:,} ({res.exposed_policy_pct:.2f}%)")
    print(f"Financially Affected Policies: {res.financially_affected_count:,} ({res.financially_affected_pct:.2f}%)")
    print(f"Total Expected Premium:        ${res.total_expected_premium:,.2f}")
    print(f"Total Billed Premium (Target): ${res.total_target_premium:,.2f}")
    print(f"Net Signed Variance (Exposure): ${res.total_signed_variance:,.2f}")
    print(f"Total Absolute Variance:       ${res.total_absolute_variance:,.2f}")

    print("\nEXPOSURE BREAKDOWN BY DEFECT / ISSUE:")
    for de in res.defect_exposures:
        print(f"\n  Issue ID:   {de.issue_id} ({de.issue_name})")
        print(f"    Exposed Policies:          {de.exposed_count:,} ({de.exposed_policy_pct:.2f}%)")
        print(f"    Financially Affected:       {de.financially_affected_count:,} ({de.affected_policy_pct:.2f}%)")
        print(f"    Signed Net Exposure:        ${de.signed_variance:,.2f}")
        print(f"    Absolute Variance:          ${de.absolute_variance:,.2f}")

    output_json = root_dir / "data" / "portfolio" / "az_ho3_2026_portfolio_impact.json"
    with open(output_json, "w", encoding="utf-8") as f:
        f.write(res.model_dump_json(indent=2))

    print(f"\nSaved portfolio impact summary JSON to: {output_json}")
    print("========================================================\n")


if __name__ == "__main__":
    main()
