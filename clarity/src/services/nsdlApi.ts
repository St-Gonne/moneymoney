import { authenticatedFetch } from './apiAuth.ts';
import type { NsdlActivityResponse, NsdlAuthorizedPortfoliosResponse, NsdlErrorCode, NsdlImportResponse, NsdlPortfolioResponse, NsdlPreviewResponse, SchwabPreviewResponse } from '../types/nsdl.ts';

const envMeta: Record<string, string | undefined> =
  typeof import.meta !== 'undefined' && import.meta.env
    ? import.meta.env as Record<string, string | undefined>
    : {};
const API_BASE_URL = (envMeta.VITE_API_BASE_URL || '').replace(/\/$/, '');
const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const IMPORT_REFERENCE = /^im-[0-9a-f]{32}$/;

export class NsdlApiError extends Error {
  readonly code: NsdlErrorCode;
  readonly status: number;
  readonly importReference: string | null;

  constructor(code: NsdlErrorCode, status: number, importReference: string | null = null) {
    super(code);
    this.name = 'NsdlApiError';
    this.code = code;
    this.status = status;
    this.importReference = importReference;
  }
}

function errorCodeFromPayload(payload: unknown, status: number): NsdlErrorCode {
  const detail = payload && typeof payload === 'object' && 'detail' in payload
    ? (payload as { detail?: unknown }).detail
    : null;
  if (status === 401) return 'AUTH_REQUIRED';
  if (status === 403) return 'ACCESS_DENIED';
  if (status === 503) return 'SERVICE_UNAVAILABLE';
  return typeof detail === 'string' && (NSDL_CODES.has(detail) || detail === 'AUTH_REQUIRED')
    ? detail as NsdlErrorCode
    : 'UNKNOWN';
}

const NSDL_CODES = new Set<string>([
  'ERR_NSDL_UPLOAD_INVALID', 'ERR_NSDL_IDEMPOTENCY_INVALID', 'ERR_NSDL_LIMIT_EXCEEDED',
  'ERR_NSDL_PASSWORD_INVALID', 'ERR_NSDL_UNSUPPORTED_LAYOUT', 'ERR_NSDL_OWNER_MISMATCH',
  'ERR_NSDL_PARSE_INCOMPLETE', 'ERR_NSDL_SAME_DATE_CONFLICT', 'ERR_NSDL_OLDER_STATEMENT',
  'ERR_NSDL_ACCOUNT_SET_CONFLICT', 'ERR_NSDL_REVISION_CONFLICT', 'ERR_NSDL_STORE_UNAVAILABLE',
  'ERR_NSDL_COMMIT_UNKNOWN', 'ERR_NSDL_ACCOUNT_COMMIT_UNKNOWN', 'ERR_NSDL_IDEMPOTENCY_CONFLICT',
  'ERR_NSDL_PREVIEW_INVALID',
  'ERR_SCHWAB_PASSWORD_UNSUPPORTED', 'ERR_SCHWAB_PREVIEW_UNSUPPORTED',
]);

async function readResponse<T>(response: Response): Promise<T> {
  let payload: unknown = null;
  try { payload = await response.json(); } catch { /* fixed safe client error below */ }
  const importReference = response.headers.get('X-MoneyMoney-Import-Ref');
  if (!response.ok) throw new NsdlApiError(errorCodeFromPayload(payload, response.status), response.status, importReference && IMPORT_REFERENCE.test(importReference) ? importReference : null);
  return payload as T;
}

function portfolioUrl(portfolioId: string): string {
  return `${API_BASE_URL}/api/nsdl/portfolio?portfolio_id=${encodeURIComponent(portfolioId)}`;
}

function authorizedPortfoliosUrl(): string {
  return `${API_BASE_URL}/api/nsdl/authorized-portfolios`;
}

function activityUrl(portfolioId: string): string {
  return `${API_BASE_URL}/api/nsdl/activity?portfolio_id=${encodeURIComponent(portfolioId)}`;
}

export async function fetchAuthorizedPortfolios(signal?: AbortSignal): Promise<NsdlAuthorizedPortfoliosResponse> {
  const payload = await readResponse<unknown>(await authenticatedFetch(authorizedPortfoliosUrl(), { method: 'GET', signal }));
  if (!payload || typeof payload !== 'object' || !Array.isArray((payload as { portfolios?: unknown }).portfolios)) return { portfolios: [] };
  const portfolios = (payload as { portfolios: unknown[] }).portfolios.flatMap((item) => {
    if (!item || typeof item !== 'object') return [];
    const value = item as { portfolioId?: unknown; label?: unknown; helping?: unknown };
    return typeof value.portfolioId === 'string' && typeof value.label === 'string' && typeof value.helping === 'boolean'
      ? [{ portfolioId: value.portfolioId, label: value.label, helping: value.helping }]
      : [];
  });
  return { portfolios };
}

export async function fetchNsdlActivity(portfolioId: string, signal?: AbortSignal): Promise<NsdlActivityResponse> {
  const payload = await readResponse<unknown>(await authenticatedFetch(activityUrl(portfolioId), { method: 'GET', signal }));
  if (!payload || typeof payload !== 'object' || !Array.isArray((payload as { activity?: unknown }).activity)) return { activity: [] };
  const activity = (payload as { activity: unknown[] }).activity.flatMap((item) => {
    if (!item || typeof item !== 'object') return [];
    const value = item as { actor_uid?: unknown; operation?: unknown; recorded_at?: unknown };
    return typeof value.actor_uid === 'string' && typeof value.operation === 'string' && typeof value.recorded_at === 'string'
      ? [{ actor_uid: value.actor_uid, operation: value.operation, recorded_at: value.recorded_at }]
      : [];
  });
  return { activity };
}

export async function fetchNsdlPortfolio(portfolioId: string, signal?: AbortSignal): Promise<NsdlPortfolioResponse> {
  return readResponse<NsdlPortfolioResponse>(await authenticatedFetch(portfolioUrl(portfolioId), { method: 'GET', signal }));
}

export function createNsdlIdempotencyKey(): string {
  const candidate = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : '';
  if (UUID_V4.test(candidate)) return candidate;
  return '00000000-0000-4000-8000-000000000001';
}

export async function importNsdlStatement(
  portfolioId: string,
  file: File,
  password: string,
  previewToken: string,
  signal?: AbortSignal,
  idempotencyKey = createNsdlIdempotencyKey(),
): Promise<NsdlImportResponse> {
  if (!UUID_V4.test(idempotencyKey)) throw new NsdlApiError('ERR_NSDL_IDEMPOTENCY_INVALID', 400);
  if (!previewToken || previewToken.length > 1024) throw new NsdlApiError('ERR_NSDL_PREVIEW_INVALID', 400);
  const form = new FormData();
  form.append('file', file, 'statement.pdf');
  if (password) form.append('password', password);
  return readResponse<NsdlImportResponse>(await authenticatedFetch(
    `${API_BASE_URL}/api/nsdl/import?portfolio_id=${encodeURIComponent(portfolioId)}`,
    { method: 'POST', headers: { 'Idempotency-Key': idempotencyKey, 'Nsdl-Preview-Token': previewToken }, body: form, signal },
  ));
}

export async function previewNsdlStatement(
  portfolioId: string,
  file: File,
  password: string,
  signal?: AbortSignal,
): Promise<NsdlPreviewResponse> {
  const form = new FormData();
  form.append('file', file, 'statement.pdf');
  if (password) form.append('password', password);
  return readResponse<NsdlPreviewResponse>(await authenticatedFetch(
    `${API_BASE_URL}/api/nsdl/import-preview?portfolio_id=${encodeURIComponent(portfolioId)}`,
    { method: 'POST', body: form, signal },
  ));
}

export async function previewSchwabStatement(
  portfolioId: string,
  file: File,
  signal?: AbortSignal,
): Promise<SchwabPreviewResponse> {
  const form = new FormData();
  form.append('file', file, 'statement.pdf');
  return readResponse<SchwabPreviewResponse>(await authenticatedFetch(
    `${API_BASE_URL}/api/nsdl/schwab-preview?portfolio_id=${encodeURIComponent(portfolioId)}`,
    { method: 'POST', body: form, signal },
  ));
}
