from typing import Any

from pydantic import BaseModel, Field


class AgentStepLog(BaseModel):
    """Log entry for an individual subagent invocation step."""

    step_index: int
    agent_name: str
    role: str
    action: str
    summary: str
    output_snapshot: dict[str, Any] = Field(default_factory=dict)


class AgenticAssuranceResult(BaseModel):
    """Structured final result produced by RateGuard multi-agent orchestration."""

    run_id: str
    status: str  # PASS, REVIEW, BLOCK_DEPLOYMENT
    executive_summary: str
    semantic_summary: str
    impact_summary: str
    test_summary: str
    root_cause_summary: str
    portfolio_summary: str
    recommendation: str
    evidence_refs: list[str] = Field(default_factory=list)
    agent_steps: list[AgentStepLog] = Field(default_factory=list)
    confidence: float = 1.0
    limitations: list[str] = Field(default_factory=list)

