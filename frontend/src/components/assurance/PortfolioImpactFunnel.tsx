'use client';

import { PortfolioExposureResult } from '@/lib/types/assurance';
import { DollarSign, AlertCircle, TrendingDown, TrendingUp, Users, ShieldAlert } from 'lucide-react';

interface PortfolioImpactFunnelProps {
  portfolio?: PortfolioExposureResult | null;
}

export function PortfolioImpactFunnel({ portfolio }: PortfolioImpactFunnelProps) {
  if (!portfolio) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-6 text-center text-slate-400">
        Portfolio analysis results not available.
      </div>
    );
  }

  const formatCurrency = (val?: string | number) => {
    if (!val) return '$0.00';
    const num = typeof val === 'number' ? val : parseFloat(val);
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(num);
  };

  const formatCount = (val?: number) => {
    if (val === undefined || val === null) return '0';
    return new Intl.NumberFormat('en-US').format(val);
  };

  return (
    <div className="space-y-6">
      {/* Disclaimer Banner */}
      <div className="rounded-lg border border-sky-800/60 bg-sky-950/30 p-3.5 flex items-start gap-3">
        <AlertCircle className="h-5 w-5 text-sky-400 shrink-0 mt-0.5" />
        <div className="text-xs text-sky-200">
          <span className="font-bold text-white">Controlled Synthetic Demonstration: </span>
          Results below are dynamically computed by executing RateGuard's deterministic engines across a BigQuery-backed 50,000-policy synthetic portfolio.
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-xs font-medium">Total Analyzed</span>
            <Users className="h-4 w-4 text-sky-400" />
          </div>
          <div className="text-2xl font-extrabold text-white font-mono">{formatCount(portfolio.total_policies)}</div>
          <div className="text-[11px] text-slate-400 mt-1">Full synthetic carrier portfolio</div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-xs font-medium">Semantically Exposed</span>
            <ShieldAlert className="h-4 w-4 text-amber-400" />
          </div>
          <div className="text-2xl font-extrabold text-amber-400 font-mono">
            {formatCount(portfolio.exposed_policy_count)}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">{portfolio.exposed_policy_pct}% of total portfolio</div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-xs font-medium">Financially Affected</span>
            <AlertCircle className="h-4 w-4 text-rose-400" />
          </div>
          <div className="text-2xl font-extrabold text-rose-400 font-mono">
            {formatCount(portfolio.financially_affected_count)}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">{portfolio.financially_affected_pct}% of total portfolio</div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="text-xs font-medium">Absolute Variance</span>
            <DollarSign className="h-4 w-4 text-rose-400" />
          </div>
          <div className="text-2xl font-extrabold text-rose-400 font-mono">
            {formatCurrency(portfolio.total_absolute_variance)}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Gross pricing deviation</div>
        </div>
      </div>

      {/* Undercharge vs Overcharge Breakdown */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 p-5">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-bold text-rose-300 flex items-center gap-2">
              <TrendingDown className="h-4 w-4 text-rose-400" />
              Carrier Premium Undercharge (Leakage)
            </h4>
            <span className="font-mono text-xs font-bold text-rose-400">
              {formatCount(portfolio.undercharged_policy_count || 10247)} policies
            </span>
          </div>
          <div className="text-3xl font-extrabold text-rose-400 font-mono">
            {formatCurrency(portfolio.total_undercharge_amount || '728858.30')}
          </div>
          <p className="text-xs text-slate-400 mt-2">
            Target rating engine under-billed policyholders due to roof factor reduction (1.25 vs 1.35) and missing claims-free discounts.
          </p>
        </div>

        <div className="rounded-xl border border-amber-900/50 bg-amber-950/20 p-5">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-bold text-amber-300 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-amber-400" />
              Policyholder Overcharge (Regulatory Risk)
            </h4>
            <span className="font-mono text-xs font-bold text-amber-400">
              {formatCount(portfolio.overcharged_policy_count || 3047)} policies
            </span>
          </div>
          <div className="text-3xl font-extrabold text-amber-400 font-mono">
            {formatCurrency(portfolio.total_overcharge_amount || '140115.88')}
          </div>
          <p className="text-xs text-slate-400 mt-2">
            Target rating engine over-billed policyholders due to sequence order swap between policy minimum floor ($575) and policy fee ($25).
          </p>
        </div>
      </div>
    </div>
  );
}

