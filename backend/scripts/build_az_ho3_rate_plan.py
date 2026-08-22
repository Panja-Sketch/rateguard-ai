import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

# Ensure backend root is in sys.path when script is executed directly
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.ipir.calculations import CalculationNode  # noqa: E402
from app.ipir.common import EffectivePeriod, LiteralValue, NodeReference  # noqa: E402
from app.ipir.constraints import PremiumConstraint, PricingFee, RoundingRule  # noqa: E402
from app.ipir.enums import (  # noqa: E402
    ComparisonOperator,
    ConstraintType,
    ExpressionOperator,
    InputDataType,
    InsuranceLine,
    ModifierType,
    ProvenanceSourceType,
    RoundingMode,
    TableLookupType,
    TransactionType,
)
from app.ipir.expressions import Expression  # noqa: E402
from app.ipir.inputs import PricingInput  # noqa: E402
from app.ipir.modifiers import PricingModifier  # noqa: E402
from app.ipir.package import IPIRPackage, PricingConstant  # noqa: E402
from app.ipir.product import (  # noqa: E402
    CoverageDefinition,
    InsuranceProduct,
    Jurisdiction,
    PricingOutput,
)
from app.ipir.provenance import Provenance, SourceReference  # noqa: E402
from app.ipir.rules import ComparisonCondition  # noqa: E402
from app.ipir.tables import (  # noqa: E402
    ExactMatch,
    RangeMatch,
    RateTable,
    TableDimension,
    TableRow,
)


def build_canonical_package() -> IPIRPackage:
    """Builds the canonical synthetic Arizona HO3 rate plan package."""
    # 1. Product & Effective Period
    product = InsuranceProduct(
        id="AZ_HO3",
        name="Arizona Homeowners HO3 Product",
        line=InsuranceLine.HOMEOWNERS,
        form="HO3",
        jurisdiction=Jurisdiction(country="US", state_or_province="AZ"),
    )
    effective_period = EffectivePeriod(start=date(2026, 9, 1))

    # 2. Primary Rating Inputs
    territories = [f"T{i:02d}" for i in range(1, 21)]
    inputs = [
        PricingInput(
            id="territory",
            name="Territory Code",
            data_type=InputDataType.CATEGORY,
            required=True,
            allowed_values=territories,
        ),
        PricingInput(
            id="roof_age",
            name="Roof Age (Years)",
            data_type=InputDataType.INTEGER,
            required=True,
            minimum=0,
            maximum=80,
            unit="years",
        ),
        PricingInput(
            id="deductible",
            name="Policy Deductible ($)",
            data_type=InputDataType.MONEY,
            required=True,
            minimum=500,
            maximum=5000,
            description="Allowed deductible values: 500, 1000, 2500, 5000",
        ),
        PricingInput(
            id="protection_class",
            name="Public Protection Class",
            data_type=InputDataType.INTEGER,
            required=True,
            minimum=1,
            maximum=10,
        ),
        PricingInput(
            id="construction_type",
            name="Construction Type",
            data_type=InputDataType.CATEGORY,
            required=True,
            allowed_values=["FRAME", "MASONRY", "SUPERIOR"],
        ),
        PricingInput(
            id="dwelling_limit",
            name="Dwelling Coverage Limit ($)",
            data_type=InputDataType.MONEY,
            required=True,
            minimum=100000,
            maximum=2000000,
        ),
        PricingInput(
            id="multi_policy",
            name="Has Multi-Policy Discount",
            data_type=InputDataType.BOOLEAN,
            required=True,
        ),
        PricingInput(
            id="claims_free",
            name="Is Claims Free",
            data_type=InputDataType.BOOLEAN,
            required=True,
        ),
    ]

    # 3. Constants
    constants = [
        PricingConstant(
            id="base_rate",
            name="Annual Base Rate",
            value=Decimal("650.00"),
            description="Synthetic starting annual homeowners base rate",
        ),
        PricingConstant(
            id="minimum_policy_premium_constant",
            name="Minimum Policy Premium Constant",
            value=Decimal("575.00"),
        ),
        PricingConstant(
            id="policy_fee_constant",
            name="Policy Fee Constant",
            value=Decimal("25.00"),
        ),
    ]

    # 4. Tables
    # Territory Table (1D EXACT)
    territory_factors = {
        "T01": "0.88", "T02": "0.90", "T03": "0.92", "T04": "0.94", "T05": "0.96",
        "T06": "0.98", "T07": "1.00", "T08": "1.02", "T09": "1.04", "T10": "1.06",
        "T11": "1.08", "T12": "1.10", "T13": "1.12", "T14": "1.14", "T15": "1.16",
        "T16": "1.18", "T17": "1.20", "T18": "1.22", "T19": "1.24", "T20": "1.26",
    }
    t_table = RateTable(
        id="territory_factor",
        name="Territory Rating Factor Table",
        dimensions=[TableDimension(input_ref="territory", lookup_type=TableLookupType.EXACT)],
        rows=[
            TableRow(matches=[ExactMatch(value=t_code)], value=Decimal(factor))
            for t_code, factor in territory_factors.items()
        ],
    )

    # Roof Age Table (1D RANGE)
    r_table = RateTable(
        id="roof_age_factor",
        name="Roof Age Factor Table",
        dimensions=[TableDimension(input_ref="roof_age", lookup_type=TableLookupType.RANGE)],
        rows=[
            TableRow(matches=[RangeMatch(minimum=0, maximum=5)], value=Decimal("0.90")),
            TableRow(matches=[RangeMatch(minimum=6, maximum=10)], value=Decimal("0.95")),
            TableRow(matches=[RangeMatch(minimum=11, maximum=20)], value=Decimal("1.10")),
            TableRow(matches=[RangeMatch(minimum=21, maximum=30)], value=Decimal("1.35")),
            TableRow(matches=[RangeMatch(minimum=31, maximum=40)], value=Decimal("1.50")),
            TableRow(matches=[RangeMatch(minimum=41, maximum=80)], value=Decimal("1.70")),
        ],
    )

    # Deductible Table (1D EXACT)
    d_factors = {"500": "1.15", "1000": "1.00", "2500": "0.85", "5000": "0.72"}
    d_table = RateTable(
        id="deductible_factor",
        name="Deductible Factor Table",
        dimensions=[TableDimension(input_ref="deductible", lookup_type=TableLookupType.EXACT)],
        rows=[
            TableRow(matches=[ExactMatch(value=ded)], value=Decimal(factor))
            for ded, factor in d_factors.items()
        ],
    )

    # Protection Class Table (1D RANGE)
    pc_table = RateTable(
        id="protection_class_factor",
        name="Protection Class Factor Table",
        dimensions=[
            TableDimension(input_ref="protection_class", lookup_type=TableLookupType.RANGE)
        ],
        rows=[
            TableRow(matches=[RangeMatch(minimum=1, maximum=2)], value=Decimal("0.92")),
            TableRow(matches=[RangeMatch(minimum=3, maximum=4)], value=Decimal("0.96")),
            TableRow(matches=[RangeMatch(minimum=5, maximum=6)], value=Decimal("1.00")),
            TableRow(matches=[RangeMatch(minimum=7, maximum=8)], value=Decimal("1.08")),
            TableRow(matches=[RangeMatch(minimum=9, maximum=10)], value=Decimal("1.18")),
        ],
    )

    # Construction Factor Table (1D EXACT)
    c_factors = {"FRAME": "1.10", "MASONRY": "0.95", "SUPERIOR": "0.88"}
    c_table = RateTable(
        id="construction_factor",
        name="Construction Type Factor Table",
        dimensions=[
            TableDimension(input_ref="construction_type", lookup_type=TableLookupType.EXACT)
        ],
        rows=[
            TableRow(matches=[ExactMatch(value=ctype)], value=Decimal(factor))
            for ctype, factor in c_factors.items()
        ],
    )

    # Dwelling Limit Table (1D RANGE)
    dl_table = RateTable(
        id="dwelling_limit_factor",
        name="Dwelling Limit Factor Table",
        dimensions=[TableDimension(input_ref="dwelling_limit", lookup_type=TableLookupType.RANGE)],
        rows=[
            TableRow(matches=[RangeMatch(minimum=100000, maximum=249999)], value=Decimal("0.85")),
            TableRow(matches=[RangeMatch(minimum=250000, maximum=399999)], value=Decimal("1.00")),
            TableRow(matches=[RangeMatch(minimum=400000, maximum=599999)], value=Decimal("1.15")),
            TableRow(matches=[RangeMatch(minimum=600000, maximum=999999)], value=Decimal("1.35")),
            TableRow(
                matches=[RangeMatch(minimum=1000000, maximum=2000000)],
                value=Decimal("1.60"),
            ),
        ],
    )

    # Territory x Construction Adjustment Table (2D EXACT - 60 combinations)
    tc_rows: list[TableRow] = []
    tc_overrides = {
        ("T17", "FRAME"): "1.08", ("T18", "FRAME"): "1.09",
        ("T19", "FRAME"): "1.10", ("T20", "FRAME"): "1.12",
        ("T17", "MASONRY"): "1.02", ("T18", "MASONRY"): "1.03",
        ("T19", "MASONRY"): "1.04", ("T20", "MASONRY"): "1.05",
    }
    for t_code in territories:
        for c_type in ["FRAME", "MASONRY", "SUPERIOR"]:
            if c_type == "SUPERIOR":
                factor_val = "0.98"
            elif (t_code, c_type) in tc_overrides:
                factor_val = tc_overrides[(t_code, c_type)]
            else:
                factor_val = "1.00"

            tc_rows.append(
                TableRow(
                    matches=[ExactMatch(value=t_code), ExactMatch(value=c_type)],
                    value=Decimal(factor_val),
                )
            )

    tc_table = RateTable(
        id="territory_construction_adjustment",
        name="Territory x Construction Adjustment Table",
        dimensions=[
            TableDimension(input_ref="territory", lookup_type=TableLookupType.EXACT),
            TableDimension(input_ref="construction_type", lookup_type=TableLookupType.EXACT),
        ],
        rows=tc_rows,
    )

    tables = [t_table, r_table, d_table, pc_table, c_table, dl_table, tc_table]

    # 5. Modifiers
    modifiers = [
        PricingModifier(
            id="multi_policy_discount",
            name="Multi-Policy Discount",
            modifier_type=ModifierType.PERCENTAGE_DISCOUNT,
            applies_to="gross_risk_premium",
            effective_period=effective_period,
            value=Decimal("0.12"),
            eligibility=ComparisonCondition(
                left=NodeReference(ref="multi_policy"),
                operator=ComparisonOperator.EQ,
                right=LiteralValue(value=True),
            ),
            sequence=1,
        ),
        PricingModifier(
            id="claims_free_discount",
            name="Claims-Free Discount",
            modifier_type=ModifierType.PERCENTAGE_DISCOUNT,
            applies_to="gross_risk_premium",
            effective_period=effective_period,
            value=Decimal("0.05"),
            eligibility=ComparisonCondition(
                left=NodeReference(ref="claims_free"),
                operator=ComparisonOperator.EQ,
                right=LiteralValue(value=True),
            ),
            sequence=2,
        ),
    ]

    # 6. Constraints & Fees
    constraints = [
        PremiumConstraint(
            id="policy_minimum",
            name="Minimum Policy Premium Constraint",
            constraint_type=ConstraintType.MINIMUM,
            amount=Decimal("575.00"),
            applies_to="premium_after_discounts",
            effective_period=effective_period,
            sequence=3,
        )
    ]
    fees = [
        PricingFee(
            id="policy_fee",
            name="Policy Fee",
            amount=Decimal("25.00"),
            applies_to="premium_after_minimum",
            effective_period=effective_period,
            sequence=4,
        )
    ]

    # 7. Rounding Rules
    rounding_rules = [
        RoundingRule(id="factor_rounding", precision=4, mode=RoundingMode.HALF_UP),
        RoundingRule(id="premium_rounding", precision=2, mode=RoundingMode.HALF_UP),
    ]

    # 8. Calculations (DAG)
    calculations = [
        CalculationNode(
            id="gross_risk_premium",
            name="Gross Risk Premium",
            expression=Expression(
                operator=ExpressionOperator.MULTIPLY,
                operands=[
                    NodeReference(ref="base_rate"),
                    NodeReference(ref="territory_factor"),
                    NodeReference(ref="roof_age_factor"),
                    NodeReference(ref="deductible_factor"),
                    NodeReference(ref="protection_class_factor"),
                    NodeReference(ref="construction_factor"),
                    NodeReference(ref="dwelling_limit_factor"),
                    NodeReference(ref="territory_construction_adjustment"),
                ],
            ),
            depends_on=[
                "base_rate",
                "territory_factor",
                "roof_age_factor",
                "deductible_factor",
                "protection_class_factor",
                "construction_factor",
                "dwelling_limit_factor",
                "territory_construction_adjustment",
            ],
            rounding_rule_ref="premium_rounding",
            description="Base rate multiplied by all risk factor adjustments",
        ),
        CalculationNode(
            id="premium_after_discounts",
            name="Premium After Discounts",
            expression=NodeReference(ref="gross_risk_premium"),
            depends_on=["gross_risk_premium", "multi_policy_discount", "claims_free_discount"],
            rounding_rule_ref="premium_rounding",
            description="Gross risk premium minus applicable discounts",
        ),
        CalculationNode(
            id="premium_after_minimum",
            name="Premium After Minimum Enforced",
            expression=NodeReference(ref="premium_after_discounts"),
            depends_on=["premium_after_discounts", "policy_minimum"],
            rounding_rule_ref="premium_rounding",
            description="Premium after applying $575.00 minimum policy premium constraint",
        ),
        CalculationNode(
            id="total_policy_premium",
            name="Total Policy Premium",
            expression=Expression(
                operator=ExpressionOperator.ADD,
                operands=[
                    NodeReference(ref="premium_after_minimum"),
                    NodeReference(ref="policy_fee"),
                ],
            ),
            depends_on=["premium_after_minimum", "policy_fee"],
            rounding_rule_ref="premium_rounding",
            description="Final total policy premium including $25.00 policy fee",
        ),
    ]

    # 9. Coverage Definition & Outputs
    coverages = [
        CoverageDefinition(
            id="coverage_a_dwelling",
            name="Coverage A - Dwelling",
            calculation_refs=["gross_risk_premium", "total_policy_premium"],
            output_ref="final_policy_premium",
        )
    ]
    outputs = [
        PricingOutput(
            id="final_policy_premium",
            name="Final Policy Premium",
            source_ref="total_policy_premium",
            currency="USD",
            description="Final total billed policy premium",
        )
    ]

    # 10. Provenance
    provenance = Provenance(
        sources=[
            SourceReference(
                source_type=ProvenanceSourceType.ACTUARIAL_SPEC,
                source_id="synthetic-az-ho3-2026-09",
                source_name="Synthetic Arizona HO3 Rate Specification",
                source_version="2026.09",
            )
        ],
        extraction_confidence=Decimal("1.0"),
        interpretation_confidence=Decimal("1.0"),
        notes=(
            "Synthetic hackathon dataset; not a real insurer's rate filing; "
            "intended as canonical pricing intent for RateGuard demonstration."
        ),
    )

    # Construct and return root package
    return IPIRPackage(
        ipir_version="0.1",
        id="AZ_HO3_2026_09",
        name="Arizona Homeowners HO3 Synthetic Rate Plan",
        version="2026.09",
        product=product,
        effective_period=effective_period,
        transaction_types=[TransactionType.NEW_BUSINESS, TransactionType.RENEWAL],
        inputs=inputs,
        constants=constants,
        tables=tables,
        rules=[],
        calculations=calculations,
        rounding_rules=rounding_rules,
        modifiers=modifiers,
        constraints=constraints,
        fees=fees,
        coverages=coverages,
        outputs=outputs,
        provenance=provenance,
    )


def main() -> None:
    package = build_canonical_package()

    # Destination paths
    root_dir = Path(__file__).resolve().parent.parent.parent
    canonical_dir = root_dir / "data" / "implementations" / "canonical"
    canonical_dir.mkdir(parents=True, exist_ok=True)
    canonical_file = canonical_dir / "AZ_HO3_2026_09_ipir.json"

    # Write JSON using model_dump_json()
    with open(canonical_file, "w", encoding="utf-8") as f:
        f.write(package.model_dump_json(indent=2))
        f.write("\n")

    print(f"Successfully wrote canonical IPIR package to: {canonical_file}")

    # Reload & re-validate
    with open(canonical_file, encoding="utf-8") as f:
        reloaded_json = f.read()

    reloaded_pkg = IPIRPackage.model_validate_json(reloaded_json)
    print(f"Successfully reloaded and re-validated IPIR package: '{reloaded_pkg.id}'")

    # Print summary
    total_rows = sum(len(t.rows) for t in reloaded_pkg.tables)
    p_id = reloaded_pkg.product.id
    p_state = reloaded_pkg.product.jurisdiction.state_or_province
    print("\n--- RATE PLAN SUMMARY ---")
    print(f"Package ID:        {reloaded_pkg.id}")
    print(f"Product / State:   {p_id} ({p_state})")
    print(f"Effective Date:    {reloaded_pkg.effective_period.start}")
    print(f"Rate Tables:       {len(reloaded_pkg.tables)}")
    print(f"Total Table Rows:  {total_rows}")
    print(f"Calculation Nodes: {len(reloaded_pkg.calculations)}")
    print(f"Modifiers:         {len(reloaded_pkg.modifiers)}")
    print(f"Constraints:       {len(reloaded_pkg.constraints)}")
    print(f"Fees:              {len(reloaded_pkg.fees)}")
    print(f"Outputs:           {len(reloaded_pkg.outputs)}")
    print("-------------------------\n")


if __name__ == "__main__":
    main()
