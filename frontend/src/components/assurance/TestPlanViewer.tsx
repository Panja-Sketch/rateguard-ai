'use client';

import { TestPlan, TestScenario } from '@/lib/types/assurance';
import { useState } from 'react';
import { CheckCircle2, XCircle, Filter, Sparkles } from 'lucide-react';

interface TestPlanViewerProps {
  testPlan: TestPlan;
  onSelectScenario?: (scenario: TestScenario) => void;
  selectedScenarioId?: string;
}

export function TestPlanViewer({
  testPlan,
  onSelectScenario,
  selectedScenarioId,
}: TestPlanViewerProps) {
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');

  if (!testPlan || !testPlan.selected_scenarios) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-6 text-center text-slate-400">
        No risk-directed test plan generated.
      </div>
    );
  }

  const scenarios = testPlan.selected_scenarios;
  const categories = Array.from(new Set(scenarios.map((s) => s.category)));

  const filteredScenarios =
    categoryFilter === 'ALL'
      ? scenarios
      : scenarios.filter((s) => s.category === categoryFilter);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-sky-400" />
            Risk-Directed Test Plan ({scenarios.length} Scenarios)
          </h3>
          <p className="text-xs text-slate-400">
            Selected from {testPlan.total_candidates_generated || 30} generated candidate risk scenarios
          </p>
        </div>

        {/* Category filter */}
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-slate-400" />
          <select
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            className="rounded border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs text-slate-200 focus:border-sky-500 focus:outline-none"
          >
            <option value="ALL">All Categories ({scenarios.length})</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/80">
        <table className="w-full text-left text-xs font-sans">
          <thead className="border-b border-slate-800 bg-slate-950 text-slate-400">
            <tr>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Scenario / Category</th>
              <th className="px-4 py-3 font-medium">Key Risk Inputs</th>
              <th className="px-4 py-3 font-medium text-right">Expected</th>
              <th className="px-4 py-3 font-medium text-right">Actual</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {filteredScenarios.map((sc) => {
              const isSelected = sc.scenario_id === selectedScenarioId;
              const matches = sc.matches;
              return (
                <tr
                  key={sc.scenario_id}
                  onClick={() => onSelectScenario && onSelectScenario(sc)}
                  className={`cursor-pointer transition-colors hover:bg-slate-800/50 ${
                    isSelected ? 'bg-sky-950/40 font-semibold' : ''
                  }`}
                >
                  <td className="px-4 py-3">
                    {matches ? (
                      <span className="inline-flex items-center gap-1 text-emerald-400 font-bold">
                        <CheckCircle2 className="h-4 w-4" /> MATCH
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-rose-400 font-bold">
                        <XCircle className="h-4 w-4" /> MISMATCH
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-semibold text-slate-200">{sc.name}</div>
                    <div className="text-[10px] text-sky-400 font-mono">{sc.category}</div>
                  </td>
                  <td className="px-4 py-3 font-mono text-slate-400">
                    {Object.entries(sc.risk_inputs || {})
                      .slice(0, 4)
                      .map(([k, v]) => `${k}=${v}`)
                      .join(', ')}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-emerald-300">
                    ${sc.expected_premium}
                  </td>
                  <td
                    className={`px-4 py-3 text-right font-mono ${
                      matches ? 'text-emerald-300' : 'text-rose-400 font-bold'
                    }`}
                  >
                    ${sc.actual_premium}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

