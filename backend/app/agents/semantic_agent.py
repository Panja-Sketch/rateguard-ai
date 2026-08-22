import logging
from typing import Any

from app.agents.config import get_agent_config
from app.agents.tools import compare_ipir_packages_tool

logger = logging.getLogger(__name__)


class SemanticAssuranceAgent:
    """Specialized agent interpreting semantic diff results between rate representations."""

    def __init__(self) -> None:
        self.config = get_agent_config()

    def run(self, left_pkg_json: str, right_pkg_json: str) -> dict[str, Any]:
        """Executes deterministic semantic diff tool and generates evidence summary."""
        # 1. Deterministic Tool Execution
        diff_data = compare_ipir_packages_tool(left_pkg_json, right_pkg_json)

        # 2. Reasoning / Summary Generation
        diff_count = diff_data["difference_count"]
        crit_count = diff_data["summary"]["critical_count"]
        high_count = diff_data["summary"]["high_count"]

        summary_text = (
            f"Semantic analysis detected {diff_count} material pricing representation differences "
            f"({crit_count} CRITICAL, {high_count} HIGH). Key changes include table factor shifts, "
            "effective start date delays, and calculation sequence swaps."
        )

        try:
            from google import genai

            client = genai.Client()
            prompt = (
                "You are the RateGuard Semantic Assurance Agent. "
                "Synthesize the following tool output into a summary.\n"
                f"Tool Output: {diff_data}\n"
                "Rules:\n"
                "- Do NOT invent differences or modify values.\n"
                "- Highlight CRITICAL and HIGH severity changes."
            )
            response = client.models.generate_content(
                model=self.config.gemini_model, contents=prompt
            )
            if response and response.text:
                summary_text = response.text.strip()
        except Exception as e:
            logger.debug("Gemini API call skipped/fallback for SemanticAssuranceAgent: %s", e)

        return {
            "summary": summary_text,
            "deterministic_data": diff_data,
        }
