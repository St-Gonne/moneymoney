"""Quote orchestration with strict owner/portfolio mappings and no calculations."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from typing import Callable
from .models.quotes import QuoteIdentityV1, QuotePayloadV1, quote_decimal
from .quote_cache import BoundedQuoteCache
from .quote_provider import DisabledQuoteProvider, QuoteProvider
from .private_nsdl_identity import PrivateNsdlIdentity

def _no_dupes(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError("duplicate configuration key")
        result[key] = value
    return result

class QuoteService:
    def __init__(self, *, enabled: bool = False, mappings: dict | None = None, provider: QuoteProvider | None = None, cache: BoundedQuoteCache | None = None, clock: Callable[[], datetime] | None = None) -> None:
        self.enabled, self.mappings, self.provider, self.cache = enabled, mappings or {}, provider or DisabledQuoteProvider(), cache or BoundedQuoteCache()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
    @classmethod
    def from_environment(cls) -> "QuoteService":
        if os.environ.get("MONEYMONEY_QUOTES_ENABLED") != "1" or os.environ.get("MONEYMONEY_QUOTES_PROVIDER") != "upstox": return cls()
        try:
            value = json.loads(os.environ.get("MONEYMONEY_NSDL_QUOTE_IDENTITIES_JSON", ""), object_pairs_hook=_no_dupes)
            if not isinstance(value, dict) or set(value) != {"schemaVersion", "owners"} or value["schemaVersion"] != 1 or not isinstance(value["owners"], dict): raise ValueError()
        except Exception: value = {}
        return cls(enabled=True, mappings=value)
    def _identities(self, identity: PrivateNsdlIdentity, snapshot) -> tuple[QuoteIdentityV1, ...]:
        try:
            rows = self.mappings["owners"][identity.uid]["portfolios"][identity.portfolio_id]
            if not isinstance(rows, list): return ()
        except (KeyError, TypeError): return ()
        holding_rows = [item.holding_id for item in snapshot.holdings]
        holding_currencies = {item.holding_id: getattr(item, "currency", None) for item in snapshot.holdings}
        holdings = set(holding_rows)
        result = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"holdingId", "provider", "instrumentKey", "currency", "venue", "quoteKind"}: return ()
            values = (row["holdingId"], row["provider"], row["instrumentKey"], row["currency"], row["venue"], row["quoteKind"])
            if not all(isinstance(value, str) and value for value in values) or row["provider"] != "upstox" or row["holdingId"] not in holdings or holding_rows.count(row["holdingId"]) != 1 or holding_currencies[row["holdingId"]] != row["currency"]: return ()
            result.append(QuoteIdentityV1(*values))
        if len(result) > 100 or len({item.holding_id for item in result}) != len(result): return ()
        return tuple(result)
    def quotes(self, identity: PrivateNsdlIdentity, snapshot_loader) -> list[dict[str, str]]:
        if not self.enabled: return []
        now, scope = self.clock(), f"{identity.uid}\x1f{identity.portfolio_id}"
        cached = self.cache.cached(scope, now)
        if not self.cache.admit(scope, now): return [item.to_wire() for item in cached]
        if cached and all(item.status != "STALE" for item in cached): return [item.to_wire() for item in cached]
        snapshot = snapshot_loader()
        if snapshot is None: return []
        identities = self._identities(identity, snapshot)
        if not identities: return []
        try: batch = self.provider.fetch(identities, timeout_seconds=5)
        except TimeoutError:
            self.cache.record_attempt(scope, now)
            return [item.to_wire() for item in cached]
        if batch.body_bytes < 0 or batch.body_bytes > 1024 * 1024:
            self.cache.record(scope, now, (), 0); return []
        expected = {entry.holding_id: entry.currency for entry in identities}
        valid = tuple(QuotePayloadV1(item.holding_id, price, item.currency, item.source, item.observed_at, item.status) for item in batch.records if item.holding_id in expected and item.currency == expected[item.holding_id] and (price := quote_decimal(item.price)) is not None and item.source.strip() and item.observed_at.tzinfo is not None and item.observed_at <= now and item.status in {"DELAYED", "DAILY_NAV", "EOD_CLOSE"} | ({"FRESH"} if now - item.observed_at <= __import__('datetime').timedelta(seconds=60) else set()))
        if len({item.holding_id for item in valid}) != len(valid): valid = ()
        if not self.cache.record(scope, now, valid, len(repr([item.to_wire() for item in valid]).encode())): return []
        return [item.to_wire() for item in valid]
