'use client';

import { ImpactAnalysis } from '@/lib/types/assurance';
import { Network, AlertCircle, ArrowDown } from 'lucide-react';

interface ImpactGraphProps {
  impact: ImpactAnalysis;
}

export function ImpactGraph({ impact }: ImpactGraphProps) {
  const nodes = [
    { id: 'risk_attributes', label: 'Risk Inputs (roof_age, effective_date)', type: 'INPUT' },
    { id: 'diff_nodes', label: 'Changed Semantic Nodes (roof_age_factor, claims_free_discount)', type: 'CHANGED' },
    { id: 'calc_nodes', label: 'Calculation Chain (gross_risk_premium -> premium_after_discounts)', type: 'CALC' },
    { id: 'output_node', label: 'Final Output (final_policy_premium)', type: 'OUTPUT' },
  ];

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-6 shadow-xl space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-white flex items-center gap-2">
          <Network className="h-5 w-5 text-sky-400" />
          Pricing Dependency Graph & Impact Chain
        </h3>
        <span className="text-xs text-slate-400">Directed Acyclic Graph (DAG) Traversal</span>
      </div>

      <div className="flex flex-col items-center gap-2 py-2">
        {nodes.map((node, idx) => (
          <div key={node.id} className="flex flex-col items-center w-full max-w-md">
            <div
              className={`w-full rounded-lg border p-3 text-center transition-all ${
                node.type === 'CHANGED'
                  ? 'border-rose-500/50 bg-rose-950/40 text-rose-300 font-bold shadow-lg shadow-rose-950/30'
                  : node.type === 'OUTPUT'
                  ? 'border-emerald-500/50 bg-emerald-950/40 text-emerald-300 font-bold'
                  : 'border-slate-800 bg-slate-950 text-slate-300'
              }`}
            >
              <div className="flex items-center justify-center gap-2">
                {node.type === 'CHANGED' && <AlertCircle className="h-4 w-4 text-rose-400" />}
                <span className="text-xs sm:text-sm">{node.label}</span>
              </div>
            </div>
            {idx < nodes.length - 1 && <ArrowDown className="my-1 h-4 w-4 text-slate-600" />}
          </div>
        ))}
      </div>

      {impact?.impacted_calculation_nodes && (
        <div className="rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs">
          <span className="text-slate-400">Impacted Calculation Nodes: </span>
          <span className="font-mono text-sky-300">{impact.impacted_calculation_nodes.join(', ')}</span>
        </div>
      )}
    </div>
  );
}

