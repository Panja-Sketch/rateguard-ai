from decimal import Decimal


def generate_range_boundary_values(
    minimum: Decimal | int | None, maximum: Decimal | int | None
) -> dict[str, int | Decimal]:
    """Generates boundary values (just below, lower, interior, upper, just above) for ranges."""
    boundaries: dict[str, int | Decimal] = {}

    if minimum is not None:
        min_is_int = isinstance(minimum, (int, Decimal)) and Decimal(str(minimum)) % 1 == 0
        min_num = int(minimum) if min_is_int else minimum
        boundaries["just_below"] = min_num - 1
        boundaries["lower_bound"] = min_num

    if maximum is not None:
        max_is_int = isinstance(maximum, (int, Decimal)) and Decimal(str(maximum)) % 1 == 0
        max_num = int(maximum) if max_is_int else maximum
        boundaries["upper_bound"] = max_num
        boundaries["just_above"] = max_num + 1

    if minimum is not None and maximum is not None:
        min_num = int(minimum)
        max_num = int(maximum)
        boundaries["interior"] = (min_num + max_num) // 2

    return boundaries

