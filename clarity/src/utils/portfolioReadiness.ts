import type { PerformanceResult, ValuationHolding, ValuationResult } from '../types/valuation.ts';

export type ReadinessStatus = 'READY' | 'REVIEW' | 'UNAVAILABLE' | 'UNANALYSED';
export type ReadinessScope = { portfolioId: string; accountId: string; currency: string; asOf: string };
export type ReadinessRequestState = 'idle' | 'loading' | 'ready' | 'error';
export type ReadinessAccountEvidence = {
  accountId: string;
  label: string;
  currency: string;
  sourceKind: 'MANUAL' | 'STATEMENT';
  sourceDate?: string;
  historyAttested?: boolean;
};
export type ReadinessItem = ReadinessAccountEvidence & {
  status: ReadinessStatus;
  message: string;
  nextAction: 'cash-flows' | 'holdings' | 'accounts' | 'statements';
  asOf?: string;
  reasons: string[];
  valuationEvidence: string[];
  historyEvidence: string;
  gainEvidence: string;
  xirrEvidence: string;
  reconciliationEvidence: string;
};
export type ReadinessInput = {
  accounts: readonly ReadinessAccountEvidence[];
  selectedAccountId?: string;
  scope?: ReadinessScope | null;
  intendedScope?: ReadinessScope | null;
  factsState: ReadinessRequestState;
  metricsState: ReadinessRequestState;
  valuation?: ValuationResult | null;
  performance?: PerformanceResult | null;
};

const known: Record<string, string> = {
  MISSING_HISTORY: 'Dated cash flows are missing or the account history has not been attested as complete.',
  MISSING_PRICE: 'A dated price is unavailable for one or more manual holdings.',
  NON_POSITIVE_TERMINAL_VALUE: 'A positive terminal value is unavailable for this date.',
  RECONCILIATION_REQUIRED: 'A manual holding overlaps statement evidence and is excluded pending review.',
  MIXED_CURRENCY: 'The saved facts contain currencies that are incompatible for this return scope.',
  SAME_DAY_ONLY: 'The recorded cash flows and terminal value do not provide distinct dates for XIRR.',
  INVALID_CASHFLOW: 'The recorded cash flows do not contain the signs required for XIRR.',
  SOLVER_FAILURE: 'XIRR could not be calculated from the recorded dated inputs.',
};
export function explainReadinessReason(code: string): string {
  return known[code] || `The backend returned an unrecognised reason (${code || 'no code'}); no eligibility or value was inferred.`;
}

/** Confirms response scope only; it deliberately does not derive a valuation or return. */
function sameReadinessScope(left: ReadinessScope | null | undefined, right: ReadinessScope | null | undefined): boolean {
  return Boolean(left && right && left.portfolioId === right.portfolioId && left.accountId === right.accountId && left.currency === right.currency && left.asOf === right.asOf);
}

export function isExactReadinessScope(scope: ReadinessScope | null | undefined, valuation: ValuationResult | null | undefined, performance: PerformanceResult | null | undefined, intendedScope?: ReadinessScope | null): boolean {
  if (!scope?.accountId || !scope.asOf || !scope.currency || !valuation || !performance) return false;
  if (intendedScope && !sameReadinessScope(scope, intendedScope)) return false;
  if (valuation.asOf !== scope.asOf || performance.asOf !== scope.asOf || valuation.holdings.length === 0) return false;
  return valuation.holdings.every((holding) => holding.accountScopeId === scope.accountId && (!holding.currency || holding.currency === scope.currency));
}

function holdingEvidence(row: ValuationHolding): string {
  if (row.status === 'STATEMENT_VALUE') return `Statement value dated ${row.statementDate || 'date unavailable'}`;
  if (row.status === 'CALCULATED') return `${row.priceStatus || 'Dated price'} from ${row.source || 'source unavailable'}, dated ${row.priceDate || 'date unavailable'}`;
  return explainReadinessReason(row.reason || '');
}

export function projectPortfolioReadiness(input: ReadinessInput): ReadinessItem[] {
  return input.accounts.map((account) => {
    const selected = input.selectedAccountId === account.accountId;
    const exact = selected && (!input.intendedScope || (input.intendedScope.accountId === account.accountId && input.intendedScope.currency === account.currency)) && isExactReadinessScope(input.scope, input.valuation, input.performance, input.intendedScope);
    const valuationRows = exact ? input.valuation!.holdings : [];
    const reasons = exact ? [...new Set([...(input.performance?.coverage.reasons || []), input.performance?.gain.reason, input.performance?.xirr.reason, ...valuationRows.map((row) => row.reason).filter((value): value is string => Boolean(value)), ...(valuationRows.some((row) => row.reconciliationStatus === 'REVIEW_REQUIRED') ? ['RECONCILIATION_REQUIRED'] : [])].filter((value): value is string => Boolean(value)))] : [];
    let status: ReadinessStatus = 'UNANALYSED';
    let message = 'Select this account to inspect its exact dated readiness.';
    if (selected && input.factsState === 'error') { status = 'UNAVAILABLE'; message = 'Saved account facts could not be confirmed. They were not treated as empty.'; }
    else if (selected && input.metricsState === 'error') { status = 'UNAVAILABLE'; message = 'This account’s readiness request could not be confirmed.'; }
    else if (selected && input.metricsState === 'ready' && input.intendedScope && !sameReadinessScope(input.scope, input.intendedScope)) { status = 'UNANALYSED'; message = 'Loading readiness evidence for the selected account and dated currency scope.'; }
    else if (selected && input.metricsState === 'ready' && !exact) { status = 'UNAVAILABLE'; message = 'The returned valuation and history did not prove this exact account and currency scope.'; }
    else if (exact && input.performance?.coverage.historyComplete && input.performance.gain.status === 'CALCULATED' && input.performance.xirr.status === 'CALCULATED') { status = 'READY'; message = 'Dated valuation and backend-eligible return inputs are available for this account.'; }
    else if (exact) { status = 'REVIEW'; message = reasons.length ? reasons.map(explainReadinessReason).join(' ') : 'The backend reports incomplete valuation or return data for this account.'; }
    else if (selected && (input.factsState === 'loading' || input.metricsState === 'loading')) message = 'Loading readiness evidence for this account.';

    const nextAction: ReadinessItem['nextAction'] = account.sourceKind === 'STATEMENT'
      ? 'statements'
      : reasons.includes('MISSING_HISTORY') ? 'cash-flows'
      : reasons.includes('MISSING_PRICE') || reasons.includes('RECONCILIATION_REQUIRED') ? 'holdings'
      : 'accounts';
    return {
      ...account,
      status,
      message,
      nextAction,
      asOf: exact ? input.scope?.asOf : undefined,
      reasons,
      valuationEvidence: valuationRows.map(holdingEvidence),
      historyEvidence: exact
        ? input.performance!.coverage.historyComplete
          ? `History coverage is attested/complete; coverage alone does not mean gain or XIRR can be calculated. ${input.performance!.coverage.cashflowCount} dated cash flow${input.performance!.coverage.cashflowCount === 1 ? '' : 's'} recorded.`
          : `History coverage is incomplete; ${input.performance!.coverage.cashflowCount} dated cash flow${input.performance!.coverage.cashflowCount === 1 ? '' : 's'} recorded.`
        : 'Not analysed for this exact account scope.',
      gainEvidence: exact ? `Gain: ${input.performance!.gain.status}${input.performance!.gain.reason ? ` (${input.performance!.gain.reason}) — ${explainReadinessReason(input.performance!.gain.reason)}` : ''}` : 'Gain: not analysed for this exact account scope.',
      xirrEvidence: exact ? `XIRR: ${input.performance!.xirr.status}${input.performance!.xirr.reason ? ` (${input.performance!.xirr.reason}) — ${explainReadinessReason(input.performance!.xirr.reason)}` : ''}` : 'XIRR: not analysed for this exact account scope.',
      reconciliationEvidence: exact && valuationRows.some((row) => row.reconciliationStatus === 'REVIEW_REQUIRED')
        ? 'Review required; overlapping manual evidence is excluded from totals.'
        : exact ? 'No reconciliation exclusion was returned for this scope.' : 'Not analysed for this exact account scope.',
    };
  });
}
