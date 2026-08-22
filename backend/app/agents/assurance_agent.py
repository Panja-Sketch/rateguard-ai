import logging
from typing import Any

from app.agents.config import get_agent_config

logger = logging.getLogger(__name__)


def evaluate_deterministic_assurance_policy(
    semantic_data: dict[str, Any],
    recon_data: dict[str, Any],
    portfolio_data: dict[str, Any] | None,
) -> tuple[str, str, list[str]]:
    """Evaluates strict deterministic policy logic to decide assurance status."""
    blocking_reasons: list[str] = []

    mismatch_count = recon_data.get("mismatch_count", 0)
    failed_count = recon_data.get("failed_count", 0)
    root_causes = recon_data.get("discovered_root_causes", [])

    crit_diffs = semantic_data.get("summary", {}).get("critical_count", 0)
    high_diffs = semantic_data.get("summary", {}).get("high_count", 0)

    fin_affected = portfolio_data.get("financially_affected_count", 0) if portfolio_data else 0

    if (mismatch_count > 0 or failed_count > 0) and (crit_diffs > 0 or high_diffs > 0):
        blocking_reasons.append(
            f"Reproduced {mismatch_count} premium mismatches originating from {crit_diffs} "
            f"CRITICAL and {high_diffs} HIGH severity semantic differences."
        )

    order_rcs = [rc for rc in root_causes if rc.get("category") == "ORDER_CHANGE"]
    if order_rcs:
        blocking_reasons.append(
            f"Detected {len(order_rcs)} calculation sequence order mismatches affecting premium."
        )

    if fin_affected > 0:
        blocking_reasons.append(
            f"Portfolio analysis identified {fin_affected:,} financially affected policies."
        )

    if blocking_reasons:
        status = "BLOCK_DEPLOYMENT"
        recommendation = (
            "BLOCK DEPLOYMENT: Material pricing discrepancies, sequence order drifts, or portfolio "
            "financial exposures were behaviorally reproduced. Deployment must be blocked until "
            "target engine logic aligns with canonical IPIR intent."
        )
    elif semantic_data.get("difference_count", 0) > 0:
        status = "REVIEW"
        recommendation = (
            "MANUAL REVIEW REQUIRED: Semantic differences exist between representations, "
            "but no active premium mismatches were reproduced in selected test scenarios."
        )
    else:
        status = "PASS"
        recommendation = (
            "PASS: Zero material semantic differences or behavioral pricing mismatches detected. "
            "Target engine implementation is semantically equivalent to canonical rate plan."
        )

    return status, recommendation, blocking_reasons


class AssuranceDecisionAgent:
    """Specialized agent synthesizing evidence across subagents into an executive recommendation."""

    def __init__(self) -> None:
        self.config = get_agent_config()

    def run(
        self,
        semantic_data: dict[str, Any],
        impact_data: dict[str, Any],
        test_data: dict[str, Any],
        recon_data: dict[str, Any],
        portfolio_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Synthesizes subagent findings and enforces deterministic assurance decision policy."""
        status, default_recommendation, blocking_reasons = (
            evaluate_deterministic_assurance_policy(semantic_data, recon_data, portfolio_data)
        )

        executive_summary = (
            f"RateGuard Autonomous Assurance Workflow completed. Decision: [{status}]. "
            f"{' '.join(blocking_reasons) if blocking_reasons else default_recommendation}"
        )

        recommendation_text = default_recommendation

        try:
            from google import genai

            client = genai.Client()
            prompt = (
                "You are the RateGuard Assurance Decision Agent. "
                "Provide an executive summary and recommendation narrative for leadership.\n"
                f"Deterministic Assurance Status: [{status}]\n"
                f"Blocking Reasons: {blocking_reasons}\n"
                f"Semantic Tool Summary: {semantic_data}\n"
                f"Reconciliation Tool Summary: {recon_data}\n"
                "Rules:\n"
                f"- You MUST NOT change the status from '{status}'.\n"
                "- Do NOT override hard blocking rules."
            )
            response = client.models.generate_content(
                model=self.config.gemini_model, contents=prompt
            )
            if response and response.text:
                executive_summary = response.text.strip()
        except Exception as e:
            logger.debug("Gemini API call skipped/fallback for AssuranceDecisionAgent: %s", e)

        return {
            "status": status,
            "executive_summary": executive_summary,
            "recommendation": recommendation_text,
            "blocking_reasons": blocking_reasons,
        }

