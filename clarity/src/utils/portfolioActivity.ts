import type { AccountDataSnapshot, CashFlowRecord, OpeningHoldingRecord } from '../types/accountData.ts';

export type ActivityKind = 'account' | 'holding' | 'cash';
export type ActivityKindFilter = 'all' | ActivityKind;
export type ActivityChange = { label: string; before?: string; after?: string; sensitive: boolean };
export type ActivityEvent = { id: string; kind: ActivityKind; accountId: string; revision: number; label: string; action: string; recordedAt?: string; effectiveDate?: string; changes: ActivityChange[]; source: 'MANUAL' };
type Field = { key: string; label: string; sensitive: boolean };

const accountFields: Field[] = [{ key: 'user_alias', label: 'Nickname', sensitive: false }, { key: 'manual_history_complete', label: 'History attestation', sensitive: false }];
const holdingFields: Field[] = [{ key: 'instrument_name', label: 'Holding', sensitive: false }, { key: 'quantity', label: 'Quantity', sensitive: true }, { key: 'as_of', label: 'As of date', sensitive: true }, { key: 'currency', label: 'Currency', sensitive: true }, { key: 'documented_cost', label: 'Documented cost', sensitive: true }, { key: 'voided', label: 'Voided', sensitive: false }];
const cashFields: Field[] = [{ key: 'effective_date', label: 'Effective date', sensitive: true }, { key: 'amount', label: 'Amount', sensitive: true }, { key: 'currency', label: 'Currency', sensitive: true }, { key: 'flow_type', label: 'Flow type', sensitive: false }, { key: 'voided', label: 'Voided', sensitive: false }];
const text = (value: unknown): string => value === null || value === undefined ? '' : String(value);
const validRevision = (value: unknown): value is number => typeof value === 'number' && Number.isInteger(value) && value > 0;
const manual = (row: { provenance?: { source_kind?: string; revision?: number } }): boolean => row.provenance?.source_kind === 'manual' && validRevision(row.provenance.revision);
const changed = (before: Record<string, unknown> | undefined, after: Record<string, unknown>, fields: Field[]): ActivityChange[] => fields.flatMap((field) => text(before?.[field.key]) === text(after[field.key]) ? [] : [{ label: field.label, before: before ? text(before[field.key]) : undefined, after: text(after[field.key]), sensitive: field.sensitive }]);

function classifyAccount(first: boolean, diff: ActivityChange[]): string | null {
  if (first) return 'Account created'; if (!diff.length) return null;
  if (diff.length === 1 && diff[0].label === 'Nickname') return 'Nickname changed';
  if (diff.length === 1 && diff[0].label === 'History attestation') return 'History attestation changed';
  return 'Account metadata changed';
}
function classifyFact(noun: 'Holding' | 'Cash flow', first: boolean, diff: ActivityChange[]): string | null {
  if (first) return `${noun} created`; if (!diff.length) return null;
  return diff.some((change) => change.label === 'Voided' && change.after === 'true') ? `${noun} voided` : `${noun} corrected`;
}
function sortEvents(events: ActivityEvent[]): ActivityEvent[] { return events.sort((l, r) => (r.recordedAt || '').localeCompare(l.recordedAt || '') || l.accountId.localeCompare(r.accountId) || l.kind.localeCompare(r.kind) || r.revision - l.revision || l.id.localeCompare(r.id)); }

export function projectPortfolioActivity(data: AccountDataSnapshot): ActivityEvent[] {
  const output: ActivityEvent[] = []; const seen = new Set<string>(); const add = (event: ActivityEvent) => { if (!seen.has(event.id)) { seen.add(event.id); output.push(event); } };
  for (const group of data.accountRevisions || []) {
    const revisions = [...group.revisions].sort((a, b) => (a.provenance?.revision || 0) - (b.provenance?.revision || 0));
    if (!group.accountId || !revisions.length || !revisions.every((row, index) => manual(row) && row.account_id === group.accountId && row.provenance?.revision === index + 1)) continue;
    revisions.forEach((row, index) => { const diff = changed(index ? revisions[index - 1] : undefined, row, accountFields); const action = classifyAccount(index === 0, diff); const revision = row.provenance!.revision!; if (action) add({ id: `account:${row.account_id}:${group.accountId}:${revision}`, kind: 'account', accountId: row.account_id, revision, label: row.user_alias || row.institution, action, recordedAt: row.provenance?.recorded_at, changes: diff, source: 'MANUAL' }); });
  }
  const projectFacts = <T extends OpeningHoldingRecord | CashFlowRecord>(kind: 'holding' | 'cash', noun: 'Holding' | 'Cash flow', groups: Array<{ factId: string; revisions: T[] }>, fields: Field[]) => {
    for (const group of groups) {
      const revisions = [...group.revisions].sort((a, b) => (a.provenance?.revision || 0) - (b.provenance?.revision || 0));
      if (!group.factId || !revisions.length || !revisions.every((row, index) => manual(row) && row.fact_id === group.factId && Boolean(row.account_id) && row.account_id === revisions[0].account_id && row.provenance?.revision === index + 1)) continue;
      revisions.forEach((row, index) => { const diff = changed(index ? revisions[index - 1] : undefined, row, fields); const action = classifyFact(noun, index === 0, diff); const revision = row.provenance!.revision!; if (action) add({ id: `${kind}:${row.account_id}:${group.factId}:${revision}`, kind, accountId: row.account_id, revision, label: kind === 'holding' ? (row as OpeningHoldingRecord).instrument_name : (row as CashFlowRecord).flow_type, action, recordedAt: row.provenance?.recorded_at, effectiveDate: kind === 'holding' ? (row as OpeningHoldingRecord).as_of : (row as CashFlowRecord).effective_date, changes: diff, source: 'MANUAL' }); });
    }
  };
  projectFacts('holding', 'Holding', data.openingHoldingRevisions || [], holdingFields);
  projectFacts('cash', 'Cash flow', data.cashFlowRevisions || [], cashFields);
  return sortEvents(output);
}

/** One formatter serves visual and ARIA text so shielded details cannot leak raw financial/audit facts. */
export function formatActivityValue(value: string | undefined, sensitive: boolean, masked: boolean): string { return !value ? 'Not recorded' : masked && sensitive ? 'Hidden by Privacy Shield' : value; }
