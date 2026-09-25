"""Ephemeral, server-only quote contracts; they never calculate portfolio values."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class QuoteIdentityV1:
    holding_id: str
    provider: str
    instrument_key: str
    currency: str
    venue: str
    quote_kind: str


@dataclass(frozen=True)
class QuotePayloadV1:
    holding_id: str
    price: str
    currency: str
    source: str
    observed_at: datetime
    status: str

    def to_wire(self) -> dict[str, str]:
        return {"holdingId": self.holding_id, "price": self.price, "currency": self.currency, "source": self.source, "observedAt": self.observed_at.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"), "status": self.status}


def quote_decimal(value: object) -> str | None:
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not decimal.is_finite() or decimal < 0:
        return None
    text = format(decimal, "f").rstrip("0").rstrip(".") if "." in format(decimal, "f") else format(decimal, "f")
    return text or "0"
