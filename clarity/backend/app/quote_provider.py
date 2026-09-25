"""Provider seam. Production access remains disabled until explicit setup."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from .models.quotes import QuoteIdentityV1, QuotePayloadV1

@dataclass(frozen=True)
class ProviderBatch:
    records: tuple[QuotePayloadV1, ...]
    body_bytes: int

class QuoteProvider(Protocol):
    def fetch(self, identities: tuple[QuoteIdentityV1, ...], *, timeout_seconds: int) -> ProviderBatch: ...

class DisabledQuoteProvider:
    def fetch(self, identities: tuple[QuoteIdentityV1, ...], *, timeout_seconds: int) -> ProviderBatch: return ProviderBatch((), 0)

class UpstoxQuoteProvider(DisabledQuoteProvider):
    """Named disabled seam; no transport is constructed or called in this milestone."""
