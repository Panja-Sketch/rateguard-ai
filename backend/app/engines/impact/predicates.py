from datetime import date
from decimal import Decimal

from app.engines.diff.enums import DifferenceType
from app.engines.diff.models import SemanticDifference
from app.engines.impact.models import ImpactPredicate, PredicateClause
from app.ipir.enums import ComparisonOperator, LogicalOperator
from app.ipir.package import IPIRPackage
from app.ipir.tables import TableLookupType


def derive_predicate_from_difference(
    diff: SemanticDifference, package: IPIRPackage
) -> ImpactPredicate | None:
    """Derives a structured ImpactPredicate describing policy risk conditions exercising a diff."""
    # 1. Effective Date Drift
    if diff.difference_type == DifferenceType.EFFECTIVE_DATE_CHANGE:
        start_a = date.fromisoformat(str(diff.left_value)) if diff.left_value else None
        start_b = date.fromisoformat(str(diff.right_value)) if diff.right_value else None

        min_start = min(filter(None, [start_a, start_b])) if (start_a or start_b) else None
        max_start = max(filter(None, [start_a, start_b])) if (start_a or start_b) else None

        return ImpactPredicate(
            id=f"pred_{diff.id}",
            clauses=[],
            logical_operator=LogicalOperator.AND,
            temporal_start=min_start,
            temporal_end=max_start,
            description=(
                f"Temporal discrepancy window for '{diff.node_id}' between "
                f"{min_start} and {max_start}"
            ),
        )

    # 2. Table Row Differences (1D Exact, 1D Range, 2D Exact)
    if diff.difference_type in (
        DifferenceType.TABLE_ROW_CHANGE,
        DifferenceType.TABLE_ROW_MISSING,
        DifferenceType.TABLE_ROW_EXTRA,
    ):
        table = next((t for t in package.tables if t.id == diff.node_id), None)
        if not table:
            return None

        dim_key = diff.metadata.get("dimension_key", "")
        key_parts = dim_key.split("|")
        clauses: list[PredicateClause] = []

        for dim, key_part in zip(table.dimensions, key_parts, strict=False):
            field_name = dim.input_ref

            if dim.lookup_type == TableLookupType.EXACT:
                clauses.append(
                    PredicateClause(
                        field=field_name,
                        operator=ComparisonOperator.EQ,
                        value=key_part,
                    )
                )
            elif dim.lookup_type == TableLookupType.RANGE and ".." in key_part:
                min_str, max_str = key_part.split("..")
                if min_str != "-inf":
                    clauses.append(
                        PredicateClause(
                            field=field_name,
                            operator=ComparisonOperator.GTE,
                            value=Decimal(min_str),
                        )
                    )
                if max_str != "+inf":
                    clauses.append(
                        PredicateClause(
                            field=field_name,
                            operator=ComparisonOperator.LTE,
                            value=Decimal(max_str),
                        )
                    )

        return ImpactPredicate(
            id=f"pred_{diff.id}",
            clauses=clauses,
            logical_operator=LogicalOperator.AND,
            description=f"Risk attributes matching table lookup '{table.id}' key [{dim_key}]",
        )

    return None

