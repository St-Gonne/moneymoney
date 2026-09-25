"""Bounded volatile quote cache and per-scope request gate."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .models.quotes import QuotePayloadV1

MAX_SCOPES, MAX_RECORDS, MAX_BYTES = 16, 100, 256 * 1024
FRESH_TTL, STALE_TTL = timedelta(seconds=60), timedelta(minutes=15)

@dataclass
class _Entry:
    attempted_at: datetime
    validated_at: datetime | None
    records: tuple[QuotePayloadV1, ...]
    encoded_bytes: int

class BoundedQuoteCache:
    def __init__(self) -> None: self._entries: dict[str, _Entry] = {}
    def _expire(self, now: datetime) -> None:
        self._entries = {key: entry for key, entry in self._entries.items() if entry.validated_at is None or now - entry.validated_at <= STALE_TTL}
    def admit(self, scope: str, now: datetime) -> bool:
        self._expire(now)
        entry = self._entries.get(scope)
        if entry: return now - entry.attempted_at >= FRESH_TTL
        return len(self._entries) < MAX_SCOPES
    def record(self, scope: str, now: datetime, records: tuple[QuotePayloadV1, ...], encoded_bytes: int) -> bool:
        self._expire(now)
        if len(records) > MAX_RECORDS or encoded_bytes > MAX_BYTES or (scope not in self._entries and len(self._entries) >= MAX_SCOPES): return False
        self._entries[scope] = _Entry(now, now, records, encoded_bytes); return True
    def record_attempt(self, scope: str, now: datetime) -> None:
        entry = self._entries.get(scope)
        if entry: self._entries[scope] = _Entry(now, entry.validated_at, entry.records, entry.encoded_bytes)
        elif len(self._entries) < MAX_SCOPES: self._entries[scope] = _Entry(now, now, (), 0)
    def cached(self, scope: str, now: datetime) -> tuple[QuotePayloadV1, ...]:
        self._expire(now); entry = self._entries.get(scope)
        if not entry or entry.validated_at is None or now - entry.validated_at > STALE_TTL: return ()
        if now - entry.validated_at <= FRESH_TTL: return entry.records
        return tuple(QuotePayloadV1(item.holding_id, item.price, item.currency, item.source, item.observed_at, "STALE") for item in entry.records)
