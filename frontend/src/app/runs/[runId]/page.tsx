'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams } from 'next/navigation';
import {
  getAssuranceRun,
  getAssuranceRunEvents,
  getAssuranceRunResult,
  getAssuranceRunEvidence,
  ApiError,
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
  RefreshCw,
  GitCompare,
  Sparkles,
  Database,
  Bot,
  BarChart3,
  Layers,
  AlertOctagon,
} from 'lucide-react';

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

        const scenarios =
          resultData.test_plan?.selected_scenarios ||
          (resultData as any)?.test_plan?.scenarios ||
          [];

        if (scenarios.length > 0) {
          const defaultScenario = scenarios.find((s: any) => !s.matches) || scenarios[0];
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
    { stage: 'SEMANTIC_ANALYSIS', label: 'Semantic Diff' },
    { stage: 'IMPACT_ANALYSIS', label: 'Impact DAG' },
    { stage: 'TEST_PLANNING', label: 'Risk Tests' },
    { stage: 'EXECUTION_RECONCILIATION', label: 'Premium Execution' },
    { stage: 'RECONCILIATION', label: 'Reconciliation & RCA' },
    { stage: 'PORTFOLIO_ANALYSIS', label: 'Blast Radius' },
    { stage: 'FINISHED', label: 'Decision Complete' },
  ];

  const currentStageIndex = workflowStages.findIndex(
    (s) => s.stage === (runRecord?.workflow_stage || 'QUEUED')
  );

  const isCompleted = runRecord?.status === 'COMPLETED';
  const isFailed = runRecord?.status === 'FAILED';

  const decision =
    report?.decision ||
    runRecord?.decision ||
    (isCompleted ? 'BLOCK_DEPLOYMENT' : 'PROCESSING');

  // Extract structured sections dynamically
  const semanticDiffs =
    report?.semantic_differences ||
    (report as any)?.semantic_diff?.differences ||
    (runRecord as any)?.semantic_diff_summary?.differences ||
    [];

  const impactData =
    report?.impact_analysis ||
    (report as any)?.impact ||
    (runRecord as any)?.impact_summary ||
    null;

  const testPlanData =
    report?.test_plan ||
    (runRecord as any)?.test_plan_summary ||
    null;

  const portfolioData =
    report?.portfolio_exposure ||
    (report as any)?.portfolio ||
    (runRecord as any)?.portfolio_summary ||
    null;

  const agentStepsData =
    (report as any)?.agent_steps ||
    (runRecord as any)?.agent_activity ||
    [];

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Header & Status Bar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold text-white font-mono">{runId}</h1>
            <span
              className={`rounded px-2.5 py-0.5 text-xs font-mono font-bold border ${
                isCompleted
                  ? decision === 'PASS'
                    ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                    : decision === 'BLOCK_DEPLOYMENT'
                    ? 'bg-rose-950 text-rose-300 border-rose-800'
                    : 'bg-amber-950 text-amber-300 border-amber-800'
                  : isFailed
                  ? 'bg-rose-950 text-rose-300 border-rose-800'
                  : 'bg-sky-950 text-sky-400 border-sky-800'
              }`}
            >
              {runRecord?.status || 'LOADING'}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Autonomous agentic pricing assurance workflow execution details
          </p>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-3.5 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-850 self-start sm:self-auto disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh Data
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300 font-mono">
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
            Current Stage: {runRecord?.workflow_stage || 'QUEUED'}
          </span>
        </div>

        <div className="grid grid-cols-3 gap-2 sm:grid-cols-9 text-center">
          {workflowStages.map((st, idx) => {
            const isFinished = isCompleted || idx < (currentStageIndex >= 0 ? currentStageIndex : 0);
            const isCurrent = idx === currentStageIndex && !isCompleted;

            return (
              <div
                key={st.stage}
                className={`flex flex-col items-center rounded-lg p-2 transition-all ${
                  isCurrent
                    ? 'bg-sky-600/20 border border-sky-500 text-sky-300 font-bold animate-pulse'
                    : isFinished
                    ? 'bg-slate-850 text-emerald-400 border border-emerald-900/40'
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

      {/* Decision Banner (Rendered when completed) */}
      {isCompleted && (
        <div
          className={`rounded-2xl border p-6 shadow-2xl transition-all ${
            decision === 'BLOCK_DEPLOYMENT'
              ? 'border-rose-800/80 bg-rose-950/40 text-rose-100'
              : decision === 'PASS'
              ? 'border-emerald-800/80 bg-emerald-950/40 text-emerald-100'
              : 'border-amber-800/80 bg-amber-950/40 text-amber-100'
          }`}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-white/10 pb-4 mb-4">
            <div className="flex items-center gap-3">
              <div
                className={`flex h-12 w-12 items-center justify-center rounded-xl border shadow-lg ${
                  decision === 'BLOCK_DEPLOYMENT'
                    ? 'bg-rose-900 text-rose-200 border-rose-700'
                    : decision === 'PASS'
                    ? 'bg-emerald-900 text-emerald-200 border-emerald-700'
                    : 'bg-amber-900 text-amber-200 border-amber-700'
                }`}
              >
                {decision === 'PASS' ? (
                  <CheckCircle2 className="h-7 w-7" />
                ) : (
                  <ShieldAlert className="h-7 w-7" />
                )}
              </div>
              <div>
                <span className="text-xs font-mono uppercase tracking-wider font-bold opacity-80">
                  Autonomous Assurance Decision
                </span>
                <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
                  {decision}
                </h2>
              </div>
            </div>

            <span
              className={`rounded px-3 py-1 text-xs font-mono font-bold border self-start sm:self-auto ${
                decision === 'BLOCK_DEPLOYMENT'
                  ? 'bg-rose-900/80 text-rose-200 border-rose-700'
                  : decision === 'PASS'
                  ? 'bg-emerald-900/80 text-emerald-200 border-emerald-700'
                  : 'bg-amber-900/80 text-amber-200 border-amber-700'
              }`}
            >
              {decision === 'BLOCK_DEPLOYMENT'
                ? 'PRICING DRIFT REPRODUCED'
                : decision === 'PASS'
                ? 'VERIFIED COMPLIANT RELEASE'
                : 'MANUAL REVIEW RECOMMENDED'}
            </span>
          </div>

          <p className="text-sm leading-relaxed opacity-90">
            {report?.executive_summary ||
              runRecord?.summary ||
              (decision === 'PASS'
                ? 'Full behavioral and semantic equivalence verified. Zero pricing drift or financial exposure detected across test scenarios and 50,000 policy portfolio.'
                : 'Autonomous assurance workflow completed analysis of pricing models.')}
          </p>
        </div>
      )}

      {/* Dynamic Key Metric Cards (Stage-gated without hardcoded numbers) */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {/* Metric 1: Semantic Diff Items */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="text-xs font-medium text-slate-400">Semantic Diff Items</div>
          <div className="text-2xl font-extrabold text-white font-mono mt-1">
            {isCompleted ? semanticDiffs.length : '-'}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            {isCompleted
              ? `${semanticDiffs.length} AST differences`
              : 'Waiting for semantic diff...'}
          </div>
        </div>

        {/* Metric 2: Semantically Exposed */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="text-xs font-medium text-slate-400">Semantically Exposed</div>
          <div className="text-2xl font-extrabold text-amber-400 font-mono mt-1">
            {isCompleted
              ? new Intl.NumberFormat('en-US').format(portfolioData?.exposed_policy_count ?? (portfolioData as any)?.semantically_exposed ?? 0)
              : '-'}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            {isCompleted
              ? `${portfolioData?.exposed_policy_pct ?? 0}% of 50K portfolio`
              : 'Pending portfolio analysis...'}
          </div>
        </div>

        {/* Metric 3: Financially Affected */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="text-xs font-medium text-slate-400">Financially Affected</div>
          <div className="text-2xl font-extrabold text-rose-400 font-mono mt-1">
            {isCompleted
              ? new Intl.NumberFormat('en-US').format(portfolioData?.financially_affected_count ?? (portfolioData as any)?.financially_affected ?? 0)
              : '-'}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            {isCompleted
              ? `${portfolioData?.financially_affected_pct ?? 0}% with variance`
              : 'Pending portfolio analysis...'}
          </div>
        </div>

        {/* Metric 4: Absolute Variance */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="text-xs font-medium text-slate-400">Absolute Variance</div>
          <div className="text-2xl font-extrabold text-rose-400 font-mono mt-1">
            {isCompleted
              ? `$${parseFloat(String(portfolioData?.total_absolute_variance ?? (portfolioData as any)?.absolute_variance ?? 0)).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
              : '-'}
          </div>
          <div className="text-[11px] text-slate-400 mt-0.5">
            {isCompleted ? 'Gross pricing deviation' : 'Pending portfolio analysis...'}
          </div>
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
            { id: 'portfolio', label: 'Blast Radius & Financial Exposure', icon: BarChart3 },
            { id: 'evidence', label: 'Evidence Lineage', icon: Database },
            { id: 'agent', label: 'ADK & Gemini Activity', icon: Bot },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={`flex items-center gap-1.5 border-b-2 px-3.5 py-2.5 transition-colors ${
                  isActive
                    ? 'border-sky-400 text-sky-400 font-bold bg-sky-950/20'
                    : 'border-transparent text-slate-400 hover:border-slate-700 hover:text-slate-200'
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content Panels */}
      <div className="pt-2">
        {activeTab === 'semantic' && (
          <SemanticDiffViewer diffs={semanticDiffs} isCompleted={isCompleted} />
        )}

        {activeTab === 'impact' && (
          <ImpactGraph impact={impactData} isCompleted={isCompleted} />
        )}

        {activeTab === 'testing' && (
          <TestPlanViewer
            testPlan={testPlanData}
            onSelectScenario={(sc) => {
              setSelectedScenario(sc);
              setActiveTab('recon');
            }}
            selectedScenarioId={selectedScenario?.scenario_id}
            isCompleted={isCompleted}
          />
        )}

        {activeTab === 'recon' && (
          <ReconciliationTrace scenario={selectedScenario} isCompleted={isCompleted} />
        )}

        {activeTab === 'portfolio' && (
          <PortfolioImpactFunnel portfolio={portfolioData} isCompleted={isCompleted} />
        )}

        {activeTab === 'evidence' && (
          <EvidenceLineage evidence={evidence} isCompleted={isCompleted} />
        )}

        {activeTab === 'agent' && (
          <AgentActivityPanel
            summary={report?.executive_summary || runRecord?.summary}
            events={events}
            agentSteps={agentStepsData}
            isCompleted={isCompleted}
          />
        )}
      </div>
    </div>
  );
}
