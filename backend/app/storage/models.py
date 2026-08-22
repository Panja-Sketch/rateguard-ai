from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):  # noqa: UP042
    """Categorized evidence type for auditability and evidence lineage."""

    SOURCE = "SOURCE"
    IPIR_PACKAGE = "IPIR_PACKAGE"
    SEMANTIC_DIFF = "SEMANTIC_DIFF"
    IMPACT_ANALYSIS = "IMPACT_ANALYSIS"
    TEST_PLAN = "TEST_PLAN"
    EXECUTION_RESULT = "EXECUTION_RESULT"
    ROOT_CAUSE = "ROOT_CAUSE"
    PORTFOLIO_EXPOSURE = "PORTFOLIO_EXPOSURE"
    ASSURANCE_DECISION = "ASSURANCE_DECISION"


class EvidenceRecord(BaseModel):
    """Typed evidence record connecting inputs to findings and decision."""

    evidence_id: str
    run_id: str
    evidence_type: EvidenceType
    title: str
    description: str
    source_ref: str | None = None
    target_ref: str | None = None
    data_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RunEvent(BaseModel):
    """Audit log entry for an agentic assurance run step or milestone."""

    event_id: str
    run_id: str
    stage: str
    agent_name: str
    action: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AssuranceRunRecord(BaseModel):
    """Persistence record for a complete assurance run state."""

    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: str = "PENDING"  # PENDING, IN_PROGRESS, COMPLETED, FAILED
    workflow_stage: str = "INITIATED"
    left_package_id: str
    right_package_id: str
    include_portfolio_analysis: bool = True
    semantic_diff_summary: dict[str, Any] = Field(default_factory=dict)
    impact_summary: dict[str, Any] = Field(default_factory=dict)
    test_plan_summary: dict[str, Any] = Field(default_factory=dict)
    reconciliation_summary: dict[str, Any] = Field(default_factory=dict)
    portfolio_summary: dict[str, Any] = Field(default_factory=dict)
    assurance_decision: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    agent_activity: list[dict[str, Any]] = Field(default_factory=list)

