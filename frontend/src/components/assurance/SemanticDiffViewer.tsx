'use client';

import { SemanticDiffItem } from '@/lib/types/assurance';
import { AlertTriangle, ArrowRight, ShieldAlert } from 'lucide-react';

interface SemanticDiffViewerProps {
  diffs: SemanticDiffItem[];
}

export function SemanticDiffViewer({ diffs }: SemanticDiffViewerProps) {
  if (!diffs || diffs.length === 0) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-6 text-center text-slate-400">
        No semantic differences detected between pricing models.
      </div>
    );
  }

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'CRITICAL':
        return 'bg-rose-950/80 text-rose-300 border-rose-800';
      case 'HIGH':
        return 'bg-amber-950/80 text-amber-300 border-amber-800';
      case 'MEDIUM':
        return 'bg-yellow-950/80 text-yellow-300 border-yellow-800';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-white flex items-center gap-2">
          <ShieldAlert className="h-5 w-5 text-rose-400" />
          Semantic Differences ({diffs.length})
        </h3>
        <span className="text-xs text-slate-400">Identified via IPIR 0.1 AST Comparison</span>
      </div>

      <div className="space-y-3">
        {diffs.map((diff, idx) => (
          <div
            key={diff.id || idx}
            className="rounded-lg border border-slate-800 bg-slate-900/80 p-4 transition-all hover:border-slate-700"
          >
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span
                  className={`rounded px-2 py-0.5 text-xs font-semibold border ${getSeverityBadge(
                    diff.severity
                  )}`}
                >
                  {diff.severity}
                </span>
                <span className="font-mono text-xs font-bold text-sky-400">
                  {diff.difference_type}
                </span>
              </div>
              <span className="font-mono text-xs text-slate-400">
                {diff.semantic_path}
              </span>
            </div>

            <p className="mb-3 text-sm text-slate-200">{diff.description}</p>

            <div className="grid grid-cols-1 gap-2 rounded border border-slate-800 bg-slate-950 p-2.5 sm:grid-cols-2 text-xs font-mono">
              <div className="flex items-center gap-2 border-b border-slate-800 pb-1.5 sm:border-b-0 sm:border-r sm:pr-2 sm:pb-0">
                <span className="text-slate-500 font-sans">Intent:</span>
                <span className="text-emerald-400 font-bold">{diff.left_value}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-slate-500 font-sans">Target:</span>
                <span className="text-rose-400 font-bold">{diff.right_value}</span>
              </div>
            </div>

            {diff.affected_output && (
              <div className="mt-2 flex items-center gap-1.5 text-[11px] text-slate-400">
                <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
                <span>Impacted Output Node:</span>
                <span className="font-mono text-slate-300">{diff.affected_output}</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

