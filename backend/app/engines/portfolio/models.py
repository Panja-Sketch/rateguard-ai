from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.ipir.enums import TransactionType


class SyntheticPolicy(BaseModel):
    """Represents a single policy record in a synthetic portfolio."""

    policy_id: str
    product_id: str
    state: str
    form: str
    transaction_type: TransactionType
    effective_date: date
    territory: str
    roof_age: int
    deductible: int
    protection_class: int
    construction_type: str
    dwelling_limit: int
    multi_policy: bool
    claims_free: bool
    canonical_premium: Decimal
    target_premium: Decimal | None = None


class DefectExposure(BaseModel):
    """Exposure breakdown for a single conceptual defect/issue."""

    issue_id: str
    issue_name: str
    exposed_count: int
    behaviorally_affected_count: int
    financially_affected_count: int
    total_expected_premium: Decimal
    total_target_premium: Decimal
    signed_variance: Decimal
    absolute_variance: Decimal


class PortfolioExposureResult(BaseModel):
    """Aggregated portfolio-level financial exposure and blast radius summary."""

    portfolio_id: str
    total_policies: int
    exposed_policy_count: int
    exposed_policy_pct: float
    behaviorally_affected_count: int
    behaviorally_affected_pct: float
    financially_affected_count: int
    financially_affected_pct: float
    total_expected_premium: Decimal
    total_target_premium: Decimal
    total_signed_variance: Decimal
    total_absolute_variance: Decimal
    undercharged_policy_count: int
    total_undercharge_amount: Decimal
    overcharged_policy_count: int
    total_overcharge_amount: Decimal
    average_variance_per_affected_policy: Decimal
    max_single_policy_variance: Decimal
    multi_defect_policy_count: int
    issue_breakdown: list[DefectExposure] = Field(default_factory=list)
    performance_telemetry: dict[str, Any] = Field(default_factory=dict)

