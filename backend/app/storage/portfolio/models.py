from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.ipir.enums import TransactionType


class PortfolioPolicyRecord(BaseModel):
    """Canonical policy record model stored in portfolio repositories."""

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
    claims_free_years: int = 3
    canonical_premium: Decimal

    def to_dict(self) -> dict[str, Any]:
        d = self.model_dump()
        d["transaction_type"] = self.transaction_type.value
        d["effective_date"] = self.effective_date.isoformat()
        d["canonical_premium"] = str(self.canonical_premium)
        return d


class PortfolioSummaryStats(BaseModel):
    """Portfolio distribution summary metrics."""

    total_policies: int
    total_expected_premium: Decimal
    roof_band_21_30_count: int
    territory_counts: dict[str, int] = Field(default_factory=dict)

