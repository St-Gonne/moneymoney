import { authenticatedFetch } from './apiAuth.ts';
import { AccountDataApiError } from '../types/accountData.ts';
import type { PerformanceResult, ValuationRangeResult, ValuationResult } from '../types/valuation.ts';
async function read<T>(response: Response): Promise<T> { let body: any = null; try { body = await response.json(); } catch { /* fixed fallback */ } if (!response.ok) throw new AccountDataApiError(typeof body?.detail === 'string' ? body.detail : 'ERR_ACCOUNT_REQUEST_INVALID', response.status); if (!body || typeof body !== 'object') throw new AccountDataApiError('ERR_ACCOUNT_REQUEST_INVALID', 400); return body as T; }
function query(portfolioId: string, asOf: string | undefined, accountId?: string, currency?: string, observations = false): string {
  const params = new URLSearchParams({ portfolio_id: portfolioId });
  if (asOf) params.set('as_of', asOf);
  if (accountId) params.set('account_id', accountId);
  if (currency) params.set('currency', currency);
  if (observations) params.set('observations', '1');
  return params.toString();
}
export async function fetchValuation(portfolioId: string, asOf: string, signal?: AbortSignal, accountId?: string, currency?: string): Promise<ValuationResult> { return read<ValuationResult>(await authenticatedFetch(`/api/nsdl/valuation?${query(portfolioId, asOf, accountId, currency)}`, { method: 'GET', signal, headers: { Accept: 'application/json' } })); }
export async function fetchValuationObservationDates(portfolioId: string, signal?: AbortSignal, accountId?: string, currency?: string): Promise<{ observationDates: string[] }> { return read<{ observationDates: string[] }>(await authenticatedFetch(`/api/nsdl/valuation?${query(portfolioId, undefined, accountId, currency, true)}`, { method: 'GET', signal, headers: { Accept: 'application/json' } })); }
export async function fetchValuationRange(portfolioId: string, scope: { accountId?: string; currency: string; start?: string; end?: string; granularity: 'daily' | 'monthly' }, signal?: AbortSignal): Promise<ValuationRangeResult> { const params = new URLSearchParams({ portfolio_id: portfolioId, currency: scope.currency, granularity: scope.granularity }); if (scope.accountId) params.set('account_id', scope.accountId); if (scope.start && scope.end) { params.set('start', scope.start); params.set('end', scope.end); } return read<ValuationRangeResult>(await authenticatedFetch(`/api/nsdl/valuation-range?${params.toString()}`, { method: 'GET', signal, headers: { Accept: 'application/json' } })); }
export async function fetchPerformance(portfolioId: string, asOf: string, signal?: AbortSignal, accountId?: string): Promise<PerformanceResult> { return read<PerformanceResult>(await authenticatedFetch(`/api/nsdl/performance?${query(portfolioId, asOf, accountId)}`, { method: 'GET', signal, headers: { Accept: 'application/json' } })); }
