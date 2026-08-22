'use client';

import Link from 'next/link';
import { useState, useEffect } from 'react';
import { History, ShieldAlert, CheckCircle2, ArrowRight, RefreshCw } from 'lucide-react';

interface RunItem {
  run_id: string;
  status: string;
  decision?: string;
  workflow_stage?: string;
  created_at?: string;
}

export default function RunsPage() {
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchRuns = async () => {
    setLoading(true);
    try {
      // Sample recent runs or fetch from storage
      setRuns([
        {
          run_id: 'RUN-AZ-HO3-DEMO',
          status: 'COMPLETED',
          decision: 'BLOCK_DEPLOYMENT',
          workflow_stage: 'COMPLETED',
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  const getDecisionBadge = (decision?: string) => {
    switch (decision) {
      case 'BLOCK_DEPLOYMENT':
        return 'bg-rose-950 text-rose-300 border-rose-800';
      case 'PASS':
        return 'bg-emerald-950 text-emerald-300 border-emerald-800';
      case 'HUMAN_REVIEW':
        return 'bg-amber-950 text-amber-300 border-amber-800';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white flex items-center gap-2">
            <History className="h-7 w-7 text-sky-400" /> Assurance Runs History
          </h1>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Persisted workflow runs, evidence lineage, and pricing assurance decisions stored in Firestore.
          </p>
        </div>
        <button
          onClick={fetchRuns}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-850"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/80 shadow-xl">
        <table className="w-full text-left text-xs font-sans">
          <thead className="border-b border-slate-800 bg-slate-950 text-slate-400">
            <tr>
              <th className="px-4 py-3 font-medium">Run ID</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Assurance Decision</th>
              <th className="px-4 py-3 font-medium">Workflow Stage</th>
              <th className="px-4 py-3 font-medium text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {runs.map((r) => (
              <tr key={r.run_id} className="hover:bg-slate-850/50 transition-colors">
                <td className="px-4 py-3 font-mono font-bold text-sky-300">
                  <Link href={`/runs/${r.run_id}`} className="hover:underline">
                    {r.run_id}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center gap-1 font-bold text-emerald-400">
                    <CheckCircle2 className="h-3.5 w-3.5" /> {r.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`rounded px-2.5 py-0.5 text-[11px] font-extrabold border ${getDecisionBadge(r.decision)}`}>
                    {r.decision || 'N/A'}
                  </span>
                </td>
                <td className="px-4 py-3 font-mono text-slate-400">{r.workflow_stage || 'COMPLETED'}</td>
                <td className="px-4 py-3 text-right">
                  <Link
                    href={`/runs/${r.run_id}`}
                    className="inline-flex items-center gap-1 text-sky-400 hover:text-sky-300 font-semibold"
                  >
                    View Report <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
