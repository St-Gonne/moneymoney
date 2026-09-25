import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ChangeEvent } from 'react';
import { AlertCircle, CalendarDays, CheckCircle2, FileUp, Filter, Loader2, RefreshCw, Search, ShieldCheck, WalletCards } from 'lucide-react';
import { PRIVACY_MASK, applyPrivacyMask } from '../utils/formatters.ts';
import { createNsdlIdempotencyKey, fetchNsdlActivity, fetchNsdlPortfolio, importNsdlStatement, previewNsdlStatement, previewSchwabStatement, NsdlApiError } from '../services/nsdlApi.ts';
import { schwabReviewAccountLabel, schwabReviewAmount } from '../types/nsdl.ts';
import type { NsdlFamilyActivity, NsdlPreviewResponse, NsdlSnapshotV1, SchwabPreviewResponse } from '../types/nsdl.ts';
import { ManualEntryPanel } from './ManualEntryPanel.tsx';
import { DadModeView } from './DadModeView.tsx';
import type { DadModeProjection } from './DadModeView.tsx';
import { createComfortVoiceScope } from '../services/comfortVoice/localContracts.ts';
import { fetchPerformance, fetchValuation, fetchValuationRange } from '../services/valuationApi.ts';
import { fetchAccountData } from '../services/accountDataApi.ts';
import { AccountDataApiError, type AccountDataSnapshot } from '../types/accountData.ts';
import { projectPortfolioReadiness, type ReadinessAccountEvidence, type ReadinessRequestState, type ReadinessScope } from '../utils/portfolioReadiness.ts';
import type { ActivityKindFilter } from '../utils/portfolioActivity.ts';
import { formatSafeSupport } from '../utils/portfolioSafeSupport.ts';
import { PortfolioReadinessPanel } from './PortfolioReadinessPanel.tsx';
import { PerformanceXirrCard, PortfolioVisualsPanel } from './PortfolioVisualsPanel.tsx';
import type { PerformanceRequestContext, VisualHoldingMetadata } from '../utils/portfolioVisuals.ts';
import { isIncludedValuationHolding, type HoldingSource, type PerformanceResult, type ValuationHolding, type ValuationRangeResult, type ValuationResult } from '../types/valuation.ts';
import type { PrivateNsdlPresentation, WorkspaceSection } from './PrivateNsdlApp.tsx';
import { ValuationRangeCache } from '../utils/valuationRangeCache.ts';
import './NsdlPortfolioView.css';

export type NsdlPortfolioNavigation = {
  accountId?: string;
  holdingId?: string;
  returnSection?: WorkspaceSection;
  returnContext?: { accountFilter: string; allocationCurrency: string; sourceFilter: HoldingSourceFilter; search: string; holdingGroup: HoldingGroup; sortDirection: 'asc' | 'desc' };
  activityContext?: { accountFilter: string; kindFilter: ActivityKindFilter; selectedEventId?: string };
};
type NsdlPortfolioViewProps = { portfolioId: string; readonly scopeLabel?: string; readonly accessRevoked?: boolean; readonly onAccessRevoked?: () => void; readonly presentation?: PrivateNsdlPresentation; readonly comfortView?: boolean; readonly comfortVoiceTestMode?: 'local-mock'; readonly workspaceSection?: WorkspaceSection; readonly isAmountsHidden?: boolean; readonly externalSelectedFile?: File | null; readonly onExternalFileConsumed?: () => void; readonly navigationContext?: NsdlPortfolioNavigation | null; readonly onNavigateWorkspace?: (destination: WorkspaceSection, context?: NsdlPortfolioNavigation | null) => void };
type ViewStatus = 'loading' | 'empty' | 'ready' | 'unavailable' | 'denied' | 'revoked';

const errorMessages: Record<string, string> = {
  AUTH_REQUIRED: 'Your private session is no longer available. Sign in again to continue.',
  ACCESS_DENIED: 'This portfolio is denied or access was revoked. No other portfolio was tried.',
  SERVICE_UNAVAILABLE: 'The private portfolio is unavailable right now. Refresh to retry.',
  ERR_NSDL_PASSWORD_INVALID: 'The statement password is not valid. Check it and try again.',
  ERR_NSDL_UPLOAD_INVALID: 'Choose one PDF statement and try again.',
  ERR_NSDL_UNSUPPORTED_LAYOUT: 'This statement layout is not supported yet. Your existing holdings were kept.',
  ERR_NSDL_PARSE_INCOMPLETE: 'The statement could not be read completely. Your existing holdings were kept.',
  ERR_NSDL_LIMIT_EXCEEDED: 'This statement exceeds the private preview limits. Your existing holdings were kept.',
  ERR_NSDL_OWNER_MISMATCH: 'This statement does not belong to the signed-in private portfolio.',
  ERR_NSDL_OLDER_STATEMENT: 'This statement is older than the saved snapshot. Your existing holdings were kept.',
  ERR_NSDL_SAME_DATE_CONFLICT: 'A different statement for this date is already saved. Your existing holdings were kept.',
  ERR_NSDL_ACCOUNT_SET_CONFLICT: 'The statement accounts do not match the saved portfolio. Your existing holdings were kept.',
  ERR_NSDL_REVISION_CONFLICT: 'The portfolio changed while importing. Refresh and retry with the same statement.',
  ERR_NSDL_STORE_UNAVAILABLE: 'Private storage could not be confirmed. Refresh before retrying.',
  ERR_NSDL_COMMIT_UNKNOWN: 'The import result could not be confirmed. Refresh to read the saved receipt before retrying.',
  ERR_NSDL_ACCOUNT_COMMIT_UNKNOWN: 'The statement result may be saved, but account setup could not be confirmed. Refresh first, then retry this same selected statement.',
  ERR_NSDL_IDEMPOTENCY_CONFLICT: 'This confirmation does not match the selected statement. Refresh and preview the statement again before retrying.',
  ERR_SCHWAB_PASSWORD_UNSUPPORTED: 'This local Schwab preview accepts readable PDFs only. No password was applied.',
  ERR_SCHWAB_PREVIEW_UNSUPPORTED: 'This Schwab PDF does not match the reviewed monthly statement layout.',
  UNKNOWN: 'The private portfolio request could not be completed. Refresh before retrying.',
};

function errorCode(error: unknown): string {
  if (error instanceof NsdlApiError) return error.code;
  if (error && typeof error === 'object' && 'code' in error && (error as { code?: unknown }).code === 'AUTH_REQUIRED') return 'AUTH_REQUIRED';
  return 'UNKNOWN';
}

function errorMessage(error: unknown): string {
  const message = errorMessages[errorCode(error)] || errorMessages.UNKNOWN;
  if (error instanceof NsdlApiError && error.importReference) return `${message} Support reference: ${error.importReference}.`;
  return message;
}

function displayDate(value: string): string {
  const date = new Date(`${value}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeZone: 'UTC' }).format(date);
}

function currencySymbol(currency: string | null): string {
  return currency === 'INR' ? '₹' : currency === 'USD' ? '$' : currency ? `${currency} ` : '';
}

function moneyValue(value: string | null, currency: string | null, masked: boolean): string {
  if (value === null) return 'Not provided in statement';
  return masked ? applyPrivacyMask(`${currencySymbol(currency)}${value}`, true) : formatMoney(value, currency);
}

function formatMoney(value: string | number, currency: string | null | undefined): string {
  if (!currency) return String(value);
  const amount = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(amount)) return `${currencySymbol(currency)}${value}`;
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 2 }).format(amount);
}

function formatPercent(value: string | number | null | undefined): string {
  const percent = Number(value);
  return Number.isFinite(percent)
    ? `${new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(percent)}%`
    : 'Unavailable';
}

function disclosureValue(value: string, _masked: boolean): string {
  return value;
}

function disclosedDate(value: string, _masked: boolean): string {
  return displayDate(value);
}

// displayedPerformance.gain.status === 'CALCULATED' && displayedPerformance.xirr.status === 'CALCULATED'
// manual_complete_history_only · Partial or unavailable
// Statement observations are excluded from return calculations

function calculatedValue(rows: readonly { status: string; currentValue?: string }[]): number {
  return rows.filter((row) => row.status === 'CALCULATED' && row.currentValue !== undefined).reduce((total, row) => total + Number(row.currentValue), 0);
}

type CanonicalScope = { accountIds: Set<string>; holdingIds: Set<string>; holdingAccounts: Map<string, string> };
type HoldingGroup = 'account' | 'asset-type' | 'market';
type HoldingSourceFilter = 'all' | 'manual' | 'statement';
type CombinedHolding = { holdingId: string; accountScopeId: string; isin: string | null; instrumentName: string; instrumentType: string; quantity: string; currency: string | null; statementPrice: string | null; statementValue: string | null; source: HoldingSource; valuation?: ValuationHolding };
type AccountAllocation = { currency: string; total: number; accounts: Array<{ id: string; label: string; value: number }> };

function canonicalScope(data: AccountDataSnapshot): CanonicalScope | null {
  const accountIds = new Set(data.accounts.map((account) => account.account_id));
  if (accountIds.size !== data.accounts.length || data.accounts.some((account) => !account.account_id)) return null;
  const activeHoldings = data.openingHoldings.filter((holding) => !holding.voided);
  const holdingIds = new Set(activeHoldings.map((holding) => holding.fact_id));
  if (holdingIds.size !== activeHoldings.length || activeHoldings.some((holding) => !holding.fact_id || !accountIds.has(holding.account_id))) return null;
  const holdingAccounts = new Map(activeHoldings.map((holding) => [holding.fact_id, holding.account_id]));
  return { accountIds, holdingIds, holdingAccounts };
}

export function canonicalValuationGate(result: ValuationResult, requestedAsOf: string, scope: CanonicalScope): boolean {
  const manualRows = result.holdings.filter((holding) => holding.holdingSource === 'MANUAL');
  if (result.asOf !== requestedAsOf || manualRows.length !== scope.holdingIds.size) return false;
  const responseIds = new Set(manualRows.map((holding) => holding.holdingId));
  return responseIds.size === scope.holdingIds.size
    && [...responseIds].every((holdingId) => scope.holdingIds.has(holdingId))
    && manualRows.every((holding) => holding.status === 'CALCULATED' && holding.currentValue !== undefined && Number.isFinite(Number(holding.currentValue)));
}

const hasExactCalculatedValuation = canonicalValuationGate;

function latestManualDate(data: AccountDataSnapshot | null): string {
  if (!data) return '';
  return [...data.openingHoldings.filter((holding) => !holding.voided).map((holding) => holding.as_of), ...data.cashFlows.filter((flow) => !flow.voided).map((flow) => flow.effective_date)]
    .filter((value): value is string => /^\d{4}-\d{2}-\d{2}$/.test(value)).sort().at(-1) || '';
}

function readinessAccountEvidence(snapshot: NsdlSnapshotV1 | null, data: AccountDataSnapshot | null): ReadinessAccountEvidence[] {
  const manualAccounts = (data?.accounts || []).map((account) => {
    const dates = [
      ...(data?.openingHoldings || []).filter((row) => row.account_id === account.account_id && !row.voided).map((row) => row.as_of),
      ...(data?.cashFlows || []).filter((row) => row.account_id === account.account_id && !row.voided).map((row) => row.effective_date),
    ].filter((value): value is string => /^\d{4}-\d{2}-\d{2}$/.test(value)).sort();
    const sourceKind = account.provenance?.source_kind === 'statement' ? 'STATEMENT' : 'MANUAL';
    return {
      accountId: account.account_id,
      label: account.user_alias || account.source_name || account.institution,
      currency: account.currency || '',
      sourceKind,
      sourceDate: sourceKind === 'STATEMENT' ? snapshot?.asOfDate : dates.at(-1),
      historyAttested: sourceKind === 'MANUAL' ? account.manual_history_complete === true : undefined,
    } satisfies ReadinessAccountEvidence;
  });
  const known = new Set(manualAccounts.map((account) => account.accountId));
  const statementAccounts = (snapshot?.accounts || []).filter((account) => !known.has(account.accountScopeId)).map((account) => {
    const holdings = (snapshot?.holdings || []).filter((holding) => holding.accountScopeId === account.accountScopeId);
    const currencies = [...new Set(holdings.map((holding) => holding.currency).filter((value): value is string => Boolean(value)))];
    return {
      accountId: account.accountScopeId,
      label: account.maskedLabel,
      currency: currencies.length === 1 ? currencies[0] : '',
      sourceKind: 'STATEMENT' as const,
      sourceDate: snapshot?.asOfDate,
    } satisfies ReadinessAccountEvidence;
  });
  return [...manualAccounts, ...statementAccounts];
}

function includedHoldingValue(holding: CombinedHolding): number | null {
  if (!isIncludedValuationHolding(holding.source, holding.valuation)) return null;
  const value = holding.source === 'MANUAL'
    ? holding.valuation?.status === 'CALCULATED' ? holding.valuation.currentValue : null
    : holding.valuation?.status === 'STATEMENT_VALUE' ? holding.valuation.statementValue || holding.statementValue : holding.statementValue;
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric >= 0 ? numeric : null;
}

export function composeCombinedHoldings(snapshot: NsdlSnapshotV1 | null, data: AccountDataSnapshot | null, valuation: ValuationResult | null): CombinedHolding[] {
  const valuationById = new Map((valuation?.holdings || []).map((holding) => [holding.holdingId, holding]));
  const statementRows = (snapshot?.holdings || []).map((holding) => ({ ...holding, source: 'STATEMENT' as const, valuation: valuationById.get(holding.holdingId) }));
  const statementIds = new Set(statementRows.map((holding) => holding.holdingId));
  const manualRows = (data?.openingHoldings || []).filter((holding) => !holding.voided && !statementIds.has(holding.fact_id)).map((holding) => ({
    holdingId: holding.fact_id, accountScopeId: holding.account_id, isin: holding.isin || null, instrumentName: holding.instrument_name, instrumentType: 'Manual holding', quantity: holding.quantity, currency: holding.currency,
    statementPrice: null, statementValue: holding.documented_cost || null, source: 'MANUAL' as const, valuation: valuationById.get(holding.fact_id),
  }));
  return [...statementRows, ...manualRows];
}

export function NsdlPortfolioView({ portfolioId, scopeLabel, accessRevoked = false, onAccessRevoked, presentation, comfortView = false, comfortVoiceTestMode, workspaceSection = 'overview', isAmountsHidden = true, externalSelectedFile, onExternalFileConsumed, navigationContext, onNavigateWorkspace }: NsdlPortfolioViewProps) {
  void formatPercent;
  const isPrivacyShieldActive = isAmountsHidden;
  const [snapshot, setSnapshot] = useState<NsdlSnapshotV1 | null>(null);
  const [status, setStatus] = useState<ViewStatus>('loading');
  const [busy, setBusy] = useState<'refreshing' | 'uploading' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [password, setPassword] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<NsdlPreviewResponse | null>(null);
  const [schwabFile, setSchwabFile] = useState<File | null>(null);
  const [schwabPreview, setSchwabPreview] = useState<SchwabPreviewResponse | null>(null);
  const [schwabBusy, setSchwabBusy] = useState(false);
  const [schwabError, setSchwabError] = useState<string | null>(null);
  const [schwabAccountChoice, setSchwabAccountChoice] = useState<'separate' | 'unresolved' | ''>('');
  const [schwabOwnershipConfirmed, setSchwabOwnershipConfirmed] = useState(false);
  const [schwabIsoCurrency, setSchwabIsoCurrency] = useState('');
  const confirmKeyRef = useRef<string | null>(null);
  const [search, setSearch] = useState('');
  const [accountFilter, setAccountFilter] = useState('all');
  const [sourceFilter, setSourceFilter] = useState<HoldingSourceFilter>('all');
  const [holdingGroup, setHoldingGroup] = useState<HoldingGroup>('account');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});
  const [allocationCurrency, setAllocationCurrency] = useState('');
  const [detailHoldingId, setDetailHoldingId] = useState('');
  const [detailReturnContext, setDetailReturnContext] = useState<NsdlPortfolioNavigation['returnContext'] | null>(null);
  const [workspaceReturn, setWorkspaceReturn] = useState<NsdlPortfolioNavigation | null>(null);
  const snapshotSequence = useRef(0);
  const snapshotAbortRef = useRef<AbortController | null>(null);
  const schwabSequence = useRef(0);
  const schwabAbortRef = useRef<AbortController | null>(null);
  const metricsSequence = useRef(0);
  const metricsAbortRef = useRef<AbortController | null>(null);
  const snapshotRef = useRef<NsdlSnapshotV1 | null>(null);
  const [valuation, setValuation] = useState<ValuationResult | null>(null);
  const [performance, setPerformance] = useState<PerformanceResult | null>(null);
  const [performanceContext, setPerformanceContext] = useState<PerformanceRequestContext | null>(null);
  const [performanceValuation, setPerformanceValuation] = useState<ValuationResult | null>(null);
  const [performanceValuationContext, setPerformanceValuationContext] = useState<PerformanceRequestContext | null>(null);
  const [accountPerformance, setAccountPerformance] = useState<PerformanceResult | null>(null);
  const [metricsStatus, setMetricsStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
  const [performanceAccountId, setPerformanceAccountId] = useState('');
  const [analysisAsOf, setAnalysisAsOf] = useState('');
  const activeTab = workspaceSection === 'holdings' || workspaceSection === 'performance' ? workspaceSection : 'overview';
  const [accountData, setAccountData] = useState<AccountDataSnapshot | null>(null);
  const accountDataSequence = useRef(0);
  const [accountDataVersion, setAccountDataVersion] = useState(0);
  const handleAccountDataChange = useCallback((next: AccountDataSnapshot) => { setAccountData(next); setAccountDataVersion((current) => current + 1); }, []);
  const [readinessAccountId, setReadinessAccountId] = useState('');
  const [readinessFactsState, setReadinessFactsState] = useState<ReadinessRequestState>('idle');
  const [readinessMetricsState, setReadinessMetricsState] = useState<ReadinessRequestState>('idle');
  const [readinessScope, setReadinessScope] = useState<ReadinessScope | null>(null);
  const [readinessValuation, setReadinessValuation] = useState<ValuationResult | null>(null);
  const [readinessPerformance, setReadinessPerformance] = useState<PerformanceResult | null>(null);
  const [readinessSupportCopy, setReadinessSupportCopy] = useState<string | undefined>();
  const [readinessMetricsRetry, setReadinessMetricsRetry] = useState(0);
  const readinessFactsSequence = useRef(0); const readinessMetricsSequence = useRef(0);
  const readinessFactsAbortRef = useRef<AbortController | null>(null); const readinessMetricsAbortRef = useRef<AbortController | null>(null);
  const [familyActivity, setFamilyActivity] = useState<NsdlFamilyActivity[]>([]);
  const [familyActivityState, setFamilyActivityState] = useState<'loading' | 'ready' | 'denied' | 'unavailable'>('loading');
  const historyValuations: readonly ValuationResult[] = [];
  const [historyRange, setHistoryRange] = useState<ValuationRangeResult | null>(null);
  const [historyRangeState, setHistoryRangeState] = useState<'idle' | 'loading' | 'ready' | 'error' | 'limit'>('idle');
  const [historyRangeRequest, setHistoryRangeRequest] = useState<{ start?: string; end?: string; granularity: 'daily' | 'monthly' }>({ granularity: 'daily' });
  const [rangeRefreshEpoch, setRangeRefreshEpoch] = useState(0);
  const rangeCacheRef = useRef(new ValuationRangeCache());
  const rangeDataVersionRef = useRef(accountDataVersion);
  const allocationChoiceMadeRef = useRef(false);
  const comfortVoiceScopeEpoch = useRef({ key: '', value: 0 });
  const readinessAccounts = readinessAccountEvidence(snapshot, accountData);

  useEffect(() => {
    schwabSequence.current += 1;
    schwabAbortRef.current?.abort();
    setSchwabFile(null); setSchwabPreview(null); setSchwabError(null); setSchwabBusy(false);
    setSchwabAccountChoice(''); setSchwabOwnershipConfirmed(false); setSchwabIsoCurrency('');
    return () => { schwabSequence.current += 1; schwabAbortRef.current?.abort(); };
  }, [portfolioId]);

  useEffect(() => {
    if (allocationChoiceMadeRef.current || allocationCurrency || accountFilter !== 'all') return;
    const availableCurrencies = new Set([
      ...(accountData?.accounts || []).map((account) => account.currency),
      ...(snapshot?.holdings || []).map((holding) => holding.currency),
      ...(valuation?.summaryByCurrency || []).map((summary) => summary.currency),
    ]);
    if (availableCurrencies.has('INR')) setAllocationCurrency('INR');
  }, [accountData, accountFilter, allocationCurrency, snapshot, valuation]);

  useEffect(() => {
    if (!navigationContext) return;
    if (navigationContext.accountId) setAccountFilter(navigationContext.accountId);
    if (navigationContext.returnContext) {
      setAllocationCurrency(navigationContext.returnContext.allocationCurrency);
      setSourceFilter(navigationContext.returnContext.sourceFilter);
      setSearch(navigationContext.returnContext.search);
      setHoldingGroup(navigationContext.returnContext.holdingGroup);
      setSortDirection(navigationContext.returnContext.sortDirection);
    }
    if (navigationContext.holdingId) {
      setDetailHoldingId(navigationContext.holdingId);
      setDetailReturnContext(navigationContext.returnContext || null);
    } else {
      setWorkspaceReturn(navigationContext.returnSection ? navigationContext : null);
    }
  }, [navigationContext]);

  const loadReadinessFacts = useCallback(() => {
    const requestId = ++readinessFactsSequence.current; readinessFactsAbortRef.current?.abort();
    const controller = new AbortController(); readinessFactsAbortRef.current = controller;
    setReadinessFactsState('loading'); setReadinessSupportCopy(undefined);
    void fetchAccountData(portfolioId, controller.signal).then((facts) => {
      if (controller.signal.aborted || requestId !== readinessFactsSequence.current) return;
      setAccountData(facts); setReadinessFactsState('ready');
    }).catch(() => {
      if (controller.signal.aborted || requestId !== readinessFactsSequence.current) return;
      setReadinessFactsState('error'); setReadinessSupportCopy(formatSafeSupport({ operation: 'account-data-read', code: 'UNKNOWN', eventTime: new Date().toISOString() }));
    });
  }, [portfolioId]);
  useEffect(() => { loadReadinessFacts(); return () => { readinessFactsSequence.current += 1; readinessFactsAbortRef.current?.abort(); }; }, [loadReadinessFacts]);

  useEffect(() => {
    if (workspaceSection !== 'activity') return;
    const controller = new AbortController();
    setFamilyActivityState('loading');
    void fetchNsdlActivity(portfolioId, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) { setFamilyActivity(response.activity); setFamilyActivityState('ready'); }
      })
      .catch((requestError: unknown) => {
        if (controller.signal.aborted) return;
        if (requestError instanceof NsdlApiError && requestError.status === 403) { onAccessRevoked?.(); setFamilyActivityState('denied'); }
        else setFamilyActivityState('unavailable');
      });
    return () => controller.abort();
  }, [onAccessRevoked, portfolioId, workspaceSection]);

  // Readiness owns a stable dated scope. Performance/Overview interactions must
  // not silently move it to another account's analysis date.
  const readinessAsOf = snapshot?.asOfDate || latestManualDate(accountData);
  const readinessAccount = readinessAccounts.find((candidate) => candidate.accountId === readinessAccountId);
  // This is render-derived so a committed account/currency change cannot paint
  // the previous response while the effect cancels and starts its request.
  const readinessIntendedScope: ReadinessScope | null = readinessAccount && readinessAsOf
    ? { portfolioId, accountId: readinessAccount.accountId, currency: readinessAccount.currency, asOf: readinessAsOf }
    : null;
  useEffect(() => {
    const requestId = ++readinessMetricsSequence.current; readinessMetricsAbortRef.current?.abort();
    setReadinessValuation(null); setReadinessPerformance(null); setReadinessScope(null); setReadinessSupportCopy(undefined);
    const account = readinessAccount;
    if (readinessFactsState !== 'ready' || !account || !readinessAsOf) { setReadinessMetricsState('idle'); return; }
    const scope = { portfolioId, accountId: account.accountId, currency: account.currency, asOf: readinessAsOf };
    const controller = new AbortController(); readinessMetricsAbortRef.current = controller;
    setReadinessScope(scope); setReadinessMetricsState('loading');
    Promise.all([fetchValuation(portfolioId, scope.asOf, controller.signal, scope.accountId, scope.currency), fetchPerformance(portfolioId, scope.asOf, controller.signal, scope.accountId)])
      .then(([nextValuation, nextPerformance]) => { if (controller.signal.aborted || requestId !== readinessMetricsSequence.current) return; setReadinessValuation(nextValuation); setReadinessPerformance(nextPerformance); setReadinessMetricsState('ready'); })
      .catch(() => { if (controller.signal.aborted || requestId !== readinessMetricsSequence.current) return; setReadinessMetricsState('error'); setReadinessSupportCopy(formatSafeSupport({ operation: 'readiness-metrics-read', code: 'UNKNOWN', eventTime: new Date().toISOString() })); });
    return () => controller.abort();
  }, [accountData, portfolioId, readinessAccountId, readinessAsOf, readinessFactsState, readinessMetricsRetry, snapshot]);

  const runRequest = useCallback(async (kind: 'refreshing' | 'loading') => {
    const requestId = ++snapshotSequence.current;
    snapshotAbortRef.current?.abort();
    const controller = new AbortController();
    snapshotAbortRef.current = controller;
    if (kind === 'loading') setStatus('loading');
    setBusy('refreshing');
    setError(null);
    setNotice(null);
    try {
      const response = await fetchNsdlPortfolio(portfolioId, controller.signal);
      if (requestId !== snapshotSequence.current || controller.signal.aborted) return;
      if (response.status === 'ready') {
        snapshotRef.current = response.snapshot;
        setSnapshot(response.snapshot);
        setStatus('ready');
      } else {
        setStatus('empty');
      }
    } catch (requestError) {
      if (controller.signal.aborted || requestId !== snapshotSequence.current) return;
      if (requestError instanceof NsdlApiError && requestError.status === 403) { setStatus('denied'); onAccessRevoked?.(); }
      else setStatus(snapshotRef.current ? 'ready' : 'unavailable');
      setError(errorMessage(requestError));
    } finally {
      if (requestId === snapshotSequence.current) setBusy(null);
    }
  }, [onAccessRevoked, portfolioId]);

  useEffect(() => {
    snapshotRef.current = null;
    setSnapshot(null);
    setPerformanceAccountId(''); setAnalysisAsOf('');
    void runRequest('loading');
    return () => {
      snapshotSequence.current += 1;
      snapshotAbortRef.current?.abort();
    };
  }, [portfolioId, runRequest]);

  useEffect(() => {
    const revalidateRange = () => {
      rangeCacheRef.current.clear();
      setRangeRefreshEpoch((current) => current + 1);
    };
    window.addEventListener('focus', revalidateRange);
    return () => window.removeEventListener('focus', revalidateRange);
  }, []);

  useEffect(() => {
    const asOf = analysisAsOf || snapshot?.asOfDate || historyRange?.last?.asOf || latestManualDate(accountData);
    if (!asOf || (!snapshot && !presentation && !accountData?.accounts.length)) { setValuation(null); setPerformance(null); setPerformanceContext(null); setPerformanceValuation(null); setPerformanceValuationContext(null); setMetricsStatus('idle'); return; }
    const requestId = ++metricsSequence.current;
    metricsAbortRef.current?.abort();
    const controller = new AbortController();
    metricsAbortRef.current = controller;
    setValuation(null); setPerformance(null); setPerformanceContext(null); setPerformanceValuation(null); setPerformanceValuationContext(null); setMetricsStatus('loading');
    const accountId = accountFilter === 'all' ? undefined : accountFilter;
    const selectedCurrency = accountId ? accountData?.accounts.find((account) => account.account_id === accountId)?.currency : undefined;
    const requestContext = accountId ? { portfolioId, accountId, asOf } : null;
    Promise.all([fetchValuation(portfolioId, asOf, controller.signal, accountId, selectedCurrency), fetchPerformance(portfolioId, asOf, controller.signal, accountId), accountId ? fetchValuation(portfolioId, asOf, controller.signal, accountId) : Promise.resolve(null)])
      .then(([nextValuation, nextPerformance, nextPerformanceValuation]) => { if (requestId !== metricsSequence.current || controller.signal.aborted) return; setValuation(nextValuation); setPerformance(nextPerformance); setPerformanceContext(requestContext); setPerformanceValuation(nextPerformanceValuation); setPerformanceValuationContext(nextPerformanceValuation ? requestContext : null); setMetricsStatus('ready'); })
      .catch(() => { if (requestId !== metricsSequence.current || controller.signal.aborted) return; setMetricsStatus('error'); })
      .finally(() => { if (requestId === metricsSequence.current && !controller.signal.aborted) setMetricsStatus((value) => value === 'loading' ? 'error' : value); });
    return () => { controller.abort(); };
  }, [accountData, accountFilter, analysisAsOf, historyRange?.last?.asOf, portfolioId, snapshot?.asOfDate]);

  useEffect(() => {
    const asOf = analysisAsOf || snapshot?.asOfDate || historyRange?.last?.asOf || latestManualDate(accountData);
    if (!performanceAccountId || !asOf) { setAccountPerformance(null); return; }
    const controller = new AbortController();
    setAccountPerformance(null);
    void fetchPerformance(portfolioId, asOf, controller.signal, performanceAccountId).then((result) => {
      if (!controller.signal.aborted) setAccountPerformance(result);
    }).catch(() => { if (!controller.signal.aborted) setAccountPerformance(null); });
    return () => controller.abort();
  }, [accountData, analysisAsOf, historyRange?.last?.asOf, performanceAccountId, portfolioId, snapshot?.asOfDate]);

  useEffect(() => {
    const requestId = ++accountDataSequence.current;
    const controller = new AbortController();
    if (rangeDataVersionRef.current !== accountDataVersion) {
      rangeCacheRef.current.clear();
      rangeDataVersionRef.current = accountDataVersion;
    }
    fetchAccountData(portfolioId, controller.signal)
      .then(async (facts) => {
        if (controller.signal.aborted || requestId !== accountDataSequence.current) return;
        const data = facts as AccountDataSnapshot;
        const selectedAccount = accountFilter === 'all' ? null : data.accounts.find((account) => account.account_id === accountFilter);
        // A history series is always one currency. All-account history therefore needs
        // an explicit currency; a selected account may use its immutable account currency.
      const currency = allocationCurrency || selectedAccount?.currency || '';
        if (!currency) { setAccountData(data); setHistoryRange(null); setHistoryRangeState('idle'); return; }
        const accountId = accountFilter === 'all' ? undefined : accountFilter;
        const rangeKey = { portfolioId, accountId, currency, ...historyRangeRequest };
        const cached = rangeCacheRef.current.get(rangeKey);
        setHistoryRangeState('loading');
        const result = cached
          ? cached
          : await fetchValuationRange(portfolioId, { accountId, currency, ...historyRangeRequest }, controller.signal);
        if (requestId !== accountDataSequence.current) return;
        if (!cached) rangeCacheRef.current.set(rangeKey, result);
        setAccountData(data); setHistoryRange(result); setHistoryRangeState('ready');
        if (!analysisAsOf && accountFilter !== 'all' && result.last?.asOf) setAnalysisAsOf(result.last.asOf);
      })
      .catch((requestError: unknown) => { if (!controller.signal.aborted && requestId === accountDataSequence.current) { setHistoryRangeState(requestError instanceof AccountDataApiError && requestError.code === 'ERR_ACCOUNT_RANGE_LIMIT' ? 'limit' : 'error'); } })
      .finally(() => controller.abort());
    return () => { controller.abort(); };
  }, [accountDataVersion, accountFilter, allocationCurrency, analysisAsOf, historyRangeRequest, portfolioId, rangeRefreshEpoch]);

  const handleRangeChange = useCallback((next: { start?: string; end?: string; granularity: 'daily' | 'monthly' }) => {
    setHistoryRangeRequest((current) => current.start === next.start && current.end === next.end && current.granularity === next.granularity ? current : next);
  }, []);

  const handleManualSelection = useCallback((selection: { accountId: string; asOf: string }) => {
    setPerformanceAccountId(selection.accountId);
    if (selection.asOf) setAnalysisAsOf(selection.asOf);
  }, []);

  const selectFile = useCallback((file: File) => {
    snapshotAbortRef.current?.abort();
    confirmKeyRef.current = null;
    setSelectedFile(file); setPreview(null); setError(null); setNotice(`Selected ${file.name}. Review the optional password, then preview the statement.`);
  }, []);

  useEffect(() => {
    if (!externalSelectedFile) return;
    selectFile(externalSelectedFile);
    onExternalFileConsumed?.();
  }, [externalSelectedFile, onExternalFileConsumed, selectFile]);

  const handleImport = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    selectFile(file);
  }, [selectFile]);

  const handlePreview = useCallback(async () => {
    if (!selectedFile) return;
    const requestId = ++snapshotSequence.current;
    snapshotAbortRef.current?.abort();
    const controller = new AbortController();
    snapshotAbortRef.current = controller;
    setBusy('uploading');
    setError(null);
    setNotice(null);
    try {
      const response = await previewNsdlStatement(portfolioId, selectedFile, password, controller.signal);
      if (requestId !== snapshotSequence.current || controller.signal.aborted) return;
      setPreview(response);
      setNotice('Review the statement details, then confirm import to save it.');
    } catch (requestError) {
      if (controller.signal.aborted || requestId !== snapshotSequence.current) return;
      setStatus(snapshotRef.current ? 'ready' : 'unavailable');
      setError(errorMessage(requestError));
    } finally {
      if (requestId === snapshotSequence.current) setBusy(null);
    }
  }, [password, portfolioId, selectedFile]);

  const handleConfirm = useCallback(async () => {
    if (!selectedFile || !preview) return;
    const requestId = ++snapshotSequence.current;
    snapshotAbortRef.current?.abort();
    const controller = new AbortController();
    snapshotAbortRef.current = controller;
    const idempotencyKey = confirmKeyRef.current || (confirmKeyRef.current = createNsdlIdempotencyKey());
    setBusy('uploading'); setError(null); setNotice(null);
    try {
      const response = await importNsdlStatement(portfolioId, selectedFile, password, preview.previewToken, controller.signal, idempotencyKey);
      if (requestId !== snapshotSequence.current || controller.signal.aborted) return;
      snapshotRef.current = response.snapshot; setSnapshot(response.snapshot); setAccountDataVersion((version) => version + 1); setStatus('ready'); setPreview(null); setSelectedFile(null); setPassword(''); confirmKeyRef.current = null;
      setNotice(response.status === 'duplicate' ? 'This statement was already imported. The saved snapshot is unchanged.' : 'Statement imported. Values below are dated to the statement.');
    } catch (requestError) {
      if (controller.signal.aborted || requestId !== snapshotSequence.current) return;
      setStatus(snapshotRef.current ? 'ready' : 'unavailable'); setError(errorMessage(requestError));
    } finally { if (requestId === snapshotSequence.current) setBusy(null); }
  }, [password, portfolioId, preview, selectedFile]);

  const handleSchwabFile = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null;
    event.target.value = '';
    schwabSequence.current += 1;
    schwabAbortRef.current?.abort();
    setSchwabFile(file); setSchwabPreview(null); setSchwabError(null);
    setSchwabAccountChoice(''); setSchwabOwnershipConfirmed(false); setSchwabIsoCurrency('');
  }, []);

  const handleSchwabPreview = useCallback(async () => {
    if (!schwabFile) return;
    const requestId = ++schwabSequence.current;
    schwabAbortRef.current?.abort();
    const controller = new AbortController();
    schwabAbortRef.current = controller;
    setSchwabBusy(true); setSchwabError(null); setSchwabPreview(null);
    try {
      const response = await previewSchwabStatement(portfolioId, schwabFile, controller.signal);
      if (controller.signal.aborted || requestId !== schwabSequence.current) return;
      setSchwabPreview(response);
    } catch (requestError) {
      if (controller.signal.aborted || requestId !== schwabSequence.current) return;
      if (requestError instanceof NsdlApiError && requestError.status === 403) onAccessRevoked?.();
      setSchwabError(errorMessage(requestError));
    } finally {
      if (requestId === schwabSequence.current) setSchwabBusy(false);
    }
  }, [onAccessRevoked, portfolioId, schwabFile]);

  const statementImportControl = <section className="card nsdl-import-card" aria-labelledby="nsdl-import-heading">
    <div className="flex items-start gap-3">
      <div className="rounded-xl bg-blue-500/10 text-blue-400 p-2"><FileUp className="w-5 h-5" aria-hidden="true" /></div>
      <div className="min-w-0 flex-1 space-y-1">
        <h2 id="nsdl-import-heading" className="font-bold text-theme-primary">Import an NSDL consolidated statement</h2>
        <p className="text-xs text-theme-secondary">PDF only. The file is used transiently; it is not shown or saved in the portfolio.</p>
        <div className="nsdl-import-controls">
          <label className="nsdl-control nsdl-button nsdl-button-primary"><FileUp className="w-4 h-4" aria-hidden="true" /><span>Choose PDF</span><input type="file" accept="application/pdf,.pdf" className="nsdl-file-input" onChange={handleImport} disabled={busy !== null} /></label>
          <label className="nsdl-password-field"><span id="nsdl-password-label">Optional statement password</span><input type="password" value={password} onChange={(event) => { setPassword(event.target.value); setPreview(null); confirmKeyRef.current = null; }} placeholder="Optional PDF password" aria-labelledby="nsdl-password-label" maxLength={128} className="nsdl-control nsdl-input" disabled={busy !== null} /></label>
          <button type="button" className="nsdl-control nsdl-button nsdl-button-secondary" onClick={() => void handlePreview()} disabled={!selectedFile || busy !== null}>{busy === 'uploading' ? 'Previewing…' : 'Preview statement'}</button>
        </div>
        {selectedFile && <p className="text-xs text-theme-secondary">Selected PDF: {selectedFile.name}</p>}
        {preview && <div className="nsdl-preview-card" data-testid="nsdl-import-preview"><p className="font-bold">Review before saving</p><p className="text-xs text-theme-secondary">Statement date {displayDate(preview.snapshot.asOfDate)} · {preview.snapshot.accounts.length} accounts · {preview.snapshot.holdings.length} holdings</p><p className="text-xs text-theme-secondary">Source accounts: {preview.sourceAccounts.map((account) => account.displayName).join(' · ')}</p><p className="text-xs text-theme-secondary">Totals: {preview.snapshot.totalsByCurrency.map((total) => moneyValue(total.statementValue, total.currency, isPrivacyShieldActive)).join(' · ') || 'Unavailable'}</p><button type="button" className="nsdl-control nsdl-button nsdl-button-primary mt-3" onClick={() => void handleConfirm()} disabled={busy !== null}>Confirm import</button></div>}
      </div>
    </div>
  </section>;

  const schwabReviewControl = <section className="card nsdl-import-card space-y-3" aria-labelledby="schwab-review-heading" data-testid="schwab-review-only">
    <div className="flex items-start gap-3">
      <div className="rounded-xl bg-blue-500/10 text-blue-400 p-2"><FileUp className="w-5 h-5" aria-hidden="true" /></div>
      <div className="min-w-0 flex-1 space-y-2">
        <h2 id="schwab-review-heading" className="font-bold text-theme-primary">Review a Schwab monthly statement</h2>
        <p className="text-xs text-theme-secondary">This reads one supported PDF for review. It does not add a holding or change the NSDL snapshot.</p>
        <div className="nsdl-import-controls">
          <label className="nsdl-control nsdl-button nsdl-button-secondary"><FileUp className="w-4 h-4" aria-hidden="true" /><span>Choose Schwab PDF</span><input type="file" accept="application/pdf,.pdf" className="nsdl-file-input" onChange={handleSchwabFile} disabled={schwabBusy} /></label>
          <button type="button" className="nsdl-control nsdl-button nsdl-button-secondary" onClick={() => void handleSchwabPreview()} disabled={!schwabFile || schwabBusy}>{schwabBusy ? 'Reading PDF…' : 'Preview Schwab statement'}</button>
        </div>
        {schwabFile && <p className="text-xs text-theme-secondary">One PDF selected. File name and bytes stay out of the response.</p>}
        {schwabError && <p role="alert" className="text-sm text-red-100">{schwabError}</p>}
        {schwabPreview && <div className="nsdl-preview-card space-y-3" data-testid="schwab-review-only-preview">
          <div><p className="font-bold">Review only — this PDF</p><p className="text-xs text-theme-secondary">{schwabReviewAccountLabel(schwabPreview.sourceAccountLabel, isPrivacyShieldActive, PRIVACY_MASK)} · statement date {displayDate(schwabPreview.asOfDate)}</p></div>
          <p className="text-xs text-theme-secondary">Printed currency evidence: “{schwabPreview.printedCurrencyGlyph}” on price/value columns. ISO currency: unknown until you confirm it. No currency conversion is applied.</p>
          <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4" aria-label="Schwab statement totals">
            {[['Cash', schwabPreview.cashValue], ['Equities', schwabPreview.equityValue], ['Funds', schwabPreview.fundValue], ['Statement total', schwabPreview.totalValue]].map(([label, value]) => <p key={label}><span className="block text-xs text-theme-secondary">{label}</span><strong>{schwabReviewAmount(value, schwabPreview.printedCurrencyGlyph, isPrivacyShieldActive, PRIVACY_MASK)}</strong></p>)}
          </div>
          <div className="overflow-x-auto"><table className="w-full text-sm"><caption className="sr-only">Three Schwab positions in this statement</caption><thead><tr><th scope="col" className="text-left">Position</th><th scope="col" className="text-right">Quantity</th><th scope="col" className="text-right">Printed price</th><th scope="col" className="text-right">Market value</th></tr></thead><tbody>{schwabPreview.positions.map((position) => <tr key={`${position.section}:${position.symbol}`}><th scope="row" className="text-left">{position.symbol} <span className="text-xs text-theme-secondary">{position.section}</span></th><td className="text-right tabular-nums">{position.quantity}</td><td className="text-right tabular-nums">{schwabReviewAmount(position.printedPrice, schwabPreview.printedCurrencyGlyph, isPrivacyShieldActive, PRIVACY_MASK)}</td><td className="text-right tabular-nums">{schwabReviewAmount(position.marketValue, schwabPreview.printedCurrencyGlyph, isPrivacyShieldActive, PRIVACY_MASK)}</td></tr>)}</tbody></table></div>
          <fieldset className="space-y-2 border-t border-theme pt-3"><legend className="font-bold">Account choice and ownership</legend>
            <label className="flex items-start gap-2 text-sm"><input type="radio" name="schwab-account-choice" value="separate" checked={schwabAccountChoice === 'separate'} onChange={() => setSchwabAccountChoice('separate')} /><span>Add this as a separate Schwab account in the selected portfolio.</span></label>
            <label className="flex items-start gap-2 text-sm"><input type="radio" name="schwab-account-choice" value="unresolved" checked={schwabAccountChoice === 'unresolved'} onChange={() => setSchwabAccountChoice('unresolved')} /><span>I cannot confirm the account mapping; keep this at review only.</span></label>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={schwabOwnershipConfirmed} onChange={(event) => setSchwabOwnershipConfirmed(event.target.checked)} /><span>I confirm that I own or am authorized to include this Schwab account in this portfolio.</span></label>
            <label className="block text-sm">ISO currency for the printed “$” evidence<select aria-label="Confirmed ISO currency for Schwab statement" className="nsdl-control nsdl-input mt-1 block" value={schwabIsoCurrency} onChange={(event) => setSchwabIsoCurrency(event.target.value)}><option value="">Select only after confirming</option><option value="USD">USD — US dollar</option><option value="CAD">CAD — Canadian dollar</option><option value="AUD">AUD — Australian dollar</option><option value="NZD">NZD — New Zealand dollar</option><option value="SGD">SGD — Singapore dollar</option><option value="HKD">HKD — Hong Kong dollar</option><option value="GBP">GBP — pound sterling</option><option value="EUR">EUR — euro</option><option value="JPY">JPY — Japanese yen</option><option value="CHF">CHF — Swiss franc</option></select></label>
          </fieldset>
          <p role="alert" className="text-sm text-amber-100">{schwabPreview.overlapWarning} Same-symbol positions are not merged with NSDL. No duplicate check exists for prior Schwab imports.</p>
          <p role="status" className="text-xs text-theme-secondary">{schwabAccountChoice === 'separate' && schwabOwnershipConfirmed && schwabIsoCurrency ? `Review choices selected: separate account · ${schwabIsoCurrency}.` : 'Choose the account path, verify ownership, and confirm the ISO currency before a future import review.'} These choices are local to this page and are not saved. Import is unavailable until a durable dated-statement contract exists.</p>
        </div>}
      </div>
    </div>
  </section>;

  const coverage = snapshot?.coverage;
  const accountNamesByScope = useMemo(() => {
    const labels = new Map((snapshot?.accounts || []).map((account) => [account.accountScopeId, account.maskedLabel]));
    (accountData?.accounts || []).forEach((account) => labels.set(account.account_id, account.user_alias || account.source_name || account.institution));
    return labels;
  }, [accountData, snapshot]);
  const accountLabels = useMemo(() => [...accountNamesByScope.entries()].map(([id, label]) => ({ id, label })).sort((left, right) => left.label.localeCompare(right.label) || left.id.localeCompare(right.id)), [accountNamesByScope]);
  const combinedHoldings = useMemo(() => composeCombinedHoldings(snapshot, accountData, valuation), [accountData, snapshot, valuation]);
  const selectedHolding = detailHoldingId ? combinedHoldings.find((holding) => holding.holdingId === detailHoldingId) || null : null;
  const holdingFilterContext = (): NonNullable<NsdlPortfolioNavigation['returnContext']> => ({ accountFilter, allocationCurrency, sourceFilter, search, holdingGroup, sortDirection });
  const openHoldingDetail = (holding: CombinedHolding) => {
    const context = holdingFilterContext();
    setDetailReturnContext(context);
    setDetailHoldingId(holding.holdingId);
    setAccountFilter(holding.accountScopeId);
    setSourceFilter('all');
    setSearch('');
  };
  const returnFromHoldingDetail = () => {
    if (detailReturnContext) {
      setAccountFilter(detailReturnContext.accountFilter);
      setAllocationCurrency(detailReturnContext.allocationCurrency);
      setSourceFilter(detailReturnContext.sourceFilter);
      setSearch(detailReturnContext.search);
      setHoldingGroup(detailReturnContext.holdingGroup);
      setSortDirection(detailReturnContext.sortDirection);
    }
    setDetailHoldingId('');
    setDetailReturnContext(null);
  };
  const returnFromAccountHoldings = () => {
    const destination = workspaceReturn?.returnSection || 'overview';
    const context = workspaceReturn?.returnContext;
    if (context) {
      setAccountFilter(context.accountFilter);
      setAllocationCurrency(context.allocationCurrency);
      setSourceFilter(context.sourceFilter);
      setSearch(context.search);
      setHoldingGroup(context.holdingGroup);
      setSortDirection(context.sortDirection);
    }
    setWorkspaceReturn(null);
    onNavigateWorkspace?.(destination, destination === 'activity' ? { activityContext: workspaceReturn?.activityContext } : null);
  };
  const filteredHoldings = useMemo(() => {
    if (!combinedHoldings.length) return [];
    const query = search.trim().toLowerCase();
    return combinedHoldings.filter((holding) => {
      const matchesAccount = accountFilter === 'all' || holding.accountScopeId === accountFilter;
      const matchesSource = sourceFilter === 'all' || holding.source.toLowerCase() === sourceFilter;
      const matchesSearch = !query || `${holding.instrumentName} ${holding.isin || ''} ${accountNamesByScope.get(holding.accountScopeId) || 'Private account'} ${holding.instrumentType} ${holding.currency || ''}`.toLowerCase().includes(query);
      const matchesDetail = !detailHoldingId || holding.holdingId === detailHoldingId;
      return matchesAccount && matchesSource && matchesSearch && matchesDetail;
    }).sort((left, right) => {
      const direction = sortDirection === 'asc' ? 1 : -1;
      const leftKey = `${accountNamesByScope.get(left.accountScopeId) || left.accountScopeId}\u0000${left.instrumentType}\u0000${left.currency || ''}\u0000${left.instrumentName}\u0000${left.holdingId}`;
      const rightKey = `${accountNamesByScope.get(right.accountScopeId) || right.accountScopeId}\u0000${right.instrumentType}\u0000${right.currency || ''}\u0000${right.instrumentName}\u0000${right.holdingId}`;
      return direction * leftKey.localeCompare(rightKey);
    });
  }, [accountFilter, accountNamesByScope, combinedHoldings, detailHoldingId, search, sortDirection, sourceFilter]);
  const groupedHoldings = useMemo(() => {
    const groups = new Map<string, CombinedHolding[]>();
    filteredHoldings.forEach((holding) => {
      const key = holdingGroup === 'account' ? accountNamesByScope.get(holding.accountScopeId) || 'Private account' : holdingGroup === 'asset-type' ? holding.instrumentType : holding.currency || 'Currency unavailable';
      groups.set(key, [...(groups.get(key) || []), holding]);
    });
    return [...groups.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([label, holdings]) => {
      const subtotalByCurrency = new Map<string, number>();
      holdings.forEach((holding) => {
        const value = includedHoldingValue(holding);
        const currency = holding.valuation?.currency || holding.currency;
        if (value === null || !currency) return;
        subtotalByCurrency.set(currency, (subtotalByCurrency.get(currency) || 0) + value);
      });
      return { id: `${holdingGroup}\u0000${label}`, label, holdings, subtotals: [...subtotalByCurrency.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([currency, value]) => ({ currency, value })) };
    });
  }, [accountNamesByScope, filteredHoldings, holdingGroup]);
  const totalText = snapshot && snapshot.coverage.complete && snapshot.totalsByCurrency.length > 0
    ? snapshot.totalsByCurrency.map((total) => moneyValue(total.statementValue, total.currency, isPrivacyShieldActive)).join(' · ')
    : 'Unavailable while statement coverage is incomplete';
  // Keep the visible analysis control and every dated valuation/performance
  // request on the same precedence. Readiness has its own isolated scope.
  const currentAsOf = analysisAsOf || readinessAsOf;
  const scopedAccountData = accountData && accountFilter !== 'all' ? { ...accountData, accounts: accountData.accounts.filter((account) => account.account_id === accountFilter), openingHoldings: accountData.openingHoldings.filter((holding) => !holding.voided && holding.account_id === accountFilter), cashFlows: accountData.cashFlows.filter((flow) => !flow.voided && flow.account_id === accountFilter) } : accountData && { ...accountData, openingHoldings: accountData.openingHoldings.filter((holding) => !holding.voided), cashFlows: accountData.cashFlows.filter((flow) => !flow.voided) };
  const scope = scopedAccountData ? canonicalScope(scopedAccountData) : null;
  const historyCurrency = allocationCurrency || (accountFilter !== 'all' ? accountData?.accounts.find((account) => account.account_id === accountFilter)?.currency : '') || '';
  const selectedAccountCurrency = accountFilter === 'all' ? '' : accountData?.accounts.find((account) => account.account_id === accountFilter)?.currency || '';
  const historyScope = scope && historyCurrency ? { ...scope, holdingIds: new Set((scopedAccountData?.openingHoldings || []).filter((holding) => holding.currency === historyCurrency).map((holding) => holding.fact_id)), holdingAccounts: new Map((scopedAccountData?.openingHoldings || []).filter((holding) => holding.currency === historyCurrency).map((holding) => [holding.fact_id, holding.account_id])) } : null;
  const rangePointsValid = Boolean(historyRange && historyRange.scope.currency === historyCurrency && historyRange.scope.accountId === (accountFilter === 'all' ? null : accountFilter) && historyRange.points.every((point) => /^\d{4}-\d{2}-\d{2}$/.test(point.asOf) && Number.isFinite(Number(point.calculatedValue))));
  const historyResponsesComplete = Boolean(historyScope && rangePointsValid);
  const syntheticComplete = historyResponsesComplete && Boolean(scope && valuation && hasExactCalculatedValuation(valuation, currentAsOf, scope) && performance?.asOf === currentAsOf && performance.coverage.historyComplete && performance.gain.status === 'CALCULATED' && performance.gain.value !== undefined && performance.xirr.status === 'CALCULATED' && performance.xirr.valuePct !== undefined);
  const currentRows = syntheticComplete && valuation ? valuation.holdings.filter((holding) => holding.status === 'CALCULATED' && holding.currentValue !== undefined) : [];
  const syntheticTotal = calculatedValue(currentRows);
  const includedAccountAllocations = useMemo((): AccountAllocation[] => {
    const perCurrency = new Map<string, Map<string, { id: string; label: string; value: number }>>();
    combinedHoldings.forEach((holding) => {
      const value = includedHoldingValue(holding);
      const currency = holding.valuation?.currency || holding.currency;
      if (value === null || !currency) return;
      const accounts = perCurrency.get(currency) || new Map<string, { id: string; label: string; value: number }>();
      const account = accounts.get(holding.accountScopeId) || { id: holding.accountScopeId, label: accountNamesByScope.get(holding.accountScopeId) || 'Private account', value: 0 };
      account.value += value;
      accounts.set(holding.accountScopeId, account);
      perCurrency.set(currency, accounts);
    });
    return [...perCurrency.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([currency, accounts]) => {
      const entries = [...accounts.values()].sort((left, right) => right.value - left.value || left.label.localeCompare(right.label));
      return { currency, total: entries.reduce((sum, account) => sum + account.value, 0), accounts: entries };
    });
  }, [accountNamesByScope, combinedHoldings]);
  const visualHoldings = useMemo<VisualHoldingMetadata[]>(() => combinedHoldings.map((holding) => ({ holdingId: holding.holdingId, accountScopeId: holding.accountScopeId, instrumentName: holding.instrumentName, instrumentType: holding.instrumentType, currency: holding.currency, source: holding.source })), [combinedHoldings]);
  const comfortHoldings = combinedHoldings.filter((holding) => accountFilter === 'all' || holding.accountScopeId === accountFilter);
  const singleStatementTotal = snapshot?.coverage.complete && snapshot.totalsByCurrency.length === 1 ? snapshot.totalsByCurrency[0] : null;
  const comfortProjection: DadModeProjection = { holdings: comfortHoldings, valuation, portfolioValuation: syntheticComplete ? String(syntheticTotal) : null, statementValue: singleStatementTotal?.statementValue || null, statementCurrency: singleStatementTotal?.currency || null, statementDate: snapshot?.asOfDate || null, performance, complete: syntheticComplete, currentAsOf, insufficientReason: 'More dated source history is needed before additional analysis is available.' };
  const displayedPerformance = performanceAccountId ? accountPerformance : performance;
  const overviewCurrency = allocationCurrency || '';
  const valuationSummaries = (valuation?.summaryByCurrency || []).filter((summary) => !overviewCurrency || summary.currency === overviewCurrency);
  const explainReason = (reason: string) => ({ MISSING_HISTORY: 'Missing dated cash flows or history; add the relevant flows in Cash flows.', MISSING_PRICE: 'No dated price is available for this holding; review Holdings coverage.', NON_POSITIVE_TERMINAL_VALUE: 'A positive terminal value is unavailable for this date.', RECONCILIATION_REQUIRED: 'A manual/source overlap must be corrected before returns can be calculated.', MIXED_CURRENCY: 'This scope contains multiple currencies; returns remain separated by currency.', SAME_DAY_ONLY: 'At least two distinct dated observations are required.' } as Record<string, string>)[reason] || reason;
  const nextActionHash = (reason: string) => reason === 'MISSING_HISTORY' ? '#cash-flows' : reason === 'RECONCILIATION_REQUIRED' ? '#holdings' : '#accounts';
  void displayedPerformance;
  void explainReason;
  void nextActionHash;
  const valuationMetadata = valuation as (ValuationResult & { calculationVersion?: unknown; inputDigest?: unknown }) | null;
  const performanceMetadata = performance as (PerformanceResult & { calculationVersion?: unknown; inputDigest?: unknown }) | null;
  const calculationVersion = typeof valuationMetadata?.calculationVersion === 'string' ? valuationMetadata.calculationVersion : typeof performanceMetadata?.calculationVersion === 'string' ? performanceMetadata.calculationVersion : null;
  const inputDigest = typeof valuationMetadata?.inputDigest === 'string' ? valuationMetadata.inputDigest : typeof performanceMetadata?.inputDigest === 'string' ? performanceMetadata.inputDigest : null;
  const comfortVoiceScopeKey = [portfolioId, accountFilter, currentAsOf, calculationVersion || '', inputDigest || ''].join('\u0000');
  if (comfortVoiceScopeEpoch.current.key !== comfortVoiceScopeKey) comfortVoiceScopeEpoch.current = { key: comfortVoiceScopeKey, value: comfortVoiceScopeEpoch.current.value + 1 };
  const comfortVoiceScope = useMemo(() => currentAsOf
    ? createComfortVoiceScope({ portfolioId, selectedAccountScope: accountFilter, asOf: currentAsOf, calculationVersion, inputDigest, viewEpoch: comfortVoiceScopeEpoch.current.value })
    : null, [accountFilter, calculationVersion, comfortVoiceScopeKey, currentAsOf, inputDigest, portfolioId]);

  if (accessRevoked) return <div className="nsdl-view" data-testid="nsdl-access-revoked"><section className="card border border-amber-500/50 p-8 text-center" role="alert"><h1 className="font-bold text-theme-primary">Helping Dad access revoked</h1><p className="text-sm text-theme-secondary mt-2">The server denied the next request. Exit Helping Dad to return to an authorized personal scope.</p></section></div>;
  if (comfortView) return <DadModeView projection={comfortProjection} accountLabels={accountLabels} selectedAccountId={accountFilter} onAccountFilterChange={setAccountFilter} localVoiceMode={comfortVoiceTestMode} comfortVoiceScope={comfortVoiceScope} />;

  const readinessItems = projectPortfolioReadiness({ accounts: readinessAccounts, selectedAccountId: readinessAccountId, scope: readinessScope, intendedScope: readinessIntendedScope, factsState: readinessFactsState, metricsState: readinessMetricsState, valuation: readinessValuation, performance: readinessPerformance });
  if (workspaceSection === 'readiness') return <div className="nsdl-view"><PortfolioReadinessPanel accounts={readinessAccounts} selectedAccountId={readinessAccountId} onSelectAccount={setReadinessAccountId} items={readinessItems} factsState={readinessFactsState} metricsState={readinessMetricsState} supportCopy={readinessSupportCopy} onRetryFacts={loadReadinessFacts} onRetryMetrics={() => setReadinessMetricsRetry((value) => value + 1)} masked={isPrivacyShieldActive} onAction={(item) => onNavigateWorkspace?.(item.nextAction, { accountId: item.accountId, returnSection: 'readiness' })} /></div>;
  if (workspaceSection === 'activity') return <div className="nsdl-view"><section className="card portfolio-surface" aria-label="Portfolio activity"><p className="nsdl-section-eyebrow">Server activity</p><h1>Activity</h1><p className="text-sm text-theme-secondary">Only the server-supplied actor identity and operation are shown.</p>{familyActivityState === 'loading' && <p role="status">Loading server activity…</p>}{familyActivityState === 'denied' && <div role="alert"><p>Activity access was denied or revoked. No other portfolio was tried.</p></div>}{familyActivityState === 'unavailable' && <div role="alert"><p>Server activity is unavailable right now. Refresh to retry.</p></div>}{familyActivityState === 'ready' && (familyActivity.length ? <div className="portfolio-activity-list">{familyActivity.map((event) => <article key={`${event.actor_uid}:${event.operation}:${event.recorded_at}`}><strong>{event.actor_uid}</strong><span>{event.operation}</span></article>)}</div> : <p>No server activity is available for this scope.</p>)}</section></div>;
  if (workspaceSection === 'accounts' || workspaceSection === 'cash-flows' || workspaceSection === 'statements') {
    const accounts = accountData?.accounts || [];
    const cashFlows = accountData?.cashFlows || [];
    return <div className="nsdl-view" data-testid={`nsdl-${workspaceSection}-view`}>
      <header className="nsdl-hero"><p className="nsdl-decorative-label text-[11px] uppercase tracking-[0.2em] text-blue-600 font-bold">Private workspace</p><h1 className="text-2xl sm:text-3xl font-black text-theme-primary">{workspaceSection === 'accounts' ? 'Accounts' : workspaceSection === 'cash-flows' ? 'Cash flows' : 'Statements'}</h1><p className="text-sm text-theme-secondary">{workspaceSection === 'accounts' ? 'Saved accounts and their protected manual facts.' : workspaceSection === 'cash-flows' ? 'Dated contributions, withdrawals, dividends, and transfers.' : 'Imported statement snapshots and transient PDF import.'}</p>{(navigationContext?.returnSection === 'activity' || navigationContext?.returnSection === 'readiness') && <button type="button" className="nsdl-control nsdl-button nsdl-button-secondary" onClick={() => onNavigateWorkspace?.(navigationContext.returnSection!, navigationContext.returnSection === 'activity' ? { activityContext: navigationContext.activityContext } : null)}>Back to {navigationContext.returnSection === 'activity' ? 'Activity' : 'Readiness'}</button>}</header>
      {workspaceSection === 'accounts' && <section className="card nsdl-workspace-panel"><h2 className="text-lg font-black text-theme-primary">Saved accounts</h2>{accounts.length ? <div className="nsdl-record-list">{accounts.map((account) => <article key={account.account_id}><strong>{account.user_alias || account.source_name || account.institution}</strong><span>{account.institution} · {account.account_type}</span><small>Identifier · {account.account_id.slice(0, 4)}••••</small><button type="button" className="nsdl-control nsdl-button nsdl-button-secondary mt-2" onClick={() => onNavigateWorkspace?.('holdings', { accountId: account.account_id, returnSection: 'accounts' })}>View account holdings</button></article>)}</div> : <p className="text-sm text-theme-secondary">No saved accounts yet. Add one below to begin recording manual facts.</p>}</section>}
      {workspaceSection === 'cash-flows' && <section className="card nsdl-workspace-panel"><h2 className="text-lg font-black text-theme-primary">Saved cash flows</h2>{cashFlows.length ? <div className="nsdl-record-list">{cashFlows.map((flow) => { const account = accounts.find((item) => item.account_id === flow.account_id); return <article key={flow.fact_id}><strong>{account?.user_alias || account?.source_name || account?.institution || 'Private account'} · {flow.flow_type}</strong><span>{displayDate(flow.effective_date)} · {isPrivacyShieldActive ? PRIVACY_MASK : formatMoney(flow.amount, flow.currency)}</span></article>; })}</div> : <p className="text-sm text-theme-secondary">No saved cash flows yet. Select an account below to add a dated row.</p>}</section>}
      {workspaceSection === 'statements' && <>
        <section className="card nsdl-workspace-panel">
          <h2 className="text-lg font-black text-theme-primary">Saved statement snapshot</h2>
          {snapshot ? <>
            <p className="text-sm text-theme-secondary">Statement date: {displayDate(snapshot.asOfDate)} · {snapshot.accounts.length} accounts</p>
            {presentation && <p className="text-sm text-theme-secondary">Synthetic summary-only sample — no actual statement import. {snapshot.accounts.map((account) => accountNamesByScope.get(account.accountScopeId) || account.maskedLabel).join(' · ')} · Summary value {isPrivacyShieldActive ? PRIVACY_MASK : snapshot.totalsByCurrency.map((total) => formatMoney(total.statementValue || '', total.currency)).join(' · ') || 'unavailable'} (not reconciled).</p>}
            {!snapshot.coverage.complete && <p className="text-sm text-amber-200">Statement coverage is incomplete; this summary is not a reconciled portfolio total.</p>}
          </> : <p className="text-sm text-theme-secondary">No statement imported yet. Open Statements to choose an NSDL PDF; it is used transiently.</p>}
        </section>
        {error && <div role="alert" className="card border border-red-500/50 p-4 text-sm text-red-100">{error}</div>}
        {notice && <div role="status" className="card border border-emerald-500/50 p-4 text-sm text-emerald-100">{notice}</div>}
        {statementImportControl}
        {schwabReviewControl}
      </>}
      {(workspaceSection === 'accounts' || workspaceSection === 'cash-flows') && <ManualEntryPanel portfolioId={portfolioId} initialAccountId={navigationContext?.accountId} entryMode={workspaceSection === 'cash-flows' ? 'cash-flow' : 'account'} onSelectionChange={handleManualSelection} onDataChange={handleAccountDataChange} />}
    </div>;
  }

  return (
    <div className="nsdl-view" data-testid="nsdl-portfolio-view" data-active-tab={activeTab}>
      <header className="nsdl-hero">
        {scopeLabel && <p className="nsdl-demo-label" data-testid="server-scope-label">{scopeLabel}</p>}
        {presentation && <p className="nsdl-demo-label" data-testid="synthetic-presentation-label">{presentation.label}</p>}
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-black text-theme-primary tracking-tight">{activeTab === 'overview' ? 'Overview' : activeTab === 'holdings' ? 'Holdings' : 'Performance'}</h1>
            <p className="text-sm text-theme-secondary mt-1">{scopeLabel || 'Private portfolio'} · {allocationCurrency || 'All available currencies'} · values as of {currentAsOf ? displayDate(currentAsOf) : snapshot?.asOfDate ? displayDate(snapshot.asOfDate) : 'date unavailable'}</p>
          </div>
          <button type="button" onClick={() => { rangeCacheRef.current.clear(); setRangeRefreshEpoch((current) => current + 1); void runRequest('refreshing'); }} disabled={busy !== null} className="nsdl-control nsdl-button nsdl-button-secondary" aria-label="Refresh private NSDL portfolio">
            <RefreshCw className={`w-4 h-4 ${busy === 'refreshing' ? 'animate-spin' : ''}`} /> Refresh
          </button>
        </div>
      </header>

      <div className="nsdl-context-nav" aria-label="Current destination"><span className="nsdl-context-meta">{snapshot ? `Statement date · ${displayDate(snapshot.asOfDate)}` : 'Statement date · unavailable'}</span></div>

      {activeTab === 'overview' && <section className="card nsdl-scope-controls" aria-label="Overview scope"><label>Account<select aria-label="Overview account scope" value={accountFilter} onChange={(event) => { const next = event.target.value; allocationChoiceMadeRef.current = true; setAccountFilter(next); if (next !== 'all') setAllocationCurrency(accountData?.accounts.find((account) => account.account_id === next)?.currency || ''); }} className="nsdl-control nsdl-input mt-1"><option value="all">All accounts</option>{accountLabels.map((account) => <option key={account.id} value={account.id}>{account.label}</option>)}</select></label><label>Allocation currency<select aria-label="Allocation currency" value={allocationCurrency} onChange={(event) => { allocationChoiceMadeRef.current = true; setAllocationCurrency(event.target.value); }} className="nsdl-control nsdl-input mt-1"><option value="">All available currencies</option>{includedAccountAllocations.map((item) => <option key={item.currency} value={item.currency}>{item.currency}</option>)}</select></label><p className="text-xs text-theme-secondary">Values never combine INR and USD; choose a currency to inspect one scope.</p></section>}
      {activeTab === 'overview' && <section className="nsdl-overview-grid" aria-label="Portfolio overview metrics">
        <article className="nsdl-metric-card nsdl-portfolio-value-card" data-testid="portfolio-value-by-currency"><p>Portfolio value</p>{valuationSummaries.length ? <div>{valuationSummaries.map((summary) => <strong key={summary.currency} className="financial-value">{summary.currency} · {isPrivacyShieldActive ? PRIVACY_MASK : formatMoney(summary.totalIncludedValue, summary.currency)}</strong>)}</div> : <strong className="financial-value">Unavailable</strong>}<span>Included dated source components, shown separately by currency.</span></article>
        <article className="nsdl-metric-card"><p>Investments</p><strong className="financial-value">{combinedHoldings.filter((holding) => accountFilter === 'all' || holding.accountScopeId === accountFilter).length || 'Unavailable'}</strong><span>{accountFilter === 'all' ? 'Statement and manual positions' : 'Positions in this selected account'}</span></article>
      </section>}

      {activeTab === 'overview' && <PortfolioVisualsPanel portfolioId={portfolioId} historyValuations={historyValuations} rangeResult={historyRange} rangePoints={historyRange?.points} rangeState={historyRangeState} onRangeChange={handleRangeChange} valuation={valuation} performance={performance} performanceContext={performanceContext} performanceValuation={performanceValuation} performanceValuationContext={performanceValuationContext} holdings={visualHoldings} accountFilter={accountFilter} currency={historyCurrency} selectedAccountCurrency={selectedAccountCurrency} asOf={currentAsOf} historyComplete={historyResponsesComplete} accountLabels={accountNamesByScope} isPrivacyShieldActive={isPrivacyShieldActive} formatMoney={(value, currency) => formatMoney(value, currency)} formatDate={displayDate} formatPercent={formatPercent} onNavigateWorkspace={(destination) => onNavigateWorkspace?.(destination, { returnSection: 'overview', returnContext: holdingFilterContext() })} />}

      {activeTab === 'overview' && <section className="card nsdl-value-components" aria-label="Dated value components">
        <div><p className="nsdl-section-eyebrow">Dated value components</p><h2>By currency and source</h2></div>
        {valuationSummaries.length ? <div className="nsdl-value-component-list">{valuationSummaries.map((summary) => <article key={summary.currency}>
          <strong>{summary.currency}</strong>
          <span>Included value {isPrivacyShieldActive ? PRIVACY_MASK : formatMoney(summary.totalIncludedValue, summary.currency)} · combines the compatible dated components below.</span>
          <span>Manual calculated value {summary.calculatedAsOf ? `as of ${displayDate(summary.calculatedAsOf)}` : 'unavailable'} · {isPrivacyShieldActive ? PRIVACY_MASK : formatMoney(summary.calculatedValue, summary.currency)}</span>
          <span>Statement observation {summary.statementAsOf ? `as of ${displayDate(summary.statementAsOf)}` : 'unavailable'} · {isPrivacyShieldActive ? PRIVACY_MASK : formatMoney(summary.statementValue, summary.currency)}</span>
          <small>Currencies remain separate; cross-currency totals are not shown.{summary.excludedForReconciliationCount ? ` ${summary.excludedForReconciliationCount} manual holding${summary.excludedForReconciliationCount === 1 ? '' : 's'} excluded pending reconciliation.` : ''}</small>
          {/* Currencies are shown separately; no FX conversion is applied. */}
        </article>)}</div> : <p className="text-sm text-theme-secondary">Dated value components appear after authoritative valuation data is available.</p>}
      </section>}

      {activeTab === 'overview' && <section className="card portfolio-overview-entry" aria-label="Portfolio data tools"><div><p className="nsdl-section-eyebrow">Data tools</p><h2>Readiness and saved activity</h2><p className="text-xs text-theme-secondary">See what each account proves and review persisted manual changes.</p></div><label className="text-xs text-theme-secondary">Readiness account<select aria-label="Overview readiness account" className="nsdl-control nsdl-input mt-1" value={readinessAccountId} onChange={(event) => setReadinessAccountId(event.target.value)}><option value="">Select a saved account</option>{readinessAccounts.map((account) => <option key={account.accountId} value={account.accountId}>{account.label}</option>)}</select></label><div className="flex flex-wrap gap-2"><span className="text-xs text-theme-secondary">{readinessItems.find((item) => item.accountId === readinessAccountId)?.message || 'Readiness is checked per account.'}</span><button type="button" className="nsdl-control nsdl-button nsdl-button-secondary" onClick={() => onNavigateWorkspace?.('readiness')}>Open readiness</button><button type="button" className="nsdl-control nsdl-button nsdl-button-secondary" onClick={() => onNavigateWorkspace?.('activity')}>Open activity</button></div></section>}

      {activeTab === 'overview' && <section className="nsdl-analysis-grid" aria-label="Portfolio analysis coverage">
        <article className="card nsdl-analysis-card">
          <div><p className="nsdl-section-eyebrow">Imported statement · whole portfolio</p><h2>{snapshot ? `Imported ${displayDate(snapshot.asOfDate)}` : 'No statement imported'}</h2></div>
          {snapshot ? <details><summary>Show printed statement context</summary><p>{snapshot.coverage.complete ? `Whole-portfolio printed statement values: ${snapshot.totalsByCurrency.map((total) => isPrivacyShieldActive ? PRIVACY_MASK : formatMoney(total.statementValue, total.currency)).join(' · ')}.` : 'Statement coverage is incomplete. Printed values are source detail, not a portfolio allocation.'}</p></details> : <p>Statement import and source coverage are available in Statements.</p>}
        </article>
      </section>}

      {activeTab === 'overview' && <div className="nsdl-privacy-status" role="status" aria-label="Privacy status">
        <span className={`nsdl-privacy-badge ${isPrivacyShieldActive ? 'is-active' : 'is-inactive'}`}><ShieldCheck className="w-3.5 h-3.5" aria-hidden="true" /> Hide amounts {isPrivacyShieldActive ? 'on' : 'off'}</span>
        <span>Calculated performance appears only with authoritative complete history; no client-side or intraday return estimate is introduced.</span>
      </div>}

      {activeTab === 'overview' && statementImportControl}
      {error && <div role="alert" className="rounded-xl border border-amber-500/40 bg-amber-500/10 text-amber-200 p-4 text-sm flex items-start gap-3"><AlertCircle className="w-5 h-5 shrink-0" aria-hidden="true" /><span>{error}</span></div>}
      {notice && <div role="status" className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-emerald-200 p-4 text-sm flex items-start gap-3"><CheckCircle2 className="w-5 h-5 shrink-0" aria-hidden="true" /><span>{notice}</span></div>}

      {status === 'loading' && <div role="status" aria-live="polite" className="card border border-theme p-8 text-center text-theme-secondary"><Loader2 className="w-6 h-6 animate-spin mx-auto mb-3" aria-hidden="true" />Loading your private snapshot…</div>}
      {status === 'unavailable' && !snapshot && <div className="card border border-theme p-8 text-center"><p className="font-bold text-theme-primary">Private portfolio unavailable</p><p className="text-sm text-theme-secondary mt-2">No empty data is shown when storage cannot be reached. Refresh to retry.</p></div>}
      {status === 'denied' && !snapshot && <div className="card border border-theme p-8 text-center" role="alert"><p className="font-bold text-theme-primary">Portfolio access denied</p><p className="text-sm text-theme-secondary mt-2">This portfolio is denied or access was revoked. No other portfolio was tried.</p></div>}
      {status === 'revoked' && !snapshot && <div className="card border border-theme p-8 text-center" role="alert"><p className="font-bold text-theme-primary">Portfolio access revoked</p><p className="text-sm text-theme-secondary mt-2">Return to an authorized personal scope to continue.</p></div>}
      {status === 'empty' && !snapshot && <div className="card border border-theme p-8 text-center"><p className="font-bold text-theme-primary">No statement imported yet</p><p className="text-sm text-theme-secondary mt-2">Choose an NSDL PDF on the Statements page. Your first successful import will appear here with its statement date and coverage.</p></div>}

      {activeTab === 'holdings' && combinedHoldings.length > 0 && (
        <section className="space-y-4" aria-label="Combined holdings">
          {detailHoldingId && <div className="card border border-theme p-3 flex flex-wrap items-center justify-between gap-3" role="status"><span><strong>Holding detail</strong> · this view keeps the selected account and shows one holding.</span><button type="button" className="nsdl-control nsdl-button nsdl-button-secondary" onClick={returnFromHoldingDetail}>Back to filtered holdings</button></div>}
          {!detailHoldingId && workspaceReturn?.returnSection && <div className="card border border-theme p-3 flex flex-wrap items-center justify-between gap-3" role="status"><span><strong>Account holdings</strong> · the account filter came from {workspaceReturn.returnSection === 'accounts' ? 'Accounts' : workspaceReturn.returnSection === 'activity' ? 'Activity' : workspaceReturn.returnSection === 'readiness' ? 'Readiness' : 'Overview'}.</span><button type="button" className="nsdl-control nsdl-button nsdl-button-secondary" onClick={returnFromAccountHoldings}>Back to {workspaceReturn.returnSection === 'accounts' ? 'Accounts' : workspaceReturn.returnSection === 'activity' ? 'Activity' : workspaceReturn.returnSection === 'readiness' ? 'Readiness' : 'Overview'}</button></div>}
          {snapshot?.holdings.length ? <details className="card nsdl-snapshot-card"><summary>Imported statement · whole portfolio</summary><div className="mt-3">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-[11px] uppercase tracking-widest text-theme-muted font-bold">Statement source detail</p>
                <h2 id="nsdl-snapshot-heading" className="text-xl font-black text-theme-primary mt-1">Statement as of {disclosedDate(snapshot.asOfDate, isPrivacyShieldActive)}</h2>
                <p className="text-xs text-theme-secondary mt-1">Imported {snapshot.importedAt ? disclosedDate(snapshot.importedAt.slice(0, 10), isPrivacyShieldActive) : 'date unavailable'} · {snapshot.parserVersion}</p>
              </div>
              <div className="text-right">
                <p className="text-[11px] uppercase tracking-widest text-theme-muted font-bold">Printed statement total</p>
                <p className="financial-value privacy-maskable text-2xl font-black text-theme-primary" aria-label={isPrivacyShieldActive ? 'Printed statement total masked by Privacy Shield' : `Printed statement total ${totalText}`}>{totalText}</p>
              </div>
            </div>
            <div className="nsdl-metrics">
              <div className="rounded-lg bg-theme-subtle p-3"><p className="text-theme-muted inline-flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> NSDL PDF coverage</p><p className="font-bold text-theme-primary mt-1">{coverage?.complete ? 'All rows read' : 'Some rows unresolved'}</p></div>
              <div className="rounded-lg bg-theme-subtle p-3"><p className="text-theme-muted inline-flex items-center gap-1"><WalletCards className="w-3.5 h-3.5" /> Statement accounts</p><p className="font-bold text-theme-primary mt-1">{snapshot.accounts.length}</p></div>
              <div className="rounded-lg bg-theme-subtle p-3"><p className="text-theme-muted inline-flex items-center gap-1"><CalendarDays className="w-3.5 h-3.5" /> Statement date</p><p className="font-bold text-theme-primary mt-1">{disclosedDate(snapshot.asOfDate, isPrivacyShieldActive)}</p></div>
            </div>
            <p className="mt-3 text-xs text-theme-muted">This status covers this NSDL statement only. Other accounts and brokers need separate review.</p>
            {coverage && (!coverage.complete || coverage.unsupportedSections.length > 0 || (coverage.warnings?.length || 0) > 0) && (
              <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-100">
                <p className="font-bold">Coverage note</p>
                <><p className="mt-1">A complete statement total is unavailable when any included value or section is missing.</p>{coverage.unsupportedSections.length > 0 && <p className="mt-1">Unsupported: {coverage.unsupportedSections.join(', ')}</p>}{coverage.warnings?.map((warning) => <p key={warning} className="mt-1">{warning}</p>)}</>
              </div>
            )}
          </div></details> : null}

          <div className="nsdl-filters nsdl-combined-filters" aria-label="Combined holding filters">
            <label className="nsdl-filter-field"><Search aria-hidden="true" /><span className="sr-only">Search holdings</span><input value={search} onChange={(event) => setSearch(event.target.value)} aria-label="Search holdings or ISIN" className="nsdl-control nsdl-input" placeholder="Search holdings or ISIN" /></label>
            <label className="nsdl-filter-field"><Filter aria-hidden="true" /><span className="sr-only">Filter by account</span><select value={accountFilter} onChange={(event) => setAccountFilter(event.target.value)} aria-label="Filter by account" className="nsdl-control nsdl-input"><option value="all">All accounts</option>{accountLabels.map((account) => <option key={account.id} value={account.id}>{account.label}</option>)}</select></label>
            <label className="text-xs text-theme-secondary">Source<select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value as HoldingSourceFilter)} aria-label="Filter by source" className="nsdl-control nsdl-input mt-1"><option value="all">All sources</option><option value="statement">Statement</option><option value="manual">Manual</option></select></label>
            <label className="text-xs text-theme-secondary">Group by<select value={holdingGroup} onChange={(event) => setHoldingGroup(event.target.value as HoldingGroup)} aria-label="Group holdings by" className="nsdl-control nsdl-input mt-1"><option value="account">Account</option><option value="asset-type">Asset type</option><option value="market">Market / currency</option></select></label>
            <label className="text-xs text-theme-secondary">Sort<button type="button" className="nsdl-control nsdl-button nsdl-button-secondary mt-1" onClick={() => setSortDirection((direction) => direction === 'asc' ? 'desc' : 'asc')} aria-label={`Sort holdings ${sortDirection === 'asc' ? 'ascending' : 'descending'}`}>{sortDirection === 'asc' ? 'A–Z' : 'Z–A'}</button></label>
          </div>

          <div className="nsdl-holding-groups" aria-label="Combined holdings">
            {groupedHoldings.map((group) => {
              const expanded = expandedGroups[group.id] !== false;
              return <section key={group.id} className="nsdl-holding-group" aria-label={`${holdingGroup} ${group.label}`}>
              <button type="button" className="nsdl-holding-group-header" onClick={() => setExpandedGroups((previous) => ({ ...previous, [group.id]: !expanded }))} aria-expanded={expanded} aria-label={`${expanded ? 'Collapse' : 'Expand'} ${group.label} holdings`}><span className="inline-flex items-center gap-2"><WalletCards className="w-4 h-4 text-blue-400" aria-hidden="true" /><strong>{disclosureValue(group.label, isPrivacyShieldActive)}</strong></span><span className="nsdl-holding-group-summary">{group.holdings.length} holding{group.holdings.length === 1 ? '' : 's'} · {group.subtotals.length ? group.subtotals.map((subtotal) => isPrivacyShieldActive ? `${subtotal.currency} ${PRIVACY_MASK}` : formatMoney(subtotal.value, subtotal.currency)).join(' · ') : 'No included value'} · {expanded ? 'Hide' : 'Show'}</span></button>
              {expanded && <div className="nsdl-holding-table-wrap"><table className="nsdl-holding-table">
                <thead><tr><th scope="col">Holding</th><th scope="col" className="nsdl-holding-secondary">Account</th><th scope="col" className="nsdl-holding-secondary nsdl-numeric">Quantity</th><th scope="col" className="nsdl-holding-secondary nsdl-numeric">Source value</th><th scope="col" className="nsdl-numeric">Calculated value</th><th scope="col"><span className="sr-only">Details</span></th></tr></thead>
                <tbody>{group.holdings.map((holding) => {
                  const manual = holding.source === 'MANUAL';
                  const calculated = holding.valuation;
                  const calculatedText = calculated?.status === 'CALCULATED' && calculated.currentValue !== undefined
                    ? (isPrivacyShieldActive ? PRIVACY_MASK : formatMoney(calculated.currentValue, calculated.currency))
                    : 'Unavailable';
                  const sourceValue = moneyValue(holding.statementValue, holding.currency, isPrivacyShieldActive);
                  return <tr key={holding.holdingId} aria-current={holding.holdingId === detailHoldingId ? 'true' : undefined} className={holding.holdingId === detailHoldingId ? 'is-selected' : undefined}>
                    <th scope="row" className="nsdl-holding-name"><span className="nsdl-holding-name-main">{disclosureValue(holding.instrumentName, isPrivacyShieldActive)}</span><span className="nsdl-holding-name-meta">{holding.instrumentType} · {holding.isin ? disclosureValue(holding.isin, isPrivacyShieldActive) : 'ISIN not provided'} · {manual ? 'Manual fact' : 'Statement'}</span></th>
                    <td className="nsdl-holding-secondary">{disclosureValue(accountNamesByScope.get(holding.accountScopeId) || 'Private account', isPrivacyShieldActive)}</td>
                    <td className="nsdl-holding-secondary nsdl-numeric financial-value privacy-maskable">{disclosureValue(holding.quantity, isPrivacyShieldActive)}</td>
                    <td className="nsdl-holding-secondary nsdl-numeric financial-value privacy-maskable"><span>{sourceValue}</span><small>{manual ? 'Documented cost' : 'Statement value'}</small></td>
                    <td className="nsdl-numeric financial-value privacy-maskable"><span>{calculatedText}</span><small>{calculated?.status === 'CALCULATED' ? `As of ${calculated.priceDate ? displayDate(calculated.priceDate) : 'date unavailable'}` : calculated?.status === 'STATEMENT_VALUE' ? 'Statement observation' : 'No calculated value'}</small></td>
                    <td className="nsdl-holding-action">{!detailHoldingId && <button type="button" className="nsdl-control nsdl-button nsdl-button-secondary" onClick={() => openHoldingDetail(holding)} aria-label={`View ${holding.instrumentName} details`}>Details</button>}</td>
                  </tr>;
                })}</tbody>
              </table></div>}
            </section>;
            })}
          </div>
          {selectedHolding && <section className="nsdl-holding-detail" aria-labelledby="selected-holding-heading">
            <div className="nsdl-holding-detail-heading"><div><h2 id="selected-holding-heading">{disclosureValue(selectedHolding.instrumentName, isPrivacyShieldActive)}</h2><p>{selectedHolding.instrumentType} · {selectedHolding.isin ? disclosureValue(selectedHolding.isin, isPrivacyShieldActive) : 'ISIN not provided'} · {selectedHolding.source === 'MANUAL' ? 'Manual fact' : 'Statement evidence'}</p></div><span className="nsdl-holding-detail-account">{disclosureValue(accountNamesByScope.get(selectedHolding.accountScopeId) || 'Private account', isPrivacyShieldActive)}</span></div>
            <dl className="nsdl-holding-detail-grid">
              <div><dt>Quantity</dt><dd className="financial-value privacy-maskable">{disclosureValue(selectedHolding.quantity, isPrivacyShieldActive)}</dd></div>
              <div><dt>{selectedHolding.source === 'MANUAL' ? 'Documented cost' : 'Statement value'}</dt><dd className="financial-value privacy-maskable">{moneyValue(selectedHolding.statementValue, selectedHolding.currency, isPrivacyShieldActive)}</dd><small>{selectedHolding.source === 'MANUAL' ? 'Manual fact' : 'From statement'}</small></div>
              {selectedHolding.source === 'STATEMENT' && <div><dt>Statement price</dt><dd className="financial-value privacy-maskable">{moneyValue(selectedHolding.statementPrice, selectedHolding.currency, isPrivacyShieldActive)}</dd><small>Printed on {disclosedDate(selectedHolding.valuation?.statementDate || snapshot?.asOfDate || '', isPrivacyShieldActive)}</small></div>}
              <div><dt>Calculated value</dt><dd className="financial-value privacy-maskable">{selectedHolding.valuation?.status === 'CALCULATED' && selectedHolding.valuation.currentValue !== undefined ? (isPrivacyShieldActive ? PRIVACY_MASK : formatMoney(selectedHolding.valuation.currentValue, selectedHolding.valuation.currency)) : 'Unavailable'}</dd><small>{presentation ? 'Dated synthetic sample value' : `Dated calculated value${selectedHolding.valuation?.priceDate ? ` · ${displayDate(selectedHolding.valuation.priceDate)}` : ''}${selectedHolding.valuation?.source ? ` · ${selectedHolding.valuation.source}` : ''}`}</small></div>
            </dl>
            {selectedHolding.source === 'MANUAL' && selectedHolding.valuation?.reconciliationStatus === 'REVIEW_REQUIRED' && <p className="nsdl-holding-review-note">This manual holding has the same account and ISIN as statement evidence. It remains excluded from value and return until reconciled.</p>}
          </section>}
          {filteredHoldings.length === 0 && <div className="card border border-theme p-6 text-center text-sm text-theme-secondary">No holdings match this search or filter.</div>}
        </section>
      )}

      {activeTab === 'holdings' && <details className="nsdl-manual-details"><summary>Add or update manual facts</summary><ManualEntryPanel portfolioId={portfolioId} initialAccountId={navigationContext?.accountId} entryMode="holding" onSelectionChange={handleManualSelection} onDataChange={handleAccountDataChange} /></details>}

      {activeTab === 'performance' && <label className="text-xs text-theme-secondary block">Performance account<select value={performanceAccountId} onChange={(event) => { const next = event.target.value; setPerformanceAccountId(next); if (next) { allocationChoiceMadeRef.current = true; setAccountFilter(next); setAllocationCurrency(accountData?.accounts.find((account) => account.account_id === next)?.currency || ''); } }} className="nsdl-control nsdl-input mt-1 w-full sm:w-auto"><option value="">All eligible manual-history accounts</option>{accountLabels.map((account) => <option key={account.id} value={account.id}>{account.label}</option>)}</select></label>}

      {activeTab === 'performance' && (snapshot || accountData?.accounts.length) && <section className="card border border-theme p-4 space-y-4" aria-labelledby="dated-metrics-heading" data-testid="dated-valuation-performance"><div><p className="text-[11px] uppercase tracking-widest text-theme-muted font-bold">Dated analysis</p><h2 id="dated-metrics-heading" className="text-lg font-black text-theme-primary">{performanceAccountId ? 'Account performance' : 'Performance'}{currentAsOf ? ` as of ${disclosedDate(currentAsOf, isPrivacyShieldActive)}` : ''}</h2><p className="text-xs text-theme-secondary mt-1">Annualised return, accounting for when money was added or withdrawn.</p></div><label className="text-xs text-theme-secondary block">Analysis date<input aria-label="Valuation and performance as of date" type="date" value={currentAsOf} onChange={(event) => setAnalysisAsOf(event.target.value)} className="nsdl-control nsdl-input mt-1 w-full sm:w-auto" /></label>{metricsStatus === 'loading' && <p role="status" className="text-sm text-theme-secondary">Loading dated analysis…</p>}{metricsStatus === 'ready' && <PerformanceXirrCard portfolioId={portfolioId} accountId={performanceAccountId} accountCurrency={performanceAccountId ? accountData?.accounts.find((account) => account.account_id === performanceAccountId)?.currency || '' : ''} asOf={currentAsOf} performance={performance} performanceContext={performanceContext} performanceValuation={performanceValuation} performanceValuationContext={performanceValuationContext} isPrivacyShieldActive={isPrivacyShieldActive} formatDate={displayDate} formatPercent={formatPercent} />}</section>}
      <footer className="flex items-start gap-2 text-xs text-theme-muted border-t border-theme pt-4"><ShieldCheck className="w-4 h-4 shrink-0 text-blue-400" aria-hidden="true" /><span>{isPrivacyShieldActive ? 'Hide amounts hides monetary values and obscures account identifiers; names, dates, quantities, percentages and controls remain readable.' : 'Hide amounts is off; monetary values are visible on this screen.'} Unsupported tax, AI and family-management actions are not available in this preview.</span></footer>
    </div>
  );
}
