'use client';

import { useState } from 'react';
import { uploadSourceFile, compileSource } from '@/lib/api/client';
import { SourceDescriptor } from '@/lib/types/assurance';
import { FileCode2, Upload, FileSpreadsheet, FileText, Server, CheckCircle2, AlertCircle } from 'lucide-react';

export default function SourcesPage() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [registeredSource, setRegisteredSource] = useState<SourceDescriptor | null>(null);
  const [compiledPackage, setCompiledPackage] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const supportedAdapters = [
    { name: 'Actuarial Excel Adapter', formats: '.xlsx, .csv', icon: FileSpreadsheet, desc: 'Parses rating tables, rate changes, discounts, and calculation rules from Excel specs.' },
    { name: 'Regulatory PDF Adapter', formats: '.pdf', icon: FileText, desc: 'Extracts rate filings, SERFF document rules, and state mandatory constraints.' },
    { name: 'Platform Config Adapter', formats: '.json, .yaml', icon: Server, desc: 'Ingests rating platform exported configurations (e.g. Guidewire, Duck Creek, Earnix).' },
    { name: 'IPIR Canonical Schema', formats: '.json', icon: FileCode2, desc: 'Native Intermediate Pricing Implementation Representation JSON schema (v0.1).' },
  ];

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const desc = await uploadSourceFile(file);
      setRegisteredSource(desc);

      // Auto-compile into IPIR
      const compiled = await compileSource(desc.source_id);
      setCompiledPackage(compiled);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white flex items-center gap-2">
          <FileCode2 className="h-7 w-7 text-sky-400" /> Source Ingestion & Adapters
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          RateGuard uses modular source adapters to ingest actuarial specs, filings, and rating engine configs, compiling them into intermediate IPIR packages.
        </p>
      </div>

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

      {/* Source Upload Panel */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 space-y-4">
        <h2 className="text-base font-bold text-white flex items-center gap-2">
          <Upload className="h-5 w-5 text-sky-400" /> Register & Compile Custom Pricing Source
        </h2>

        <form onSubmit={handleUpload} className="space-y-4">
          <input
            type="file"
            accept=".json,.xlsx,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="block w-full text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-sky-950 file:text-sky-300 border border-slate-800 rounded-lg p-2 bg-slate-950"
          />

          <button
            type="submit"
            disabled={!file || uploading}
            className="inline-flex items-center gap-2 rounded-lg bg-sky-600 px-5 py-2 text-xs font-bold text-white hover:bg-sky-500 transition-all disabled:opacity-50"
          >
            {uploading ? 'Processing & Compiling...' : 'Upload & Compile Source'}
          </button>
        </form>

        {error && (
          <div className="rounded-lg border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-300 font-mono">
            [Upload Error] {error}
          </div>
        )}

        {registeredSource && (
          <div className="rounded-lg border border-emerald-800/80 bg-emerald-950/30 p-4 space-y-2 text-xs">
            <div className="flex items-center gap-2 text-emerald-400 font-bold">
              <CheckCircle2 className="h-4 w-4" /> Source Successfully Registered & Compiled to IPIR
            </div>
            <div className="font-mono text-slate-300 space-y-1">
              <div>Source ID: <span className="text-sky-300">{registeredSource.source_id}</span></div>
              <div>Source Format: <span className="text-white">{registeredSource.format}</span></div>
              {compiledPackage && <div>IPIR Package Compiled: <span className="text-emerald-300 font-bold">AZ_HO3_2026_09</span></div>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
