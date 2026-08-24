'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { startAssuranceRun, launchScenarioLabRun, fetchDemoScenarios } from '@/lib/api/client';
import {
  Cpu,
  FileSpreadsheet,
  Server,
  ArrowRight,
  ShieldCheck,
  ShieldAlert,
  Zap,
  Sliders,
  CheckCircle2,
  AlertCircle,
  Play,
  RotateCcw,
  Sparkles,
} from 'lucide-react';

export default function DemoPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [runningScenarioId, setRunningScenarioId] = useState<string | null>(null);
  const [asyncExecution, setAsyncExecution] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scenarios, setScenarios] = useState<Array<any>>([]);

  // Scenario Lab Editable Parameters
  const [labName, setLabName] = useState('Custom Judge Experiment');
  const [roofFactor, setRoofFactor] = useState<number>(1.20);
  const [deductibleFactor, setDeductibleFactor] = useState<number>(0.85);
  const [territoryFactor, setTerritoryFactor] = useState<number>(1.10);
  const [claimsDiscount, setClaimsDiscount] = useState<number>(3.0);
  const [effectiveDate, setEffectiveDate] = useState('2026-09-15');
  const [minimumPremium, setMinimumPremium] = useState<number>(550);
  const [policyFee, setPolicyFee] = useState<number>(30);

  useEffect(() => {
    fetchDemoScenarios()
      .then((data) => setScenarios(data.scenarios || []))
      .catch(() => {
        // Fallback default list if offline
        setScenarios([
          {
            id: 'SCENARIO_A',
            name: 'Scenario A: Golden Multi-Defect (Filing vs Buggy Engine)',
            description: 'Roof age factor mismatch (1.35 vs 1.25), effective date drift, and minimum/fee sequence swap.',
            left_package_id: 'AZ_HO3_2026_09',
            right_package_id: 'AZ_HO3_2026_09_DEFECTIVE',
            expected_decision: 'BLOCK_DEPLOYMENT',
            tags: ['Multi-Defect', 'Financial Exposure'],
          },
          {
            id: 'SCENARIO_B',
            name: 'Scenario B: Clean Baseline (No Drift / Perfect Equivalence)',
            description: 'Filing intent compared against a compliant, bug-free target implementation. 100% equivalence.',
            left_package_id: 'AZ_HO3_2026_09',
            right_package_id: 'AZ_HO3_2026_09_CLEAN',
            expected_decision: 'PASS',
            tags: ['No Drift', 'Green Path'],
          },
          {
            id: 'SCENARIO_C',
            name: 'Scenario C: Deductible Factor Table Drift',
            description: 'Target engine contains factor drift on the $1,000 deductible tier (0.80 target vs 0.90 intent).',
            left_package_id: 'AZ_HO3_2026_09',
            right_package_id: 'AZ_HO3_2026_09_DEDUCTIBLE_DRIFT',
            expected_decision: 'BLOCK_DEPLOYMENT',
            tags: ['Table Drift', 'Deductible'],
          },
          {
            id: 'SCENARIO_D',
            name: 'Scenario D: Claims-Free Discount Effective-Date Drift',
            description: 'Target engine implements discount with an effective date of 2026-09-20 instead of 2026-09-01.',
            left_package_id: 'AZ_HO3_2026_09',
            right_package_id: 'AZ_HO3_2026_09_EFFDATE_DRIFT',
            expected_decision: 'BLOCK_DEPLOYMENT',
            tags: ['Temporal Drift', 'SERFF Compliance'],
          },
          {
            id: 'SCENARIO_E',
            name: 'Scenario E: Rating Territory Factor Drift',
            description: 'Target engine misconfigures Territory T05 multiplier (1.15 target vs 1.05 intent).',
            left_package_id: 'AZ_HO3_2026_09',
            right_package_id: 'AZ_HO3_2026_09_TERRITORY_DRIFT',
            expected_decision: 'BLOCK_DEPLOYMENT',
            tags: ['Territory', 'Regional Drift'],
          },
        ]);
      });
  }, []);

  const handleRunPresetScenario = async (sc: any) => {
    setLoading(true);
    setRunningScenarioId(sc.id);
    setError(null);
    try {
      const res = await startAssuranceRun({
        leftPackageId: sc.left_package_id,
        rightPackageId: sc.right_package_id,
        asyncExecution,
      });
      if (res.run_id) {
        router.push(`/runs/${res.run_id}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setLoading(false);
      setRunningScenarioId(null);
    }
  };

  const handleRunScenarioLab = async () => {
    setLoading(true);
    setRunningScenarioId('SCENARIO_LAB');
    setError(null);
    try {
      const res = await launchScenarioLabRun({
        name: labName,
        roof_age_21_30_factor: roofFactor,
        deductible_1000_factor: deductibleFactor,
        territory_t05_factor: territoryFactor,
        claims_free_discount_pct: claimsDiscount,
        claims_free_effective_date: effectiveDate,
        minimum_premium: minimumPremium,
        policy_fee: policyFee,
        async_execution: asyncExecution,
      });
      if (res.run_id) {
        router.push(`/runs/${res.run_id}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setLoading(false);
      setRunningScenarioId(null);
    }
  };

  return (
    <div className="space-y-10 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <div className="inline-flex items-center gap-2 rounded-full bg-sky-950 px-3 py-1 text-xs font-semibold text-sky-300 border border-sky-800 mb-2">
          <Cpu className="h-4 w-4" /> Multi-Scenario Assurance & Scenario Lab
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white">
          Dynamic Pricing Assurance Demonstrations
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          Select ready-to-run assurance scenarios or interactively modify target pricing parameters in the Scenario Lab. Every run executes the full autonomous multi-agent pipeline.
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300 font-mono">
          [Error] {error}
        </div>
      )}

      {/* SECTION 1: Ready-To-Run Demo Scenarios Catalog */}
      <div className="space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-sky-400" />
              1. Ready-To-Run Assurance Scenarios
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Launch pre-configured test scenarios to evaluate clean releases, factor drifts, and multi-defect regressions.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4">
          {scenarios.map((sc) => {
            const isRunning = loading && runningScenarioId === sc.id;
            const isPass = sc.expected_decision === 'PASS';

            return (
              <div
                key={sc.id}
                className="rounded-xl border border-slate-800 bg-slate-900/80 p-5 transition-all hover:border-slate-700 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-lg"
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-bold text-white text-sm">{sc.name}</span>
                    <span
                      className={`rounded px-2 py-0.5 text-[10px] font-mono font-bold border ${
                        isPass
                          ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                          : 'bg-rose-950 text-rose-300 border-rose-800'
                      }`}
                    >
                      Expected: {sc.expected_decision}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed">{sc.description}</p>

                  <div className="flex flex-wrap gap-2 text-[11px] font-mono text-slate-400 pt-1">
                    <span className="text-slate-500">Spec:</span>
                    <span className="text-sky-300">{sc.left_package_id}</span>
                    <span className="text-slate-600">↔</span>
                    <span className="text-purple-300">{sc.right_package_id}</span>
                  </div>
                </div>

                <button
                  onClick={() => handleRunPresetScenario(sc)}
                  disabled={loading}
                  className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-xs font-bold text-white transition-all shrink-0 disabled:opacity-50 ${
                    isPass
                      ? 'bg-emerald-600 hover:bg-emerald-500 shadow-lg shadow-emerald-950/40'
                      : 'bg-sky-600 hover:bg-sky-500 shadow-lg shadow-sky-950/40'
                  }`}
                >
                  <Play className={`h-3.5 w-3.5 ${isRunning ? 'animate-spin' : ''}`} />
                  {isRunning ? 'Launching...' : 'Run Assurance'}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* SECTION 2: Interactive Scenario Lab */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-6 sm:p-8 space-y-6 shadow-2xl">
        <div className="border-b border-slate-800 pb-4">
          <div className="inline-flex items-center gap-2 rounded-full bg-purple-950 px-3 py-1 text-xs font-semibold text-purple-300 border border-purple-800 mb-2">
            <Sliders className="h-4 w-4" /> Interactive Experimentation
          </div>
          <h2 className="text-xl font-extrabold text-white">
            2. Scenario Lab: Parameter Drift Sandbox
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Test arbitrary pricing parameter drift on-the-fly. The backend dynamically clones the canonical Arizona HO3 specification and executes end-to-end IPIR diffing, risk-directed testing, trace alignment, and 50K portfolio blast radius analysis.
          </p>
        </div>

        {/* Experiment Title */}
        <div className="space-y-1.5">
          <label className="text-xs font-bold text-slate-300">Experiment Name</label>
          <input
            type="text"
            value={labName}
            onChange={(e) => setLabName(e.target.value)}
            className="w-full rounded-lg border border-slate-800 bg-slate-950 px-3 py-2 text-xs font-medium text-white focus:border-sky-500 focus:outline-none"
          />
        </div>

        {/* Parameters Grid */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {/* Roof Age Factor */}
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
            <div className="flex justify-between items-center text-xs">
              <span className="font-bold text-slate-200">Roof Age 21..30 Factor</span>
              <span className="font-mono text-emerald-400">Canonical: 1.35</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Target Override:</span>
              <input
                type="number"
                step="0.01"
                value={roofFactor}
                onChange={(e) => setRoofFactor(parseFloat(e.target.value))}
                className="flex-1 rounded border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs font-mono text-white focus:border-sky-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Deductible Factor */}
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
            <div className="flex justify-between items-center text-xs">
              <span className="font-bold text-slate-200">Deductible $1,000 Factor</span>
              <span className="font-mono text-emerald-400">Canonical: 0.90</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Target Override:</span>
              <input
                type="number"
                step="0.01"
                value={deductibleFactor}
                onChange={(e) => setDeductibleFactor(parseFloat(e.target.value))}
                className="flex-1 rounded border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs font-mono text-white focus:border-sky-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Territory Factor */}
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
            <div className="flex justify-between items-center text-xs">
              <span className="font-bold text-slate-200">Territory T05 Factor</span>
              <span className="font-mono text-emerald-400">Canonical: 1.05</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Target Override:</span>
              <input
                type="number"
                step="0.01"
                value={territoryFactor}
                onChange={(e) => setTerritoryFactor(parseFloat(e.target.value))}
                className="flex-1 rounded border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs font-mono text-white focus:border-sky-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Claims-Free Discount % */}
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
            <div className="flex justify-between items-center text-xs">
              <span className="font-bold text-slate-200">Claims-Free Discount (%)</span>
              <span className="font-mono text-emerald-400">Canonical: 5.0%</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Target Override:</span>
              <input
                type="number"
                step="0.5"
                value={claimsDiscount}
                onChange={(e) => setClaimsDiscount(parseFloat(e.target.value))}
                className="flex-1 rounded border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs font-mono text-white focus:border-sky-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Claims-Free Effective Date */}
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
            <div className="flex justify-between items-center text-xs">
              <span className="font-bold text-slate-200">Claims-Free Effective Date</span>
              <span className="font-mono text-emerald-400">Canonical: 2026-09-01</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400">Target Date:</span>
              <input
                type="date"
                value={effectiveDate}
                onChange={(e) => setEffectiveDate(e.target.value)}
                className="flex-1 rounded border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs font-mono text-white focus:border-sky-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Policy Minimum & Fee */}
          <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 space-y-2">
            <div className="flex justify-between items-center text-xs">
              <span className="font-bold text-slate-200">Policy Min ($) / Fee ($)</span>
              <span className="font-mono text-emerald-400">Canonical: $500 / $25</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input
                type="number"
                value={minimumPremium}
                onChange={(e) => setMinimumPremium(parseFloat(e.target.value))}
                placeholder="Min Premium"
                className="rounded border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs font-mono text-white focus:border-sky-500 focus:outline-none"
              />
              <input
                type="number"
                value={policyFee}
                onChange={(e) => setPolicyFee(parseFloat(e.target.value))}
                placeholder="Policy Fee"
                className="rounded border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs font-mono text-white focus:border-sky-500 focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Action Button */}
        <div className="pt-2 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-t border-slate-800">
          <p className="text-xs text-slate-400">
            Creates an immutable in-memory derived package without modifying on-disk canonical specifications.
          </p>
          <button
            onClick={handleRunScenarioLab}
            disabled={loading}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-purple-600 px-6 py-3 text-xs font-bold text-white hover:bg-purple-500 transition-all shadow-xl shadow-purple-950/40 disabled:opacity-50 shrink-0"
          >
            <Play className={`h-4 w-4 ${loading && runningScenarioId === 'SCENARIO_LAB' ? 'animate-spin' : ''}`} />
            {loading && runningScenarioId === 'SCENARIO_LAB' ? 'Executing Multi-Agent Assurance...' : 'Launch Scenario Lab Assurance Run'}
          </button>
        </div>
      </div>
    </div>
  );
}
