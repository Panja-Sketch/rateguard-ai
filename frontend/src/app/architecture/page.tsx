import { Network, Database, Bot, Cpu, Lock, Server, ShieldCheck } from 'lucide-react';

export default function ArchitecturePage() {
  const techStack = [
    {
      title: 'Google ADK + Gemini 3.5+',
      category: 'Agent Framework',
      desc: 'Orchestrates multi-agent workflow, reasons across semantic diffs, generates test plans, and provides natural-language executive explanations.',
      icon: Bot,
      color: 'border-sky-500/50 bg-sky-950/30 text-sky-300',
    },
    {
      title: 'BigQuery (50K Portfolio)',
      category: 'Portfolio Analytics',
      desc: 'Stores 50,000 synthetic carrier policies and executes high-performance SQL exposure predicate filters for financial blast radius analysis.',
      icon: Database,
      color: 'border-blue-500/50 bg-blue-950/30 text-blue-300',
    },
    {
      title: 'Firestore (Native)',
      category: 'Workflow State & Audit',
      desc: 'Persists real-time assurance run states, workflow event logs, and audit evidence records in Native mode database (default).',
      icon: Server,
      color: 'border-purple-500/50 bg-purple-950/30 text-purple-300',
    },
    {
      title: 'Cloud Storage (GCS)',
      category: 'Artifact Management',
      desc: 'Stores pricing source files, compiled IPIR AST models, semantic diff reports, and execution traces in gs://rateguard-ai-artifacts.',
      icon: Database,
      color: 'border-amber-500/50 bg-amber-950/30 text-amber-300',
    },
    {
      title: 'Pub/Sub Worker Queue',
      category: 'Async Queue',
      desc: 'Delivers asynchronous assurance jobs via authenticated push subscription to Cloud Run worker endpoints for background execution.',
      icon: Cpu,
      color: 'border-emerald-500/50 bg-emerald-950/30 text-emerald-300',
    },
    {
      title: 'Cloud Run Runtime',
      category: 'Serverless Compute',
      desc: 'Hosts rateguard-api, rateguard-web, and worker runtimes in us-central1 with service-account least-privilege security.',
      icon: ShieldCheck,
      color: 'border-rose-500/50 bg-rose-950/30 text-rose-300',
    },
  ];

  return (
    <div className="space-y-8 max-w-5xl mx-auto">
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-white flex items-center gap-2">
          <Network className="h-7 w-7 text-sky-400" /> RateGuard System Architecture
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          Combining deterministic software calculation with agentic AI orchestration on Google Cloud.
        </p>
      </div>

      {/* Core Principle Alert */}
      <div className="rounded-xl border border-sky-800 bg-sky-950/40 p-4 space-y-2">
        <div className="flex items-center gap-2 font-bold text-sky-300 text-sm">
          <Lock className="h-4 w-4" /> Core Non-Negotiable Architecture Principle
        </div>
        <p className="text-xs text-sky-100 leading-relaxed">
          Gemini and Google ADK orchestrate multi-agent workflows, reason over semantic AST diffs, and generate executive summaries. All monetary arithmetic, rate table lookups, pricing graph evaluation, test execution, and financial blast radius exposure calculations are executed exclusively by deterministic Python code using Python <code className="font-mono text-white font-bold">Decimal</code>.
        </p>
      </div>

      {/* Tech Stack Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {techStack.map((tech, idx) => {
          const Icon = tech.icon;
          return (
            <div key={idx} className={`rounded-xl border p-4 shadow-lg space-y-2 ${tech.color}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-bold text-white text-sm">
                  <Icon className="h-5 w-5" />
                  {tech.title}
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900/80 border border-slate-700">
                  {tech.category}
                </span>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">{tech.desc}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

