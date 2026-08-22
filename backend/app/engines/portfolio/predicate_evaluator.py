from decimal import Decimal

from app.engines.impact.models import ImpactPredicate
from app.engines.portfolio.models import SyntheticPolicy
from app.ipir.enums import ComparisonOperator


def matches_predicate(policy: SyntheticPolicy, predicate: ImpactPredicate) -> bool:
    """Evaluates whether a policy matches a structured ImpactPredicate."""
    # 1. Temporal Check
    if predicate.temporal_start and predicate.temporal_end:
        if not (predicate.temporal_start <= policy.effective_date < predicate.temporal_end):
            return False

    # 2. Relational Clause Checks
    for clause in predicate.clauses:
        val = getattr(policy, clause.field, None)
        if val is None:
            return False

        target_val = clause.value
        op = clause.operator

        if isinstance(val, (int, Decimal)) and isinstance(target_val, (int, Decimal)):
            val_dec = Decimal(str(val))
            target_dec = Decimal(str(target_val))

            if op == ComparisonOperator.EQ and val_dec != target_dec:
                return False
            if op == ComparisonOperator.NE and val_dec == target_dec:
                return False
            if op == ComparisonOperator.GTE and val_dec < target_dec:
                return False
            if op == ComparisonOperator.GT and val_dec <= target_dec:
                return False
            if op == ComparisonOperator.LTE and val_dec > target_dec:
                return False
            if op == ComparisonOperator.LT and val_dec >= target_dec:
                return False
        else:
            if op == ComparisonOperator.EQ and str(val) != str(target_val):
                return False
            if op == ComparisonOperator.NE and str(val) == str(target_val):
                return False

    return True
