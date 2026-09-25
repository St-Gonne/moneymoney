import type { ValuationRangeResult } from '../types/valuation.ts';

export type ValuationRangeRequestKey = {
  portfolioId: string;
  accountId?: string;
  currency: string;
  start?: string;
  end?: string;
  granularity: 'daily' | 'monthly';
};

type Entry = { expiresAt: number; revision: string; result: ValuationRangeResult };

/** In-memory only: callers own lifecycle clearing on scope and local-data changes. */
export class ValuationRangeCache {
  private readonly values = new Map<string, Entry>();

  get(key: ValuationRangeRequestKey, now = Date.now()): ValuationRangeResult | null {
    const entry = this.values.get(rangeCacheKey(key));
    if (!entry || entry.expiresAt <= now) { this.values.delete(rangeCacheKey(key)); return null; }
    return entry.result;
  }

  set(key: ValuationRangeRequestKey, result: ValuationRangeResult, now = Date.now(), ttlMs = 15_000): void {
    this.values.set(rangeCacheKey(key), { expiresAt: now + ttlMs, revision: result.inputDigest, result });
  }

  clear(): void { this.values.clear(); }
}

export function rangeCacheKey(key: ValuationRangeRequestKey): string {
  return [key.portfolioId, key.accountId || '', key.currency, key.start || '', key.end || '', key.granularity].join('\u0000');
}
