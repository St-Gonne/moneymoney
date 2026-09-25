"""Owner-scoped account and manual-entry facts for the private MVP."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

FactKind = Literal["account", "opening_holding", "cash_flow"]


class AccountDataError(ValueError):
    pass


def _text(value: object, field: str, *, required: bool = True) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise AccountDataError(f"ERR_ACCOUNT_{field.upper()}_INVALID")
    value = value.strip()
    if required and not value:
        raise AccountDataError(f"ERR_ACCOUNT_{field.upper()}_INVALID")
    return value or None


@dataclass(frozen=True)
class Provenance:
    source_kind: str
    source_reference: str
    revision: int
    recorded_at: datetime

    def __post_init__(self) -> None:
        if self.source_kind not in {"manual", "statement"} or self.revision < 1 or not _text(self.source_reference, "source_reference"):
            raise AccountDataError("ERR_ACCOUNT_PROVENANCE_INVALID")


@dataclass(frozen=True)
class AccountFact:
    account_id: str
    owner_scope_id: str
    institution: str
    account_type: str
    currency: str
    source_name: str | None = None
    user_alias: str | None = None
    custodian_or_dp: str | None = None
    execution_broker: str | None = None
    masked_identifier: str | None = None
    provenance: Provenance | None = None
    portfolio_id: str = "private-preview"
    manual_history_complete: bool = False

    def __post_init__(self) -> None:
        for value, field in ((self.account_id, "account_id"), (self.owner_scope_id, "owner_scope_id"),
                             (self.institution, "institution"), (self.account_type, "account_type"), (self.currency, "currency")):
            _text(value, field)
        for value, field in ((self.source_name, "source_name"), (self.user_alias, "user_alias"),
                             (self.custodian_or_dp, "custodian_or_dp"), (self.execution_broker, "execution_broker"),
                             (self.masked_identifier, "masked_identifier")):
            _text(value, field, required=False)
        if not isinstance(self.provenance, Provenance):
            raise AccountDataError("ERR_ACCOUNT_PROVENANCE_INVALID")
        _text(self.portfolio_id, "portfolio_id")
        if not isinstance(self.manual_history_complete, bool):
            raise AccountDataError("ERR_ACCOUNT_HISTORY_INVALID")

    @property
    def display_name(self) -> str:
        return self.user_alias or self.source_name or self.institution


@dataclass(frozen=True)
class OpeningHoldingFact:
    fact_id: str
    account_id: str
    owner_scope_id: str
    instrument_name: str
    isin: str | None
    quantity: Decimal
    as_of: date
    currency: str
    documented_cost: Decimal | None
    provenance: Provenance
    portfolio_id: str = "private-preview"
    voided: bool = False

    def __post_init__(self) -> None:
        for value, field in ((self.fact_id, "fact_id"), (self.account_id, "account_id"), (self.owner_scope_id, "owner_scope_id"), (self.instrument_name, "instrument_name"), (self.currency, "currency")):
            _text(value, field)
        if self.quantity <= 0 or (self.documented_cost is not None and self.documented_cost < 0):
            raise AccountDataError("ERR_ACCOUNT_AMOUNT_INVALID")
        if not isinstance(self.provenance, Provenance):
            raise AccountDataError("ERR_ACCOUNT_PROVENANCE_INVALID")
        _text(self.portfolio_id, "portfolio_id")
        if not isinstance(self.voided, bool):
            raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")


@dataclass(frozen=True)
class CashFlowFact:
    fact_id: str
    account_id: str
    owner_scope_id: str
    effective_date: date
    amount: Decimal
    currency: str
    flow_type: Literal["contribution", "withdrawal", "dividend", "transfer"]
    note: str | None
    provenance: Provenance
    portfolio_id: str = "private-preview"
    voided: bool = False

    def __post_init__(self) -> None:
        for value, field in ((self.fact_id, "fact_id"), (self.account_id, "account_id"), (self.owner_scope_id, "owner_scope_id"), (self.currency, "currency")):
            _text(value, field)
        if self.amount == 0 or self.flow_type not in {"contribution", "withdrawal", "dividend", "transfer"}:
            raise AccountDataError("ERR_ACCOUNT_FLOW_INVALID")
        if not isinstance(self.provenance, Provenance):
            raise AccountDataError("ERR_ACCOUNT_PROVENANCE_INVALID")
        _text(self.portfolio_id, "portfolio_id")
        if not isinstance(self.voided, bool):
            raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")


def manual_provenance(reference: str, revision: int = 1) -> Provenance:
    return Provenance("manual", _text(reference, "source_reference") or "manual", revision, datetime.now(timezone.utc))


def statement_provenance(reference: str, revision: int = 1) -> Provenance:
    """Create provenance for an already-redacted statement receipt reference."""
    return Provenance("statement", _text(reference, "source_reference") or "statement", revision, datetime.now(timezone.utc))
