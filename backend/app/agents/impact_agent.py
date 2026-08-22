import logging
from typing import Any

from app.agents.config import get_agent_config
from app.agents.tools import analyze_pricing_impact_tool

logger = logging.getLogger(__name__)


class ImpactAgent:
    """Specialized agent analyzing pricing graph dependency paths and impact predicates."""

    def __init__(self) -> None:
        self.config = get_agent_config()

    def run(self, diff_result_dict: dict[str, Any], canonical_pkg_json: str) -> dict[str, Any]:
        """Executes deterministic impact analysis tool and generates evidence summary."""
        # 1. Deterministic Tool Execution
        impact_data = analyze_pricing_impact_tool(diff_result_dict, canonical_pkg_json)

        # 2. Reasoning / Summary Generation
        chg_nodes = impact_data.get("changed_nodes", [])
        aff_outputs = impact_data.get("affected_outputs", [])
        preds = impact_data.get("candidate_risk_predicates", [])
        pred_count = len(preds)
        out_str = ", ".join(aff_outputs)

        summary_text = (
            f"Impact analysis confirmed {len(chg_nodes)} changed calculation nodes affecting "
            f"outputs ({out_str}). Derived {pred_count} risk predicates "
            "isolating range boundaries, temporal windows, and sequence order constraints."
        )

        try:
            from google import genai

            client = genai.Client()
            prompt = (
                "You are the RateGuard Impact Agent. "
                "Synthesize the following deterministic tool output into a summary.\n"
                f"Tool Output: {impact_data}\n"
                "Rules:\n"
                "- Explain affected pricing calculation paths.\n"
                "- Do NOT invent node names or graph dependencies."
            )
            response = client.models.generate_content(
                model=self.config.gemini_model, contents=prompt
            )
            if response and response.text:
                summary_text = response.text.strip()
        except Exception as e:
            logger.debug("Gemini API call skipped/fallback for ImpactAgent: %s", e)

        return {
            "summary": summary_text,
            "deterministic_data": impact_data,
        }
