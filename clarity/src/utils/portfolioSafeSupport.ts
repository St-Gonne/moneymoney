export const SUPPORT_CONTEXT = 'MoneyMoney private portfolio · local synthetic';
export type SupportOperation = 'account-data-read' | 'readiness-metrics-read';
export type SupportCode = 'ERR_ACCOUNT_STORE_UNAVAILABLE' | 'ERR_ACCOUNT_REQUEST_INVALID' | 'ERR_ACCOUNT_REVISION_INVALID' | 'UNKNOWN';
export type SafeSupportInput = { operation: SupportOperation | string; code: SupportCode | string; requestReference?: string; eventTime?: string };

const operations = new Set<SupportOperation>(['account-data-read', 'readiness-metrics-read']);
const codes = new Set<SupportCode>(['ERR_ACCOUNT_STORE_UNAVAILABLE', 'ERR_ACCOUNT_REQUEST_INVALID', 'ERR_ACCOUNT_REVISION_INVALID', 'UNKNOWN']);
const safeReference = /^[A-Za-z0-9._:-]{1,80}$/;
const safeTime = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z$/;

/** A deliberately closed support receipt: never pass an exception, response, or identity here. */
export function formatSafeSupport(input: SafeSupportInput): string {
  const operation = operations.has(input.operation as SupportOperation) ? input.operation : 'readiness-metrics-read';
  const code = codes.has(input.code as SupportCode) ? input.code : 'UNKNOWN';
  const parts = [SUPPORT_CONTEXT, `operation=${operation}`, `code=${code}`];
  if (typeof input.requestReference === 'string' && safeReference.test(input.requestReference)) parts.push(`reference=${input.requestReference}`);
  if (typeof input.eventTime === 'string' && safeTime.test(input.eventTime)) parts.push(`time=${input.eventTime}`);
  return parts.join(' · ');
}
