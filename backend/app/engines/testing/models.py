from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.ipir.enums import TransactionType


class PricingTestScenario(BaseModel):
    """Represents a single risk-directed test scenario for pricing assurance."""

    id: str
    name: str
    risk_values: dict[str, int | Decimal | str | bool | date]
    effective_date: date
    transaction_type: TransactionType = TransactionType.NEW_BUSINESS
    purpose: str
    target_difference_ids: list[str] = Field(default_factory=list)
    target_node_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    score: float = 0.0
    expected_coverage: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PricingTestPlan(BaseModel):
    """Aggregated test plan generated deterministically from semantic differences."""

    package_id: str
    compared_package_ids: list[str] = Field(default_factory=list)
    semantic_difference_ids: list[str] = Field(default_factory=list)
    candidate_count: int
    selected_count: int
    selected_scenarios: list[PricingTestScenario] = Field(default_factory=list)
    candidate_scenarios: list[PricingTestScenario] = Field(default_factory=list)
    coverage_metrics: dict[str, Any] = Field(default_factory=dict)
    planning_metadata: dict[str, Any] = Field(default_factory=dict)

