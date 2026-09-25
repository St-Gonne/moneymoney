import assert from 'node:assert/strict';
import { ValuationRangeCache, rangeCacheKey } from '../src/utils/valuationRangeCache.ts';

const result = { inputDigest: 'revision-a', calculationVersion: 'range', scope: { accountId: null, currency: 'INR' }, range: { start: null, end: null, granularity: 'daily' }, coverage: { availableStart: null, availableEnd: null, observedCount: 0, selectedObservedCount: 0, returnedCount: 0, partial: false }, points: [], first: null, last: null };
const allInr = { portfolioId: 'portfolio-a', currency: 'INR', granularity: 'daily' };
const accountInr = { ...allInr, accountId: 'account-a' };
const allUsd = { ...allInr, currency: 'USD' };
const cache = new ValuationRangeCache();
cache.set(allInr, result, 1_000, 100);
assert.equal(cache.get(allInr, 1_050), result, 'same scope reuses its fresh range without another request');
assert.equal(cache.get(accountInr, 1_050), null, 'account scope never reuses whole-portfolio data');
assert.equal(cache.get(allUsd, 1_050), null, 'currency never crosses a range cache boundary');
assert.notEqual(rangeCacheKey(allInr), rangeCacheKey({ ...allInr, granularity: 'monthly' }), 'display granularity is part of the request cache key');
assert.equal(cache.get(allInr, 1_100), null, 'expired last-observed revision is revalidated');
cache.set(allInr, result, 2_000, 100);
cache.clear();
assert.equal(cache.get(allInr, 2_001), null, 'scope/logout or mutation clearing removes private range data');
console.log('Clarity range cache checks passed');
