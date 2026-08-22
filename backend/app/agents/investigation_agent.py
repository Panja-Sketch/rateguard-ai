import logging
from typing import Any

from app.agents.config import get_agent_config
from app.agents.tools import execute_pricing_assurance_tool

logger = logging.getLogger(__name__)


class InvestigationAgent:
    """Specialized agent interpreting target quote results, reconciliation, and RCA findings."""

    def __init__(self) -> None:
        self.config = get_agent_config()

    def run(self, canonical_pkg_json: str, target_pkg_json: str) -> dict[str, Any]:
        """Executes deterministic reconciliation tool and generates evidence summary."""
        # 1. Deterministic Tool Execution
        recon_data = execute_pricing_assurance_tool(canonical_pkg_json, target_pkg_json)

        # 2. Reasoning / Summary Generation
        mismatch_c = recon_data["mismatch_count"]
        rc_count = recon_data["unique_root_cause_count"]
        beh_cov = recon_data["behavioral_difference_coverage_pct"]
        prem_cov = recon_data["premium_difference_reproduction_rate_pct"]

        summary_text = (
            f"Execution & Investigation detected {mismatch_c} pricing mismatches and isolated "
            f"{rc_count} root causes. "
            f"Achieved {beh_cov}% behavioral coverage and {prem_cov}% premium reproduction."
        )

        try:
            from google import genai

            client = genai.Client()
            prompt = (
                "You are the RateGuard Investigation Agent. "
                "Synthesize the following deterministic tool output into a summary.\n"
                f"Tool Output: {recon_data}\n"
                "Rules:\n"
                "- Do NOT override deterministic root cause analysis.\n"
                "- Relate first divergent nodes to semantic evidence."
            )
            response = client.models.generate_content(
                model=self.config.gemini_model, contents=prompt
            )
            if response and response.text:
                summary_text = response.text.strip()
        except Exception as e:
            logger.debug("Gemini API call skipped/fallback for InvestigationAgent: %s", e)

        return {
            "summary": summary_text,
            "deterministic_data": recon_data,
        }

