import type { PerformanceResult, ValuationHolding, ValuationRangePoint, ValuationResult } from '../types/valuation.ts';

export type VisualPeriod = 'today' | 'last-week' | 'last-month' | 'ytd' | 'current-fy' | 'previous-fy' | 'all' | 'custom';
export type VisualFrequency = 'daily' | 'monthly';

export type VisualHoldingMetadata = {
  holdingId: string;
  accountScopeId: string;
  instrumentName: string;
  instrumentType: string;
  currency: string | null;
  source: 'MANUAL' | 'STATEMENT';
};

export type VisualObservation = {
  asOf: string;
  currency: string;
  value: number;
  source: string;
  priceDate: string | null;
};

/** The UI records the immutable request inputs beside a protected performance response. */
export type PerformanceRequestContext = { portfolioId: string; accountId: string; asOf: string };

export type VisualRankedHolding = VisualObservation & {
  holdingId: string;
  accountScopeId: string;
  label: string;
  instrumentType: string;
};

export type VisualAccountAllocation = {
  accountId: string;
  label: string;
  currency: string;
  value: number;
};

export type PortfolioVisualsProjection = {
  currency: string;
  asOf: string;
  trendPoints: VisualObservation[];
  topHoldings: VisualRankedHolding[];
  accountAllocation: VisualAccountAllocation[];
  xirr: { valuePct: number; asOf: string } | null;
  xirrReason: string;
  todayMovementAvailable: false;
  todayMovementLabel: "Today's movement unavailable";
};

export type PortfolioVisualsInput = {
  portfolioId: string;
  historyValuations: readonly ValuationResult[];
  rangePoints?: readonly ValuationRangePoint[];
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
  accountLabels?: ReadonlyMap<string, string> | Readonly<Record<string, string>>;
};

export function isIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
}

export const getIndiaToday = indiaToday;
export const getPeriodBounds = periodBounds;
export const filterObservationsByPeriod = filterVisualObservations;
export const sampleObservations = sampleVisualObservations;

function dateFromIso(value: string): Date {
  return new Date(`${value}T00:00:00Z`);
}

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function addDays(value: string, days: number): string {
  const date = dateFromIso(value);
  date.setUTCDate(date.getUTCDate() + days);
  return isoDate(date);
}

function addMonths(value: string, months: number): string {
  const date = dateFromIso(value);
  const originalDay = date.getUTCDate();
  date.setUTCDate(1);
  date.setUTCMonth(date.getUTCMonth() + months);
  const lastDay = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate();
  date.setUTCDate(Math.min(originalDay, lastDay));
  return isoDate(date);
}

export function indiaToday(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function periodBounds(period: VisualPeriod, today: string = indiaToday(), customStart = '', customEnd = ''): { start: string | null; end: string | null } {
  if (!isIsoDate(today)) return { start: null, end: null };
  const date = dateFromIso(today);
  const year = date.getUTCFullYear();
  const month = date.getUTCMonth();
  if (period === 'all') return { start: null, end: null };
  if (period === 'custom') return { start: isIsoDate(customStart) ? customStart : null, end: isIsoDate(customEnd) ? customEnd : null };
  if (period === 'today') return { start: today, end: today };
  if (period === 'last-week') return { start: addDays(today, -6), end: today };
  if (period === 'last-month') return { start: addMonths(today, -1), end: today };
  if (period === 'ytd') return { start: `${year}-01-01`, end: today };
  const currentFyStartYear = month >= 3 ? year : year - 1;
  if (period === 'current-fy') return { start: `${currentFyStartYear}-04-01`, end: today };
  return { start: `${currentFyStartYear - 1}-04-01`, end: `${currentFyStartYear}-03-31` };
}

export function filterVisualObservations<T extends { asOf: string }>(observations: readonly T[], period: VisualPeriod, customStart = '', customEnd = '', today = indiaToday()): T[] {
  const bounds = periodBounds(period, today, customStart, customEnd);
  if (period === 'custom' && (!bounds.start || !bounds.end || bounds.start > bounds.end)) return [];
  return [...observations]
    .filter((observation) => isIsoDate(observation.asOf))
    .filter((observation) => (!bounds.start || observation.asOf >= bounds.start) && (!bounds.end || observation.asOf <= bounds.end))
    .sort((left, right) => left.asOf.localeCompare(right.asOf));
}

export function sampleVisualObservations<T extends { asOf: string }>(observations: readonly T[], frequency: VisualFrequency): T[] {
  const sorted = [...observations].sort((left, right) => left.asOf.localeCompare(right.asOf));
  if (frequency === 'daily') return sorted;
  const latestByMonth = new Map<string, T>();
  sorted.forEach((observation) => latestByMonth.set(observation.asOf.slice(0, 7), observation));
  return [...latestByMonth.values()].sort((left, right) => left.asOf.localeCompare(right.asOf));
}

function accountLabel(accountLabels: PortfolioVisualsInput['accountLabels'], accountId: string): string {
  if (accountLabels instanceof Map) return accountLabels.get(accountId) || 'Private account';
  return (accountLabels as Readonly<Record<string, string>> | undefined)?.[accountId] || 'Private account';
}

function validCalculatedValue(row: ValuationHolding | undefined, currency: string): number | null {
  if (!row || row.status !== 'CALCULATED' || row.reconciliationStatus === 'REVIEW_REQUIRED' || row.currency !== currency || typeof row.currentValue !== 'string' || row.currentValue.trim() === '') return null;
  const value = Number(row.currentValue);
  return Number.isFinite(value) && value >= 0 ? value : null;
}

function projectTrend(historyValuations: readonly ValuationResult[], rangePoints: readonly ValuationRangePoint[] | undefined, currency: string, holdings: ReadonlyMap<string, VisualHoldingMetadata>, accountFilter: string): VisualObservation[] {
  if (rangePoints) return rangePoints.flatMap((point) => {
    if (!isIsoDate(point.asOf)) return [];
    const value = Number(point.calculatedValue);
    return Number.isFinite(value) && value >= 0 ? [{ asOf: point.asOf, currency, value, source: 'Scoped calculation', priceDate: null }] : [];
  }).sort((left, right) => left.asOf.localeCompare(right.asOf));
  return historyValuations
    .filter((result) => isIsoDate(result.asOf))
    .map((result) => {
      const rows = result.holdings
        .map((row) => ({ row, value: validCalculatedValue(row, currency), meta: holdings.get(row.holdingId) }))
        .filter((item): item is { row: ValuationHolding; value: number; meta: VisualHoldingMetadata } => item.value !== null && item.meta !== undefined)
        .filter((item) => accountFilter === 'all' || item.meta.accountScopeId === accountFilter);
      if (!rows.length) return null;
      const sources = new Set(rows.map((item) => item.row.source).filter((value): value is string => Boolean(value)));
      const priceDates = new Set(rows.map((item) => item.row.priceDate).filter((value): value is string => typeof value === 'string' && isIsoDate(value)));
      return {
        asOf: result.asOf,
        currency,
        value: rows.reduce((sum, item) => sum + item.value, 0),
        source: sources.size === 1 ? [...sources][0] : sources.size ? 'Multiple eligible sources' : 'Source unavailable',
        priceDate: priceDates.size === 1 ? [...priceDates][0] : null,
      };
    })
    .filter((point): point is VisualObservation => point !== null)
    .sort((left, right) => left.asOf.localeCompare(right.asOf));
}

export function trustedXirrForAccount(performance: PerformanceResult | null, responseContext: PerformanceRequestContext | null, performanceValuation: ValuationResult | null, performanceValuationContext: PerformanceRequestContext | null, expectedContext: PerformanceRequestContext | null, accountCurrency: string): { valuePct: number; asOf: string } | null {
  const raw = performance?.xirr.valuePct;
  const valuePct = typeof raw === 'number' || (typeof raw === 'string' && raw.trim() !== '') ? Number(raw) : NaN;
  const pairedCurrencies = new Set((performanceValuation?.summaryByCurrency || []).map((summary) => summary.currency));
  const validDigest = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0;
  if (!performance || !responseContext || !performanceValuation || !performanceValuationContext || !expectedContext || !accountCurrency || !expectedContext.portfolioId || !expectedContext.accountId || !isIsoDate(expectedContext.asOf) || !isIsoDate(responseContext.asOf) || !isIsoDate(performanceValuationContext.asOf) || !isIsoDate(performance.asOf) || !isIsoDate(performanceValuation.asOf) || !validDigest(performance.inputDigest) || !validDigest(performanceValuation.inputDigest) || responseContext.portfolioId !== expectedContext.portfolioId || responseContext.accountId !== expectedContext.accountId || responseContext.asOf !== expectedContext.asOf || performanceValuationContext.portfolioId !== expectedContext.portfolioId || performanceValuationContext.accountId !== expectedContext.accountId || performanceValuationContext.asOf !== expectedContext.asOf || performance.asOf !== expectedContext.asOf || performanceValuation.asOf !== expectedContext.asOf || pairedCurrencies.size !== 1 || !pairedCurrencies.has(accountCurrency) || performance.inputDigest !== performanceValuation.inputDigest || !performance.coverage.historyComplete || performance.xirr.status !== 'CALCULATED' || !Number.isFinite(valuePct)) return null;
  return { valuePct, asOf: performance.asOf };
}

export function projectPortfolioVisuals(input: PortfolioVisualsInput): PortfolioVisualsProjection {
  const { currency } = input;
  const metadata = new Map(input.holdings.map((holding) => [holding.holdingId, holding]));
  const currentRows = (input.valuation?.holdings || []).map((row) => ({ row, value: validCalculatedValue(row, currency), meta: metadata.get(row.holdingId) })).filter((item): item is { row: ValuationHolding; value: number; meta: VisualHoldingMetadata } => item.value !== null && item.meta !== undefined);
  const eligibleRows = input.accountFilter === 'all' ? currentRows : currentRows.filter((item) => item.meta.accountScopeId === input.accountFilter);
  const topHoldings = eligibleRows
    .map(({ row, value, meta }) => ({ asOf: input.valuation?.asOf || input.asOf, currency, value, source: row.source || 'Source unavailable', priceDate: row.priceDate || '', holdingId: meta.holdingId, accountScopeId: meta.accountScopeId, label: meta.instrumentName, instrumentType: meta.instrumentType }))
    .sort((left, right) => right.value - left.value || left.label.localeCompare(right.label) || left.holdingId.localeCompare(right.holdingId))
    .slice(0, 5);
  const allocationMap = new Map<string, VisualAccountAllocation>();
  eligibleRows.forEach(({ value, meta }) => {
    const existing = allocationMap.get(meta.accountScopeId);
    if (existing) existing.value += value;
    else allocationMap.set(meta.accountScopeId, { accountId: meta.accountScopeId, label: accountLabel(input.accountLabels, meta.accountScopeId), currency, value });
  });
  const accountAllocation = [...allocationMap.values()].sort((left, right) => right.value - left.value || left.label.localeCompare(right.label) || left.accountId.localeCompare(right.accountId));
  const expectedPerformanceContext = input.accountFilter === 'all' ? null : { portfolioId: input.portfolioId, accountId: input.accountFilter, asOf: input.asOf };
  const xirr = input.currency === input.selectedAccountCurrency
    ? trustedXirrForAccount(input.performance, input.performanceContext, input.performanceValuation, input.performanceValuationContext, expectedPerformanceContext, input.selectedAccountCurrency)
    : null;
  return {
    currency,
    asOf: input.asOf,
    trendPoints: projectTrend(input.historyValuations, input.rangePoints, currency, metadata, input.accountFilter),
    topHoldings,
    accountAllocation,
    xirr,
    xirrReason: xirr ? '' : input.performance?.xirr.reason || 'XIRR is unavailable for this exact single-currency scope.',
    todayMovementAvailable: false,
    todayMovementLabel: "Today's movement unavailable",
  };
}
