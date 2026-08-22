import logging
from typing import Any

from app.agents.config import get_agent_config
from app.agents.tools import analyze_portfolio_exposure_tool

logger = logging.getLogger(__name__)


class PortfolioAgent:
    """Specialized agent interpreting portfolio-wide blast radius and financial exposure."""

    def __init__(self) -> None:
        self.config = get_agent_config()

    def run(self, csv_path: str, canonical_pkg_json: str, target_pkg_json: str) -> dict[str, Any]:
        """Executes deterministic portfolio analyzer tool and generates evidence summary."""
        # 1. Deterministic Tool Execution
        port_data = analyze_portfolio_exposure_tool(csv_path, canonical_pkg_json, target_pkg_json)

        # 2. Reasoning / Summary Generation
        tot_pol = port_data["total_policies"]
        exp_pol = port_data["exposed_policy_count"]
        fin_pol = port_data["financially_affected_count"]
        abs_var = port_data["total_absolute_variance"]
        net_var = port_data["total_signed_variance"]
        exp_pct = port_data["exposed_policy_pct"]
        fin_pct = port_data["financially_affected_pct"]

        summary_text = (
            f"Portfolio Analysis evaluated {tot_pol:,} synthetic policies: "
            f"{exp_pol:,} exposed ({exp_pct}%), "
            f"and {fin_pol:,} financially affected ({fin_pct}%). "
            f"Total signed variance: ${net_var}, absolute financial exposure: ${abs_var}."
        )

        try:
            from google import genai

            client = genai.Client()
            prompt = (
                "You are the RateGuard Portfolio Agent. "
                "Synthesize the following tool output into a summary.\n"
                f"Tool Output: {port_data}\n"
                "Rules:\n"
                "- Explain financial exposure metrics accurately.\n"
                "- Clarify that these results represent a synthetic portfolio analysis."
            )
            response = client.models.generate_content(
                model=self.config.gemini_model, contents=prompt
            )
            if response and response.text:
                summary_text = response.text.strip()
        except Exception as e:
            logger.debug("Gemini API call skipped/fallback for PortfolioAgent: %s", e)

        return {
            "summary": summary_text,
            "deterministic_data": port_data,
        }
