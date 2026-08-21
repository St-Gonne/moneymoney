import React from 'react';
import { 
  TrendingUp, 
  ArrowUpRight, 
  ArrowDownRight, 
  Sparkles, 
  Globe, 
  Headphones, 
  PieChart as PieIcon, 
  ArrowRight
} from 'lucide-react';
import type { Portfolio, Asset } from '../types/portfolio';
import { formatINR, formatUSD, formatPercent, LIVE_USD_INR_RATE } from '../utils/formatters';
import { 
  ResponsiveContainer, 
  PieChart, 
  Pie, 
  Cell, 
  Tooltip as RechartsTooltip 
} from 'recharts';

interface DashboardViewProps {
  portfolio: Portfolio;
  onAskGemini: (question: string) => void;
  onNavigate: (screen: string) => void;
  onInspectAsset: (asset: Asset) => void;
}

const ASSET_COLORS: Record<string, string> = {
  US_EQUITY: '#60a5fa',      // Light Blue (Schwab)
  EQUITY: '#34d399',         // Emerald (Indian Stocks)
  MUTUAL_FUND: '#38bdf8',    // Cyan (Direct MFs)
  FIXED_DEPOSIT: '#fbbf24',  // Amber (FDs/SCSS)
  SGB: '#f59e0b',            // Gold
  GOLD_PHYSICAL: '#eab308',  // Yellow
  PPF: '#a78bfa',            // Purple
  EPF: '#c084fc',            // Violet
  NPS: '#f472b6',            // Pink
};

const ASSET_NAMES: Record<string, string> = {
  US_EQUITY: 'US Equities (Charles Schwab)',
  EQUITY: 'Indian Equities (Zerodha/HDFC)',
  MUTUAL_FUND: 'Direct Mutual Funds (CAMS)',
  FIXED_DEPOSIT: 'Fixed Income & Term Deposits',
  SGB: 'Sovereign Gold Bonds',
  GOLD_PHYSICAL: 'Physical Hallmark Gold',
  PPF: 'Public Provident Fund (PPF)',
  EPF: 'Employee Provident Fund (EPFO)',
  NPS: 'National Pension Scheme (NPS)',
};

export const DashboardView: React.FC<DashboardViewProps> = ({
  portfolio,
  onAskGemini,
  onNavigate,
  onInspectAsset
}) => {
  // Aggregate allocation by asset class
  const allocationMap = portfolio.assets.reduce((acc, asset) => {
    const valINR = asset.currency === 'USD' ? asset.currentValue * LIVE_USD_INR_RATE : asset.currentValue;
    acc[asset.assetType] = (acc[asset.assetType] || 0) + valINR;
    return acc;
  }, {} as Record<string, number>);

  const allocationData = Object.entries(allocationMap).map(([type, value]) => ({
    name: ASSET_NAMES[type] || type,
    type,
    value,
    percent: portfolio.currentValueINR > 0 ? (value / portfolio.currentValueINR) * 100 : 0
  })).sort((a, b) => b.value - a.value);

  // Liquid capital calculation
  const liquidCapital = portfolio.assets
    .filter(a => a.assetType === 'EQUITY' || a.assetType === 'MUTUAL_FUND' || a.assetType === 'US_EQUITY' || a.assetType === 'FIXED_DEPOSIT')
    .reduce((sum, a) => sum + (a.currency === 'USD' ? a.currentValue * LIVE_USD_INR_RATE : a.currentValue), 0);

  const liquidPct = portfolio.currentValueINR > 0 ? (liquidCapital / portfolio.currentValueINR) * 100 : 0;

  // Top Holdings
  const topHoldings = [...portfolio.assets].sort((a, b) => b.currentValue - a.currentValue).slice(0, 5);

  return (
    <div id="app-main-view" className="space-y-5">
      
      {/* Top Banner with Quick Actions & Dad's Mode Prompt */}
      <div className="card flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="badge text-[11px] font-mono uppercase bg-zinc-800 text-zinc-300">
              {portfolio.entityType.replace('_', ' ')}
            </span>
            <span className="text-xs text-zinc-500 font-mono">
              PAN: {portfolio.pan}
            </span>
          </div>
          <h1 className="text-2xl font-extrabold text-zinc-100 tracking-tight">
            {portfolio.name}
          </h1>
          <p className="text-xs text-zinc-400">
            Multi-asset family vault • Domestic & US assets unified at reference rate <span className="font-mono text-blue-400">₹{LIVE_USD_INR_RATE}</span>
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => onNavigate('father-mode')}
            className="btn btn-outline border-yellow-500/40 text-yellow-400 hover:bg-yellow-500/10 font-bold"
          >
            <Headphones className="w-4 h-4 text-yellow-400" />
            <span>Dad's Voice Mode</span>
          </button>

          <button
            onClick={() => onAskGemini(`Provide a full macro summary of ${portfolio.name}, including asset allocation and US stock weighting.`)}
            className="btn btn-primary"
          >
            <Sparkles className="w-4 h-4 text-blue-600" />
            <span>AI Macro Summary</span>
          </button>
        </div>
      </div>

      {/* Primary Key Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
        
        {/* Total Net Worth */}
        <div className="card-raised">
          <span className="text-xs font-bold text-zinc-400 uppercase tracking-wider block mb-1">
            Consolidated Net Worth
          </span>
          <div className="text-2xl font-extrabold text-zinc-100 font-mono-num">
            {formatINR(portfolio.currentValueINR, false)}
          </div>
          <div className="text-xs text-zinc-500 font-mono mt-1">
            Invested: {formatINR(portfolio.totalInvestedINR, false)}
          </div>
        </div>

        {/* All-Time Gain */}
        <div className="card-raised">
          <span className="text-xs font-bold text-zinc-400 uppercase tracking-wider block mb-1">
            All-Time Profit
          </span>
          <div className={`text-2xl font-extrabold font-mono-num ${portfolio.totalGainINR >= 0 ? 'text-[var(--color-gain)]' : 'text-[var(--color-loss)]'}`}>
            {formatINR(portfolio.totalGainINR, false)}
          </div>
          <div className="flex items-center gap-1 text-xs font-bold mt-1">
            <span className={`badge ${portfolio.totalGainINR >= 0 ? 'badge-gain' : 'badge-loss'}`}>
              {portfolio.totalGainINR >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
              {formatPercent(portfolio.totalGainPct)}
            </span>
          </div>
        </div>

        {/* Annualized XIRR */}
        <div className="card-raised">
          <span className="text-xs font-bold text-zinc-400 uppercase tracking-wider block mb-1">
            Portfolio XIRR
          </span>
          <div className="text-2xl font-extrabold text-yellow-400 font-mono-num">
            {portfolio.xirr.toFixed(2)}%
          </div>
          <div className="text-xs text-zinc-500 mt-1">
            Hybrid Bisection/Newton rate
          </div>
        </div>

        {/* US Holdings (Charles Schwab) */}
        <div className="card-raised">
          <span className="text-xs font-bold text-blue-400 uppercase tracking-wider flex items-center gap-1 mb-1">
            <Globe className="w-3.5 h-3.5" />
            <span>US Equities (Schwab)</span>
          </span>
          <div className="text-2xl font-extrabold text-blue-300 font-mono-num">
            {formatUSD(portfolio.usHoldingsValueUSD, false)}
          </div>
          <div className="text-xs text-zinc-500 font-mono mt-1">
            ≈ {formatINR(portfolio.usHoldingsValueUSD * LIVE_USD_INR_RATE, false)}
          </div>
        </div>

        {/* Liquid vs Locked Capital */}
        <div className="card-raised">
          <span className="text-xs font-bold text-zinc-400 uppercase tracking-wider block mb-1">
            Liquid Capital
          </span>
          <div className="text-2xl font-extrabold text-zinc-100 font-mono-num">
            {formatINR(liquidCapital, false)}
          </div>
          <div className="text-xs text-zinc-500 mt-1 font-mono">
            {liquidPct.toFixed(0)}% accessible liquidity
          </div>
        </div>

      </div>

      {/* If Vault is Empty (Wiped State) */}
      {portfolio.assets.length === 0 && (
        <div className="card p-8 border-2 border-dashed border-zinc-700 text-center space-y-4">
          <div className="w-16 h-16 rounded-full bg-blue-950/40 border border-blue-800/40 text-blue-400 flex items-center justify-center mx-auto text-2xl">
            📥
          </div>
          <div className="max-w-md mx-auto space-y-1.5">
            <h2 className="text-lg font-bold text-white">
              Vault Clean & Ready for Real Data
            </h2>
            <p className="text-xs text-zinc-400 leading-relaxed">
              No financial statements have been imported yet for <strong>{portfolio.ownerName}</strong>. Drop your CAMS/KFintech CAS PDF, Zerodha Tradebook, or Schwab CSV to populate your real portfolio.
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <button
              onClick={() => onNavigate('importer')}
              className="btn btn-primary px-5 py-2.5 text-xs font-extrabold"
            >
              <span>📥 Import Financial Statement</span>
            </button>
          </div>
        </div>
      )}

      {/* Allocation & Top Assets Grid (Visible when assets exist) */}
      {portfolio.assets.length > 0 && (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        
        {/* Allocation Donut & Legend */}
        <div className="card lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-[#27272a]">
            <div>
              <h2 className="text-base font-bold text-zinc-100 flex items-center gap-2">
                <PieIcon className="w-4 h-4 text-blue-400" />
                <span>Multi-Asset Allocation Architecture</span>
              </h2>
              <p className="text-xs text-zinc-400">
                Diversification across US Equities, Indian Equities, Mutual Funds, Fixed Deposits, and SGBs
              </p>
            </div>
            <button
              onClick={() => onNavigate('holdings')}
              className="text-xs font-bold text-blue-400 hover:text-blue-300 flex items-center gap-1"
            >
              <span>View Ledger</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 items-center gap-6">
            <div className="h-56 w-full relative flex items-center justify-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={allocationData}
                    cx="50%"
                    cy="50%"
                    innerRadius={58}
                    outerRadius={88}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {allocationData.map((entry) => (
                      <Cell key={entry.type} fill={ASSET_COLORS[entry.type] || '#71717a'} />
                    ))}
                  </Pie>
                  <RechartsTooltip 
                    formatter={(val: any) => [formatINR(Number(val)), 'Valuation (INR)']}
                    contentStyle={{ backgroundColor: '#121215', borderColor: '#27272a', borderRadius: '8px', color: '#fff', fontSize: '12px' }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute flex flex-col items-center justify-center pointer-events-none text-center">
                <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Asset Mix</span>
                <span className="text-sm font-extrabold text-zinc-100 font-mono-num">{allocationData.length} Classes</span>
              </div>
            </div>

            {/* Allocation Progress Bars */}
            <div className="space-y-2.5">
              {allocationData.map((item) => (
                <div key={item.type}>
                  <div className="flex justify-between text-xs font-bold mb-1">
                    <span className="text-zinc-200 flex items-center gap-1.5">
                      <span 
                        className="w-2 h-2 rounded-full inline-block" 
                        style={{ backgroundColor: ASSET_COLORS[item.type] || '#71717a' }}
                      />
                      {item.name}
                    </span>
                    <span className="font-mono-num text-zinc-400">
                      {formatINR(item.value, false)} ({item.percent.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="w-full bg-zinc-800/60 rounded-full h-1.5 overflow-hidden">
                    <div 
                      className="h-1.5 rounded-full transition-all duration-500" 
                      style={{ 
                        width: `${item.percent}%`,
                        backgroundColor: ASSET_COLORS[item.type] || '#71717a' 
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Top Asset Positions */}
        <div className="card space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-zinc-800">
            <h2 className="text-sm font-bold text-zinc-100 flex items-center gap-1.5">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              <span>Top Portfolio Positions</span>
            </h2>
            <span className="text-xs font-mono text-zinc-500">By Valuation</span>
          </div>

          <div className="space-y-2">
            {topHoldings.map((asset) => {
              const isUS = asset.currency === 'USD';
              const valINR = isUS ? asset.currentValue * LIVE_USD_INR_RATE : asset.currentValue;

              return (
                <div 
                  key={asset.id}
                  onClick={() => onInspectAsset(asset)}
                  className="p-2.5 rounded-lg bg-zinc-800/40 hover:bg-zinc-800/70 border border-zinc-800 flex items-center justify-between cursor-pointer transition-colors"
                >
                  <div>
                    <div className="text-xs font-bold text-zinc-200 flex items-center gap-1">
                      {asset.name}
                      {isUS && <span className="badge badge-us text-[9px] py-0 px-1 font-mono">US</span>}
                    </div>
                    <div className="text-[11px] font-mono text-zinc-500">
                      {asset.institution} • {asset.symbolOrCode}
                    </div>
                  </div>

                  <div className="text-right font-mono-num">
                    <div className="text-xs font-extrabold text-zinc-100">
                      {formatINR(valINR, false)}
                    </div>
                    <div className="text-[10px] font-bold text-[var(--color-gain)]">
                      +{formatPercent(asset.pnlPercentage)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

      </div>
      )}

    </div>
  );
};
