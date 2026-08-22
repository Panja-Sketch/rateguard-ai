import csv
import json
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

# Ensure backend root is in sys.path when script is executed directly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.engines.oracle import PremiumOracle, RiskInput  # noqa: E402
from app.ipir.enums import TransactionType  # noqa: E402
from app.ipir.package import IPIRPackage  # noqa: E402


def generate_portfolio(
    package: IPIRPackage, seed: int = 42, count: int = 50000
) -> tuple[list[dict], dict]:
    """Generates a deterministic synthetic portfolio of policies with canonical premiums."""
    random.seed(seed)
    oracle = PremiumOracle()

    territories = [f"T{i:02d}" for i in range(1, 21)]
    deductibles = [500, 1000, 2500, 5000]
    constructions = ["FRAME", "MASONRY", "FIRE_RESISTIVE"]
    transaction_types = [TransactionType.NEW_BUSINESS.value, TransactionType.RENEWAL.value]

    pkg_start = package.effective_period.start

    policies: list[dict] = []
    territory_counts: dict[str, int] = {}
    roof_band_21_30_count = 0
    temporal_window_count = 0

    for i in range(1, count + 1):
        policy_id = f"POL-AZ-{i:06d}"

        # Weighted sampling
        territory = random.choice(territories)
        territory_counts[territory] = territory_counts.get(territory, 0) + 1

        # Roof age distribution (0 to 50, ~20% in 21..30)
        if random.random() < 0.20:
            roof_age = random.randint(21, 30)
            roof_band_21_30_count += 1
        else:
            roof_age = random.choice(
                [random.randint(0, 20) for _ in range(4)] + [random.randint(31, 50)]
            )

        deductible = random.choices(deductibles, weights=[15, 60, 20, 5])[0]
        protection_class = random.randint(1, 10)
        construction_type = random.choices(constructions, weights=[40, 45, 15])[0]
        dwelling_limit = random.randint(15, 100) * 10000  # 150k to 1.0M

        multi_policy = random.random() < 0.35
        claims_free = random.random() < 0.70
        claims_free_years = random.randint(3, 10) if claims_free else random.randint(0, 2)

        # Effective date distribution (5% in 2026-09-01..2026-09-14)
        if random.random() < 0.05:
            offset = random.randint(0, 13)
            eff_date = pkg_start + timedelta(days=offset)
            temporal_window_count += 1
        else:
            offset = random.randint(14, 180)
            eff_date = pkg_start + timedelta(days=offset)

        tx_type = random.choices(transaction_types, weights=[30, 70])[0]

        # Calculate authoritative expected premium via Premium Oracle
        risk = RiskInput(
            policy_id=policy_id,
            effective_date=eff_date,
            transaction_type=TransactionType(tx_type),
            values={
                "territory": territory,
                "roof_age": roof_age,
                "deductible": str(deductible),
                "protection_class": protection_class,
                "construction_type": construction_type,
                "dwelling_limit": dwelling_limit,
                "multi_policy": multi_policy,
                "claims_free": claims_free,
                "claims_free_years": claims_free_years,
            },
        )
        oracle_trace = oracle.calculate(
            package, risk, effective_date=eff_date, transaction_type=TransactionType(tx_type)
        )
        expected_premium = oracle_trace.final_premium

        row = {
            "policy_id": policy_id,
            "product_id": package.product.id,
            "state": package.product.jurisdiction.state_or_province or "AZ",
            "form": package.product.form or "HO3",
            "transaction_type": tx_type,
            "effective_date": eff_date.isoformat(),
            "territory": territory,
            "roof_age": roof_age,
            "deductible": deductible,
            "protection_class": protection_class,
            "construction_type": construction_type,
            "dwelling_limit": dwelling_limit,
            "multi_policy": multi_policy,
            "claims_free": claims_free,
            "claims_free_years": claims_free_years,
            "canonical_premium": str(expected_premium),
        }
        policies.append(row)

    summary = {
        "portfolio_size": count,
        "seed": seed,
        "territory_distribution": territory_counts,
        "roof_band_21_30_count": roof_band_21_30_count,
        "roof_band_21_30_population": roof_band_21_30_count,
        "roof_band_21_30_pct": round(roof_band_21_30_count / count * 100, 2),
        "temporal_window_count": temporal_window_count,
        "temporal_window_pct": round(temporal_window_count / count * 100, 2),
        "total_expected_premium": str(
            sum(Decimal(p["canonical_premium"]) for p in policies)
        ),
    }

    return policies, summary


def main() -> None:
    root_dir = Path(__file__).resolve().parent.parent.parent
    canonical_file = (
        root_dir / "data" / "implementations" / "canonical" / "AZ_HO3_2026_09_ipir.json"
    )

    with open(canonical_file, encoding="utf-8") as f:
        package = IPIRPackage.model_validate_json(f.read())

    policies, summary = generate_portfolio(package, seed=42, count=50000)

    portfolio_dir = root_dir / "data" / "portfolio"
    portfolio_dir.mkdir(parents=True, exist_ok=True)

    csv_file = portfolio_dir / "az_ho3_2026_synthetic_50k.csv"
    summary_file = portfolio_dir / "az_ho3_2026_synthetic_50k_summary.json"

    fieldnames = list(policies[0].keys())
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(policies)

    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"Successfully generated 50,000 synthetic policies CSV: {csv_file}")
    print(f"Summary saved to: {summary_file}")


if __name__ == "__main__":
    main()
