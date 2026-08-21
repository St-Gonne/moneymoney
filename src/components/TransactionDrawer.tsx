import { 
  X, 
  Sparkles, 
  Building2, 
  Globe, 
  Layers,
  Zap,
  TrendingUp,
  ArrowDownLeft,
  ArrowUpRight
} from 'lucide-react';
import type { Asset } from '../types/portfolio.ts';
import { formatCurrency, formatPercent, formatINR, LIVE_USD_INR_RATE } from '../utils/formatters.ts';
import { getAssetXIRRInfo, getAssetCashflows } from '../utils/analyticsEngine.ts';

interface TransactionDrawerProps {
  asset: Asset | null;
  onClose: () => void;
  onAskGemini: (question: string) => void;
}

export const TransactionDrawer: React.FC<TransactionDrawerProps> = ({
  asset,
  onClose,
  onAskGemini
}) => {
  if (!asset) return null;

  const isUS = asset.currency === 'USD';
  const convertedCurrentValueINR = isUS ? asset.currentValue * LIVE_USD_INR_RATE : asset.currentValue;
  const xirrInfo = getAssetXIRRInfo(asset);
  const cashflows = getAssetCashflows(asset);

  return (
    <div className="fixed inset-0 z-50 overflow-hidden modal-backdrop animate-fade-in flex justify-end">
      <div 
        className="w-full max-w-xl bg-theme-surface border-l border-theme h-full shadow-2xl overflow-y-auto drawer-animate flex flex-col justify-between"
        onClick={e => e.stopPropagation()}
      >
        {/* Drawer Header */}
        <div>
          <div className="p-6 border-b border-theme bg-theme-subtle flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <span className={`badge ${isUS ? 'badge-us' : 'badge'}`}>
                  {isUS ? <Globe className="w-3 h-3 text-blue-500" /> : <Building2 className="w-3 h-3 text-theme-muted" />}
                  {asset.institution}
                </span>
                <span className="text-xs font-mono text-theme-secondary">
                  {asset.symbolOrCode}
                </span>
                {asset.isin && (
                  <span className="text-xs font-mono text-theme-muted">
                    ISIN: {asset.isin}
                  </span>
                )}
              </div>
              <h2 className="text-2xl font-extrabold text-theme-primary tracking-tight">
                {asset.name}
              </h2>
            </div>

            <button
              onClick={onClose}
              className="btn btn-sm btn-ghost p-2 rounded-lg text-theme-secondary hover:text-theme-primary"
              aria-label="Close drawer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Key Holdings Metrics */}
          <div className="p-6 space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div className="p-3.5 rounded-lg bg-theme-raised border border-theme">
                <span className="text-xs font-bold text-theme-muted uppercase block mb-1">
                  Current Valuation
                </span>
                <div className="text-xl font-extrabold text-theme-primary font-mono-num">
                  {formatCurrency(asset.currentValue, asset.currency)}
                </div>
                {isUS && (
                  <div className="text-xs font-mono text-theme-muted mt-0.5">
                    ≈ {formatINR(convertedCurrentValueINR, false)} (@ ₹{LIVE_USD_INR_RATE})
                  </div>
                )}
              </div>

              <div className="p-3.5 rounded-lg bg-theme-raised border border-theme">
                <span className="text-xs font-bold text-theme-muted uppercase block mb-1">
                  Total Profit / Loss
                </span>
                <div className={`text-xl font-extrabold font-mono-num ${asset.unrealizedPnl >= 0 ? 'text-[var(--color-gain)]' : 'text-[var(--color-loss)]'}`}>
                  {formatCurrency(asset.unrealizedPnl, asset.currency)}
                </div>
                <div className={`text-xs font-bold ${asset.pnlPercentage >= 0 ? 'text-[var(--color-gain)]' : 'text-[var(--color-loss)]'}`}>
                  {formatPercent(asset.pnlPercentage)}
                </div>
              </div>
            </div>

            {/* Annualized XIRR Performance Banner */}
            <div className={`p-4 rounded-xl flex items-center justify-between border ${
              xirrInfo.isVerified 
                ? (xirrInfo.value >= 0 ? 'bg-blue-600/10 border-blue-500/30' : 'bg-rose-600/10 border-rose-500/30')
                : 'bg-amber-500/10 border-amber-500/30 border-dashed'
            }`}>
              <div>
                <span className={`text-xs font-extrabold uppercase tracking-wider flex items-center gap-1.5 ${
                  xirrInfo.isVerified 
                    ? (xirrInfo.value >= 0 ? 'text-blue-400' : 'text-rose-400')
                    : 'text-amber-400'
                }`}>
                  <Zap className={`w-4 h-4 ${xirrInfo.isVerified ? (xirrInfo.value >= 0 ? 'text-yellow-400' : 'text-rose-400') : 'text-amber-400'}`} />
                  <span>{xirrInfo.isVerified ? 'Annualized Compounded XIRR (Verified)' : 'Estimated Annualized CAGR (Provisional)*'}</span>
                </span>
                <p className="text-[11px] text-theme-secondary mt-0.5">
                  {xirrInfo.tooltip}
                </p>
              </div>
              <div className="text-right">
                <div className={`text-2xl font-black font-mono-num ${
                  xirrInfo.isVerified 
                    ? (xirrInfo.value >= 0 ? 'text-blue-400' : 'text-rose-400')
                    : 'text-amber-400'
                }`}>
                  {xirrInfo.formatted}
                </div>
                <span className="text-[10px] font-bold text-theme-muted uppercase">{xirrInfo.isVerified ? 'p.a. Compounded' : 'p.a. Baseline*'}</span>
              </div>
            </div>

            {/* Missing History Resolution Card (Rendered for Provisional Holdings) */}
            {xirrInfo.isEstimate && (
              <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/25 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-amber-400 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Estimated Baseline (Trade History Pending)</span>
                  </span>
                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold uppercase">
                    Provisional CAGR*
                  </span>
                </div>
                <p className="text-[11px] text-theme-secondary">
                  This position is using an estimated holding period baseline. Import your detailed CAMS transaction CAS or broker tradebook to unlock exact tax lot dates and verified XIRR.
                </p>
                <div className="flex items-center gap-2 pt-1">
                  <button
                    onClick={() => onAskGemini(`How do I fetch the detailed transaction history or contract notes for ${asset.name} (${asset.institution})?`)}
                    className="btn btn-sm text-amber-400 bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-[11px] font-bold flex items-center gap-1.5"
                  >
                    <Sparkles className="w-3 h-3 text-amber-400" />
                    <span>Ask Gemini to Reconcile</span>
                  </button>
                </div>
              </div>
            )}

            {/* Position Breakdown Table */}
            <div className="p-4 rounded-lg bg-theme-subtle border border-theme space-y-2.5 text-xs">
              <div className="flex justify-between">
                <span className="text-theme-secondary">Total Quantity Held:</span>
                <span className="font-mono-num font-bold text-theme-primary">{asset.quantity.toLocaleString('en-IN')} units</span>
              </div>
              <div className="flex justify-between">
                <span className="text-theme-secondary">Average Acquisition Cost:</span>
                <span className="font-mono-num font-bold text-theme-primary">{formatCurrency(asset.avgBuyPrice, asset.currency)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-theme-secondary">Total Capital Invested:</span>
                <span className="font-mono-num font-bold text-theme-primary">{formatCurrency(asset.totalInvested, asset.currency)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-theme-secondary">Current Market Price:</span>
                <span className="font-mono-num font-bold text-theme-primary">{formatCurrency(asset.currentPrice, asset.currency)}</span>
              </div>
              {asset.folioOrAccount && (
                <div className="flex justify-between">
                  <span className="text-theme-secondary">Account / Folio Reference:</span>
                  <span className="font-mono font-bold text-blue-500">{asset.folioOrAccount}</span>
                </div>
              )}
            </div>

            {/* Foreign Asset Schedule FA (Charles Schwab Specific) */}
            {asset.scheduleFA && (
              <div className="p-4 rounded-lg bg-theme-subtle border border-theme space-y-2 text-xs text-theme-secondary">
                <div className="flex items-center gap-1.5 font-bold text-blue-500">
                  <Globe className="w-4 h-4" />
                  <span>Indian ITR Schedule FA (Foreign Assets Compliance)</span>
                </div>
                <div className="space-y-1 pt-1 text-theme-secondary">
                  <div className="flex justify-between">
                    <span>Country / Institution:</span>
                    <span className="font-semibold text-theme-primary">{asset.scheduleFA.countryCode} • {asset.scheduleFA.entityName}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Initial Cost Basis:</span>
                    <span className="font-mono-num text-theme-primary">${asset.scheduleFA.initialInvestmentUSD.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Peak Value During FY:</span>
                    <span className="font-mono-num text-theme-primary">${asset.scheduleFA.peakValueUSD.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Gross US Dividends & 25% Tax Withheld:</span>
                    <span className="font-mono-num text-theme-primary">${asset.scheduleFA.grossDividendsUSD} (${asset.scheduleFA.taxWithheldUSD} IRS 1042-S)</span>
                  </div>
                </div>
              </div>
            )}

            {/* FIFO Tax Lots Inspection */}
            <div className="space-y-3">
              <h3 className="text-sm font-extrabold uppercase tracking-wider text-theme-muted flex items-center gap-2">
                <Layers className="w-4 h-4 text-emerald-400" />
                <span>FIFO Tax Lots & Holding Ledger</span>
              </h3>

              {asset.taxLots.length > 0 ? (
                <div className="space-y-2">
                  {asset.taxLots.map((lot) => (
                    <div 
                      key={lot.id} 
                      className="p-3 rounded-lg bg-theme-raised border border-theme space-y-1.5 text-xs font-mono"
                    >
                      <div className="flex justify-between font-bold text-theme-primary">
                        <span>Acquired: {lot.purchaseDate} ({lot.holdingDays} days)</span>
                        <span className={lot.isLongTerm ? 'text-emerald-400' : 'text-amber-400'}>
                          {lot.isLongTerm ? (isUS ? 'LTCG (>24m)' : 'LTCG (>12m)') : 'STCG'}
                        </span>
                      </div>
                      <div className="flex justify-between text-theme-secondary">
                        <span>Units: {lot.quantity.toLocaleString()} @ {formatCurrency(lot.costPerUnit, asset.currency)}</span>
                        <span>Gain: {formatCurrency(lot.unrealizedGain, asset.currency)}</span>
                      </div>
                      <div className="flex justify-between text-theme-muted pt-1 border-t border-theme">
                        <span>Tax Rate: {lot.taxRatePct}% (Finance Act 2024)</span>
                        <span>Est Tax: {formatCurrency(lot.estimatedTax, 'INR')}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-theme-muted italic">
                  Aggregated holding. Granular lot history synchronized from primary broker ledger.
                </p>
              )}
            </div>

            {/* Cashflow Stream Waterfall for XIRR */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-extrabold uppercase tracking-wider text-theme-muted flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-blue-400" />
                  <span>XIRR Cashflow Stream Waterfall</span>
                </h3>
                <span className="text-[10px] font-mono text-blue-400 font-bold">
                  {cashflows.length} Flow Events
                </span>
              </div>

              <div className="rounded-xl border border-theme bg-theme-raised overflow-hidden">
                <table className="w-full text-xs font-mono">
                  <thead>
                    <tr className="border-b border-theme bg-theme-subtle text-theme-muted text-[10px] uppercase">
                      <th className="p-2.5 text-left">Date</th>
                      <th className="p-2.5 text-left">Event Description</th>
                      <th className="p-2.5 text-right">Cashflow Amount</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-theme">
                    {cashflows.map((cf, idx) => {
                      const isOutflow = cf.amount < 0;
                      const isTerminal = idx === cashflows.length - 1;
                      return (
                        <tr key={idx} className="hover:bg-theme-hover transition-colors">
                          <td className="p-2.5 text-theme-primary font-bold">{cf.date}</td>
                          <td className="p-2.5 text-theme-secondary flex items-center gap-1.5">
                            {isTerminal ? (
                              <span className="text-blue-400 flex items-center gap-1">
                                <ArrowUpRight className="w-3.5 h-3.5" />
                                <span>Current Valuation</span>
                              </span>
                            ) : isOutflow ? (
                              <span className="text-amber-400 flex items-center gap-1">
                                <ArrowDownLeft className="w-3.5 h-3.5" />
                                <span>Capital Investment</span>
                              </span>
                            ) : (
                              <span className="text-emerald-400 flex items-center gap-1">
                                <ArrowUpRight className="w-3.5 h-3.5" />
                                <span>Dividend / Inflow</span>
                              </span>
                            )}
                          </td>
                          <td className={`p-2.5 text-right font-bold ${isOutflow ? 'text-amber-400' : 'text-emerald-400'}`}>
                            {formatINR(cf.amount, false)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        {/* Drawer Action Footer */}
        <div className="p-6 border-t border-theme bg-theme-subtle flex gap-3">
          <button
            onClick={() => onAskGemini(`Give me a detailed portfolio and tax breakdown for my holding in ${asset.name} (${asset.symbolOrCode}) held via ${asset.institution}.`)}
            className="w-full btn btn-md btn-primary py-2.5 text-xs font-bold"
          >
            <Sparkles className="w-4 h-4 text-blue-500" />
            <span>Ask Gemini to Analyze Holding</span>
          </button>
        </div>

      </div>
    </div>
  );
};
