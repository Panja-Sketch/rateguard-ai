import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

# Ensure backend root is in sys.path when script is executed directly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.ipir.common import EffectivePeriod, NodeReference  # noqa: E402
from app.ipir.enums import ProvenanceSourceType  # noqa: E402
from app.ipir.package import IPIRPackage  # noqa: E402
from app.ipir.provenance import Provenance, SourceReference  # noqa: E402
from app.ipir.tables import RangeMatch  # noqa: E402
from scripts.build_az_ho3_rate_plan import build_canonical_package  # noqa: E402


def build_defective_package() -> IPIRPackage:
    """Loads canonical package and injects 3 controlled defects for RateGuard testing."""
    pkg = build_canonical_package()

    # Define defective package metadata
    pkg.id = "AZ_HO3_2026_09_DEFECTIVE"
    pkg.name = "Arizona Homeowners HO3 Synthetic Defective Implementation Rate Plan"
    pkg.version = "2026.09-defective"

    # Defect 1: Critical Roof Factor (roof_age 21-30: 1.35 -> 1.25)
    roof_table = next(t for t in pkg.tables if t.id == "roof_age_factor")
    for row in roof_table.rows:
        if (
            isinstance(row.matches[0], RangeMatch)
            and row.matches[0].minimum == Decimal("21")
            and row.matches[0].maximum == Decimal("30")
        ):
            row.value = Decimal("1.25")

    # Defect 2: Effective Date Drift on claims_free_discount (2026-09-01 -> 2026-09-15)
    claims_mod = next(m for m in pkg.modifiers if m.id == "claims_free_discount")
    claims_mod.effective_period = EffectivePeriod(start=date(2026, 9, 15))

    # Defect 3: Calculation Order / Sequence Drift
    # Swap sequence numbers of policy_minimum (3 -> 4) and policy_fee (4 -> 3)
    policy_min = next(c for c in pkg.constraints if c.id == "policy_minimum")
    policy_fee = next(f for f in pkg.fees if f.id == "policy_fee")
    policy_min.sequence = 4
    policy_fee.sequence = 3

    calc_min = next(n for n in pkg.calculations if n.id == "premium_after_minimum")
    calc_total = next(n for n in pkg.calculations if n.id == "total_policy_premium")

    # Swapped order: policy_fee (seq 3) applies to premium_after_discounts in calc_min node.
    # policy_minimum (seq 4) applies to total_policy_premium node.
    policy_fee.applies_to = "premium_after_discounts"
    policy_min.applies_to = "premium_after_minimum"

    calc_min.depends_on = ["premium_after_discounts", "policy_fee"]
    calc_total.expression = NodeReference(ref="premium_after_minimum")
    calc_total.depends_on = ["premium_after_minimum", "policy_minimum"]

    # Defective Provenance
    pkg.provenance = Provenance(
        sources=[
            SourceReference(
                source_type=ProvenanceSourceType.RATING_ENGINE,
                source_id="synthetic-rating-engine-implementation",
                source_name="Synthetic Rating Engine Implementation",
                source_version="2026.09-defective",
            )
        ],
        extraction_confidence=Decimal("1.0"),
        interpretation_confidence=Decimal("1.0"),
        notes=(
            "Synthetic hackathon defective implementation package; "
            "intentionally contains controlled pricing defects for RateGuard assurance testing."
        ),
    )

    return pkg


def main() -> None:
    pkg = build_defective_package()

    root_dir = Path(__file__).resolve().parent.parent.parent
    defective_dir = root_dir / "data" / "implementations" / "defective"
    defective_dir.mkdir(parents=True, exist_ok=True)

    defective_file = defective_dir / "AZ_HO3_2026_09_ipir.json"
    manifest_file = defective_dir / "DEFECT_MANIFEST.json"

    # Write defective IPIR JSON
    with open(defective_file, "w", encoding="utf-8") as f:
        f.write(pkg.model_dump_json(indent=2))
        f.write("\n")

    print(f"Successfully wrote defective IPIR package to: {defective_file}")

    # Write Defect Manifest
    manifest_data = {
        "package_id": pkg.id,
        "base_canonical_id": "AZ_HO3_2026_09",
        "defects": [
            {
                "id": "DEFECT_ROOF_AGE_FACTOR",
                "node": "roof_age_factor",
                "semantic_path": "tables.roof_age_factor[21..30]",
                "expected": "1.35",
                "implemented": "1.25",
                "severity": "CRITICAL",
                "description": "Roof age 21-30 rating factor reduced from 1.35 to 1.25",
            },
            {
                "id": "DEFECT_CLAIMS_FREE_EFFECTIVE_DATE",
                "node": "claims_free_discount",
                "semantic_path": "modifiers.claims_free_discount.effective_period",
                "expected": "2026-09-01",
                "implemented": "2026-09-15",
                "severity": "HIGH",
                "description": "Claims-free discount effective start date delayed by 14 days",
            },
            {
                "id": "DEFECT_PREMIUM_SEQUENCE_DRIFT",
                "node": "policy_minimum / policy_fee",
                "semantic_path": "constraints.policy_minimum.sequence",
                "expected": "policy_minimum sequence=3, policy_fee sequence=4",
                "implemented": "policy_fee sequence=3, policy_minimum sequence=4",
                "severity": "CRITICAL",
                "description": "Minimum policy premium constraint sequence swapped with policy fee",
            },
        ],
    }

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
        f.write("\n")

    print(f"Successfully wrote defect manifest to: {manifest_file}")

    # Reload & re-validate defective package
    with open(defective_file, encoding="utf-8") as f:
        reloaded_pkg = IPIRPackage.model_validate_json(f.read())
    print(f"Successfully reloaded & re-validated defective package: '{reloaded_pkg.id}'\n")


if __name__ == "__main__":
    main()
