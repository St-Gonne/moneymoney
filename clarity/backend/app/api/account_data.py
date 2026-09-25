"""Strict wire helpers for the owner-scoped local account-data routes."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, fields
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from ..account_data_store import IDEMPOTENCY_CONFLICT, STORE_UNAVAILABLE
from ..models.account_data import AccountDataError, AccountFact, CashFlowFact, OpeningHoldingFact, manual_provenance


REQUEST_INVALID = "ERR_ACCOUNT_REQUEST_INVALID"
_MAX_BODY_BYTES = 16 * 1024
_MAX_IDEMPOTENCY_BYTES = 128
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")
_ACCOUNT_TYPES = frozenset({"demat", "mutual_fund", "cash", "other"})


def _wire(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_wire(item) for item in value]
    if isinstance(value, dict):
        return {key: _wire(item) for key, item in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return _wire(asdict(value))
    return value


def owner_facts(store: Any, owner_scope_id: str, portfolio_id: str | None = None) -> dict[str, Any]:
    """Return only an owner's selected portfolio facts in fixed camel-case wire keys."""
    if portfolio_id is None:
        return _wire(store.list_owner(owner_scope_id))
    facts = store.list_scope(owner_scope_id, portfolio_id)
    output = {
        "accounts": _wire(facts["accounts"]),
        "openingHoldings": _wire(facts["opening_holdings"]),
        "cashFlows": _wire(facts["cash_flows"]),
    }
    if portfolio_id is not None:
        output["accountRevisions"] = [
            {"accountId": account.account_id, "revisions": _wire(store.account_revisions(owner_scope_id, account.account_id, portfolio_id))}
            for account in facts["accounts"]
        ]
        output["openingHoldingRevisions"] = [
            {"factId": fact.fact_id, "revisions": _wire(store.holding_revisions(owner_scope_id, fact.fact_id, portfolio_id))}
            for fact in facts["opening_holdings"]
        ]
        output["cashFlowRevisions"] = [
            {"factId": fact.fact_id, "revisions": _wire(store.cash_flow_revisions(owner_scope_id, fact.fact_id, portfolio_id))}
            for fact in facts["cash_flows"]
        ]
    return output


def record_wire(value: Any) -> Any:
    """Serialize one canonical persisted record without exposing store internals."""
    return _wire(value)


def stable_fact_key(fact: object) -> tuple:
    """Public deterministic identity excluding recording time from provenance."""
    if not isinstance(fact, (AccountFact, OpeningHoldingFact, CashFlowFact)) or not getattr(fact, "provenance", None):
        raise AccountDataError("ERR_ACCOUNT_PROVENANCE_INVALID")
    semantics = tuple((field.name, getattr(fact, field.name)) for field in fields(fact) if field.name != "provenance")
    provenance = fact.provenance
    return (type(fact).__name__, semantics, (provenance.source_kind, provenance.source_reference, provenance.revision))


def strict_json_object(raw: bytes) -> dict[str, Any]:
    if not isinstance(raw, bytes) or not raw or len(raw) > _MAX_BODY_BYTES:
        raise AccountDataError(REQUEST_INVALID)
    try:
        text = raw.decode("utf-8")
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        raise AccountDataError(REQUEST_INVALID) from None
    if not isinstance(value, dict):
        raise AccountDataError(REQUEST_INVALID)
    return value


def idempotency_key(headers: Any) -> str:
    values = headers.getlist("idempotency-key")
    if len(values) != 1 or not isinstance(values[0], str):
        raise AccountDataError(REQUEST_INVALID)
    value = values[0]
    if not value or not value.isascii() or len(value) > _MAX_IDEMPOTENCY_BYTES or any(not character.isprintable() or character.isspace() for character in value):
        raise AccountDataError(REQUEST_INVALID)
    return value


def request_digest(payload: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        raise AccountDataError(REQUEST_INVALID) from None
    return hashlib.sha256(encoded).hexdigest()


def generated_manual_id(kind: str, owner_scope_id: str, portfolio_id: str, idempotency: str) -> str:
    """Derive an opaque manual identifier from the server-authorized request.

    A retry carries the same idempotency key and therefore resolves to the same
    identifier.  Clients may still name an existing record when revising it,
    but a new form submission never requires a user-invented ID.
    """
    if kind not in {"account", "holding", "cash_flow"}:
        raise AccountDataError(REQUEST_INVALID)
    material = "\x1f".join(("manual-id-v1", kind, owner_scope_id, portfolio_id, idempotency)).encode("utf-8")
    return f"manual-{kind}-{hashlib.sha256(material).hexdigest()[:30]}"


def parse_account(payload: Mapping[str, Any], *, owner_scope_id: str, portfolio_id: str, idempotency: str) -> tuple[AccountFact, int | None]:
    expected = {"institution", "accountType", "currency", "sourceName", "userAlias", "custodianOrDp", "executionBroker", "maskedIdentifier", "expectedRevision"}
    extended = expected | {"manualHistoryComplete"}
    allowed = extended | {"accountId"}
    if not expected.issubset(payload) or set(payload) - allowed:
        raise AccountDataError(REQUEST_INVALID)
    expected_revision = _optional_revision(payload["expectedRevision"])
    account_id = _identifier(payload["accountId"]) if "accountId" in payload else generated_manual_id("account", owner_scope_id, portfolio_id, idempotency)
    if "accountId" not in payload and expected_revision is not None:
        raise AccountDataError(REQUEST_INVALID)
    account = AccountFact(
        account_id, owner_scope_id, _required_text(payload["institution"]), _account_type(payload["accountType"]), _currency(payload["currency"]),
        _optional_text(payload["sourceName"]), _optional_text(payload["userAlias"]), _optional_text(payload["custodianOrDp"]), _optional_text(payload["executionBroker"]), _optional_text(payload["maskedIdentifier"]),
        manual_provenance(idempotency, 1), portfolio_id, payload.get("manualHistoryComplete", False),
    )
    return account, expected_revision


def parse_opening_holding(payload: Mapping[str, Any], *, owner_scope_id: str, portfolio_id: str, idempotency: str) -> OpeningHoldingFact:
    expected = {"accountId", "instrumentName", "isin", "quantity", "asOf", "currency", "documentedCost"}
    if not expected.issubset(payload) or set(payload) - (expected | {"factId"}):
        raise AccountDataError(REQUEST_INVALID)
    return OpeningHoldingFact(
        _identifier(payload["factId"]) if "factId" in payload else generated_manual_id("holding", owner_scope_id, portfolio_id, idempotency), _identifier(payload["accountId"]), owner_scope_id, _required_text(payload["instrumentName"]), _optional_text(payload["isin"]),
        _decimal(payload["quantity"], positive=True), _date(payload["asOf"]), _currency(payload["currency"]), _decimal(payload["documentedCost"], nullable=True, nonnegative=True),
        manual_provenance(idempotency, 1), portfolio_id,
    )


def parse_cash_flow(payload: Mapping[str, Any], *, owner_scope_id: str, portfolio_id: str, idempotency: str) -> CashFlowFact:
    expected = {"accountId", "effectiveDate", "amount", "currency", "flowType", "note"}
    if not expected.issubset(payload) or set(payload) - (expected | {"factId"}):
        raise AccountDataError(REQUEST_INVALID)
    flow_type = payload["flowType"]
    if flow_type not in {"contribution", "withdrawal", "dividend", "transfer"}:
        raise AccountDataError(REQUEST_INVALID)
    return CashFlowFact(
        _identifier(payload["factId"]) if "factId" in payload else generated_manual_id("cash_flow", owner_scope_id, portfolio_id, idempotency), _identifier(payload["accountId"]), owner_scope_id, _date(payload["effectiveDate"]), _decimal(payload["amount"], nonzero=True),
        _currency(payload["currency"]), flow_type, _optional_text(payload["note"]), manual_provenance(idempotency, 1), portfolio_id,
    )


def correction_revision(payload: Mapping[str, Any]) -> int:
    if "expectedRevision" not in payload:
        raise AccountDataError(REQUEST_INVALID)
    return _optional_revision(payload["expectedRevision"]) or (_ for _ in ()).throw(AccountDataError(REQUEST_INVALID))


def void_revision(payload: Mapping[str, Any]) -> int:
    if set(payload) != {"expectedRevision"}:
        raise AccountDataError(REQUEST_INVALID)
    return correction_revision(payload)


def public_error(error: AccountDataError) -> tuple[int, str]:
    code = str(error)
    if code == STORE_UNAVAILABLE:
        return 503, STORE_UNAVAILABLE
    if code in {IDEMPOTENCY_CONFLICT, "ERR_ACCOUNT_DUPLICATE_CONFLICT", "ERR_ACCOUNT_REVISION_INVALID"}:
        return 409, code
    if code == REQUEST_INVALID or code == "ERR_ACCOUNT_NOT_FOUND":
        return 400, REQUEST_INVALID
    if code.startswith("ERR_ACCOUNT_") and code.endswith("_INVALID"):
        return 422, code
    return 400, REQUEST_INVALID


def _keys(payload: Mapping[str, Any], expected: set[str]) -> None:
    if set(payload) != expected:
        raise AccountDataError(REQUEST_INVALID)


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise AccountDataError(REQUEST_INVALID)
    return value


def _required_text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise AccountDataError(REQUEST_INVALID)
    return value.strip()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 256:
        raise AccountDataError(REQUEST_INVALID)
    return value.strip() or None


def _account_type(value: Any) -> str:
    if value not in _ACCOUNT_TYPES:
        raise AccountDataError(REQUEST_INVALID)
    return value


def _currency(value: Any) -> str:
    if not isinstance(value, str) or not _CURRENCY.fullmatch(value):
        raise AccountDataError(REQUEST_INVALID)
    return value


def _decimal(value: Any, *, nullable: bool = False, positive: bool = False, nonnegative: bool = False, nonzero: bool = False) -> Decimal | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value or value.strip() != value:
        raise AccountDataError(REQUEST_INVALID)
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError):
        raise AccountDataError(REQUEST_INVALID) from None
    if not parsed.is_finite() or format(parsed, "f") != value or (positive and parsed <= 0) or (nonnegative and parsed < 0) or (nonzero and parsed == 0):
        raise AccountDataError(REQUEST_INVALID)
    return parsed


def _date(value: Any) -> date:
    if not isinstance(value, str):
        raise AccountDataError(REQUEST_INVALID)
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise AccountDataError(REQUEST_INVALID) from None
    if parsed.isoformat() != value:
        raise AccountDataError(REQUEST_INVALID)
    return parsed


def strict_as_of(value: Any) -> date:
    """Strict query date used only by local injected valuation routes."""
    return _date(value)


def strict_account_id(value: Any) -> str:
    """Strict optional selector for the authorized local performance scope."""
    return _identifier(value)


def _optional_revision(value: Any) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise AccountDataError(REQUEST_INVALID)
    return value


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("duplicate JSON key")
        output[key] = value
    return output


def _reject_constant(_value: str) -> None:
    raise ValueError("non-finite JSON value")
