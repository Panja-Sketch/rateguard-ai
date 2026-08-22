from decimal import Decimal
from typing import Any

from app.engines.oracle.errors import TableLookupError
from app.ipir.enums import TableLookupType
from app.ipir.tables import ExactMatch, RangeMatch, RateTable, TableRow


def _matches_exact(match: ExactMatch, val: Any) -> bool:
    """Evaluates an exact dimension match."""
    # Compare string representations to avoid subtle type mismatches
    return str(match.value).strip() == str(val).strip()


def _matches_range(match: RangeMatch, val: Any) -> bool:
    """Evaluates a range dimension match with bounds check."""
    num_val = Decimal(str(val))

    if match.minimum is not None:
        min_val = Decimal(str(match.minimum))
        if match.include_minimum:
            if num_val < min_val:
                return False
        else:
            if num_val <= min_val:
                return False

    if match.maximum is not None:
        max_val = Decimal(str(match.maximum))
        if match.include_maximum:
            if num_val > max_val:
                return False
        else:
            if num_val >= max_val:
                return False

    return True


def lookup_table(table: RateTable, dimension_values: dict[str, Any]) -> tuple[Decimal, TableRow]:
    """Deterministically resolves a single rate table factor from dimension inputs.
    
    Args:
        table: Target IPIR RateTable instance.
        dimension_values: Mapping of input_ref -> supplied input value.
        
    Returns:
        Tuple of (factor_value: Decimal, matched_row: TableRow).
        
    Raises:
        TableLookupError: If zero rows or multiple rows match.
    """
    matching_rows: list[TableRow] = []

    for row in table.rows:
        row_matches = True
        for dim, match in zip(table.dimensions, row.matches, strict=True):
            input_val = dimension_values.get(dim.input_ref)
            if input_val is None:
                row_matches = False
                break

            if dim.lookup_type == TableLookupType.EXACT:
                if not isinstance(match, ExactMatch) or not _matches_exact(match, input_val):
                    row_matches = False
                    break
            elif dim.lookup_type == TableLookupType.RANGE:
                if not isinstance(match, RangeMatch) or not _matches_range(match, input_val):
                    row_matches = False
                    break

        if row_matches:
            matching_rows.append(row)

    if len(matching_rows) == 0:
        raise TableLookupError(
            f"No matching row found in table '{table.id}' for inputs: {dimension_values}"
        )

    if len(matching_rows) > 1:
        raise TableLookupError(
            f"Ambiguous rate table lookup in table '{table.id}': "
            f"found {len(matching_rows)} matching rows for inputs: {dimension_values}"
        )

    return matching_rows[0].value, matching_rows[0]
