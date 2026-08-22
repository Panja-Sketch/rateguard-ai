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
                    product_id=row["product_id"],
                    state=row["state"],
                    form=row["form"],
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
                    canonical_premium=Decimal(row["canonical_premium"]),
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
    output_json = root_dir / "data" / "portfolio" / "az_ho3_2026_portfolio_impact.json"

    if not canonical_file.exists() or not defective_file.exists() or not csv_file.exists():
        print("Error: Required input files not found.")
        sys.exit(1)

    with open(canonical_file, encoding="utf-8") as f:
        canonical_pkg = IPIRPackage.model_validate_json(f.read())

    with open(defective_file, encoding="utf-8") as f:
        defective_pkg = IPIRPackage.model_validate_json(f.read())

    print("Loading 50,000 synthetic policies...")
    policies = load_synthetic_portfolio_csv(csv_file)

    print("Executing RateGuard Portfolio Blast Radius & Financial Exposure Analysis...")
    analyzer = PortfolioAnalyzer()
    res = analyzer.analyze(policies, canonical_pkg, defective_pkg)

    # Write output JSON artifact
    with open(output_json, "w", encoding="utf-8") as f:
        f.write(res.model_dump_json(indent=2))
        f.write("\n")

    print("\n========================================================")
    print("           RateGuard Portfolio Financial Exposure        ")
    print("========================================================\n")
    print("Portfolio Overview")
    print("--------------------------------------------------------")
    print(f"Policies Analyzed:                      {res.total_policies:,}")
    print(
        f"Exposed Policies (Semantic Region):     {res.exposed_policy_count:,} "
        f"({res.exposed_policy_pct}%)"
    )
    print(
        f"Behaviorally Affected (Trace Diverged): {res.behaviorally_affected_count:,} "
        f"({res.behaviorally_affected_pct}%)"
    )
    print(
        f"Financially Affected (Premium Variance): {res.financially_affected_count:,} "
        f"({res.financially_affected_pct}%)\n"
    )

    print("Financial Exposure Metrics")
    print("--------------------------------------------------------")
    print(f"Expected Canonical Premium:              ${res.total_expected_premium:,.2f}")
    print(f"Target Engine Premium:                ${res.total_target_premium:,.2f}")
    print(f"Signed Premium Variance:                ${res.total_signed_variance:,.2f}")
    print(f"Total Absolute Variance:              ${res.total_absolute_variance:,.2f}")
    print(
        f"Undercharged Policies:                {res.undercharged_policy_count:,} "
        f"(Total Undercharge: ${res.total_undercharge_amount:,.2f})"
    )
    print(
        f"Overcharged Policies:                 {res.overcharged_policy_count:,} "
        f"(Total Overcharge: ${res.total_overcharge_amount:,.2f})"
    )
    print(
        f"Average Variance per Affected Policy: ${res.average_variance_per_affected_policy:,.2f}"
    )
    print(f"Maximum Single Policy Variance:       ${res.max_single_policy_variance:,.2f}\n")

    print("Issue-by-Issue Exposure Breakdown")
    print("--------------------------------------------------------")
    for issue in res.issue_breakdown:
        print(f"Issue: {issue.issue_name}")
        exp_c = f"{issue.exposed_count:,}"
        beh_c = f"{issue.behaviorally_affected_count:,}"
        fin_c = f"{issue.financially_affected_count:,}"
        print(f"  Exposed: {exp_c} | Behavioral: {beh_c} | Financial: {fin_c}")
        sig_v = f"${issue.signed_variance:,.2f}"
        abs_v = f"${issue.absolute_variance:,.2f}"
        print(f"  Signed Variance: {sig_v} | Absolute Variance: {abs_v}\n")

    print("Overlapping & Multi-Defect Exposure")
    print("--------------------------------------------------------")
    print(f"Policies Affected by Multiple Issues:   {res.multi_defect_policy_count:,}\n")

    print("Performance & Execution Telemetry")
    print("--------------------------------------------------------")
    t_sec = res.performance_telemetry["elapsed_seconds"]
    t_pps = res.performance_telemetry["policies_per_second"]
    print(f"Elapsed Runtime:                        {t_sec} seconds")
    print(f"Analysis Throughput:                    {t_pps:,} policies/sec")
    print("========================================================\n")


if __name__ == "__main__":
    main()

