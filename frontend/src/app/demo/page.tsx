'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { startAssuranceRun } from '@/lib/api/client';
import { Cpu, FileSpreadsheet, Server, ArrowRight, ShieldCheck, Zap } from 'lucide-react';

export default function DemoPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [asyncExecution, setAsyncExecution] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleRunDemo = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await startAssuranceRun({
        leftPackageId: 'AZ_HO3_2026_09',
        rightPackageId: 'AZ_HO3_2026_09_DEFECTIVE',
        asyncExecution,
      });

      if (res.run_id) {
        router.push(`/runs/${res.run_id}`);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div>
        <div className="inline-flex items-center gap-2 rounded-full bg-sky-950 px-3 py-1 text-xs font-semibold text-sky-300 border border-sky-800 mb-2">
          <Cpu className="h-4 w-4" /> Interactive Judge Demonstration
        </div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white">Execute Synthetic Pricing Assurance</h1>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          Select pricing source models and launch an agentic pricing assurance workflow comparing actuarial filing intent against a target engine implementation.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300 font-mono">
          [Error] {error}
        </div>
      )}

      {/* Source Comparison Panels */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        {/* Left Side: Pricing Intent */}
        <div className="rounded-xl border border-sky-800/80 bg-slate-900/80 p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between">
            <span className="rounded bg-sky-950 px-2 py-0.5 text-xs font-bold text-sky-300 border border-sky-800">
              Pricing Intent (Source A)
            </span>
            <span className="text-xs text-slate-400 font-mono">AZ_HO3_2026_09</span>
          </div>

          <div className="flex items-start gap-3">
            <div className="rounded-lg bg-sky-950 p-2 text-sky-400 border border-sky-800">
              <FileSpreadsheet className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Arizona HO3 Actuarial Workbook</h3>
              <p className="text-xs text-slate-400 mt-0.5">Authoritative Rate Filing Specification (2026.09)</p>
            </div>
          </div>

          <div className="space-y-1.5 text-xs text-slate-300 border-t border-slate-800 pt-3">
            <div className="flex justify-between">
              <span className="text-slate-500">Source Format:</span>
              <span className="font-mono text-sky-300">Excel / Structured JSON</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Effective Date:</span>
              <span className="font-mono text-slate-200">2026-09-01</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Roof Age 21..30 Factor:</span>
              <span className="font-mono text-emerald-400 font-bold">1.35</span>
            </div>
          </div>
        </div>

        {/* Right Side: Target Implementation */}
        <div className="rounded-xl border border-purple-800/80 bg-slate-900/80 p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between">
            <span className="rounded bg-purple-950 px-2 py-0.5 text-xs font-bold text-purple-300 border border-purple-800">
              Target Implementation (Source B)
            </span>
            <span className="text-xs text-slate-400 font-mono">AZ_HO3_2026_09_DEFECTIVE</span>
          </div>

          <div className="flex items-start gap-3">
            <div className="rounded-lg bg-purple-950 p-2 text-purple-400 border border-purple-800">
              <Server className="h-6 w-6" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Synthetic Rating Platform Config</h3>
              <p className="text-xs text-slate-400 mt-0.5">Target Rating Engine Implementation (2026.09-defective)</p>
            </div>
          </div>

          <div className="space-y-1.5 text-xs text-slate-300 border-t border-slate-800 pt-3">
            <div className="flex justify-between">
              <span className="text-slate-500">Source Format:</span>
              <span className="font-mono text-purple-300">Platform Configuration</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Effective Date:</span>
              <span className="font-mono text-rose-400">2026-09-15 (Drift)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Roof Age 21..30 Factor:</span>
              <span className="font-mono text-rose-400 font-bold">1.25 (Defective)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Execution Options */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Zap className="h-5 w-5 text-amber-400" />
          <div>
            <div className="text-xs font-bold text-white">Asynchronous Pub/Sub Execution Mode</div>
            <div className="text-[11px] text-slate-400">Queues workflow via Pub/Sub worker for background Cloud Run execution</div>
          </div>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={asyncExecution}
            onChange={(e) => setAsyncExecution(e.target.checked)}
            className="sr-only peer"
          />
          <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sky-600"></div>
        </label>
      </div>

      {/* Action Button */}
      <div className="text-center pt-2">
        <button
          onClick={handleRunDemo}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-xl bg-sky-600 px-8 py-4 text-base font-extrabold text-white shadow-xl shadow-sky-600/30 hover:bg-sky-500 transition-all disabled:opacity-50"
        >
          {loading ? (
            <>
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
              <span>Initiating Assurance Workflow...</span>
            </>
          ) : (
            <>
              <ShieldCheck className="h-6 w-6" />
              <span>Run Pricing Assurance Demo</span>
              <ArrowRight className="h-5 w-5" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}

