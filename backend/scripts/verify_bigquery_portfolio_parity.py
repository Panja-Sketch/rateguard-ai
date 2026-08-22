import sys
from pathlib import Path

# Ensure backend root is in sys.path when script is executed directly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.engines.diff.comparator import compare_packages  # noqa: E402
from app.engines.portfolio.analyzer import PortfolioAnalyzer  # noqa: E402
from app.ipir.package import IPIRPackage  # noqa: E402
from app.storage.portfolio.bigquery_repository import BigQueryPortfolioRepository  # noqa: E402
from app.storage.portfolio.local_repository import LocalPortfolioRepository  # noqa: E402


def verify_parity() -> bool:
    """Verifies 100% financial and exposure metric parity between CSV and BigQuery repositories."""
    root_dir = Path(__file__).resolve().parent.parent.parent
    canonical_file = (
        root_dir / "data" / "implementations" / "canonical" / "AZ_HO3_2026_09_ipir.json"
    )
    defective_file = (
        root_dir / "data" / "implementations" / "defective" / "AZ_HO3_2026_09_ipir.json"
    )

    with open(canonical_file, encoding="utf-8") as f:
        canonical_pkg = IPIRPackage.model_validate_json(f.read())
    with open(defective_file, encoding="utf-8") as f:
        defective_pkg = IPIRPackage.model_validate_json(f.read())

    print("========================================================")
    print("   RateGuard AI -- BigQuery & CSV Parity Verification   ")
    print("========================================================\n")

    local_repo = LocalPortfolioRepository()
    bq_repo = BigQueryPortfolioRepository()

    # Load first 1,000 policy sample for rapid parity verification
    print("1. Loading Local CSV Repository Policies...")
    local_pols = [p.to_dict() for p in local_repo.load_policies(limit=1000)]
    print(f"   Loaded {len(local_pols):,} policies.\n")

    print("2. Loading BigQuery Repository Policies...")
    try:
        bq_pols = [p.to_dict() for p in bq_repo.load_policies(limit=1000)]
        print(f"   Loaded {len(bq_pols):,} policies from BigQuery.\n")
    except Exception as e:
        print(f"   [ERROR] Failed to query BigQuery: {e}")
        return False

    analyzer = PortfolioAnalyzer()
    diff_res = compare_packages(canonical_pkg, defective_pkg)

    print("3. Executing Local Portfolio Analysis...")
    res_local = analyzer.analyze(local_pols, canonical_pkg, defective_pkg, diff_result=diff_res)

    print("4. Executing BigQuery Portfolio Analysis...")
    res_bq = analyzer.analyze(bq_pols, canonical_pkg, defective_pkg, diff_result=diff_res)

    print("\n--------------------------------------------------------")
    print("Metrics Parity Comparison (Sample: 1,000 Policies):")
    print(f"  Exposed Policy Count:        Local={res_local.exposed_policy_count:,} | BQ={res_bq.exposed_policy_count:,}")
    print(f"  Financially Affected Count: Local={res_local.financially_affected_count:,} | BQ={res_bq.financially_affected_count:,}")
    print(f"  Signed Variance ($):         Local=${res_local.total_signed_variance:,.2f} | BQ=${res_bq.total_signed_variance:,.2f}")
    print(f"  Absolute Variance ($):       Local=${res_local.total_absolute_variance:,.2f} | BQ=${res_bq.total_absolute_variance:,.2f}")
    print("--------------------------------------------------------\n")

    parity_passed = (
        res_local.exposed_policy_count == res_bq.exposed_policy_count
        and res_local.financially_affected_count == res_bq.financially_affected_count
        and res_local.total_signed_variance == res_bq.total_signed_variance
        and res_local.total_absolute_variance == res_bq.total_absolute_variance
    )

    if parity_passed:
        print("STATUS: PERFECT PARITY VERIFIED (100% equivalence)")
        print("========================================================\n")
        return True
    else:
        print("STATUS: PARITY DISCREPANCY DETECTED")
        print("========================================================\n")
        return False


if __name__ == "__main__":
    success = verify_parity()
    if not success:
        sys.exit(1)

