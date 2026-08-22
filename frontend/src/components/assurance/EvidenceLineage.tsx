'use client';

import { EvidenceRecord } from '@/lib/types/assurance';
import { Database, FileText, CheckCircle2, Clock } from 'lucide-react';

interface EvidenceLineageProps {
  evidence: EvidenceRecord[];
}

export function EvidenceLineage({ evidence }: EvidenceLineageProps) {
  if (!evidence || evidence.length === 0) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-6 text-center text-slate-400">
        No audit evidence records persisted for this run.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-white flex items-center gap-2">
          <Database className="h-5 w-5 text-sky-400" />
          Evidence Lineage & Audit Trail ({evidence.length} Artifacts)
        </h3>
        <span className="text-xs text-slate-400">Persisted in Firestore & Cloud Storage</span>
      </div>

      <div className="space-y-3">
        {evidence.map((ev, idx) => (
          <div
            key={ev.evidence_id || idx}
            className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-900/80 p-4 transition-all hover:border-slate-700"
          >
            <div className="flex items-start gap-3">
              <div className="mt-0.5 rounded bg-sky-950 p-1.5 text-sky-400 border border-sky-800">
                <FileText className="h-4 w-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-sky-300">{ev.stage}</span>
                  <span className="text-[10px] text-slate-500 font-mono">({ev.evidence_type})</span>
                </div>
                <p className="text-xs text-slate-200 mt-1">{ev.summary}</p>
                {ev.storage_uri && (
                  <div className="text-[11px] font-mono text-slate-400 mt-1">
                    URI: <span className="text-slate-300">{ev.storage_uri}</span>
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center gap-1.5 text-[11px] text-slate-400 font-mono self-end sm:self-center">
              <Clock className="h-3.5 w-3.5 text-slate-500" />
              <span>{ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : 'Just now'}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

