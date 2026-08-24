import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import get_data_dir
from app.engines.oracle.calculator import PremiumOracleCalculator
from app.ipir.package import IPIRPackage

router = APIRouter(prefix="/api/v1/demo-rating", tags=["demo-rating-api"])

_defective_oracle: PremiumOracleCalculator | None = None


def _get_defective_oracle() -> PremiumOracleCalculator:
    global _defective_oracle
    if _defective_oracle is None:
        data_dir = get_data_dir()
        defective_file = (
            data_dir / "implementations" / "defective" / "AZ_HO3_2026_09_ipir.json"
        )
        if not defective_file.exists():
            raise RuntimeError(f"Defective target package not found at {defective_file}")
        with open(defective_file, encoding="utf-8") as f:
            pkg = IPIRPackage.model_validate_json(f.read())
        _defective_oracle = PremiumOracleCalculator(pkg)
    return _defective_oracle


class DemoQuoteRequest(BaseModel):
    """Request schema for the synthetic external black-box rating API."""
    product: str = Field(default="AZ_HO3")
    effective_date: str = Field(default="2026-09-15")
    territory: str = Field(default="T05")
    roof_age: int = Field(default=25)
    deductible: int = Field(default=1000)
    protection_class: int = Field(default=5)
    construction_type: str = Field(default="FRAME")
    dwelling_limit: Decimal = Field(default=Decimal("500000"))
    multi_policy: bool = Field(default=True)
    claims_free: bool = Field(default=True)


@router.post("/quote")
def calculate_quote(req: DemoQuoteRequest) -> dict[str, Any]:
    """Synthetic Black-Box Rating Endpoint for Runtime Verification mode testing.
    Behaves strictly as an external rating microservice without revealing internal implementation details.
    """
    oracle = _get_defective_oracle()

    risk_inputs = {
        "dwelling_limit": req.dwelling_limit,
        "roof_age": req.roof_age,
        "deductible": req.deductible,
        "territory": req.territory,
        "protection_class": req.protection_class,
        "construction_type": req.construction_type,
        "claims_free": req.claims_free,
        "multi_policy": req.multi_policy,
        "effective_date": req.effective_date,
    }

    try:
        calc_result = oracle.calculate_policy_premium(risk_inputs)
        return {
            "request_id": f"REQ-{uuid.uuid4().hex[:8].upper()}",
            "premium": str(calc_result.final_premium),
            "currency": "USD",
            "status": "QUOTED",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Rating API calculation error: {e}",
        ) from e
