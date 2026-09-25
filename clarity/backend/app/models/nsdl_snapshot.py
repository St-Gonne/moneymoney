"""Typed, redacted NSDL statement-date snapshot values.

This module deliberately has no legacy-ledger or transaction-engine imports.
It represents only the values printed on one NSDL statement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import re
from typing import Optional, Sequence


DECIMAL_STRING_RE = re.compile(r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$")


class NsdlSnapshotError(ValueError):
    """A safe, category-only failure from the NSDL snapshot boundary."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def canonical_decimal(value: object) -> str:
    """Return a non-exponent decimal string, rejecting malformed values."""
    if isinstance(value, bool) or value is None:
        raise NsdlSnapshotError("ERR_NSDL_PARSE_INCOMPLETE")
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        raise NsdlSnapshotError("ERR_NSDL_PARSE_INCOMPLETE") from None
    if not decimal_value.is_finite():
        raise NsdlSnapshotError("ERR_NSDL_PARSE_INCOMPLETE")
    text = format(decimal_value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    if text in ("", "-0"):
        text = "0"
    if not DECIMAL_STRING_RE.fullmatch(text):
        raise NsdlSnapshotError("ERR_NSDL_PARSE_INCOMPLETE")
    return text


def opaque_id(secret: bytes, *parts: str) -> str:
    """Make a stable opaque identifier without emitting its source fields."""
    if not secret:
        raise NsdlSnapshotError("ERR_NSDL_PARSE_INCOMPLETE")
    message = "\x1f".join(("nsdl-snapshot-v1", *parts)).encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class NsdlCoverage:
    complete: bool
    sections: tuple[str, ...]
    unsupported_sections: tuple[str, ...]
    missing_values: int
    warnings: tuple[str, ...] = ()

    def to_wire(self) -> dict:
        return {
            "complete": self.complete,
            "sections": list(self.sections),
            "unsupportedSections": list(self.unsupported_sections),
            "missingValues": self.missing_values,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class NsdlAccount:
    account_scope_id: str
    section_type: str
    masked_label: str

    def to_wire(self) -> dict:
        return {
            "accountScopeId": self.account_scope_id,
            "sectionType": self.section_type,
            "maskedLabel": self.masked_label,
        }


@dataclass(frozen=True)
class NsdlHolding:
    holding_id: str
    account_scope_id: str
    isin: Optional[str]
    instrument_name: str
    instrument_type: str
    quantity: str
    currency: Optional[str]
    statement_price: Optional[str]
    statement_value: Optional[str]

    def __post_init__(self) -> None:
        if not DECIMAL_STRING_RE.fullmatch(self.quantity):
            raise NsdlSnapshotError("ERR_NSDL_PARSE_INCOMPLETE")
        for value in (self.statement_price, self.statement_value):
            if value is not None and not DECIMAL_STRING_RE.fullmatch(value):
                raise NsdlSnapshotError("ERR_NSDL_PARSE_INCOMPLETE")

    def to_wire(self) -> dict:
        return {
            "holdingId": self.holding_id,
            "accountScopeId": self.account_scope_id,
            "isin": self.isin,
            "instrumentName": self.instrument_name,
            "instrumentType": self.instrument_type,
            "quantity": self.quantity,
            "currency": self.currency,
            "statementPrice": self.statement_price,
            "statementValue": self.statement_value,
        }


@dataclass(frozen=True)
class NsdlTotal:
    currency: str
    statement_value: str

    def to_wire(self) -> dict:
        return {"currency": self.currency, "statementValue": self.statement_value}


@dataclass(frozen=True)
class NsdlSnapshotV1:
    portfolio_id: str
    as_of_date: date
    coverage: NsdlCoverage
    accounts: tuple[NsdlAccount, ...]
    holdings: tuple[NsdlHolding, ...]
    totals_by_currency: tuple[NsdlTotal, ...]
    parser_version: str
    revision_id: Optional[str] = None
    imported_at: Optional[str] = None
    schema_version: int = 1

    def to_wire(self) -> dict:
        return {
            "schemaVersion": self.schema_version,
            "portfolioId": self.portfolio_id,
            "asOfDate": self.as_of_date.isoformat(),
            "coverage": self.coverage.to_wire(),
            "accounts": [account.to_wire() for account in self.accounts],
            "holdings": [holding.to_wire() for holding in self.holdings],
            "totalsByCurrency": [total.to_wire() for total in self.totals_by_currency],
            "parserVersion": self.parser_version,
            "revisionId": self.revision_id,
            "importedAt": self.imported_at,
        }


def totals_from_holdings(holdings: Sequence[NsdlHolding]) -> tuple[NsdlTotal, ...]:
    """Return statement totals only when every included holding has a value."""
    if any(holding.statement_value is None for holding in holdings):
        return ()
    totals: dict[str, Decimal] = {}
    for holding in holdings:
        if holding.currency is None:
            return ()
        totals[holding.currency] = totals.get(holding.currency, Decimal("0")) + Decimal(holding.statement_value or "0")
    return tuple(
        NsdlTotal(currency=currency, statement_value=canonical_decimal(value))
        for currency, value in sorted(totals.items())
    )
