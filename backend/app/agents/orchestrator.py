import logging
import uuid

from app.agents.assurance_agent import AssuranceDecisionAgent
from app.agents.config import get_agent_config
from app.agents.impact_agent import ImpactAgent
from app.agents.investigation_agent import InvestigationAgent
from app.agents.portfolio_agent import PortfolioAgent
from app.agents.schemas import AgenticAssuranceResult, AgentStepLog
from app.agents.semantic_agent import SemanticAssuranceAgent
from app.agents.test_planner_agent import TestPlannerAgent
from app.core.config import get_data_dir
from app.ipir.package import IPIRPackage
from app.storage import BaseRunStore, get_run_store
from app.storage.models import (
    AssuranceRunRecord,
    AssuranceRunStatus,
    EvidenceRecord,
    EvidenceType,
    RunEvent,
)

logger = logging.getLogger(__name__)


class RateGuardOrchestrator:
    """Multi-Agent Orchestrator executing the complete RateGuard autonomous assurance workflow."""

    def __init__(self, run_store: BaseRunStore | None = None) -> None:
        self.config = get_agent_config()
        self.store = run_store if run_store is not None else get_run_store()

        self.semantic_agent = SemanticAssuranceAgent()
        self.impact_agent = ImpactAgent()
        self.test_planner_agent = TestPlannerAgent()
        self.investigation_agent = InvestigationAgent()
        self.portfolio_agent = PortfolioAgent()
        self.assurance_agent = AssuranceDecisionAgent()

    def run_assurance_workflow(
        self,
        left_package: IPIRPackage,
        right_package: IPIRPackage,
        include_portfolio_analysis: bool = True,
        portfolio_csv_path: str | None = None,
        run_id: str | None = None,
    ) -> AgenticAssuranceResult:
        """Coordinates multi-agent workflow, tool calls, evidence lineage, and persistence."""
        actual_run_id = run_id or f"RUN-{uuid.uuid4().hex[:8].upper()}"

        run_record = AssuranceRunRecord(
            run_id=actual_run_id,
            status="IN_PROGRESS",
            workflow_stage="INITIATING",
            left_package_id=left_package.id,
            right_package_id=right_package.id,
            include_portfolio_analysis=include_portfolio_analysis,
        )
        self.store.create_run(run_record)

        agent_steps: list[AgentStepLog] = []
        evidence_ids: list[str] = []
        step_counter = 1

        left_json = left_package.model_dump_json()
        right_json = right_package.model_dump_json()

        # Evidence: Source IPIR Packages
        ev_left = EvidenceRecord(
            evidence_id=f"EV-{uuid.uuid4().hex[:6].upper()}",
            run_id=actual_run_id,
            evidence_type=EvidenceType.IPIR_PACKAGE,
            title=f"Canonical Rate Plan Package ({left_package.id})",
            description="Authoritative canonical IPIR rate plan representation.",
            source_ref=left_package.id,
            data_summary={"package_id": left_package.id, "version": left_package.version},
        )
        self.store.add_evidence(actual_run_id, ev_left)
        evidence_ids.append(ev_left.evidence_id)

        ev_right = EvidenceRecord(
            evidence_id=f"EV-{uuid.uuid4().hex[:6].upper()}",
            run_id=actual_run_id,
            evidence_type=EvidenceType.IPIR_PACKAGE,
            title=f"Target Rating Engine Implementation ({right_package.id})",
            description="Target engine IPIR implementation representation.",
            target_ref=right_package.id,
            data_summary={"package_id": right_package.id, "version": right_package.version},
        )
        self.store.add_evidence(actual_run_id, ev_right)
        evidence_ids.append(ev_right.evidence_id)

        # Step 1: Semantic Assurance Agent
        self._log_event(
            actual_run_id,
            "SEMANTIC_ANALYSIS",
            "SemanticAssuranceAgent",
            "Invoking semantic diff tool",
        )
        sem_res = self.semantic_agent.run(left_json, right_json)
        sem_data = sem_res["deterministic_data"]

        agent_steps.append(
            AgentStepLog(
                step_index=step_counter,
                agent_name="SemanticAssuranceAgent",
                role="Semantic Assurance Specialist",
                action="COMPARE_IPIR_PACKAGES",
                summary=sem_res["summary"],
                output_snapshot={
                    "difference_count": sem_data["difference_count"],
                    "summary": sem_data["summary"],
                },
            )
        )
        step_counter += 1

        ev_sem = EvidenceRecord(
            evidence_id=f"EV-{uuid.uuid4().hex[:6].upper()}",
            run_id=actual_run_id,
            evidence_type=EvidenceType.SEMANTIC_DIFF,
            title="Deterministic Semantic Diff Results",
            description=sem_res["summary"],
            data_summary=sem_data["summary"],
        )
        self.store.add_evidence(actual_run_id, ev_sem)
        evidence_ids.append(ev_sem.evidence_id)

        # Step 2: Impact Agent
        self._log_event(
            actual_run_id,
            "IMPACT_ANALYSIS",
            "ImpactAgent",
            "Traversing pricing DAG & predicates",
        )
        impact_res = self.impact_agent.run(sem_data, left_json)
        impact_data = impact_res["deterministic_data"]

        agent_steps.append(
            AgentStepLog(
                step_index=step_counter,
                agent_name="ImpactAgent",
                role="Pricing Impact Specialist",
                action="ANALYZE_PRICING_IMPACT",
                summary=impact_res["summary"],
                output_snapshot={
                    "changed_nodes": impact_data["changed_nodes"],
                    "affected_outputs": impact_data["affected_outputs"],
                },
            )
        )
        step_counter += 1

        ev_impact = EvidenceRecord(
            evidence_id=f"EV-{uuid.uuid4().hex[:6].upper()}",
            run_id=actual_run_id,
            evidence_type=EvidenceType.IMPACT_ANALYSIS,
            title="Dependency Graph Impact Analysis",
            description=impact_res["summary"],
            data_summary={"changed_nodes": impact_data["changed_nodes"]},
        )
        self.store.add_evidence(actual_run_id, ev_impact)
        evidence_ids.append(ev_impact.evidence_id)

        # Step 3: Test Planner Agent
        self._log_event(
            actual_run_id,
            "TEST_PLANNING",
            "TestPlannerAgent",
            "Generating risk-directed scenario plan",
        )
        test_res = self.test_planner_agent.run(left_json, sem_data, impact_data)
        test_data = test_res["deterministic_data"]

        agent_steps.append(
            AgentStepLog(
                step_index=step_counter,
                agent_name="TestPlannerAgent",
                role="Risk-Directed Test Planner",
                action="GENERATE_TEST_PLAN",
                summary=test_res["summary"],
                output_snapshot={
                    "candidate_count": test_data["candidate_count"],
                    "selected_count": test_data["selected_count"],
                },
            )
        )
        step_counter += 1

        ev_test = EvidenceRecord(
            evidence_id=f"EV-{uuid.uuid4().hex[:6].upper()}",
            run_id=actual_run_id,
            evidence_type=EvidenceType.TEST_PLAN,
            title="Risk-Directed Assurance Test Plan",
            description=test_res["summary"],
            data_summary={"selected_count": test_data["selected_count"]},
        )
        self.store.add_evidence(actual_run_id, ev_test)
        evidence_ids.append(ev_test.evidence_id)

        # Step 4: Investigation Agent
        self._log_event(
            actual_run_id,
            "EXECUTION_RECONCILIATION",
            "InvestigationAgent",
            "Executing target engine & RCA",
        )
        recon_res = self.investigation_agent.run(left_json, right_json)
        recon_data = recon_res["deterministic_data"]

        agent_steps.append(
            AgentStepLog(
                step_index=step_counter,
                agent_name="InvestigationAgent",
                role="Reconciliation & Root Cause Investigator",
                action="EXECUTE_PRICING_ASSURANCE",
                summary=recon_res["summary"],
                output_snapshot={
                    "mismatch_count": recon_data["mismatch_count"],
                    "root_causes": recon_data["discovered_root_causes"],
                },
            )
        )
        step_counter += 1

        ev_recon = EvidenceRecord(
            evidence_id=f"EV-{uuid.uuid4().hex[:6].upper()}",
            run_id=actual_run_id,
            evidence_type=EvidenceType.EXECUTION_RESULT,
            title="Target Execution & Premium Reconciliation",
            description=recon_res["summary"],
            data_summary={"mismatch_count": recon_data["mismatch_count"]},
        )
        self.store.add_evidence(actual_run_id, ev_recon)
        evidence_ids.append(ev_recon.evidence_id)

        # Step 5: Portfolio Agent (Optional)
        port_res = None
        port_data = None
        if include_portfolio_analysis:
            self._log_event(
                actual_run_id,
                "PORTFOLIO_ANALYSIS",
                "PortfolioAgent",
                "Evaluating 50,000 policy portfolio",
            )
            data_dir = get_data_dir()
            default_csv = data_dir / "portfolio" / "az_ho3_2026_synthetic_50k.csv"
            target_csv = portfolio_csv_path or str(default_csv)

            port_res = self.portfolio_agent.run(target_csv, left_json, right_json)
            port_data = port_res["deterministic_data"]

            agent_steps.append(
                AgentStepLog(
                    step_index=step_counter,
                    agent_name="PortfolioAgent",
                    role="Portfolio Exposure Analyst",
                    action="ANALYZE_PORTFOLIO_EXPOSURE",
                    summary=port_res["summary"],
                    output_snapshot={
                        "total_policies": port_data["total_policies"],
                        "financially_affected_count": port_data["financially_affected_count"],
                        "total_signed_variance": port_data["total_signed_variance"],
                    },
                )
            )
            step_counter += 1

            ev_port = EvidenceRecord(
                evidence_id=f"EV-{uuid.uuid4().hex[:6].upper()}",
                run_id=actual_run_id,
                evidence_type=EvidenceType.PORTFOLIO_EXPOSURE,
                title="50,000 Policy Portfolio Exposure Analysis",
                description=port_res["summary"],
                data_summary={
                    "financially_affected_count": port_data["financially_affected_count"],
                    "total_signed_variance": port_data["total_signed_variance"],
                },
            )
            self.store.add_evidence(actual_run_id, ev_port)
            evidence_ids.append(ev_port.evidence_id)

        # Step 6: Assurance Decision Agent
        self._log_event(
            actual_run_id,
            "ASSURANCE_DECISION",
            "AssuranceDecisionAgent",
            "Evaluating decision policy",
        )
        assurance_res = self.assurance_agent.run(
            sem_data, impact_data, test_data, recon_data, port_data
        )

        agent_steps.append(
            AgentStepLog(
                step_index=step_counter,
                agent_name="AssuranceDecisionAgent",
                role="Executive Assurance Decision Maker",
                action="EVALUATE_ASSURANCE_DECISION",
                summary=assurance_res["recommendation"],
                output_snapshot={
                    "status": assurance_res["status"],
                    "blocking_reasons": assurance_res["blocking_reasons"],
                },
            )
        )

        ev_decision = EvidenceRecord(
            evidence_id=f"EV-{uuid.uuid4().hex[:6].upper()}",
            run_id=actual_run_id,
            evidence_type=EvidenceType.ASSURANCE_DECISION,
            title="Evidence-Backed Assurance Decision",
            description=assurance_res["recommendation"],
            data_summary={"status": assurance_res["status"]},
        )
        self.store.add_evidence(actual_run_id, ev_decision)
        evidence_ids.append(ev_decision.evidence_id)

        # Update Final Run Record in Storage
        run_record.status = AssuranceRunStatus.COMPLETED
        run_record.workflow_stage = "FINISHED"
        run_record.semantic_diff_summary = sem_data
        run_record.impact_summary = impact_data
        run_record.test_plan_summary = test_data
        run_record.reconciliation_summary = recon_data
        run_record.portfolio_summary = port_data or {}
        run_record.assurance_decision = assurance_res
        run_record.evidence_refs = evidence_ids
        run_record.agent_activity = [step.model_dump(mode="json") for step in agent_steps]

        self.store.update_run(run_record)

        return AgenticAssuranceResult(
            run_id=actual_run_id,
            status=assurance_res["status"],
            executive_summary=assurance_res["executive_summary"],
            semantic_summary=sem_res["summary"],
            impact_summary=impact_res["summary"],
            test_summary=test_res["summary"],
            root_cause_summary=recon_res["summary"],
            portfolio_summary=port_res["summary"] if port_res else "Portfolio analysis omitted.",
            recommendation=assurance_res["recommendation"],
            evidence_refs=evidence_ids,
            agent_steps=agent_steps,
            confidence=1.0,
            limitations=[
                "Assurance evaluation is scoped to supported IPIR 0.1 pricing semantics.",
                "Portfolio analysis uses synthetic risk distribution parameters.",
            ],
        )

    def _log_event(self, run_id: str, stage: str, agent_name: str, action: str) -> None:
        event = RunEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:6].upper()}",
            run_id=run_id,
            stage=stage,
            agent_name=agent_name,
            action=action,
        )
        self.store.add_event(run_id, event)
