'use client';

import { WorkflowEvent } from '@/lib/types/assurance';
import { Bot, Terminal, Activity, Clock, CheckCircle2 } from 'lucide-react';

export interface AgentStep {
  step_index?: number;
  agent_name?: string;
  agent?: string;
  role?: string;
  action?: string;
  summary?: string;
  type?: string;
  output_snapshot?: Record<string, unknown>;
  timestamp?: string;
}

interface AgentActivityPanelProps {
  summary?: string;
  events?: WorkflowEvent[];
  agentSteps?: AgentStep[];
  isCompleted?: boolean;
}

export function AgentActivityPanel({
  summary,
  events = [],
  agentSteps = [],
  isCompleted = true,
}: AgentActivityPanelProps) {
  // Combine agent steps and workflow events into chronological list
  const combinedItems = [
    ...agentSteps.map((s, idx) => ({
      id: `step-${s.step_index || idx}`,
      title: s.agent_name || s.agent || 'AssuranceAgent',
      role: s.role || 'Specialized Agent',
      action: s.action || 'REASONING',
      description: s.summary || '',
      type: (s.type || (s.action?.includes('TOOL') || s.action?.includes('CALCULATE') || s.action?.includes('COMPARE') ? 'TOOL' : 'REASONING')).toUpperCase(),
      timestamp: s.timestamp,
    })),
    ...events.map((e, idx) => ({
      id: `evt-${e.event_id || idx}`,
      title: e.stage || 'WORKFLOW_MILESTONE',
      role: 'Orchestrator Stage',
      action: 'WORKFLOW_EVENT',
      description: e.message || '',
      type: 'WORKFLOW',
      timestamp: e.timestamp,
    })),
  ];

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-6 shadow-xl space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <Bot className="h-5 w-5 text-sky-400" />
            Google ADK + Gemini 3.7 Flash Agent Activity & Tool Invocations
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time execution trace of autonomous Google ADK agents and deterministic tools
          </p>
        </div>
        <span className="rounded bg-sky-950 px-2.5 py-1 text-xs font-mono font-medium text-sky-300 border border-sky-800">
          Gemini 3.7 Flash Runtime
        </span>
      </div>

      {combinedItems.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-slate-950 p-8 text-center text-xs text-slate-400">
          <Activity className="h-6 w-6 text-sky-400 animate-pulse mx-auto mb-2" />
          {isCompleted
            ? 'Workflow complete.'
            : 'Waiting for agent reasoning and tool invocations...'}
        </div>
      ) : (
        <div className="space-y-2.5">
          {combinedItems.map((item) => (
            <div
              key={item.id}
              className="flex items-start gap-3 rounded-lg border border-slate-800 bg-slate-950 p-3.5 text-xs transition-all hover:border-slate-700"
            >
              {item.type === 'REASONING' ? (
                <div className="mt-0.5 rounded bg-sky-950 p-1.5 text-sky-400 border border-sky-800">
                  <Bot className="h-4 w-4" />
                </div>
              ) : item.type === 'TOOL' ? (
                <div className="mt-0.5 rounded bg-purple-950 p-1.5 text-purple-400 border border-purple-800">
                  <Terminal className="h-4 w-4" />
                </div>
              ) : (
                <div className="mt-0.5 rounded bg-slate-800 p-1.5 text-slate-300 border border-slate-700">
                  <Activity className="h-4 w-4" />
                </div>
              )}

              <div className="flex-1 space-y-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white">{item.title}</span>
                    <span className="text-[11px] text-slate-400 font-sans">({item.role})</span>
                  </div>
                  <span
                    className={`rounded px-2 py-0.5 text-[10px] font-mono font-semibold border ${
                      item.type === 'REASONING'
                        ? 'bg-sky-950 text-sky-300 border-sky-800'
                        : item.type === 'TOOL'
                        ? 'bg-purple-950 text-purple-300 border-purple-800'
                        : 'bg-slate-800 text-slate-300 border-slate-700'
                    }`}
                  >
                    {item.type === 'REASONING'
                      ? 'AGENT REASONING'
                      : item.type === 'TOOL'
                      ? 'DETERMINISTIC TOOL'
                      : 'WORKFLOW EVENT'}
                  </span>
                </div>

                <p className="text-slate-200 text-xs leading-relaxed">{item.description}</p>

                {item.timestamp && (
                  <div className="flex items-center gap-1 text-[10px] font-mono text-slate-500">
                    <Clock className="h-3 w-3" />
                    <span>{new Date(item.timestamp).toLocaleTimeString()}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
