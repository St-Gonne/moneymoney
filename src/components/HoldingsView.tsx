import { useState, useMemo } from 'react';
import { 
  Search, 
  Layers, 
  Globe, 
  Building2,
  Zap,
  Award,
  ArrowUpRight,
  ArrowDownRight,
  ArrowLeftRight
} from 'lucide-react';
import type { Portfolio, Asset, AssetType, Currency } from '../types/portfolio.ts';
import { formatCurrency, formatPercent, formatINR, formatUSD, formatXIRR, LIVE_USD_INR_RATE } from '../utils/formatters.ts';
import { getCategoryAnalytics, getAssetXIRRInfo } from '../utils/analyticsEngine.ts';

interface HoldingsViewProps {
  portfolio: Portfolio;
  activeFilter?: string;
  onFilterChange: (filter: string) => void;
  onInspectAsset: (asset: Asset) => void;
}

const CATEGORY_TABS: { id: string; label: string; type?: AssetType }[] = [
  { id: 'ALL', label: 'All Holdings' },
  { id: 'EQUITY', label: 'Indian Equities (Zerodha/HDFC)', type: 'EQUITY' },
  { id: 'MUTUAL_FUND', label: 'Direct Mutual Funds (CAMS)', type: 'MUTUAL_FUND' },
  { id: 'US_EQUITY', label: 'US Equities (Charles Schwab)', type: 'US_EQUITY' },
  { id: 'FIXED_DEPOSIT', label: 'Fixed Deposits & SCSS', type: 'FIXED_DEPOSIT' },
  { id: 'SGB', label: 'SGB & Gold', type: 'SGB' },
  { id: 'PPF', label: 'PPF / EPF / NPS', type: 'PPF' },
];

/**
 * Clean Inline SVG Sparkline for Institutional Financial Data
 */
const Sparkline: React.FC<{ points: number[]; isGain: boolean }> = ({ points, isGain }) => {
  if (!points || points.length < 2) {
    return <span className="text-theme-muted font-mono text-xs">┈┈┈┈</span>;
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const width = 64;
  const height = 20;

  const pathD = points.map((p, i) => {
    const x = (i / (points.length - 1)) * width;
    const y = height - ((p - min) / range) * (height - 4) - 2;
    return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(' ');

  const strokeColor = isGain ? 'var(--color-gain)' : 'var(--color-loss)';

  return (
    <svg width={width} height={height} className="overflow-visible inline-block">
      <path
        d={pathD}
        fill="none"
        stroke={strokeColor}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

export const HoldingsView: React.FC<HoldingsViewProps> = ({
  portfolio,
  activeFilter = 'ALL',
  onFilterChange,
  onInspectAsset
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [currencyMode, setCurrencyMode] = useState<Currency>('INR');
  const [rowCurrencyOverride, setRowCurrencyOverride] = useState<Record<string, Currency>>({});

  const toggleRowCurrency = (assetId: string) => {
    setRowCurrencyOverride(prev => {
      const current = prev[assetId] || currencyMode;
      return {
        ...prev,
        [assetId]: current === 'INR' ? 'USD' : 'INR'
      };
    });
  };

  // Filter assets
  const filteredAssets = portfolio.assets.filter((asset) => {
    let matchesCategory = true;
    if (activeFilter === 'MUTUAL_FUND') matchesCategory = asset.assetType === 'MUTUAL_FUND';
    else if (activeFilter === 'EQUITY') matchesCategory = asset.assetType === 'EQUITY';
    else if (activeFilter === 'US_EQUITY') matchesCategory = asset.assetType === 'US_EQUITY';
    else if (activeFilter === 'FIXED_DEPOSIT') matchesCategory = asset.assetType === 'FIXED_DEPOSIT';
    else if (activeFilter === 'SGB') matchesCategory = asset.assetType === 'SGB' || asset.assetType === 'GOLD_PHYSICAL';
    else if (activeFilter === 'PPF') matchesCategory = asset.assetType === 'PPF' || asset.assetType === 'EPF' || asset.assetType === 'NPS';

    const matchesSearch = asset.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          asset.symbolOrCode.toLowerCase().includes(searchTerm.toLowerCase()) ||
                          asset.institution.toLowerCase().includes(searchTerm.toLowerCase());

    return matchesCategory && matchesSearch;
  });

  // Calculate dynamic category analytics
  const categoryAnalytics = useMemo(() => {
    return getCategoryAnalytics(portfolio.assets, activeFilter);
  }, [portfolio.assets, activeFilter]);

  return (
    <div id="app-main-view" className="space-y-4">
      
      {/* Header & Controls */}
      <div className="card space-y-3 p-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-extrabold text-theme-primary flex items-center gap-2 tracking-tight">
              <Layers className="w-5 h-5 text-blue-500 shrink-0" />
              <span>Institutional Holdings Ledger</span>
              <span className="badge font-mono text-xs ml-1">
                {filteredAssets.length} Active Positions
              </span>
            </h1>
            <p className="text-xs text-theme-secondary mt-0.5">
              Multi-asset portfolio for <strong className="text-theme-primary">{portfolio.name}</strong> • USD/INR Reference: <span className="font-mono font-bold text-blue-500">₹{LIVE_USD_INR_RATE}</span>
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto justify-between md:justify-end">
            {/* Currency Mode Selector */}
            <div className="flex items-center rounded-lg bg-theme-subtle p-0.5 border border-theme shrink-0">
              <button
                onClick={() => setCurrencyMode('INR')}
                className={`btn btn-sm ${currencyMode === 'INR' ? 'btn-primary font-bold shadow-sm' : 'btn-ghost text-theme-secondary'}`}
              >
                ₹ INR
              </button>
              <button
                onClick={() => setCurrencyMode('USD')}
                className={`btn btn-sm ${currencyMode === 'USD' ? 'btn-primary font-bold shadow-sm' : 'btn-ghost text-theme-secondary'}`}
              >
                $ USD
              </button>
            </div>

            {/* Search Input */}
            <div className="relative grow md:grow-0 md:w-80">
              <Search className="w-3.5 h-3.5 text-theme-muted absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Filter by scrip, institution, or ticker..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-theme-raised border border-theme rounded-lg pl-8 pr-3 py-1.5 text-xs font-medium text-theme-primary placeholder:text-theme-muted focus:outline-none focus:ring-2 focus:ring-[var(--focus-ring)] hover:border-theme-strong transition-all"
              />
            </div>
          </div>
        </div>

        {/* Filter Pills with Dynamic Asset Counts */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1" role="tablist">
          {CATEGORY_TABS.map((tab) => {
            const count = tab.id === 'ALL'
              ? portfolio.assets.length
              : tab.id === 'SGB'
              ? portfolio.assets.filter(a => a.assetType === 'SGB' || a.assetType === 'GOLD_PHYSICAL').length
              : tab.id === 'PPF'
              ? portfolio.assets.filter(a => a.assetType === 'PPF' || a.assetType === 'EPF' || a.assetType === 'NPS').length
              : portfolio.assets.filter(a => a.assetType === tab.type).length;

            return (
              <button
                key={tab.id}
                onClick={() => onFilterChange(tab.id)}
                className={`btn btn-sm transition-all whitespace-nowrap flex items-center gap-1.5 ${
                  activeFilter === tab.id
                    ? 'btn-primary font-extrabold shadow-sm'
                    : 'btn-secondary text-theme-secondary'
                }`}
              >
                <span>{tab.label}</span>
                <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono font-bold ${
                  activeFilter === tab.id ? 'bg-theme-surface text-theme-primary' : 'bg-theme-subtle text-theme-muted'
                }`}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Category Performance & XIRR Analytics Banner */}
      <div className="p-4 rounded-2xl bg-theme-surface border border-theme shadow-sm grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <span className="text-[11px] font-bold text-theme-muted uppercase tracking-wider block">
            {categoryAnalytics.categoryLabel}
          </span>
          <div className="text-xl font-extrabold text-theme-primary font-mono-num mt-0.5">
            {formatINR(categoryAnalytics.currentValueINR, false)}
          </div>
          <div className="text-[11px] text-theme-secondary mt-0.5">
            Cost: <span className="font-mono">{formatINR(categoryAnalytics.totalInvestedINR, false)}</span>
          </div>
        </div>

        <div>
          <span className="text-[11px] font-bold text-theme-muted uppercase tracking-wider block">
            Absolute Gain / Returns
          </span>
          <div className={`text-xl font-extrabold font-mono-num mt-0.5 flex items-center gap-1 ${
            categoryAnalytics.totalGainINR >= 0 ? 'text-[var(--color-gain)]' : 'text-[var(--color-loss)]'
          }`}>
            {categoryAnalytics.totalGainINR >= 0 ? <ArrowUpRight className="w-5 h-5 shrink-0" /> : <ArrowDownRight className="w-5 h-5 shrink-0" />}
            <span>{formatINR(categoryAnalytics.totalGainINR, false)}</span>
          </div>
          <div className={`text-[11px] font-bold ${
            categoryAnalytics.totalGainPct >= 0 ? 'text-[var(--color-gain)]' : 'text-[var(--color-loss)]'
          }`}>
            {formatPercent(categoryAnalytics.totalGainPct)} Absolute Profit
          </div>
        </div>

        <div className="p-3 rounded-xl bg-blue-600/10 border border-blue-500/25">
          <div className="flex items-center justify-between gap-1">
            <span className="text-[11px] font-extrabold uppercase tracking-wider text-blue-400 flex items-center gap-1">
              <Zap className="w-3.5 h-3.5 text-yellow-400" />
              <span>Category XIRR</span>
            </span>
            <span className="text-[10px] font-mono text-blue-400 font-bold">Annualized</span>
          </div>
          <div className="text-xl font-black text-blue-400 font-mono-num mt-0.5">
            {formatXIRR(categoryAnalytics.xirr)} <span className="text-xs font-medium text-blue-300">p.a.</span>
          </div>
          <div className="text-[10px] text-theme-muted mt-0.5 truncate">
            Exact cashflow internal rate of return
          </div>
        </div>

        {categoryAnalytics.topAsset ? (
          <div className="p-3 rounded-xl bg-theme-subtle border border-theme flex flex-col justify-between">
            <div className="flex items-center gap-1.5 text-xs text-theme-muted font-bold">
              <Award className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span className="truncate">Top Performer</span>
            </div>
            <div className="font-extrabold text-xs text-theme-primary truncate mt-0.5">
              {categoryAnalytics.topAsset.name}
            </div>
            <div className="text-[11px] font-mono font-bold text-[var(--color-gain)] flex items-center justify-between">
              <span>{formatPercent(categoryAnalytics.topAsset.gainPct)}</span>
              {categoryAnalytics.topAsset.xirr !== undefined && categoryAnalytics.topAsset.xirr !== 0 && (
                <span className="text-blue-400">⚡ {formatXIRR(categoryAnalytics.topAsset.xirr)} XIRR</span>
              )}
            </div>
          </div>
        ) : (
          <div className="p-3 rounded-xl bg-theme-subtle border border-theme flex items-center justify-center text-xs text-theme-muted font-mono">
            {categoryAnalytics.assetCount} Asset Positions
          </div>
        )}
      </div>

      {/* High-Density Ledger Table */}
      <div className="card p-0 overflow-hidden border border-theme shadow-xl">
        <div className="overflow-x-auto">
          <table className="ledger-table">
            <thead>
              <tr>
                <th className="text-left">Asset / Holding</th>
                <th className="text-left">Institution</th>
                <th className="text-right">Quantity</th>
                <th className="text-right">Avg Price</th>
                <th className="text-right">Current Price</th>
                <th className="text-right">Total Invested</th>
                <th className="text-right">Current Value</th>
                <th className="text-right">Profit / Loss & XIRR</th>
                <th className="text-center">7D Trend</th>
                <th className="text-center">Inspect</th>
              </tr>
            </thead>
            <tbody>
              {filteredAssets.length === 0 && (
                <tr>
                  <td colSpan={10} className="p-8 text-center text-xs text-theme-muted font-mono">
                    No holdings found in this category. Click <strong>Import</strong> in the top navbar to upload statements.
                  </td>
                </tr>
              )}
              {filteredAssets.map((asset) => {
                const isGain = asset.unrealizedPnl >= 0;
                const isUS = asset.currency === 'USD';
                const xirrInfo = getAssetXIRRInfo(asset);
                const rowCurrency = rowCurrencyOverride[asset.id] || currencyMode;
                const isRowUSD = rowCurrency === 'USD';

                // Display conversion based on effective row currency
                const valInUSD = isUS ? asset.currentValue : asset.currentValue / LIVE_USD_INR_RATE;
                const valInINR = isUS ? asset.currentValue * LIVE_USD_INR_RATE : asset.currentValue;
                const displayValuation = isRowUSD ? valInUSD : valInINR;
                const altValuationStr = isRowUSD ? formatINR(valInINR, false) : formatUSD(valInUSD, false);

                const invInUSD = isUS ? asset.totalInvested : asset.totalInvested / LIVE_USD_INR_RATE;
                const invInINR = isUS ? asset.totalInvested * LIVE_USD_INR_RATE : asset.totalInvested;
                const displayInvested = isRowUSD ? invInUSD : invInINR;

                const priceInUSD = isUS ? asset.currentPrice : asset.currentPrice / LIVE_USD_INR_RATE;
                const priceInINR = isUS ? asset.currentPrice * LIVE_USD_INR_RATE : asset.currentPrice;
                const displayPrice = isRowUSD ? priceInUSD : priceInINR;

                const avgPriceInUSD = isUS ? asset.avgBuyPrice : asset.avgBuyPrice / LIVE_USD_INR_RATE;
                const avgPriceInINR = isUS ? asset.avgBuyPrice * LIVE_USD_INR_RATE : asset.avgBuyPrice;
                const displayAvgPrice = isRowUSD ? avgPriceInUSD : avgPriceInINR;

                const pnlInUSD = isUS ? asset.unrealizedPnl : asset.unrealizedPnl / LIVE_USD_INR_RATE;
                const pnlInINR = isUS ? asset.unrealizedPnl * LIVE_USD_INR_RATE : asset.unrealizedPnl;
                const displayPnl = isRowUSD ? pnlInUSD : pnlInINR;

                return (
                  <tr 
                    key={asset.id} 
                    onClick={() => onInspectAsset(asset)}
                    className="ledger-row"
                  >
                    {/* Asset Name & Badge */}
                    <td>
                      <div className="font-bold text-theme-primary flex items-center gap-1.5">
                        <span>{asset.name}</span>
                        {isUS && (
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleRowCurrency(asset.id);
                            }}
                            className="badge badge-us text-[10px] cursor-pointer hover:opacity-80 transition-opacity flex items-center gap-1"
                            title="Toggle display between USD and INR"
                          >
                            <span>{isRowUSD ? '$ USD' : '₹ INR'}</span>
                            <ArrowLeftRight className="w-2.5 h-2.5 opacity-80" />
                          </button>
                        )}
                      </div>
                      <div className="text-[11px] font-mono text-theme-muted">
                        {asset.symbolOrCode}
                      </div>
                    </td>

                    {/* Institution */}
                    <td className="text-xs text-theme-secondary">
                      <span className="flex items-center gap-1">
                        {isUS ? <Globe className="w-3 h-3 text-blue-500 shrink-0" /> : <Building2 className="w-3 h-3 text-theme-muted shrink-0" />}
                        {asset.institution}
                      </span>
                    </td>

                    {/* Quantity */}
                    <td className="text-right font-mono-num text-xs text-theme-primary">
                      {asset.quantity.toLocaleString('en-IN')}
                    </td>

                    {/* Avg Price */}
                    <td className="text-right font-mono-num text-xs text-theme-secondary">
                      {formatCurrency(displayAvgPrice, rowCurrency)}
                    </td>

                    {/* Current Price */}
                    <td className="text-right font-mono-num text-xs font-bold text-theme-primary">
                      {formatCurrency(displayPrice, rowCurrency)}
                    </td>

                    {/* Total Invested */}
                    <td className="text-right font-mono-num text-xs text-theme-secondary">
                      {formatCurrency(displayInvested, rowCurrency, false)}
                    </td>

                    {/* Current Value */}
                    <td className="text-right font-mono-num text-xs">
                      <div className="font-extrabold text-theme-primary">
                        {formatCurrency(displayValuation, rowCurrency, false)}
                      </div>
                      {isUS && (
                        <div className="text-[10px] text-theme-muted font-normal mt-0.5">
                          ≈ {altValuationStr}
                        </div>
                      )}
                    </td>

                    {/* Unrealized PnL & XIRR */}
                    <td className="text-right font-mono-num">
                      <div className={`text-xs font-extrabold ${isGain ? 'text-[var(--color-gain)]' : 'text-[var(--color-loss)]'}`}>
                        {formatCurrency(displayPnl, rowCurrency, false)}
                      </div>
                      <div className="flex items-center justify-end gap-1.5 mt-0.5">
                        <span className={`text-[10px] font-bold ${isGain ? 'text-[var(--color-gain)]' : 'text-[var(--color-loss)]'}`}>
                          {formatPercent(asset.pnlPercentage)}
                        </span>
                        {xirrInfo.value !== 0 && (
                          <span 
                            className={`text-[9px] font-mono font-bold px-1.5 py-0.2 rounded border cursor-help ${
                              xirrInfo.isVerified 
                                ? (xirrInfo.value > 0 ? 'bg-blue-600/10 text-blue-400 border-blue-500/20' : 'bg-rose-600/10 text-rose-400 border-rose-500/20')
                                : 'bg-amber-500/10 text-amber-400 border-amber-500/30 border-dashed'
                            }`} 
                            title={xirrInfo.tooltip}
                          >
                            {xirrInfo.badgeLabel}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* 7D Trend Sparkline */}
                    <td className="text-center">
                      <Sparkline points={asset.sparkline} isGain={isGain} />
                    </td>

                    {/* Inspect Button */}
                    <td className="text-center" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => onInspectAsset(asset)}
                        className="btn btn-sm btn-outline text-theme-primary font-bold"
                        title="Inspect Tax Lots & Schedule FA"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Footer info */}
        <div className="p-3 border-t border-theme bg-theme-subtle flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs text-theme-muted font-mono">
          <span>Click any row to open the <strong>Tax Lot & Schedule FA Inspection Drawer</strong></span>
          <span>Press <strong>⌘K</strong> for instant search</span>
        </div>
      </div>

    </div>
  );
};
