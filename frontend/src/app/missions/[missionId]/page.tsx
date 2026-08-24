'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { getAssuranceMission, ApiError } from '@/lib/api/client';
import { AssuranceResultV2 } from '@/lib/types/assurance';
import { MissionErrorBoundary } from '@/components/assurance/MissionErrorBoundary';
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
  Check,
  TrendingDown,
  Clock,
  ArrowLeft,
  Sliders,
} from 'lucide-react';

export default function MissionDetailPage() {
  const params = useParams();
  const missionId = params.missionId as string;

  const [missionData, setMissionData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [consecutiveErrors, setConsecutiveErrors] = useState(0);

  const [activeTab, setActiveTab] = useState<
    'summary' | 'semantic' | 'impact' | 'experiments' | 'recon' | 'blast' | 'remediation' | 'evidence' | 'agent'
  >('summary');

  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      let attempts = 0;
      let lastErr: any = null;
      while (attempts < 3) {
        try {
          const data = await getAssuranceMission(missionId);
          setMissionData(data);
          setConsecutiveErrors(0);
          return;
        } catch (err) {
          lastErr = err;
          attempts++;
          if (attempts < 3) {
            await new Promise((resolve) => setTimeout(resolve, 400));
          }
        }
      }
      setConsecutiveErrors((prev) => prev + 1);
      if (lastErr instanceof ApiError) {
        setError(`API Error (${lastErr.message})`);
      } else {
        setError(lastErr instanceof Error ? lastErr.message : String(lastErr));
      }
    } finally {
      setLoading(false);
    }
  }, [missionId]);

  // Active Polling Loop (Interval 2.5s)
  useEffect(() => {
    loadData();

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, [loadData]);

  useEffect(() => {
    if (!missionData) return;

    const currentStatus = (missionData.status || '').toUpperCase();
    const isTerminal = ['COMPLETED', 'FAILED', 'NEEDS_REVIEW', 'CANCELLED', 'ARCHIVED'].includes(currentStatus);

    if (!isTerminal && consecutiveErrors < 5) {
      pollTimerRef.current = setInterval(() => {
        loadData();
      }, 2500);
    } else {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    }

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, [missionData, consecutiveErrors, loadData]);

  if (loading && !missionData) {
    return (
      <div className="py-20 text-center space-y-3">
        <RefreshCw className="h-8 w-8 text-sky-400 animate-spin mx-auto" />
        <div className="text-sm font-bold text-white">Loading Assurance Mission Details...</div>
      </div>
    );
  }

  if (error && !missionData) {
    return (
      <div className="max-w-4xl mx-auto py-10 space-y-4">
        <div className="rounded-xl border border-rose-800 bg-rose-950/50 p-6 text-xs font-mono text-rose-300">
          [Mission Error] {error}
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={loadData}
            className="inline-flex items-center gap-1.5 rounded-lg bg-sky-600 px-4 py-2 text-xs font-bold text-white hover:bg-sky-500"
          >
            <RefreshCw className="h-4 w-4" /> Retry Polling
          </button>
          <Link
            href="/missions"
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-800"
          >
            <ArrowLeft className="h-4 w-4" /> Back to History
          </Link>
        </div>
      </div>
    );
  }

  const result: AssuranceResultV2 = missionData?.result || {};
  const meta = missionData?.metadata || {};
  const statusStr = (missionData?.status || 'QUEUED').toUpperCase();
  const isRunning = ['QUEUED', 'RUNNING', 'VALIDATING', 'WAITING_RETRY'].includes(statusStr);
  const decision = result?.release_decision?.data?.status || missionData?.decision || 'UNKNOWN';

  // Section Safeties
  const validationSec = result?.validation || { status: 'NOT_RUN' };
  const semanticSec = result?.semantic_analysis || { status: 'NOT_RUN' };
  const impactSec = result?.impact_analysis || { status: 'NOT_RUN' };
  const experimentsSec = result?.experiments || { status: 'NOT_RUN' };
  const reconSec = result?.reconciliation || { status: 'NOT_RUN' };
  const blastSec = result?.blast_radius || { status: 'NOT_RUN' };
  const remediationSec = result?.remediation || { status: 'NOT_RUN' };
  const revalidationSec = result?.revalidation || { status: 'NOT_RUN' };
  const agentSec = result?.agent_execution || { status: 'NOT_RUN' };

  // Heartbeat threshold check (> 120s)
  const lastUpdated = missionData?.updated_at ? new Date(missionData.updated_at).getTime() : Date.now();
  const isStale = isRunning && Date.now() - lastUpdated > 120000;

  return (
    <MissionErrorBoundary onRetry={loadData}>
      <div className="space-y-8 max-w-6xl mx-auto">
        {/* Header Bar */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-extrabold text-white font-mono">{missionId}</h1>
              <span className={`rounded px-2.5 py-0.5 text-xs font-mono font-bold border ${
                isRunning ? 'bg-sky-950 text-sky-300 border-sky-800 animate-pulse' : 'bg-slate-800 text-slate-200 border-slate-700'
              }`}>
                {statusStr}
              </span>
              <span className="rounded bg-purple-950 px-2 py-0.5 text-xs font-mono font-bold text-purple-300 border border-purple-800">
                {meta.mode || 'RELEASE_CONFORMANCE'}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              {meta.name || 'Autonomous Pricing Release Assurance Mission'}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={loadData}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-3.5 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-850"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isRunning ? 'animate-spin' : ''}`} /> Refresh
            </button>
          </div>
        </div>

        {/* Stale Mission Heartbeat Warning Banner */}
        {isStale && (
          <div className="rounded-xl border border-amber-800 bg-amber-950/40 p-4 text-xs text-amber-200 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-amber-400 flex-shrink-0" />
              <span>Warning: Execution is taking longer than expected (&gt; 120s). Background worker may be calculating 50K portfolio blast radius.</span>
            </div>
            <button
              onClick={loadData}
              className="rounded bg-amber-900 px-3 py-1 text-xs font-bold text-amber-100 border border-amber-700 hover:bg-amber-800"
            >
              Retry Polling
            </button>
          </div>
        )}

        {/* Running Banner */}
        {isRunning && (
          <div className="rounded-xl border border-sky-800/80 bg-sky-950/30 p-5 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sky-300 font-bold text-sm">
                <RefreshCw className="h-4 w-4 animate-spin text-sky-400" />
                Assurance Supervisor Executing Mission Stages...
              </div>
              <span className="font-mono text-xs text-sky-400">{missionData?.workflow_stage || 'PROCESSING'}</span>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              Google ADK + Gemini 3.7 Flash supervisor is actively coordinating AST diff comparison, DAG impact analysis, boundary probes, and 50K portfolio blast radius calculations in the background.
            </p>
          </div>
        )}

        {/* Release Decision Banner */}
        {result?.release_decision?.data && (
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
                  {decision === 'PASS' ? <CheckCircle2 className="h-7 w-7" /> : <ShieldAlert className="h-7 w-7" />}
                </div>
                <div>
                  <span className="text-xs font-mono uppercase tracking-wider font-bold opacity-80">
                    Release Gate Decision
                  </span>
                  <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">{decision}</h2>
                </div>
              </div>

              <span className="rounded bg-black/40 px-3 py-1 text-xs font-mono font-bold border border-white/20">
                Confidence: {Math.round((result.release_decision.data.confidence_score || 1) * 100)}%
              </span>
            </div>

            <p className="text-sm leading-relaxed opacity-90">{result.release_decision.data.summary}</p>
          </div>
        )}

        {/* AI Runtime Header */}
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-sky-400" />
            <span className="font-bold text-white">AI Runtime:</span>
            <span className="font-mono text-sky-300 font-bold">Gemini 3.7 Flash</span>
            <span className="text-slate-500">|</span>
            <span className="text-slate-300">Framework: Google ADK</span>
            <span className="text-slate-500">|</span>
            <span className="text-emerald-400 font-bold">Model Status: Ready</span>
          </div>
          <span className="font-mono text-[11px] text-slate-400">Strict Deterministic Boundary Enforced</span>
        </div>

        {/* Tab Navigation */}
        <div className="border-b border-slate-800">
          <nav className="flex flex-wrap gap-2 text-xs font-medium">
            {[
              { id: 'summary', label: 'Mission Summary', icon: Layers },
              { id: 'semantic', label: 'Material Findings', icon: ShieldAlert },
              { id: 'impact', label: 'Dependency DAG', icon: GitCompare },
              { id: 'experiments', label: 'Boundary Experiments', icon: Sparkles },
              { id: 'recon', label: 'Reconciliation & RCA', icon: Sliders },
              { id: 'blast', label: 'Blast Radius & Telemetry', icon: BarChart3 },
              { id: 'remediation', label: 'Remediation & Revalidation', icon: Check },
              { id: 'evidence', label: 'Evidence Lineage', icon: Database },
              { id: 'agent', label: 'Gemini Action Timeline', icon: Bot },
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
          {/* Tab 1: Mission Summary */}
          {activeTab === 'summary' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 space-y-1">
                  <div className="text-xs text-slate-400">Comparison Mode</div>
                  <div className="text-lg font-extrabold text-white font-mono">{meta.mode || 'RELEASE_CONFORMANCE'}</div>
                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 space-y-1">
                  <div className="text-xs text-slate-400">Target Product & State</div>
                  <div className="text-lg font-extrabold text-sky-300 font-mono">AZ_HO3 (Arizona)</div>
                </div>

                <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 space-y-1">
                  <div className="text-xs text-slate-400">Effective Period</div>
                  <div className="text-lg font-extrabold text-emerald-400 font-mono">2026-09-01</div>
                </div>
              </div>

              {/* Source Overview Card */}
              <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 space-y-3">
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">Source & Runtime Config</h3>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 text-xs font-mono">
                  <div className="rounded-lg border border-sky-800/80 bg-slate-950 p-3 space-y-1">
                    <div className="text-sky-400 font-bold font-sans">Source A (Pricing Intent):</div>
                    <div className="text-slate-200">{meta.source_a || 'AZ_HO3_2026_09'}</div>
                  </div>
                  <div className="rounded-lg border border-purple-800/80 bg-slate-950 p-3 space-y-1">
                    <div className="text-purple-400 font-bold font-sans">Source B / Target Runtime:</div>
                    <div className="text-slate-200">{meta.source_b || 'AZ_HO3_2026_09_DEFECTIVE'}</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Tab 2: Material Findings */}
          {activeTab === 'semantic' && (
            semanticSec?.status === 'SUCCEEDED' ? (
              <SemanticDiffViewer diffs={semanticSec.data?.differences} isCompleted={true} />
            ) : (
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-xs text-slate-400 font-mono">
                Status: {semanticSec?.status || 'NOT_RUN'} — {semanticSec?.reason || (isRunning ? 'Executing semantic diff analysis...' : 'Omitted or not available.')}
              </div>
            )
          )}

          {/* Tab 3: Dependency DAG */}
          {activeTab === 'impact' && (
            impactSec?.status === 'SUCCEEDED' ? (
              <ImpactGraph impact={impactSec.data} isCompleted={true} />
            ) : (
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-xs text-slate-400 font-mono">
                Status: {impactSec?.status || 'NOT_RUN'} — {impactSec?.reason || (isRunning ? 'Executing DAG graph traversal...' : 'Omitted or not available.')}
              </div>
            )
          )}

          {/* Tab 4: Boundary Experiments */}
          {activeTab === 'experiments' && (
            experimentsSec?.status === 'SUCCEEDED' ? (
              <TestPlanViewer testPlan={experimentsSec.data} isCompleted={true} />
            ) : (
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-xs text-slate-400 font-mono">
                Status: {experimentsSec?.status || 'NOT_RUN'} — {experimentsSec?.reason || (isRunning ? 'Executing risk-directed probes...' : 'Omitted or not available.')}
              </div>
            )
          )}

          {/* Tab 5: Reconciliation & RCA */}
          {activeTab === 'recon' && (
            reconSec?.status === 'SUCCEEDED' ? (
              <ReconciliationTrace scenario={experimentsSec?.data?.experiments?.[0] as any} isCompleted={true} />
            ) : (
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-xs text-slate-400 font-mono">
                Status: {reconSec?.status || 'NOT_RUN'} — {reconSec?.reason || (isRunning ? 'Executing trace reconciliation & RCA...' : 'Omitted or not available.')}
              </div>
            )
          )}

          {/* Tab 6: Blast Radius & Telemetry */}
          {activeTab === 'blast' && (
            blastSec?.status === 'SUCCEEDED' ? (
              <PortfolioImpactFunnel portfolio={blastSec.data as any} isCompleted={true} />
            ) : (
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-xs text-slate-400 font-mono">
                Status: {blastSec?.status || 'NOT_RUN'} — {blastSec?.reason || (isRunning ? 'Evaluating 50K portfolio exposure...' : 'Omitted or not available.')}
              </div>
            )
          )}

          {/* Tab 7: Remediation & Revalidation */}
          {activeTab === 'remediation' && (
            remediationSec?.status === 'SUCCEEDED' && remediationSec?.data ? (
              <div className="space-y-6">
                <div className="rounded-xl border border-sky-800/80 bg-slate-900/80 p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                      <Check className="h-5 w-5 text-sky-400" /> {remediationSec.data.title}
                    </h3>
                    <span className="font-mono text-xs text-sky-300 rounded bg-sky-950 px-2.5 py-0.5 border border-sky-800">
                      {remediationSec.data.derived_package_id}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">{remediationSec.data.rationale}</p>

                  {/* Changes List */}
                  <div className="space-y-2 pt-2">
                    <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">Proposed Modifications</div>
                    {Object.entries(remediationSec.data.proposed_changes || {}).map(([key, val]: any) => (
                      <div key={key} className="rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs font-mono space-y-1">
                        <div className="font-bold text-sky-300">{val.title || key}</div>
                        <div className="grid grid-cols-2 gap-2 text-[11px]">
                          <div>Target Value: <span className="text-rose-400 font-bold">{val.before_target_value}</span></div>
                          <div>Proposed Value: <span className="text-emerald-400 font-bold">{val.proposed_intent_value}</span></div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Revalidation Results */}
                {revalidationSec?.status === 'SUCCEEDED' && revalidationSec?.data && (
                  <div className="rounded-xl border border-emerald-800/80 bg-emerald-950/20 p-5 space-y-4 shadow-xl">
                    <div className="flex items-center justify-between border-b border-emerald-800/60 pb-3">
                      <h4 className="text-sm font-bold text-emerald-300 flex items-center gap-2">
                        <TrendingDown className="h-4 w-4 text-emerald-400" /> Remediation Revalidation Analysis
                      </h4>
                      <span className="font-mono text-xs font-bold text-emerald-400">
                        {revalidationSec.data.exposure_eliminated_pct}% Exposure Eliminated
                      </span>
                    </div>

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 text-xs font-mono">
                      <div className="rounded-lg border border-rose-900/60 bg-rose-950/30 p-3 space-y-1">
                        <div className="text-rose-400 font-bold font-sans">BEFORE Remediation Exposure:</div>
                        <div className="text-xl font-extrabold text-rose-300">${revalidationSec.data.before_absolute_exposure}</div>
                        <div className="text-[11px] text-slate-400">{revalidationSec.data.before_affected_policies} affected policies</div>
                      </div>

                      <div className="rounded-lg border border-emerald-900/60 bg-emerald-950/30 p-3 space-y-1">
                        <div className="text-emerald-400 font-bold font-sans">AFTER Remediation Exposure:</div>
                        <div className="text-xl font-extrabold text-emerald-300">${revalidationSec.data.after_absolute_exposure}</div>
                        <div className="text-[11px] text-slate-400">{revalidationSec.data.after_affected_policies} affected policies</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-xs text-slate-400 font-mono">
                Status: {remediationSec?.status || 'NOT_RUN'} — {remediationSec?.reason || (isRunning ? 'Generating remediation proposal...' : 'Omitted or not required.')}
              </div>
            )
          )}

          {/* Tab 8: Evidence Lineage */}
          {activeTab === 'evidence' && (
            <EvidenceLineage evidence={result?.evidence_refs as any} isCompleted={true} />
          )}

          {/* Tab 9: Gemini Action Timeline */}
          {activeTab === 'agent' && (
            agentSec?.status === 'SUCCEEDED' ? (
              <AgentActivityPanel agentSteps={agentSec.data as any} isCompleted={true} />
            ) : (
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-8 text-center text-xs text-slate-400 font-mono">
                Status: {agentSec?.status || 'NOT_RUN'} — {agentSec?.reason || (isRunning ? 'Logging agent execution timeline...' : 'Timeline omitted.')}
              </div>
            )
          )}
        </div>
      </div>
    </MissionErrorBoundary>
  );
}
