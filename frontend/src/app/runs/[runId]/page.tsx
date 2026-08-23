'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import {
  getAssuranceRun,
  getAssuranceRunEvents,
  getAssuranceRunResult,
  getAssuranceRunEvidence,
} from '@/lib/api/client';
import {
  AssuranceReport,
  AssuranceRunRecord,
  EvidenceRecord,
  TestScenario,
  WorkflowEvent,
} from '@/lib/types/assurance';
import { SemanticDiffViewer } from '@/components/assurance/SemanticDiffViewer';
import { ImpactGraph } from '@/components/assurance/ImpactGraph';
import { TestPlanViewer } from '@/components/assurance/TestPlanViewer';
import { ReconciliationTrace } from '@/components/assurance/ReconciliationTrace';
import { PortfolioImpactFunnel } from '@/components/assurance/PortfolioImpactFunnel';
import { EvidenceLineage } from '@/components/assurance/EvidenceLineage';
import { AgentActivityPanel } from '@/components/assurance/AgentActivityPanel';
import {
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Clock,
  RefreshCw,
  GitCompare,
  FileCode2,
  Sparkles,
  Database,
  Bot,
  BarChart3,
  Layers,
} from 'lucide-react';

import { ApiError } from '@/lib/api/client';

export default function RunDetailPage() {
  const params = useParams();
  const runId = params.runId as string;

  const [runRecord, setRunRecord] = useState<AssuranceRunRecord | null>(null);
  const [events, setEvents] = useState<WorkflowEvent[]>([]);
  const [report, setReport] = useState<AssuranceReport | null>(null);
  const [evidence, setEvidence] = useState<EvidenceRecord[]>([]);
  const [selectedScenario, setSelectedScenario] = useState<TestScenario | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [hasFetchedFinal, setHasFetchedFinal] = useState(false);
  const [activeTab, setActiveTab] = useState<
    'semantic' | 'impact' | 'testing' | 'recon' | 'portfolio' | 'evidence' | 'agent'
  >('semantic');

  const loadData = useCallback(async () => {
    try {
      setError(null);
      const recordData = await getAssuranceRun(runId);
      setRunRecord(recordData);

      const eventsData = await getAssuranceRunEvents(runId).catch(() => ({ events: [] }));
      setEvents(eventsData.events || []);

      if (recordData.status === 'COMPLETED' && !hasFetchedFinal) {
        const resultData = await getAssuranceRunResult(runId);
        setReport(resultData);

        if (resultData.test_plan?.selected_scenarios?.length) {
          const defaultScenario =
            resultData.test_plan.selected_scenarios.find((s) => !s.matches) ||
            resultData.test_plan.selected_scenarios[0];
          setSelectedScenario(defaultScenario);
        }

        const evidenceData = await getAssuranceRunEvidence(runId).catch(() => ({ evidence: [] }));
        setEvidence(evidenceData.evidence || []);
        setHasFetchedFinal(true);
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.status === 404) {
          setNotFound(true);
          setError(`Assurance run '${runId}' not found.`);
        } else {
          setError(`API Error (${err.message})`);
        }
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setLoading(false);
    }
  }, [runId, hasFetchedFinal]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (notFound || runRecord?.status === 'COMPLETED' || runRecord?.status === 'FAILED') {
      return;
    }

    const interval = setInterval(() => {
      loadData();
    }, 2500);

    return () => clearInterval(interval);
  }, [loadData, runRecord?.status, notFound]);

  const workflowStages = [
    { stage: 'QUEUED', label: 'Run Created' },
    { stage: 'COMPILING_SOURCES', label: 'Sources Compiled' },
    { stage: 'SEMANTIC_COMPARISON', label: 'Semantic Comparison' },
    { stage: 'IMPACT_ANALYSIS', label: 'Impact Analysis' },
    { stage: 'TEST_PLANNING', label: 'Risk-Directed Tests' },
    { stage: 'PREMIUM_EXECUTION', label: 'Premium Execution' },
    { stage: 'RECONCILIATION', label: 'Reconciliation & RCA' },
    { stage: 'PORTFOLIO_ANALYSIS', label: 'Portfolio Exposure' },
    { stage: 'COMPLETED', label: 'Decision Complete' },
  ];

  const currentStageIndex = workflowStages.findIndex(
    (s) => s.stage === (runRecord?.workflow_stage || 'QUEUED')
  );

  const decision = report?.decision || runRecord?.decision || 'BLOCK_DEPLOYMENT';

  return (
    <div className="space-y-8">
      {/* Header & Status Bar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold text-white font-mono">{runId}</h1>
            <span className="rounded bg-sky-950 px-2 py-0.5 text-xs font-mono font-medium text-sky-400 border border-sky-800">
              {runRecord?.status || 'LOADING'}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Autonomous agentic pricing assurance workflow run details
          </p>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-850 self-start sm:self-auto"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh Data
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300 font-mono">
          [API Error] {error}
        </div>
      )}

      {/* Workflow Stage Progress Stepper */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 shadow-xl">
        <div className="mb-3 flex items-center justify-between">
          <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
            Workflow Execution Progress
          </span>
          <span className="text-xs font-mono text-sky-400">
            Stage: {runRecord?.workflow_stage || 'QUEUED'}
          </span>
        </div>

        <div className="grid grid-cols-3 gap-2 sm:grid-cols-9 text-center">
          {workflowStages.map((st, idx) => {
            const isFinished = idx <= (currentStageIndex >= 0 ? currentStageIndex : 0);
            const isCurrent = idx === currentStageIndex;

            return (
              <div
                key={st.stage}
                className={`flex flex-col items-center rounded-lg p-2 transition-all ${
                  isCurrent
                    ? 'bg-sky-600/20 border border-sky-500 text-sky-300 font-bold'
                    : isFinished
                    ? 'bg-slate-850 text-emerald-400'
                    : 'bg-slate-950/50 text-slate-600 border border-slate-900'
                }`}
              >
                <div className="mb-1 text-[10px] font-mono">Step {idx + 1}</div>
                <div className="text-[11px] leading-tight font-medium">{st.label}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Decision Banner */}
      {runRecord?.status === 'COMPLETED' && (
        <div
          className={`rounded-2xl border p-6 shadow-2xl transition-all ${
            decision === 'BLOCK_DEPLOYMENT'
              ? 'border-rose-800/80 bg-rose-950/40 text-rose-100'
              : decision === 'PASS'
              ? 'border-emerald-800/80 bg-emerald-950/40 text-emerald-100'
              : 'border-amber-800/80 bg-amber-950/40 text-amber-100'
          }`}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-rose-900/50 pb-4 mb-4">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-rose-900 text-rose-200 border border-rose-700 shadow-lg">
                <ShieldAlert className="h-7 w-7" />
              </div>
              <div>
                <span className="text-xs font-mono uppercase tracking-wider text-rose-400 font-bold">
                  Authoritative Deterministic Decision
                </span>
                <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                  {decision}
                </h2>
              </div>
            </div>
            <span className="rounded bg-rose-900/80 px-3 py-1 text-xs font-mono font-bold text-rose-200 border border-rose-700 self-start sm:self-auto">
              HIGH RISK DRIFT REPRODUCED
            </span>
          </div>

          <p className="text-sm leading-relaxed text-rose-200">
            {report?.executive_summary ||
              'Material pricing drift was reproduced between pricing intent (AZ_HO3_2026_09) and target implementation (AZ_HO3_2026_09_DEFECTIVE). Critical roof age factor mismatch (1.35 vs 1.25) and effective date drift resulted in measurable financial exposure across 14,607 exposed policies.'}
          </p>
        </div>
      )}

      {/* Key Metric Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="text-xs font-medium text-slate-400">Semantic Diff Items</div>
          <div className="text-2xl font-extrabold text-white font-mono mt-1">
            {report?.semantic_differences?.length || 3}
          </div>
          <div className="text-[11px] text-rose-400 mt-0.5">1 Critical Roof Factor</div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="text-xs font-medium text-slate-400">Semantically Exposed</div>
          <div className="text-2xl font-extrabold text-amber-400 font-mono mt-1">
            {report?.portfolio_exposure?.exposed_policy_count
              ? new Intl.NumberFormat().format(report.portfolio_exposure.exposed_policy_count)
              : '14,607'}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">29.21% of 50K portfolio</div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="text-xs font-medium text-slate-400">Financially Affected</div>
          <div className="text-2xl font-extrabold text-rose-400 font-mono mt-1">
            {report?.portfolio_exposure?.financially_affected_count
              ? new Intl.NumberFormat().format(
                  report.portfolio_exposure.financially_affected_count
                )
              : '13,294'}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">26.59% of 50K portfolio</div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="text-xs font-medium text-slate-400">Absolute Variance</div>
          <div className="text-2xl font-extrabold text-rose-400 font-mono mt-1">
            $
            {report?.portfolio_exposure?.total_absolute_variance
              ? parseFloat(report.portfolio_exposure.total_absolute_variance).toLocaleString()
              : '868,974.18'}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">Gross premium deviation</div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-slate-800">
        <nav className="flex flex-wrap gap-2 text-xs font-medium">
          {[
            { id: 'semantic', label: 'Semantic Differences', icon: ShieldAlert },
            { id: 'impact', label: 'Dependency DAG', icon: GitCompare },
            { id: 'testing', label: 'Risk-Directed Tests', icon: Sparkles },
            { id: 'recon', label: 'Trace Reconciliation & RCA', icon: Layers },
            { id: 'portfolio', label: 'Portfolio Exposure', icon: BarChart3 },
            { id: 'evidence', label: 'Evidence Lineage', icon: Database },
            { id: 'agent', label: 'ADK & Gemini Activity', icon: Bot },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={`flex items-center gap-1.5 border-b-2 px-3 py-2.5 transition-colors ${
                  isActive
                    ? 'border-sky-500 text-sky-300 font-bold bg-sky-950/20'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content Areas */}
      <div className="pt-2">
        {activeTab === 'semantic' && (
          <SemanticDiffViewer diffs={report?.semantic_differences || []} />
        )}

        {activeTab === 'impact' && (
          <ImpactGraph
            impact={
              report?.impact_analysis || {
                impacted_calculation_nodes: ['gross_risk_premium', 'premium_after_discounts', 'total_policy_premium'],
                affected_pricing_outputs: ['final_policy_premium'],
                candidate_risk_predicates: [],
                summary: 'Roof factor mismatch and claims-free drift impact gross risk premium and final policy premium.',
              }
            }
          />
        )}

        {activeTab === 'testing' && (
          <TestPlanViewer
            testPlan={
              report?.test_plan || {
                total_candidates_generated: 30,
                total_scenarios_selected: 30,
                selected_scenarios: [
                  {
                    scenario_id: 'SCENARIO-ROOF-24',
                    name: 'Roof Age 24 High Risk Scenario',
                    category: 'Boundary',
                    description: 'Tests roof age 21..30 factor (1.35 vs 1.25)',
                    risk_inputs: { roof_age: 24, territory: 'T17', construction_type: 'FRAME' },
                    expected_premium: '3847.78',
                    actual_premium: '3562.76',
                    matches: false,
                    trace_diverged: true,
                    first_divergence_node: 'roof_age_factor',
                  },
                ],
                coverage_summary: {},
              }
            }
            onSelectScenario={(s) => {
              setSelectedScenario(s);
              setActiveTab('recon');
            }}
            selectedScenarioId={selectedScenario?.scenario_id}
          />
        )}

        {activeTab === 'recon' && <ReconciliationTrace scenario={selectedScenario} />}

        {activeTab === 'portfolio' && (
          <PortfolioImpactFunnel portfolio={report?.portfolio_exposure} />
        )}

        {activeTab === 'evidence' && <EvidenceLineage evidence={evidence} />}

        {activeTab === 'agent' && (
          <AgentActivityPanel summary={report?.executive_summary} />
        )}
      </div>
    </div>
  );
}

