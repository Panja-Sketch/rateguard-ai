'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { uploadSourceFile, compileSource, startAssuranceRun } from '@/lib/api/client';
import { SourceDescriptor } from '@/lib/types/assurance';
import {
  FileCode2,
  Upload,
  FileSpreadsheet,
  FileText,
  Server,
  CheckCircle2,
  AlertCircle,
  Play,
  Layers,
  ArrowRight,
} from 'lucide-react';

export default function SourcesPage() {
  const router = useRouter();
  const [fileA, setFileA] = useState<File | null>(null);
  const [fileB, setFileB] = useState<File | null>(null);

  const [sourceA, setSourceA] = useState<SourceDescriptor | null>(null);
  const [sourceB, setSourceB] = useState<SourceDescriptor | null>(null);

  const [compiledA, setCompiledA] = useState<any | null>(null);
  const [compiledB, setCompiledB] = useState<any | null>(null);

  const [uploadingA, setUploadingA] = useState(false);
  const [uploadingB, setUploadingB] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const supportedAdapters = [
    {
      name: 'Actuarial Excel Adapter',
      formats: '.xlsx, .csv',
      icon: FileSpreadsheet,
      desc: 'Parses rating tables, rate changes, discounts, and calculation rules from actuarial rate filing workbooks.',
    },
    {
      name: 'Regulatory PDF Adapter',
      formats: '.pdf',
      icon: FileText,
      desc: 'Extracts rate filing specifications, SERFF rule forms, and state mandatory constraints.',
    },
    {
      name: 'Platform Config Adapter',
      formats: '.json, .yaml',
      icon: Server,
      desc: 'Ingests rating platform exported configurations (e.g. Guidewire, Duck Creek, Earnix).',
    },
    {
      name: 'IPIR Canonical Schema',
      formats: '.json',
      icon: FileCode2,
      desc: 'Native Intermediate Pricing Implementation Representation JSON schema (v0.1).',
    },
  ];

  const handleUploadA = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fileA) return;
    setUploadingA(true);
    setError(null);
    try {
      const desc = await uploadSourceFile(fileA);
      setSourceA(desc);
      const compiled = await compileSource(desc.source_id);
      setCompiledA(compiled);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploadingA(false);
    }
  };

  const handleUploadB = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fileB) return;
    setUploadingB(true);
    setError(null);
    try {
      const desc = await uploadSourceFile(fileB);
      setSourceB(desc);
      const compiled = await compileSource(desc.source_id);
      setCompiledB(compiled);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploadingB(false);
    }
  };

  const handleLaunchFromSources = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await startAssuranceRun({
        leftSourceId: sourceA?.source_id,
        rightSourceId: sourceB?.source_id,
        leftPackageId: compiledA?.ipir_package_id || 'AZ_HO3_2026_09',
        rightPackageId: compiledB?.ipir_package_id || 'AZ_HO3_2026_09_DEFECTIVE',
        asyncExecution: true,
      });
      if (res.run_id) {
        router.push(`/runs/${res.run_id}`);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setRunning(false);
    }
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white flex items-center gap-2">
          <FileCode2 className="h-7 w-7 text-sky-400" /> Source Ingestion & Modular Adapters
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          RateGuard ingests heterogeneous actuarial specifications, PDFs, Excel workbooks, and platform JSON configs, automatically compiling them into canonical Intermediate Pricing Implementation Representation (IPIR 0.1) models.
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-800 bg-rose-950/50 p-4 text-xs text-rose-300 font-mono">
          [Error] {error}
        </div>
      )}

      {/* Supported Adapters Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {supportedAdapters.map((ad, idx) => {
          const Icon = ad.icon;
          return (
            <div key={idx} className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-bold text-white text-sm">
                  <Icon className="h-4 w-4 text-sky-400" />
                  {ad.name}
                </div>
                <span className="font-mono text-[10px] text-sky-300 rounded bg-sky-950 px-2 py-0.5 border border-sky-800">
                  {ad.formats}
                </span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">{ad.desc}</p>
            </div>
          );
        })}
      </div>

      {/* Dual Source Upload & Compilation Panels */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        {/* Source A: Pricing Intent */}
        <div className="rounded-2xl border border-sky-800/60 bg-slate-900/80 p-5 space-y-4 shadow-xl">
          <div className="flex items-center justify-between">
            <span className="rounded bg-sky-950 px-2.5 py-0.5 text-xs font-bold text-sky-300 border border-sky-800">
              Source A: Actuarial Filing Intent
            </span>
            <span className="text-xs text-slate-400 font-mono">Spec / Filing</span>
          </div>

          <form onSubmit={handleUploadA} className="space-y-3">
            <input
              type="file"
              accept=".json,.xlsx,.pdf"
              onChange={(e) => setFileA(e.target.files?.[0] || null)}
              className="block w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-sky-950 file:text-sky-300 border border-slate-800 rounded-lg p-2 bg-slate-950"
            />
            <button
              type="submit"
              disabled={!fileA || uploadingA}
              className="w-full inline-flex items-center justify-center gap-1.5 rounded-lg bg-sky-600 px-4 py-2 text-xs font-bold text-white hover:bg-sky-500 transition-all disabled:opacity-50"
            >
              <Upload className="h-3.5 w-3.5" />
              {uploadingA ? 'Compiling to IPIR...' : 'Upload & Compile Source A'}
            </button>
          </form>

          {compiledA && (
            <div className="rounded-lg border border-emerald-800/80 bg-emerald-950/30 p-3 text-xs space-y-1 font-mono">
              <div className="flex items-center gap-1.5 text-emerald-400 font-bold font-sans">
                <CheckCircle2 className="h-4 w-4" /> Compiled to IPIR 0.1
              </div>
              <div className="text-slate-300">Package ID: <span className="text-white">{compiledA.ipir_package_id}</span></div>
              <div className="text-slate-300">Confidence: <span className="text-emerald-300 font-bold">{Math.round((compiledA.confidence || 1) * 100)}%</span></div>
              <div className="text-slate-300">Adapter: <span className="text-sky-300">{compiledA.adapter_id}</span></div>
            </div>
          )}
        </div>

        {/* Source B: Target Engine Implementation */}
        <div className="rounded-2xl border border-purple-800/60 bg-slate-900/80 p-5 space-y-4 shadow-xl">
          <div className="flex items-center justify-between">
            <span className="rounded bg-purple-950 px-2.5 py-0.5 text-xs font-bold text-purple-300 border border-purple-800">
              Source B: Target Engine Config
            </span>
            <span className="text-xs text-slate-400 font-mono">Implementation</span>
          </div>

          <form onSubmit={handleUploadB} className="space-y-3">
            <input
              type="file"
              accept=".json,.xlsx,.pdf"
              onChange={(e) => setFileB(e.target.files?.[0] || null)}
              className="block w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-purple-950 file:text-purple-300 border border-slate-800 rounded-lg p-2 bg-slate-950"
            />
            <button
              type="submit"
              disabled={!fileB || uploadingB}
              className="w-full inline-flex items-center justify-center gap-1.5 rounded-lg bg-purple-600 px-4 py-2 text-xs font-bold text-white hover:bg-purple-500 transition-all disabled:opacity-50"
            >
              <Upload className="h-3.5 w-3.5" />
              {uploadingB ? 'Compiling to IPIR...' : 'Upload & Compile Source B'}
            </button>
          </form>

          {compiledB && (
            <div className="rounded-lg border border-emerald-800/80 bg-emerald-950/30 p-3 text-xs space-y-1 font-mono">
              <div className="flex items-center gap-1.5 text-emerald-400 font-bold font-sans">
                <CheckCircle2 className="h-4 w-4" /> Compiled to IPIR 0.1
              </div>
              <div className="text-slate-300">Package ID: <span className="text-white">{compiledB.ipir_package_id}</span></div>
              <div className="text-slate-300">Confidence: <span className="text-emerald-300 font-bold">{Math.round((compiledB.confidence || 1) * 100)}%</span></div>
              <div className="text-slate-300">Adapter: <span className="text-purple-300">{compiledB.adapter_id}</span></div>
            </div>
          )}
        </div>
      </div>

      {/* Launch Assurance from Sources Banner */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/90 p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-xl">
        <div>
          <h3 className="text-base font-bold text-white flex items-center gap-2">
            <Play className="h-4 w-4 text-sky-400" /> Run Assurance on Ingested Sources
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Launch multi-agent assurance workflow directly comparing compiled Source A against Source B.
          </p>
        </div>

        <button
          onClick={handleLaunchFromSources}
          disabled={running}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-sky-600 to-purple-600 px-6 py-3 text-xs font-bold text-white hover:opacity-90 transition-all shadow-lg disabled:opacity-50 shrink-0"
        >
          {running ? 'Launching Workflow...' : 'Execute Assurance (A ↔ B)'}
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
