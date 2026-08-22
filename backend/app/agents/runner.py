from app.agents.orchestrator import RateGuardOrchestrator
from app.agents.schemas import AgenticAssuranceResult
from app.ipir.package import IPIRPackage
from app.storage import BaseRunStore


class AgenticAssuranceRunner:
    """High-level runner interface for agentic autonomous pricing assurance workflow."""

    def __init__(self, run_store: BaseRunStore | None = None) -> None:
        self.orchestrator = RateGuardOrchestrator(run_store=run_store)

    def run_assurance(
        self,
        left_package: IPIRPackage,
        right_package: IPIRPackage,
        include_portfolio_analysis: bool = True,
        portfolio_csv_path: str | None = None,
        run_id: str | None = None,
    ) -> AgenticAssuranceResult:
        """Executes full multi-agent autonomous pricing assurance pipeline."""
        return self.orchestrator.run_assurance_workflow(
            left_package=left_package,
            right_package=right_package,
            include_portfolio_analysis=include_portfolio_analysis,
            portfolio_csv_path=portfolio_csv_path,
            run_id=run_id,
        )
