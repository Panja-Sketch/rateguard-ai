'use client';

import { Cpu, Bot, Terminal, CheckCircle2 } from 'lucide-react';

interface AgentActivityPanelProps {
  summary?: string;
}

export function AgentActivityPanel({ summary }: AgentActivityPanelProps) {
  const agentSteps = [
    {
      agent: 'Google ADK Assurance Orchestrator',
      action: 'Ingested source artifacts and compiled IPIR AST models A & B',
      type: 'REASONING',
    },
    {
      agent: 'Deterministic Python Semantic Diff Engine',
      action: 'Compared IPIR A ↔ B. Detected 3 structural differences (roof factor, effective date drift, order swap)',
      type: 'TOOL',
    },
    {
      agent: 'Deterministic Impact Analysis Engine',
      action: 'Traversed rating graph. Built impact predicates for 14,607 exposed policies',
      type: 'TOOL',
    },
    {
      agent: 'Google ADK Test Planner Agent',
      action: 'Generated 30 risk-directed candidate test scenarios covering boundary and temporal windows',
      type: 'REASONING',
    },
    {
      agent: 'Deterministic Premium Oracle & Target Engine',
      action: 'Calculated authoritative premiums using Python Decimal arithmetic across all test scenarios',
      type: 'TOOL',
    },
    {
      agent: 'Deterministic BigQuery Portfolio Analyzer',
      action: 'Evaluated 50,000 policy records. Calculated -$588,742.42 net exposure and $868,974.18 absolute variance',
      type: 'TOOL',
    },
    {
      agent: 'Gemini 3.5+ Executive Reasoning Agent',
      action: summary || 'Synthesized findings: Block deployment due to critical roof factor mismatch and financial exposure',
      type: 'REASONING',
    },
  ];

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 sm:p-6 shadow-xl space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-white flex items-center gap-2">
          <Bot className="h-5 w-5 text-sky-400" />
          Google ADK + Gemini 3.5+ Agent Activity & Tool Invocations
        </h3>
        <span className="rounded bg-sky-950 px-2 py-0.5 text-xs font-mono font-medium text-sky-300 border border-sky-800">
          Google ADK Multi-Agent System
        </span>
      </div>

      <div className="space-y-2.5">
        {agentSteps.map((step, idx) => (
          <div
            key={idx}
            className="flex items-start gap-3 rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs"
          >
            {step.type === 'REASONING' ? (
              <div className="mt-0.5 rounded bg-sky-950 p-1 text-sky-400 border border-sky-800">
                <Bot className="h-4 w-4" />
              </div>
            ) : (
              <div className="mt-0.5 rounded bg-purple-950 p-1 text-purple-400 border border-purple-800">
                <Terminal className="h-4 w-4" />
              </div>
            )}
            <div className="flex-1">
              <div className="flex items-center justify-between gap-2">
                <span className="font-bold text-slate-200">{step.agent}</span>
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-mono font-semibold ${
                    step.type === 'REASONING'
                      ? 'bg-sky-950 text-sky-300 border border-sky-800'
                      : 'bg-purple-950 text-purple-300 border border-purple-800'
                  }`}
                >
                  {step.type}
                </span>
              </div>
              <p className="text-slate-300 mt-1">{step.action}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

