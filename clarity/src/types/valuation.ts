/** `STATEMENT_VALUE` is a dated statement observation, never a current-price calculation. */
export type ValuationStatus = 'CALCULATED' | 'INSUFFICIENT_DATA' | 'STATEMENT_VALUE';
export type PerformanceStatus = 'CALCULATED' | 'INSUFFICIENT_DATA' | 'UNAVAILABLE';
export type HoldingSource = 'MANUAL' | 'STATEMENT';
export type ValuationHolding = { holdingId: string; holdingSource: HoldingSource; reconciliationStatus?: 'CLEAR' | 'REVIEW_REQUIRED'; status: ValuationStatus; reason?: string; quantity?: string; price?: string; currency?: string; priceDate?: string; source?: string; priceStatus?: string; currentValue?: string; accountScopeId?: string; statementPrice?: string | null; statementValue?: string | null; statementDate?: string };
/** Manual rows awaiting reconciliation remain visible but never contribute to included UI aggregates. */
export function isIncludedValuationHolding(source: HoldingSource, holding: Pick<ValuationHolding, 'reconciliationStatus'> | undefined): boolean {
  return source !== 'MANUAL' || holding?.reconciliationStatus !== 'REVIEW_REQUIRED';
}
export type ValuationSummary = { currency: string; calculatedValue: string; statementValue: string; totalIncludedValue: string; calculatedAsOf: string | null; statementAsOf: string | null; excludedForReconciliationCount: number };
export type ValuationResult = { calculationVersion: string; inputDigest: string; asOf: string; holdings: ValuationHolding[]; summaryByCurrency: ValuationSummary[] };
/** Compact server aggregate. It intentionally contains no per-holding historic rows. */
export type ValuationRangePoint = { asOf: string; calculatedValue: string; statementValue: string; totalIncludedValue: string };
export type ValuationRangeResult = { calculationVersion: string; inputDigest: string; scope: { accountId: string | null; currency: string }; range: { start: string | null; end: string | null; granularity: 'daily' | 'monthly' }; coverage: { availableStart: string | null; availableEnd: string | null; observedCount: number; selectedObservedCount: number; returnedCount: number; partial: boolean }; points: ValuationRangePoint[]; first: ValuationRangePoint | null; last: ValuationRangePoint | null };
export type PerformanceMetric = { status: PerformanceStatus; reason?: string; value?: string; valuePct?: string; currency?: string };
export type PerformanceResult = { calculationVersion: string; inputDigest: string; asOf: string; coverage: { historyComplete: boolean; cashflowCount: number; reasons: string[]; scope: 'manual_complete_history_only' }; gain: PerformanceMetric; xirr: PerformanceMetric };
