'use client';

import { TestScenario } from '@/lib/types/assurance';
import { ShieldAlert, ArrowRight, CheckCircle2, AlertOctagon } from 'lucide-react';

interface ReconciliationTraceProps {
  scenario?: TestScenario | null;
}

export function ReconciliationTrace({ scenario }: ReconciliationTraceProps) {
  if (!scenario) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-6 text-center text-slate-400">
        Select a test scenario from the Test Plan to inspect its node trace reconciliation and root cause analysis.
      </div>
    );
  }

  // Sample trace step comparison for the selected scenario
  const traceNodes = [
    { name: 'base_rate', left: '650.00', right: '650.00', match: true },
    { name: 'territory_factor', left: '1.20', right: '1.20', match: true },
    {
      name: 'roof_age_factor',
      left: '1.35',
      right: '1.25',
      match: false,
      isFirstDivergence: scenario.category?.includes('Roof') || scenario.scenario_id?.includes('roof'),
    },
    {
      name: 'gross_risk_premium',
      left: '3847.78',
      right: '3562.76',
      match: false,
      isFirstDivergence: false,
    },
    {
      name: 'claims_free_discount',
      left: '0.05',
      right: '0.00 (Ineligible / Effective Drift)',
      match: false,
      isFirstDivergence: scenario.category?.includes('Temporal') || scenario.scenario_id?.includes('temporal'),
    },
    { name: 'total_policy_premium', left: scenario.expected_premium, right: scenario.actual_premium, match: scenario.matches },
  ];

  return (
    <div className="space-y-4 rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-6 shadow-xl">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <ShieldAlert className="h-5 w-5 text-rose-400" />
            Pricing Node Reconciliation Trace & RCA
          </h3>
          <p className="font-mono text-xs text-sky-400">Scenario: {scenario.name} ({scenario.scenario_id})</p>
        </div>
        <span
          className={`rounded px-2.5 py-1 text-xs font-bold ${
            scenario.matches
              ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
              : 'bg-rose-950 text-rose-300 border border-rose-800'
          }`}
        >
          {scenario.matches ? 'EXACT MATCH' : 'PRICE DIVERGENCE'}
        </span>
      </div>

      {!scenario.matches && (
        <div className="rounded-lg border border-rose-800/80 bg-rose-950/40 p-4">
          <div className="flex items-center gap-2 text-rose-300 font-bold text-sm mb-1">
            <AlertOctagon className="h-5 w-5 text-rose-400" />
            Deterministic Root Cause Identified
          </div>
          <p className="text-xs text-rose-200">
            Node <span className="font-mono font-bold text-white">{scenario.first_divergence_node || 'roof_age_factor'}</span> produced first trace divergence. Pricing intent expects factor <span className="font-mono text-emerald-300 font-bold">1.35</span> while target implementation returned <span className="font-mono text-rose-300 font-bold">1.25</span>.
          </p>
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950">
        <table className="w-full text-left text-xs font-mono">
          <thead className="border-b border-slate-800 bg-slate-900 text-slate-400 font-sans">
            <tr>
              <th className="px-4 py-2.5">Calculation Node</th>
              <th className="px-4 py-2.5 text-emerald-400">Intent Expected</th>
              <th className="px-4 py-2.5 text-rose-400">Target Actual</th>
              <th className="px-4 py-2.5">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {traceNodes.map((node) => (
              <tr
                key={node.name}
                className={node.isFirstDivergence ? 'bg-rose-950/30 border-l-4 border-l-rose-500 font-bold' : ''}
              >
                <td className="px-4 py-2.5 text-slate-200">
                  {node.name}
                  {node.isFirstDivergence && (
                    <span className="ml-2 rounded bg-rose-900 px-1.5 py-0.5 text-[10px] text-rose-200 font-sans">
                      FIRST DIVERGENCE
                    </span>
                  )}
                </td>
                <td className="px-4 py-2.5 text-emerald-300">${node.left}</td>
                <td className="px-4 py-2.5 text-rose-300">${node.right}</td>
                <td className="px-4 py-2.5">
                  {node.match ? (
                    <span className="text-emerald-400 flex items-center gap-1 font-sans">
                      <CheckCircle2 className="h-3.5 w-3.5" /> OK
                    </span>
                  ) : (
                    <span className="text-rose-400 font-bold font-sans">MISMATCH</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

