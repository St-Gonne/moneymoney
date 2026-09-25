import { useEffect, useMemo, useState } from 'react';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { PerformanceResult, ValuationRangePoint, ValuationRangeResult, ValuationResult } from '../types/valuation.ts';
import { periodBounds, projectPortfolioVisuals, trustedXirrForAccount, type PerformanceRequestContext, type VisualFrequency, type VisualHoldingMetadata, type VisualPeriod } from '../utils/portfolioVisuals.ts';

type WorkspaceNavigate = (destination: 'holdings' | 'accounts') => void;

export type PortfolioVisualsPanelProps = {
  portfolioId: string;
  historyValuations: readonly ValuationResult[];
  rangeResult?: ValuationRangeResult | null;
  rangePoints?: readonly ValuationRangePoint[];
  rangeState?: 'idle' | 'loading' | 'ready' | 'error' | 'limit';
  onRangeChange?: (request: { start?: string; end?: string; granularity: VisualFrequency }) => void;
  valuation: ValuationResult | null;
  performance: PerformanceResult | null;
  performanceContext: PerformanceRequestContext | null;
  performanceValuation: ValuationResult | null;
  performanceValuationContext: PerformanceRequestContext | null;
  holdings: readonly VisualHoldingMetadata[];
  accountFilter: string;
  currency: string;
  selectedAccountCurrency: string;
  asOf: string;
  historyComplete: boolean;
  accountLabels: ReadonlyMap<string, string>;
  isPrivacyShieldActive: boolean;
  formatMoney: (value: number, currency: string | null | undefined) => string;
  formatDate: (value: string) => string;
  formatPercent: (value: number | string | null | undefined) => string;
  onNavigateWorkspace?: WorkspaceNavigate;
};

const periods: Array<{ value: VisualPeriod; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'today', label: 'Today' },
  { value: 'last-week', label: 'Last week' },
  { value: 'last-month', label: 'Last month' },
  { value: 'ytd', label: 'YTD' },
  { value: 'current-fy', label: 'Current FY' },
  { value: 'previous-fy', label: 'Previous FY' },
  { value: 'custom', label: 'Custom' },
];

function axisDate(value: string): string {
  return new Intl.DateTimeFormat('en-IN', { day: '2-digit', month: 'short', timeZone: 'UTC' }).format(new Date(`${value}T00:00:00Z`));
}

export function PortfolioVisualsPanel(props: PortfolioVisualsPanelProps) {
  return <PortfolioVisualsContent {...props} />;
}

export type PerformanceXirrCardProps = {
  portfolioId: string;
  accountId: string;
  accountCurrency: string;
  asOf: string;
  performance: PerformanceResult | null;
  performanceContext: PerformanceRequestContext | null;
  performanceValuation: ValuationResult | null;
  performanceValuationContext: PerformanceRequestContext | null;
  isPrivacyShieldActive: boolean;
  formatDate: (value: string) => string;
  formatPercent: (value: number | string | null | undefined) => string;
};

/** Used on both routes so XIRR has one request-context and digest contract. */
export function PerformanceXirrCard({ portfolioId, accountId, accountCurrency, asOf, performance, performanceContext, performanceValuation, performanceValuationContext, isPrivacyShieldActive, formatDate, formatPercent }: PerformanceXirrCardProps) {
  if (isPrivacyShieldActive) return <section id="performance-xirr" className="portfolio-visuals-xirr" aria-label="Since inception XIRR"><div><h2>Since inception XIRR</h2><p className="text-sm text-theme-secondary">Privacy Shield is on. Return values are hidden.</p></div></section>;
  const expectedContext = accountId && asOf ? { portfolioId, accountId, asOf } : null;
  const xirr = trustedXirrForAccount(performance, performanceContext, performanceValuation, performanceValuationContext, expectedContext, accountCurrency);
  return <section id="performance-xirr" className="portfolio-visuals-xirr" aria-labelledby="xirr-heading"><div><h2 id="xirr-heading">Since inception XIRR</h2><p className="text-sm text-theme-secondary">Annualised return, accounting for when money was added or withdrawn.</p></div>{xirr ? <strong>{formatPercent(xirr.valuePct)} <small>· Since inception · as of {formatDate(xirr.asOf)}</small></strong> : <p className="portfolio-visuals-empty">{accountId ? performance?.xirr.reason || 'XIRR is unavailable for this exact single-currency scope.' : 'Select a single-currency account for supported XIRR.'}</p>}</section>;
}

function PortfolioVisualsContent({ portfolioId, historyValuations, rangeResult, rangePoints, rangeState = 'idle', onRangeChange, valuation, performance, performanceContext, performanceValuation, performanceValuationContext, holdings, accountFilter, currency, selectedAccountCurrency, asOf, historyComplete, accountLabels, isPrivacyShieldActive, formatMoney, formatDate, formatPercent, onNavigateWorkspace }: PortfolioVisualsPanelProps) {
  const [period, setPeriod] = useState<VisualPeriod>('all');
  const [frequency, setFrequency] = useState<VisualFrequency>('daily');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const [appliedCustom, setAppliedCustom] = useState<{ start: string; end: string } | null>(null);

  const selectedBounds = useMemo(() => periodBounds(period, undefined, period === 'custom' ? appliedCustom?.start || '' : customStart, period === 'custom' ? appliedCustom?.end || '' : customEnd), [appliedCustom, customEnd, customStart, period]);
  const invalidCustomRange = period === 'custom' && (!selectedBounds.start || !selectedBounds.end || selectedBounds.start > selectedBounds.end);
  useEffect(() => {
    if (!onRangeChange || invalidCustomRange || (period === 'custom' && appliedCustom === null)) return;
    onRangeChange({ start: selectedBounds.start || undefined, end: selectedBounds.end || undefined, granularity: frequency });
  }, [appliedCustom, frequency, invalidCustomRange, onRangeChange, period, selectedBounds.end, selectedBounds.start]);
  const responseMatches = Boolean((period !== 'custom' || appliedCustom !== null) && rangeResult && rangeResult.scope.accountId === (accountFilter === 'all' ? null : accountFilter) && rangeResult.scope.currency === currency && rangeResult.range.start === (selectedBounds.start || null) && rangeResult.range.end === (selectedBounds.end || null) && rangeResult.range.granularity === frequency);
  const projection = useMemo(() => projectPortfolioVisuals({ portfolioId, historyValuations, rangePoints: responseMatches ? rangePoints : [], valuation, performance, performanceContext, performanceValuation, performanceValuationContext, holdings, accountFilter, currency, selectedAccountCurrency, asOf, historyComplete, accountLabels }), [accountFilter, accountLabels, asOf, currency, historyComplete, historyValuations, holdings, performance, performanceContext, performanceValuation, performanceValuationContext, portfolioId, rangePoints, responseMatches, selectedAccountCurrency, valuation]);
  const points = projection.trendPoints;
  const endpointChange = responseMatches && rangeResult?.first && rangeResult.last ? Number(rangeResult.last.calculatedValue) - Number(rangeResult.first.calculatedValue) : null;
  const chartData = points.map((point) => ({ ...point, dateLabel: axisDate(point.asOf) }));

  if (isPrivacyShieldActive) return <section id="portfolio-visuals" className="portfolio-visuals-panel card" aria-label="Portfolio visuals"><div className="portfolio-visuals-private" role="status"><strong>Privacy Shield is on.</strong><span>Trend, dated holdings, account allocation, and return values are hidden.</span></div></section>;

  return <section id="portfolio-visuals" className="portfolio-visuals-panel card" aria-labelledby="portfolio-visuals-heading">
    <div className="portfolio-visuals-heading">
      <div><p className="nsdl-section-eyebrow">Portfolio view</p><h2 id="portfolio-visuals-heading">Value trend and allocation</h2><p className="text-sm text-theme-secondary">Actual calculated dated values in {currency || 'the selected currency'}{asOf ? ` · current as of ${formatDate(asOf)}` : ''}. Statement-only values are excluded.</p></div>
      <span className="portfolio-visuals-status">{projection.todayMovementLabel}</span>
    </div>
    <div className="portfolio-visuals-controls" aria-label="Trend controls">
      <div className="portfolio-visuals-periods" role="group" aria-label="Chart period">{periods.map((item) => <button key={item.value} type="button" className={period === item.value ? 'is-active' : ''} aria-pressed={period === item.value} onClick={() => setPeriod(item.value)}>{item.label}</button>)}</div>
      <label>Chart frequency<select className="nsdl-control nsdl-input" value={frequency} onChange={(event) => setFrequency(event.target.value as VisualFrequency)}><option value="daily">Daily actual points</option><option value="monthly">Monthly latest point</option></select></label>
      <label>Calendar month<select className="nsdl-control nsdl-input" aria-label="Calendar month" value="" onChange={(event) => { const month = event.target.value; if (!month) return; const [year, number] = month.split('-').map(Number); const end = new Date(Date.UTC(year, number, 0)).toISOString().slice(0, 10); setCustomStart(`${month}-01`); setCustomEnd(end); setAppliedCustom({ start: `${month}-01`, end }); setPeriod('custom'); }}><option value="">Choose a calendar month</option>{Array.from({ length: 12 }, (_item, index) => `${(asOf || new Date().toISOString().slice(0, 4)).slice(0, 4)}-${String(index + 1).padStart(2, '0')}`).map((month) => <option key={month} value={month}>{new Intl.DateTimeFormat('en-IN', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${month}-01T00:00:00Z`))}</option>)}</select></label>
      {period === 'custom' && <div className="portfolio-visuals-custom-dates"><label>From<input className="nsdl-control nsdl-input" type="date" value={customStart} onChange={(event) => { setCustomStart(event.target.value); setAppliedCustom(null); }} /></label><label>To<input className="nsdl-control nsdl-input" type="date" value={customEnd} onChange={(event) => { setCustomEnd(event.target.value); setAppliedCustom(null); }} /></label><button type="button" className="nsdl-control nsdl-button nsdl-button-secondary" onClick={() => setAppliedCustom({ start: customStart, end: customEnd })}>Apply custom dates</button></div>}
    </div>
    {period !== 'all' && !invalidCustomRange && selectedBounds.start && selectedBounds.end && <p className="portfolio-visuals-range">Requested range: {formatDate(selectedBounds.start)} to {formatDate(selectedBounds.end)}{responseMatches && rangeResult?.first && rangeResult.last ? ` · actual endpoints ${formatDate(rangeResult.first.asOf)} to ${formatDate(rangeResult.last.asOf)}` : ''}.</p>}
    {invalidCustomRange && <p className="portfolio-visuals-empty" role="status">Choose both custom dates, with From on or before To.</p>}
    <p className="portfolio-visuals-note">Changes in value can include money added or withdrawn; this is not a return chart.</p>
    {endpointChange !== null && Number.isFinite(endpointChange) && rangeResult?.coverage.selectedObservedCount && rangeResult.coverage.selectedObservedCount >= 2 && <p className="portfolio-visuals-range">Selected-period value change: {formatMoney(endpointChange, currency)} from raw eligible endpoints.</p>}
    {!currency && <p className="portfolio-visuals-empty">Choose a currency to view a separated dated trend.</p>}
    {currency && rangeState === 'loading' && <p className="portfolio-visuals-empty" role="status">Updating this exact range…</p>}
    {currency && rangeState === 'limit' && <p className="portfolio-visuals-empty" role="status">This daily range has more than 1,000 actual points. Choose Monthly or a smaller period.</p>}
    {currency && rangeState === 'error' && <p className="portfolio-visuals-empty" role="alert">This dated range is unavailable. Current holdings remain available; choose another range or refresh.</p>}
    {currency && !historyComplete && rangeState !== 'loading' && rangeState !== 'error' && rangeState !== 'limit' && <p className="portfolio-visuals-empty">Complete dated observations are not available for this exact scope yet.</p>}
    {currency && historyComplete && !invalidCustomRange && !points.length && <p className="portfolio-visuals-empty">No actual dated observations are available for this period.</p>}
    {currency && historyComplete && points.length === 1 && <p className="portfolio-visuals-empty">One dated observation is available. A trend needs at least two.</p>}
    {currency && historyComplete && points.length > 0 && <>
      <div id="valuation-trend" className="portfolio-visuals-chart" aria-hidden="true"><ResponsiveContainer width="100%" height={260}><LineChart data={chartData.map((point) => ({ ...point, timestamp: Date.parse(`${point.asOf}T00:00:00Z`) }))} margin={{ top: 12, right: 18, left: 8, bottom: 8 }}><CartesianGrid strokeDasharray="2 4" vertical={false} /><XAxis dataKey="timestamp" type="number" domain={['dataMin', 'dataMax']} tickFormatter={(value) => axisDate(new Date(Number(value)).toISOString().slice(0, 10))} minTickGap={26} /><YAxis tickFormatter={(value) => formatMoney(Number(value), currency)} width={94} /><Tooltip labelFormatter={(value) => formatDate(new Date(Number(value)).toISOString().slice(0, 10))} formatter={(value) => formatMoney(Number(value), currency)} /><Line type="linear" dataKey="value" stroke="var(--private-accent)" strokeWidth={2.5} dot={{ r: 3 }} activeDot={{ r: 5 }} isAnimationActive={false} /></LineChart></ResponsiveContainer></div>
      <table className="portfolio-visuals-table"><caption>Actual dated portfolio values</caption><thead><tr><th scope="col">Date</th><th scope="col">Value</th><th scope="col">Source</th><th scope="col">Price date</th></tr></thead><tbody>{points.map((point) => <tr key={`${point.asOf}-${point.value}`}><th scope="row">{formatDate(point.asOf)}</th><td>{formatMoney(point.value, point.currency)}</td><td>{point.source}</td><td>{point.priceDate ? formatDate(point.priceDate) : 'Multiple eligible price dates'}</td></tr>)}</tbody></table>
    </>}
    <div className="portfolio-visuals-grid">
      <section id="top-holdings-chart" className="portfolio-visuals-subcard" aria-labelledby="top-dated-holdings-heading"><div className="portfolio-visuals-subheading"><h3 id="top-dated-holdings-heading">Top 5 dated holdings</h3><button type="button" className="nsdl-link-button" onClick={() => onNavigateWorkspace?.('holdings')}>View holdings</button></div>{projection.topHoldings.length ? <ol className="portfolio-visuals-bars">{projection.topHoldings.map((holding) => <li key={holding.holdingId}><span><strong>{holding.label}</strong><small>{holding.instrumentType} · {formatMoney(holding.value, holding.currency)} · {holding.source}{holding.priceDate ? ` · ${formatDate(holding.priceDate)}` : ''}</small></span><i style={{ width: `${(holding.value / Math.max(...projection.topHoldings.map((item) => item.value), 1)) * 100}%` }} /></li>)}</ol> : <p className="portfolio-visuals-empty">No eligible calculated holdings in this currency.</p>}</section>
      <section id="asset-allocation-chart" className="portfolio-visuals-subcard" aria-labelledby="allocation-heading"><div className="portfolio-visuals-subheading"><h3 id="allocation-heading">Allocation by account</h3><button type="button" className="nsdl-link-button" onClick={() => onNavigateWorkspace?.('accounts')}>View accounts</button></div>{projection.accountAllocation.length ? <ol className="portfolio-visuals-bars">{projection.accountAllocation.map((account) => <li key={account.accountId}><span><strong>{account.label}</strong><small>{formatMoney(account.value, account.currency)}</small></span><i style={{ width: `${(account.value / Math.max(...projection.accountAllocation.map((item) => item.value), 1)) * 100}%` }} /></li>)}</ol> : <p className="portfolio-visuals-empty">No eligible account allocation is available.</p>}</section>
    </div>
    <PerformanceXirrCard portfolioId={portfolioId} accountId={accountFilter === 'all' ? '' : accountFilter} accountCurrency={selectedAccountCurrency} asOf={asOf} performance={performance} performanceContext={performanceContext} performanceValuation={performanceValuation} performanceValuationContext={performanceValuationContext} isPrivacyShieldActive={isPrivacyShieldActive} formatDate={formatDate} formatPercent={formatPercent} />
  </section>;
}
