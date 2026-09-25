"""Typed local-only valuation records with no provider or transport concerns."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


class ValuationError(ValueError):
    pass


@dataclass(frozen=True)
class SyntheticDailyPrice:
    holding_id: str
    owner_scope_id: str
    portfolio_id: str
    price: Decimal
    currency: str
    price_date: date
    source: str
    status: str
    source_revision: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value for value in (self.holding_id, self.owner_scope_id, self.portfolio_id, self.currency, self.source_revision)):
            raise ValuationError("ERR_VALUATION_INVALID")
        if not isinstance(self.price, Decimal) or not self.price.is_finite() or self.price < 0 or not isinstance(self.price_date, date) or self.source not in {"AMFI", "NSE"} or self.status not in {"DAILY_NAV", "EOD_CLOSE"}:
            raise ValuationError("ERR_VALUATION_INVALID")
