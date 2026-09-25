"""Owner-scoped account facts and injected local persistence for the private MVP."""
from __future__ import annotations

import json
import os
import stat
import tempfile
from dataclasses import fields, replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from .models.account_data import AccountDataError, AccountFact, CashFlowFact, OpeningHoldingFact, Provenance, manual_provenance
from .models.nsdl_snapshot import opaque_id


STORE_UNAVAILABLE = "ERR_ACCOUNT_STORE_UNAVAILABLE"
IDEMPOTENCY_CONFLICT = "ERR_ACCOUNT_IDEMPOTENCY_CONFLICT"
_SCHEMA_VERSION = 3
_MAX_RECEIPTS = 256
_CALCULATION_VERSION = "mvp-dated-valuation-v1"
_CACHE_REASONS = frozenset({"MISSING_HISTORY", "MISSING_PRICE", "MIXED_CURRENCY", "NON_POSITIVE_TERMINAL_VALUE", "SAME_DAY_ONLY", "INVALID_CASHFLOW", "SOLVER_FAILURE", "RECONCILIATION_REQUIRED"})


def _fact_key(fact: object) -> tuple:
    provenance = getattr(fact, "provenance", None)
    values = tuple((field.name, getattr(fact, field.name)) for field in fields(fact) if field.name != "provenance")
    provenance_key = (provenance.source_kind, provenance.source_reference, provenance.revision) if provenance else None
    return values + (("provenance", provenance_key),)


def _account_semantics(account: AccountFact) -> tuple:
    return tuple((field.name, getattr(account, field.name)) for field in fields(account) if field.name != "provenance")


def _manual_account_update_is_metadata_only(current: AccountFact, candidate: AccountFact) -> bool:
    """Keep manual account identity/currency facts immutable after creation.

    The only ordinary user edits admitted by the private MVP are the display
    alias and the separately-attested complete-history flag.  This guard lives
    below both persistence adapters; a disabled browser field is not a data
    invariant.
    """
    mutable = {"user_alias", "manual_history_complete", "provenance"}
    return all(
        getattr(current, field.name) == getattr(candidate, field.name)
        for field in fields(AccountFact)
        if field.name not in mutable
    )


def _require_manual_account_update_is_metadata_only(current: AccountFact, candidate: AccountFact) -> None:
    if current.provenance.source_kind == "manual" and not _manual_account_update_is_metadata_only(current, candidate):
        raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")


class AccountDataStore:
    """Deterministic in-memory fact contract used by local adapters and tests."""

    def __init__(self) -> None:
        self._accounts: dict[tuple[str, str, str], AccountFact] = {}
        self._account_revisions: dict[tuple[str, str, str], tuple[AccountFact, ...]] = {}
        self._holdings: dict[tuple[str, str, str], OpeningHoldingFact] = {}
        self._holding_revisions: dict[tuple[str, str, str], tuple[OpeningHoldingFact, ...]] = {}
        self._flows: dict[tuple[str, str, str], CashFlowFact] = {}
        self._flow_revisions: dict[tuple[str, str, str], tuple[CashFlowFact, ...]] = {}
        self._derived_cache: dict[tuple[str, str, str, str], tuple[str, str]] = {}

    def clone(self) -> "AccountDataStore":
        duplicate = AccountDataStore()
        duplicate._accounts = dict(self._accounts)
        duplicate._account_revisions = dict(self._account_revisions)
        duplicate._holdings = dict(self._holdings)
        duplicate._holding_revisions = dict(self._holding_revisions)
        duplicate._flows = dict(self._flows)
        duplicate._flow_revisions = dict(self._flow_revisions)
        duplicate._derived_cache = dict(self._derived_cache)
        return duplicate

    def get_account(self, owner_scope_id: str, account_id: str, portfolio_id: str = "private-preview") -> AccountFact | None:
        return self._accounts.get((owner_scope_id, portfolio_id, account_id))

    def put_account(self, account: AccountFact) -> AccountFact:
        key = (account.owner_scope_id, account.portfolio_id, account.account_id)
        existing = self._accounts.get(key)
        if existing and _fact_key(existing) == _fact_key(account):
            return existing
        if existing and (existing.provenance.source_kind != account.provenance.source_kind or (existing.source_name != account.source_name and account.provenance.source_kind != "statement")):
            raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
        if existing:
            if existing.provenance.revision < 1 or account.provenance.revision != existing.provenance.revision + 1:
                raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
            self._account_revisions[key] = self._account_revisions[key] + (account,)
        else:
            if account.provenance.revision != 1:
                raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
            self._account_revisions[key] = (account,)
        self._accounts[key] = account
        return account

    def add_opening_holding(self, fact: OpeningHoldingFact) -> OpeningHoldingFact:
        self._require_account(fact.owner_scope_id, fact.account_id, fact.portfolio_id)
        key = (fact.owner_scope_id, fact.portfolio_id, fact.fact_id)
        existing = self._holdings.get(key)
        if existing and _fact_key(existing) == _fact_key(fact):
            return existing
        if existing:
            raise AccountDataError("ERR_ACCOUNT_DUPLICATE_CONFLICT")
        if fact.provenance.revision != 1 or fact.voided:
            raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
        self._holdings[key] = fact
        self._holding_revisions[key] = (fact,)
        return fact

    def add_cash_flow(self, fact: CashFlowFact) -> CashFlowFact:
        self._require_account(fact.owner_scope_id, fact.account_id, fact.portfolio_id)
        key = (fact.owner_scope_id, fact.portfolio_id, fact.fact_id)
        existing = self._flows.get(key)
        if existing and _fact_key(existing) == _fact_key(fact):
            return existing
        if existing:
            raise AccountDataError("ERR_ACCOUNT_DUPLICATE_CONFLICT")
        if fact.provenance.revision != 1 or fact.voided:
            raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
        self._flows[key] = fact
        self._flow_revisions[key] = (fact,)
        return fact

    def revise_opening_holding(self, fact: OpeningHoldingFact, expected_revision: int) -> OpeningHoldingFact:
        key = (fact.owner_scope_id, fact.portfolio_id, fact.fact_id)
        current = self._holdings.get(key)
        if current is None or current.provenance.source_kind != "manual" or current.voided:
            raise AccountDataError("ERR_ACCOUNT_NOT_FOUND")
        if not isinstance(expected_revision, int) or isinstance(expected_revision, bool) or expected_revision != current.provenance.revision:
            raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
        if fact.account_id != current.account_id or fact.currency != current.currency or fact.voided:
            raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
        revised = replace(fact, provenance=replace(fact.provenance, source_kind="manual", revision=current.provenance.revision + 1, recorded_at=datetime.now(current.provenance.recorded_at.tzinfo)))
        self._holdings[key] = revised
        self._holding_revisions[key] = self._holding_revisions[key] + (revised,)
        return revised

    def void_opening_holding(self, owner_scope_id: str, portfolio_id: str, fact_id: str, expected_revision: int, reference: str) -> OpeningHoldingFact:
        key = (owner_scope_id, portfolio_id, fact_id)
        current = self._holdings.get(key)
        if current is None or current.provenance.source_kind != "manual" or current.voided:
            raise AccountDataError("ERR_ACCOUNT_NOT_FOUND")
        if not isinstance(expected_revision, int) or isinstance(expected_revision, bool) or expected_revision != current.provenance.revision:
            raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
        revised = replace(current, voided=True, provenance=manual_provenance(reference, current.provenance.revision + 1))
        self._holdings[key] = revised
        self._holding_revisions[key] = self._holding_revisions[key] + (revised,)
        return revised

    def revise_cash_flow(self, fact: CashFlowFact, expected_revision: int) -> CashFlowFact:
        key = (fact.owner_scope_id, fact.portfolio_id, fact.fact_id)
        current = self._flows.get(key)
        if current is None or current.provenance.source_kind != "manual" or current.voided:
            raise AccountDataError("ERR_ACCOUNT_NOT_FOUND")
        if not isinstance(expected_revision, int) or isinstance(expected_revision, bool) or expected_revision != current.provenance.revision:
            raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
        if fact.account_id != current.account_id or fact.currency != current.currency or fact.voided:
            raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
        revised = replace(fact, provenance=replace(fact.provenance, source_kind="manual", revision=current.provenance.revision + 1, recorded_at=datetime.now(current.provenance.recorded_at.tzinfo)))
        self._flows[key] = revised
        self._flow_revisions[key] = self._flow_revisions[key] + (revised,)
        return revised

    def void_cash_flow(self, owner_scope_id: str, portfolio_id: str, fact_id: str, expected_revision: int, reference: str) -> CashFlowFact:
        key = (owner_scope_id, portfolio_id, fact_id)
        current = self._flows.get(key)
        if current is None or current.provenance.source_kind != "manual" or current.voided:
            raise AccountDataError("ERR_ACCOUNT_NOT_FOUND")
        if not isinstance(expected_revision, int) or isinstance(expected_revision, bool) or expected_revision != current.provenance.revision:
            raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
        revised = replace(current, voided=True, provenance=manual_provenance(reference, current.provenance.revision + 1))
        self._flows[key] = revised
        self._flow_revisions[key] = self._flow_revisions[key] + (revised,)
        return revised

    def list_owner(self, owner_scope_id: str) -> dict[str, tuple[Any, ...]]:
        if not owner_scope_id:
            raise AccountDataError("ERR_ACCOUNT_OWNER_INVALID")
        return {
            "accounts": tuple(v for (owner, _, _), v in self._accounts.items() if owner == owner_scope_id),
            "opening_holdings": tuple(v for (owner, _, _), v in self._holdings.items() if owner == owner_scope_id),
            "cash_flows": tuple(v for (owner, _, _), v in self._flows.items() if owner == owner_scope_id),
        }

    def list_scope(self, owner_scope_id: str, portfolio_id: str) -> dict[str, tuple[Any, ...]]:
        if not owner_scope_id or not portfolio_id:
            raise AccountDataError("ERR_ACCOUNT_OWNER_INVALID")
        return {
            "accounts": tuple(v for (owner, portfolio, _), v in self._accounts.items() if owner == owner_scope_id and portfolio == portfolio_id),
            "opening_holdings": tuple(v for (owner, portfolio, _), v in self._holdings.items() if owner == owner_scope_id and portfolio == portfolio_id),
            "cash_flows": tuple(v for (owner, portfolio, _), v in self._flows.items() if owner == owner_scope_id and portfolio == portfolio_id),
        }

    def revise_account(self, owner_scope_id: str, account_id: str, portfolio_id: str = "private-preview", **changes: str | None) -> AccountFact:
        current = self._accounts.get((owner_scope_id, portfolio_id, account_id))
        if current is None:
            raise AccountDataError("ERR_ACCOUNT_NOT_FOUND")
        allowed = {"institution", "account_type", "currency", "source_name", "user_alias", "custodian_or_dp", "execution_broker", "masked_identifier", "manual_history_complete"}
        if set(changes) - allowed:
            raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
        if "source_name" in changes and changes["source_name"] != current.source_name:
            raise AccountDataError("ERR_ACCOUNT_SOURCE_IMMUTABLE")
        candidate = replace(current, **changes)
        _require_manual_account_update_is_metadata_only(current, candidate)
        provenance = replace(current.provenance, revision=current.provenance.revision + 1, recorded_at=datetime.now(current.provenance.recorded_at.tzinfo))
        return self.put_account(replace(candidate, provenance=provenance))

    def account_revisions(self, owner_scope_id: str, account_id: str, portfolio_id: str | None = None) -> tuple[AccountFact, ...]:
        account = self._require_account(owner_scope_id, account_id, portfolio_id or "private-preview")
        return self._account_revisions[(account.owner_scope_id, account.portfolio_id, account.account_id)]

    def holding_revisions(self, owner_scope_id: str, fact_id: str, portfolio_id: str) -> tuple[OpeningHoldingFact, ...]:
        key = (owner_scope_id, portfolio_id, fact_id)
        if key not in self._holding_revisions:
            raise AccountDataError("ERR_ACCOUNT_NOT_FOUND")
        return self._holding_revisions[key]

    def cash_flow_revisions(self, owner_scope_id: str, fact_id: str, portfolio_id: str) -> tuple[CashFlowFact, ...]:
        key = (owner_scope_id, portfolio_id, fact_id)
        if key not in self._flow_revisions:
            raise AccountDataError("ERR_ACCOUNT_NOT_FOUND")
        return self._flow_revisions[key]

    def _require_account(self, owner_scope_id: str, account_id: str, portfolio_id: str = "private-preview") -> AccountFact:
        account = self._accounts.get((owner_scope_id, portfolio_id, account_id))
        if account is None:
            raise AccountDataError("ERR_ACCOUNT_NOT_FOUND")
        return account

    def cached_derived(self, owner: str, portfolio: str, kind: str, as_of: str, input_digest: str) -> dict[str, Any] | None:
        row = self._derived_cache.get((owner, portfolio, kind, as_of))
        if row is None or row[0] != input_digest:
            return None
        try:
            value = json.loads(row[1], object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        except (TypeError, ValueError, json.JSONDecodeError):
            raise AccountDataError(STORE_UNAVAILABLE) from None
        if not _valid_derived_result(kind, value, as_of, input_digest):
            raise AccountDataError(STORE_UNAVAILABLE)
        return value

    def cache_derived(self, owner: str, portfolio: str, kind: str, as_of: str, input_digest: str, result: dict[str, Any]) -> None:
        if kind not in {"valuation", "performance"} or not all(isinstance(value, str) and value for value in (owner, portfolio, as_of, input_digest)):
            raise AccountDataError(STORE_UNAVAILABLE)
        if not _valid_derived_result(kind, result, as_of, input_digest):
            raise AccountDataError(STORE_UNAVAILABLE)
        try:
            encoded = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        except (TypeError, ValueError):
            raise AccountDataError(STORE_UNAVAILABLE) from None
        if len(encoded) > 16384:
            raise AccountDataError(STORE_UNAVAILABLE)
        self._derived_cache[(owner, portfolio, kind, as_of)] = (input_digest, encoded)


class LocalAccountDataStore:
    """Caller-injected atomic JSON persistence adapter; it never self-configures a path."""

    def __init__(self, data_path: str | Path) -> None:
        self._path = self._validate_path(data_path)
        self._store = AccountDataStore()
        self._receipts: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        self._load()

    @staticmethod
    def _validate_path(data_path: str | Path) -> Path:
        path = Path(data_path)
        if not path.is_absolute() or path.name in {"", ".", ".."} or path.parent == path:
            raise AccountDataError(STORE_UNAVAILABLE)
        try:
            parent = path.parent.resolve(strict=True)
            target = path.resolve(strict=False)
            mode = parent.stat().st_mode
            if target.parent != parent or not stat.S_ISDIR(mode) or mode & 0o077:
                raise ValueError()
            if path.exists():
                target_mode = path.lstat().st_mode
                if not stat.S_ISREG(target_mode) or stat.S_ISLNK(target_mode) or target_mode & 0o077:
                    raise ValueError()
        except (OSError, ValueError):
            raise AccountDataError(STORE_UNAVAILABLE) from None
        return target

    def list_scope(self, owner_scope_id: str, portfolio_id: str) -> dict[str, tuple[Any, ...]]:
        return self._store.list_scope(owner_scope_id, portfolio_id)

    def account_revisions(self, owner_scope_id: str, account_id: str, portfolio_id: str) -> tuple[AccountFact, ...]:
        return self._store.account_revisions(owner_scope_id, account_id, portfolio_id)

    def holding_revisions(self, owner_scope_id: str, fact_id: str, portfolio_id: str) -> tuple[OpeningHoldingFact, ...]:
        return self._store.holding_revisions(owner_scope_id, fact_id, portfolio_id)

    def cash_flow_revisions(self, owner_scope_id: str, fact_id: str, portfolio_id: str) -> tuple[CashFlowFact, ...]:
        return self._store.cash_flow_revisions(owner_scope_id, fact_id, portfolio_id)

    def commit_account(self, account: AccountFact, *, route: str, idempotency_key: str, request_digest: str, expected_revision: int | None) -> AccountFact:
        def mutate(candidate: AccountDataStore) -> AccountFact:
            current = candidate.get_account(account.owner_scope_id, account.account_id, account.portfolio_id)
            if current is None:
                if expected_revision is not None or account.provenance.revision != 1:
                    raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
                return candidate.put_account(account)
            if current.provenance.source_kind != account.provenance.source_kind or (current.source_name != account.source_name and account.provenance.source_kind != "statement"):
                raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
            _require_manual_account_update_is_metadata_only(current, account)
            if _account_semantics(current) == _account_semantics(account) and expected_revision in {None, current.provenance.revision}:
                if current.provenance.source_kind == account.provenance.source_kind == "statement" and current.provenance.source_reference != account.provenance.source_reference:
                    return candidate.put_account(replace(account, provenance=replace(account.provenance, revision=current.provenance.revision + 1)))
                return current
            if expected_revision != current.provenance.revision:
                raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
            return candidate.put_account(replace(account, provenance=replace(account.provenance, revision=current.provenance.revision + 1)))
        return self._commit(route, account.owner_scope_id, account.portfolio_id, idempotency_key, request_digest, "account", account.account_id, mutate)

    def commit_opening_holding(self, fact: OpeningHoldingFact, *, route: str, idempotency_key: str, request_digest: str) -> OpeningHoldingFact:
        return self._commit(route, fact.owner_scope_id, fact.portfolio_id, idempotency_key, request_digest, "opening_holding", fact.fact_id, lambda candidate: candidate.add_opening_holding(fact))

    def commit_cash_flow(self, fact: CashFlowFact, *, route: str, idempotency_key: str, request_digest: str) -> CashFlowFact:
        return self._commit(route, fact.owner_scope_id, fact.portfolio_id, idempotency_key, request_digest, "cash_flow", fact.fact_id, lambda candidate: candidate.add_cash_flow(fact))

    def revise_opening_holding(self, fact: OpeningHoldingFact, *, route: str, idempotency_key: str, request_digest: str, expected_revision: int) -> OpeningHoldingFact:
        return self._commit(route, fact.owner_scope_id, fact.portfolio_id, idempotency_key, request_digest, "opening_holding", fact.fact_id, lambda candidate: candidate.revise_opening_holding(fact, expected_revision))

    def void_opening_holding(self, owner: str, portfolio: str, fact_id: str, *, route: str, idempotency_key: str, request_digest: str, expected_revision: int) -> OpeningHoldingFact:
        return self._commit(route, owner, portfolio, idempotency_key, request_digest, "opening_holding", fact_id, lambda candidate: candidate.void_opening_holding(owner, portfolio, fact_id, expected_revision, idempotency_key))

    def revise_cash_flow(self, fact: CashFlowFact, *, route: str, idempotency_key: str, request_digest: str, expected_revision: int) -> CashFlowFact:
        return self._commit(route, fact.owner_scope_id, fact.portfolio_id, idempotency_key, request_digest, "cash_flow", fact.fact_id, lambda candidate: candidate.revise_cash_flow(fact, expected_revision))

    def void_cash_flow(self, owner: str, portfolio: str, fact_id: str, *, route: str, idempotency_key: str, request_digest: str, expected_revision: int) -> CashFlowFact:
        return self._commit(route, owner, portfolio, idempotency_key, request_digest, "cash_flow", fact_id, lambda candidate: candidate.void_cash_flow(owner, portfolio, fact_id, expected_revision, idempotency_key))

    def cache_derived(self, owner: str, portfolio: str, kind: str, as_of: str, input_digest: str, result: dict[str, Any]) -> None:
        candidate = self._store.clone()
        candidate.cache_derived(owner, portfolio, kind, as_of, input_digest, result)
        self._persist(candidate, self._receipts)
        self._store = candidate

    def cached_derived(self, owner: str, portfolio: str, kind: str, as_of: str, input_digest: str) -> dict[str, Any] | None:
        return self._store.cached_derived(owner, portfolio, kind, as_of, input_digest)

    def _commit(self, route: str, owner: str, portfolio: str, idempotency_key: str, request_digest: str, kind: str, result_id: str, mutate: Callable[[AccountDataStore], Any]) -> Any:
        receipt_key = (route, owner, portfolio, idempotency_key)
        prior = self._receipts.get(receipt_key)
        if prior is not None:
            if prior["requestDigest"] != request_digest:
                raise AccountDataError(IDEMPOTENCY_CONFLICT)
            return self._resolve_receipt(self._store, prior, owner, portfolio)
        if len(self._receipts) >= _MAX_RECEIPTS:
            raise AccountDataError(STORE_UNAVAILABLE)
        candidate = self._store.clone()
        result = mutate(candidate)
        receipts = dict(self._receipts)
        revision = result.provenance.revision
        receipts[receipt_key] = {"requestDigest": request_digest, "resultKind": kind, "resultId": result_id, "revision": revision}
        try:
            self._persist(candidate, receipts)
        except _PostReplaceDurabilityError:
            # os.replace completed, so the newly encoded snapshot is the current
            # target. Reload it before returning the fixed unavailable outcome;
            # callers can safely retry with their same persisted idempotency key.
            try:
                self._load()
            except AccountDataError:
                # The replacement has still happened, and the candidate is the
                # only validated representation of that exact snapshot.
                self._store, self._receipts = candidate, receipts
            raise AccountDataError(STORE_UNAVAILABLE) from None
        self._store, self._receipts = candidate, receipts
        return result

    @staticmethod
    def _resolve_receipt(store: AccountDataStore, receipt: dict[str, Any], owner: str, portfolio: str) -> Any:
        kind, result_id = receipt["resultKind"], receipt["resultId"]
        if kind == "account":
            revisions = store._account_revisions.get((owner, portfolio, result_id), ())
            index = receipt["revision"] - 1
            if 0 <= index < len(revisions) and revisions[index].provenance.revision == receipt["revision"]:
                return revisions[index]
        elif kind == "opening_holding":
            revisions = store._holding_revisions.get((owner, portfolio, result_id), ())
            index = receipt["revision"] - 1
            if 0 <= index < len(revisions) and revisions[index].provenance.revision == receipt["revision"]:
                return revisions[index]
        elif kind == "cash_flow":
            revisions = store._flow_revisions.get((owner, portfolio, result_id), ())
            index = receipt["revision"] - 1
            if 0 <= index < len(revisions) and revisions[index].provenance.revision == receipt["revision"]:
                return revisions[index]
        raise AccountDataError(STORE_UNAVAILABLE)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            store, receipts = _decode_document(value)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError, InvalidOperation, AccountDataError):
            raise AccountDataError(STORE_UNAVAILABLE) from None
        self._store, self._receipts = store, receipts

    def _persist(self, candidate: AccountDataStore, receipts: dict[tuple[str, str, str, str], dict[str, Any]]) -> None:
        descriptor = None
        temporary_path: str | None = None
        replaced = False
        try:
            payload = json.dumps(_encode_document(candidate, receipts), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")
            descriptor, temporary_path = tempfile.mkstemp(prefix=f".{self._path.name}.", suffix=".tmp", dir=self._path.parent)
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb", closefd=True) as handle:
                descriptor = None
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self._path)
            temporary_path = None
            replaced = True
            directory_fd = os.open(self._path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except (OSError, TypeError, ValueError, OverflowError, UnicodeError):
            if replaced:
                raise _PostReplaceDurabilityError() from None
            raise AccountDataError(STORE_UNAVAILABLE) from None
        finally:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
            if temporary_path is not None:
                try:
                    os.unlink(temporary_path)
                except OSError:
                    pass


class FirestoreAccountDataStore:
    """Owner-scoped Firestore adapter with injected, named Admin SDK dependencies.

    The account graph stays in one bounded root document so each fact mutation
    and its idempotency receipt can commit together. Derived results live in a
    separate subcollection because they grow with valuation dates rather than
    with the account graph.
    """

    MAX_GRAPH_DOCUMENT_BYTES = 512 * 1024

    def __init__(self, project_id: str, account_key: bytes, *, client: Any = None, firestore_module: Any = None) -> None:
        if not isinstance(project_id, str) or not project_id.strip() or not isinstance(account_key, bytes) or len(account_key) != 32 or client is None or firestore_module is None:
            raise AccountDataError(STORE_UNAVAILABLE)
        self.project_id = project_id
        self._secret = account_key
        self.client = client
        self._firestore = firestore_module

    def _owner_key(self, owner: str) -> str:
        if not isinstance(owner, str) or not owner:
            raise AccountDataError("ERR_ACCOUNT_OWNER_INVALID")
        try:
            return opaque_id(self._secret, "account-owner", owner)
        except Exception as error:
            raise AccountDataError(STORE_UNAVAILABLE) from error

    def holding_revisions(self, owner_scope_id: str, fact_id: str, portfolio_id: str) -> tuple[OpeningHoldingFact, ...]:
        try:
            store, _count = self._decode_root(self._direct_document(self._root(owner_scope_id, portfolio_id)), owner_scope_id, portfolio_id)
            return store.holding_revisions(owner_scope_id, fact_id, portfolio_id)
        except AccountDataError:
            raise
        except Exception as error:
            raise AccountDataError(STORE_UNAVAILABLE) from error

    def cash_flow_revisions(self, owner_scope_id: str, fact_id: str, portfolio_id: str) -> tuple[CashFlowFact, ...]:
        try:
            store, _count = self._decode_root(self._direct_document(self._root(owner_scope_id, portfolio_id)), owner_scope_id, portfolio_id)
            return store.cash_flow_revisions(owner_scope_id, fact_id, portfolio_id)
        except AccountDataError:
            raise
        except Exception as error:
            raise AccountDataError(STORE_UNAVAILABLE) from error

    def _portfolio_key(self, owner: str, portfolio: str) -> str:
        if not isinstance(portfolio, str) or not portfolio:
            raise AccountDataError("ERR_ACCOUNT_OWNER_INVALID")
        try:
            return opaque_id(self._secret, "account-portfolio", owner, portfolio)
        except Exception as error:
            raise AccountDataError(STORE_UNAVAILABLE) from error

    def _root(self, owner: str, portfolio: str) -> Any:
        return self.client.collection("private_account_data").document(self._owner_key(owner)).collection("portfolios").document(self._portfolio_key(owner, portfolio))

    def _receipt(self, owner: str, portfolio: str, route: str, idempotency_key: str) -> Any:
        if not all(isinstance(value, str) and value for value in (route, idempotency_key)):
            raise AccountDataError(STORE_UNAVAILABLE)
        try:
            key = opaque_id(self._secret, "account-receipt", owner, portfolio, route, idempotency_key)
        except Exception as error:
            raise AccountDataError(STORE_UNAVAILABLE) from error
        return self._root(owner, portfolio).collection("receipts").document(key)

    def _derived(self, owner: str, portfolio: str, kind: str, as_of: str) -> Any:
        try:
            key = opaque_id(self._secret, "account-derived", owner, portfolio, kind, as_of)
        except Exception as error:
            raise AccountDataError(STORE_UNAVAILABLE) from error
        return self._root(owner, portfolio).collection("derived").document(key)

    @staticmethod
    def _transaction_document(transaction: Any, reference: Any) -> Any:
        value = transaction.get(reference)
        return value if hasattr(value, "exists") else next(iter(value), None)

    @staticmethod
    def _direct_document(reference: Any) -> Any:
        value = reference.get()
        if not hasattr(value, "exists"):
            raise AccountDataError(STORE_UNAVAILABLE)
        return value

    @staticmethod
    def _encoded_size(value: Any) -> int:
        try:
            return len(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8"))
        except (TypeError, ValueError, UnicodeError) as error:
            raise AccountDataError(STORE_UNAVAILABLE) from error

    def _graph_wire(self, store: AccountDataStore) -> dict[str, Any]:
        value = _encode_document(store, {})
        if value.get("receipts") != [] or value.get("derivedCache") != []:
            raise AccountDataError(STORE_UNAVAILABLE)
        # Cloud Firestore forbids an array directly containing another array.
        # LocalAccountDataStore intentionally retains its compact list-of-lists
        # JSON contract; only this Firestore adapter wraps each revision group.
        value["accountRevisions"] = [{"revisions": revisions} for revisions in value["accountRevisions"]]
        value["holdingRevisions"] = [{"revisions": revisions} for revisions in value["holdingRevisions"]]
        value["cashFlowRevisions"] = [{"revisions": revisions} for revisions in value["cashFlowRevisions"]]
        return value

    @staticmethod
    def _decode_graph(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict) or not isinstance(value.get("accountRevisions"), list):
            raise AccountDataError(STORE_UNAVAILABLE)
        normalized = dict(value)
        legacy = "holdingRevisions" not in value and "cashFlowRevisions" not in value
        if legacy:
            if not isinstance(value.get("openingHoldings"), list) or not isinstance(value.get("cashFlows"), list):
                raise AccountDataError(STORE_UNAVAILABLE)
            normalized["holdingRevisions"] = [[item] for item in value["openingHoldings"]]
            normalized["cashFlowRevisions"] = [[item] for item in value["cashFlows"]]
            normalized.pop("openingHoldings", None)
            normalized.pop("cashFlows", None)
            normalized["schemaVersion"] = _SCHEMA_VERSION
        for name in ("accountRevisions", "holdingRevisions", "cashFlowRevisions"):
            if not isinstance(normalized.get(name), list):
                raise AccountDataError(STORE_UNAVAILABLE)
            revisions: list[list[Any]] = []
            for group in normalized[name]:
                # The list form is accepted only for synthetic documents written
                # by the prior adapter. Firestore itself cannot persist it.
                if isinstance(group, list):
                    revisions.append(group)
                elif isinstance(group, dict) and set(group) == {"revisions"} and isinstance(group["revisions"], list):
                    revisions.append(group["revisions"])
                else:
                    raise AccountDataError(STORE_UNAVAILABLE)
            normalized[name] = revisions
        return normalized

    def _validate_scope(self, store: AccountDataStore, owner: str, portfolio: str) -> None:
        keys = (*store._accounts, *store._account_revisions, *store._holdings, *store._holding_revisions, *store._flows, *store._flow_revisions)
        if any(key[0] != owner or key[1] != portfolio for key in keys):
            raise AccountDataError(STORE_UNAVAILABLE)

    def _decode_root(self, document: Any, owner: str, portfolio: str | None) -> tuple[AccountDataStore, int]:
        if not document or not document.exists:
            return AccountDataStore(), 0
        value = document.to_dict()
        if not isinstance(value, dict) or set(value) != {"ownerKey", "portfolioKey", "receiptCount", "graph"}:
            raise AccountDataError(STORE_UNAVAILABLE)
        owner_key = self._owner_key(owner)
        if value["ownerKey"] != owner_key or not isinstance(value["portfolioKey"], str) or not isinstance(value["receiptCount"], int) or isinstance(value["receiptCount"], bool) or not 0 <= value["receiptCount"] <= _MAX_RECEIPTS:
            raise AccountDataError(STORE_UNAVAILABLE)
        try:
            store, receipts = _decode_document(self._decode_graph(value["graph"]))
        except (AccountDataError, TypeError, ValueError, InvalidOperation, json.JSONDecodeError):
            raise AccountDataError(STORE_UNAVAILABLE) from None
        if receipts or store._derived_cache:
            raise AccountDataError(STORE_UNAVAILABLE)
        portfolios = {key[1] for key in (*store._accounts, *store._account_revisions, *store._holdings, *store._holding_revisions, *store._flows, *store._flow_revisions)}
        if len(portfolios) != 1:
            raise AccountDataError(STORE_UNAVAILABLE)
        stored_portfolio = next(iter(portfolios))
        if portfolio is not None and stored_portfolio != portfolio:
            raise AccountDataError(STORE_UNAVAILABLE)
        self._validate_scope(store, owner, stored_portfolio)
        if value["portfolioKey"] != self._portfolio_key(owner, stored_portfolio):
            raise AccountDataError(STORE_UNAVAILABLE)
        return store, value["receiptCount"]

    def _root_value(self, owner: str, portfolio: str, store: AccountDataStore, receipt_count: int) -> dict[str, Any]:
        value = {
            "ownerKey": self._owner_key(owner),
            "portfolioKey": self._portfolio_key(owner, portfolio),
            "receiptCount": receipt_count,
            "graph": self._graph_wire(store),
        }
        if self._encoded_size(value) > self.MAX_GRAPH_DOCUMENT_BYTES:
            raise AccountDataError(STORE_UNAVAILABLE)
        return value

    @staticmethod
    def _receipt_value(value: Any) -> dict[str, Any]:
        if not isinstance(value, dict) or set(value) != {"requestDigest", "resultKind", "resultId", "revision"}:
            raise AccountDataError(STORE_UNAVAILABLE)
        if not all(isinstance(value[key], str) and value[key].isascii() and value[key] for key in ("requestDigest", "resultKind", "resultId")) or value["resultKind"] not in {"account", "opening_holding", "cash_flow"} or not isinstance(value["revision"], int) or isinstance(value["revision"], bool) or value["revision"] < 1:
            raise AccountDataError(STORE_UNAVAILABLE)
        return dict(value)

    def _run_transaction(self, callback: Callable[[Any], Any]) -> Any:
        started = wrote = False

        def wrapped(transaction: Any) -> Any:
            nonlocal started, wrote
            started = True
            result = callback(transaction)
            wrote = True
            return result

        try:
            return self._firestore.transactional(wrapped)(self.client.transaction(max_attempts=2))
        except AccountDataError:
            raise
        except Exception as error:
            # Acknowledgement can fail after a transaction commits. The caller's
            # persisted idempotency key is the only safe recovery mechanism.
            raise AccountDataError(STORE_UNAVAILABLE) from error

    def list_scope(self, owner_scope_id: str, portfolio_id: str) -> dict[str, tuple[Any, ...]]:
        try:
            store, _count = self._decode_root(self._direct_document(self._root(owner_scope_id, portfolio_id)), owner_scope_id, portfolio_id)
            return store.list_scope(owner_scope_id, portfolio_id)
        except AccountDataError:
            raise
        except Exception as error:
            raise AccountDataError(STORE_UNAVAILABLE) from error

    def list_owner(self, owner_scope_id: str) -> dict[str, tuple[Any, ...]]:
        owner_key = self._owner_key(owner_scope_id)
        try:
            documents = self.client.collection("private_account_data").document(owner_key).collection("portfolios").stream()
            merged = {"accounts": (), "opening_holdings": (), "cash_flows": ()}
            for document in documents:
                store, _count = self._decode_root(document, owner_scope_id, None)
                facts = store.list_owner(owner_scope_id)
                merged = {name: merged[name] + facts[name] for name in merged}
            return merged
        except AccountDataError:
            raise
        except Exception as error:
            raise AccountDataError(STORE_UNAVAILABLE) from error

    def account_revisions(self, owner_scope_id: str, account_id: str, portfolio_id: str) -> tuple[AccountFact, ...]:
        try:
            store, _count = self._decode_root(self._direct_document(self._root(owner_scope_id, portfolio_id)), owner_scope_id, portfolio_id)
            return store.account_revisions(owner_scope_id, account_id, portfolio_id)
        except AccountDataError:
            raise
        except Exception as error:
            raise AccountDataError(STORE_UNAVAILABLE) from error

    def commit_account(self, account: AccountFact, *, route: str, idempotency_key: str, request_digest: str, expected_revision: int | None) -> AccountFact:
        def mutate(candidate: AccountDataStore) -> AccountFact:
            current = candidate.get_account(account.owner_scope_id, account.account_id, account.portfolio_id)
            if current is None:
                if expected_revision is not None or account.provenance.revision != 1:
                    raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
                return candidate.put_account(account)
            if current.provenance.source_kind != account.provenance.source_kind or (current.source_name != account.source_name and account.provenance.source_kind != "statement"):
                raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
            _require_manual_account_update_is_metadata_only(current, account)
            if _account_semantics(current) == _account_semantics(account) and expected_revision in {None, current.provenance.revision}:
                if current.provenance.source_kind == account.provenance.source_kind == "statement" and current.provenance.source_reference != account.provenance.source_reference:
                    return candidate.put_account(replace(account, provenance=replace(account.provenance, revision=current.provenance.revision + 1)))
                return current
            if expected_revision != current.provenance.revision:
                raise AccountDataError("ERR_ACCOUNT_REVISION_INVALID")
            return candidate.put_account(replace(account, provenance=replace(account.provenance, revision=current.provenance.revision + 1)))
        return self._commit(route, account.owner_scope_id, account.portfolio_id, idempotency_key, request_digest, "account", account.account_id, mutate)

    def commit_opening_holding(self, fact: OpeningHoldingFact, *, route: str, idempotency_key: str, request_digest: str) -> OpeningHoldingFact:
        return self._commit(route, fact.owner_scope_id, fact.portfolio_id, idempotency_key, request_digest, "opening_holding", fact.fact_id, lambda candidate: candidate.add_opening_holding(fact))

    def commit_cash_flow(self, fact: CashFlowFact, *, route: str, idempotency_key: str, request_digest: str) -> CashFlowFact:
        return self._commit(route, fact.owner_scope_id, fact.portfolio_id, idempotency_key, request_digest, "cash_flow", fact.fact_id, lambda candidate: candidate.add_cash_flow(fact))

    def revise_opening_holding(self, fact: OpeningHoldingFact, *, route: str, idempotency_key: str, request_digest: str, expected_revision: int) -> OpeningHoldingFact:
        return self._commit(route, fact.owner_scope_id, fact.portfolio_id, idempotency_key, request_digest, "opening_holding", fact.fact_id, lambda candidate: candidate.revise_opening_holding(fact, expected_revision))

    def void_opening_holding(self, owner: str, portfolio: str, fact_id: str, *, route: str, idempotency_key: str, request_digest: str, expected_revision: int) -> OpeningHoldingFact:
        return self._commit(route, owner, portfolio, idempotency_key, request_digest, "opening_holding", fact_id, lambda candidate: candidate.void_opening_holding(owner, portfolio, fact_id, expected_revision, idempotency_key))

    def revise_cash_flow(self, fact: CashFlowFact, *, route: str, idempotency_key: str, request_digest: str, expected_revision: int) -> CashFlowFact:
        return self._commit(route, fact.owner_scope_id, fact.portfolio_id, idempotency_key, request_digest, "cash_flow", fact.fact_id, lambda candidate: candidate.revise_cash_flow(fact, expected_revision))

    def void_cash_flow(self, owner: str, portfolio: str, fact_id: str, *, route: str, idempotency_key: str, request_digest: str, expected_revision: int) -> CashFlowFact:
        return self._commit(route, owner, portfolio, idempotency_key, request_digest, "cash_flow", fact_id, lambda candidate: candidate.void_cash_flow(owner, portfolio, fact_id, expected_revision, idempotency_key))

    def _commit(self, route: str, owner: str, portfolio: str, idempotency_key: str, request_digest: str, kind: str, result_id: str, mutate: Callable[[AccountDataStore], Any]) -> Any:
        root = self._root(owner, portfolio)
        receipt = self._receipt(owner, portfolio, route, idempotency_key)
        planned_receipt = self._receipt_value({"requestDigest": request_digest, "resultKind": kind, "resultId": result_id, "revision": 1})

        def callback(transaction: Any) -> Any:
            current, receipt_count = self._decode_root(self._transaction_document(transaction, root), owner, portfolio)
            saved = self._transaction_document(transaction, receipt)
            if saved and saved.exists:
                prior = self._receipt_value(saved.to_dict())
                if prior["requestDigest"] != request_digest:
                    raise AccountDataError(IDEMPOTENCY_CONFLICT)
                return LocalAccountDataStore._resolve_receipt(current, prior, owner, portfolio)
            if receipt_count >= _MAX_RECEIPTS:
                raise AccountDataError(STORE_UNAVAILABLE)
            candidate = current.clone()
            result = mutate(candidate)
            revision = result.provenance.revision
            receipt_value = {**planned_receipt, "revision": revision}
            transaction.set(root, self._root_value(owner, portfolio, candidate, receipt_count + 1))
            transaction.set(receipt, receipt_value)
            return result

        return self._run_transaction(callback)

    def cached_derived(self, owner: str, portfolio: str, kind: str, as_of: str, input_digest: str) -> dict[str, Any] | None:
        try:
            document = self._direct_document(self._derived(owner, portfolio, kind, as_of))
            if not document.exists:
                return None
            value = document.to_dict()
            expected = {"ownerKey", "portfolioKey", "kind", "asOf", "inputDigest", "result"}
            if not isinstance(value, dict) or set(value) != expected or value["ownerKey"] != self._owner_key(owner) or value["portfolioKey"] != self._portfolio_key(owner, portfolio) or value["kind"] != kind or value["asOf"] != as_of or not isinstance(value["inputDigest"], str):
                raise AccountDataError(STORE_UNAVAILABLE)
            if value["inputDigest"] != input_digest:
                return None
            validator = AccountDataStore()
            validator.cache_derived(owner, portfolio, kind, as_of, input_digest, value["result"])
            return validator.cached_derived(owner, portfolio, kind, as_of, input_digest)
        except AccountDataError:
            raise
        except Exception as error:
            raise AccountDataError(STORE_UNAVAILABLE) from error

    def cache_derived(self, owner: str, portfolio: str, kind: str, as_of: str, input_digest: str, result: dict[str, Any]) -> None:
        validator = AccountDataStore()
        validator.cache_derived(owner, portfolio, kind, as_of, input_digest, result)
        normalized = validator.cached_derived(owner, portfolio, kind, as_of, input_digest)
        if normalized is None:
            raise AccountDataError(STORE_UNAVAILABLE)
        document = self._derived(owner, portfolio, kind, as_of)
        value = {
            "ownerKey": self._owner_key(owner),
            "portfolioKey": self._portfolio_key(owner, portfolio),
            "kind": kind,
            "asOf": as_of,
            "inputDigest": input_digest,
            "result": normalized,
        }
        if self._encoded_size(value) > 20 * 1024:
            raise AccountDataError(STORE_UNAVAILABLE)
        self._run_transaction(lambda transaction: transaction.set(document, value))


class _PostReplaceDurabilityError(Exception):
    """Internal marker: replacement succeeded but its directory sync did not."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise ValueError("non-finite number")


def _wire_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "__dataclass_fields__"):
        return {field.name: _wire_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple):
        return [_wire_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _wire_value(item) for key, item in value.items()}
    return value


def _encode_document(store: AccountDataStore, receipts: dict[tuple[str, str, str, str], dict[str, Any]]) -> dict[str, Any]:
    receipt_rows = []
    for (route, owner, portfolio, key), receipt in sorted(receipts.items()):
        receipt_rows.append({"route": route, "ownerScopeId": owner, "portfolioId": portfolio, "key": key, **receipt})
    return {
        "schemaVersion": _SCHEMA_VERSION,
        "accountRevisions": [_wire_value(revisions) for _key, revisions in sorted(store._account_revisions.items())],
        "holdingRevisions": [_wire_value(revisions) for _key, revisions in sorted(store._holding_revisions.items())],
        "cashFlowRevisions": [_wire_value(revisions) for _key, revisions in sorted(store._flow_revisions.items())],
        "receipts": receipt_rows,
        "derivedCache": [
            {"ownerScopeId": owner, "portfolioId": portfolio, "kind": kind, "asOf": as_of, "inputDigest": digest, "result": result}
            for (owner, portfolio, kind, as_of), (digest, result) in sorted(store._derived_cache.items())
        ],
    }


def _decode_text(value: Any, name: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(name)
    return value.strip()


def _decode_date(value: Any) -> date:
    if not isinstance(value, str):
        raise ValueError("date")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("date")
    return parsed


def _decode_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("datetime")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.isoformat() != value:
        raise ValueError("datetime")
    return parsed


def _decode_decimal(value: Any, *, nullable: bool = False) -> Decimal | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError("decimal")
    decimal = Decimal(value)
    if not decimal.is_finite() or format(decimal, "f") != value:
        raise ValueError("decimal")
    return decimal


def _canonical_decimal_text(value: Any) -> bool:
    try:
        return isinstance(value, str) and bool(value) and value.strip() == value and Decimal(value).is_finite() and format(Decimal(value), "f") == value
    except (InvalidOperation, ValueError):
        return False


def _valid_reason(value: Any) -> bool:
    return isinstance(value, str) and value in _CACHE_REASONS


def _valid_derived_result(kind: str, result: Any, as_of: str, input_digest: str) -> bool:
    if kind not in {"valuation", "performance"} or not isinstance(result, dict) or not isinstance(as_of, str) or not isinstance(input_digest, str) or len(input_digest) != 64 or any(character not in "0123456789abcdef" for character in input_digest):
        return False
    try:
        _decode_date(as_of)
    except ValueError:
        return False
    if result.get("calculationVersion") != _CALCULATION_VERSION or result.get("inputDigest") != input_digest or result.get("asOf") != as_of:
        return False
    if kind == "valuation":
        if set(result) != {"calculationVersion", "inputDigest", "asOf", "holdings", "summaryByCurrency"} or not isinstance(result["holdings"], list) or not isinstance(result["summaryByCurrency"], list):
            return False
        holding_ids: set[str] = set()
        for row in result["holdings"]:
            if not isinstance(row, dict) or not isinstance(row.get("holdingId"), str) or not row["holdingId"]:
                return False
            if row["holdingId"] in holding_ids:
                return False
            holding_ids.add(row["holdingId"])
            if row.get("status") == "INSUFFICIENT_DATA":
                if set(row) != {"holdingId", "accountScopeId", "holdingSource", "reconciliationStatus", "status", "reason"} or not isinstance(row.get("accountScopeId"), str) or not row["accountScopeId"] or row.get("holdingSource") != "MANUAL" or row.get("reconciliationStatus") not in {"CLEAR", "REVIEW_REQUIRED"} or row.get("reason") not in {"MISSING_PRICE", "MIXED_CURRENCY"}:
                    return False
            elif row.get("status") == "CALCULATED":
                if set(row) != {"holdingId", "accountScopeId", "holdingSource", "reconciliationStatus", "status", "quantity", "price", "currency", "priceDate", "source", "priceStatus", "currentValue"} or not isinstance(row.get("accountScopeId"), str) or not row["accountScopeId"] or row.get("holdingSource") != "MANUAL" or row.get("reconciliationStatus") not in {"CLEAR", "REVIEW_REQUIRED"} or not all(_canonical_decimal_text(row.get(key)) for key in ("quantity", "price", "currentValue")) or not isinstance(row.get("currency"), str) or len(row["currency"]) != 3 or row["currency"] != row["currency"].upper() or not isinstance(row.get("priceDate"), str) or row.get("source") not in {"AMFI", "NSE"} or row.get("priceStatus") not in {"DAILY_NAV", "EOD_CLOSE"}:
                    return False
                try:
                    _decode_date(row["priceDate"])
                except ValueError:
                    return False
                if row["priceDate"] != as_of or Decimal(row["quantity"]) * Decimal(row["price"]) != Decimal(row["currentValue"]):
                    return False
            elif row.get("status") == "STATEMENT_VALUE":
                if set(row) != {"holdingId", "holdingSource", "status", "accountScopeId", "quantity", "currency", "statementPrice", "statementValue", "statementDate"} or row.get("holdingSource") != "STATEMENT" or not isinstance(row.get("accountScopeId"), str) or not row["accountScopeId"] or not _canonical_decimal_text(row.get("quantity")) or not isinstance(row.get("currency"), str) or len(row["currency"]) != 3 or row["currency"] != row["currency"].upper() or (row.get("statementPrice") is not None and not _canonical_decimal_text(row.get("statementPrice"))) or (row.get("statementValue") is not None and not _canonical_decimal_text(row.get("statementValue"))) or not isinstance(row.get("statementDate"), str):
                    return False
                try:
                    _decode_date(row["statementDate"])
                except ValueError:
                    return False
            else:
                return False
        currencies: set[str] = set()
        for row in result["summaryByCurrency"]:
            if not isinstance(row, dict) or set(row) != {"currency", "calculatedValue", "statementValue", "totalIncludedValue", "calculatedAsOf", "statementAsOf", "excludedForReconciliationCount"} or not isinstance(row.get("currency"), str) or len(row["currency"]) != 3 or row["currency"] != row["currency"].upper() or row["currency"] in currencies or not isinstance(row.get("excludedForReconciliationCount"), int) or isinstance(row.get("excludedForReconciliationCount"), bool) or row["excludedForReconciliationCount"] < 0 or not all(_canonical_decimal_text(row.get(key)) for key in ("calculatedValue", "statementValue", "totalIncludedValue")):
                return False
            currencies.add(row["currency"])
            if Decimal(row["calculatedValue"]) + Decimal(row["statementValue"]) != Decimal(row["totalIncludedValue"]):
                return False
            for date_key, value in (("calculatedAsOf", row["calculatedAsOf"]), ("statementAsOf", row["statementAsOf"])):
                if value is not None:
                    if not isinstance(value, str):
                        return False
                    try:
                        _decode_date(value)
                    except ValueError:
                        return False
        return True
    if set(result) != {"calculationVersion", "inputDigest", "asOf", "coverage", "gain", "xirr"} or not isinstance(result.get("coverage"), dict) or set(result["coverage"]) != {"historyComplete", "cashflowCount", "reasons", "scope"}:
        return False
    coverage = result["coverage"]
    if not isinstance(coverage["historyComplete"], bool) or not isinstance(coverage["cashflowCount"], int) or isinstance(coverage["cashflowCount"], bool) or coverage["cashflowCount"] < 0 or coverage.get("scope") != "manual_complete_history_only" or not isinstance(coverage["reasons"], list) or not all(_valid_reason(reason) for reason in coverage["reasons"]):
        return False
    gain, xirr = result["gain"], result["xirr"]
    if not isinstance(gain, dict) or not isinstance(xirr, dict):
        return False
    gain_valid = (set(gain) == {"status", "value", "currency"} and gain.get("status") == "CALCULATED" and _canonical_decimal_text(gain.get("value")) and isinstance(gain.get("currency"), str) and len(gain["currency"]) == 3) or (set(gain) == {"status", "reason"} and gain.get("status") == "INSUFFICIENT_DATA" and _valid_reason(gain.get("reason")))
    xirr_valid = (set(xirr) == {"status", "valuePct"} and xirr.get("status") == "CALCULATED" and _canonical_decimal_text(xirr.get("valuePct"))) or (set(xirr) == {"status", "reason"} and xirr.get("status") == "UNAVAILABLE" and _valid_reason(xirr.get("reason")))
    if not gain_valid or not xirr_valid or ((gain["status"] == "CALCULATED") != (xirr["status"] == "CALCULATED")):
        return False
    reasons = coverage["reasons"]
    if gain["status"] == "CALCULATED":
        return coverage["historyComplete"] is True and not reasons
    if gain["reason"] != xirr["reason"]:
        return False
    if reasons:
        return coverage["historyComplete"] is False and gain["reason"] == reasons[0]
    return coverage["historyComplete"] is True and gain["reason"] in {"SAME_DAY_ONLY", "INVALID_CASHFLOW", "SOLVER_FAILURE"}


def _decode_provenance(value: Any) -> Provenance:
    if not isinstance(value, dict) or set(value) != {"source_kind", "source_reference", "revision", "recorded_at"} or not isinstance(value["revision"], int) or isinstance(value["revision"], bool):
        raise ValueError("provenance")
    return Provenance(_decode_text(value["source_kind"], "source_kind") or "", _decode_text(value["source_reference"], "source_reference") or "", value["revision"], _decode_datetime(value["recorded_at"]))


def _decode_account(value: Any) -> AccountFact:
    expected = {"account_id", "owner_scope_id", "institution", "account_type", "currency", "source_name", "user_alias", "custodian_or_dp", "execution_broker", "masked_identifier", "provenance", "portfolio_id"}
    extended = expected | {"manual_history_complete"}
    if not isinstance(value, dict) or (set(value) != expected and set(value) != extended):
        raise ValueError("account")
    history = value.get("manual_history_complete", False)
    if not isinstance(history, bool):
        raise ValueError("account")
    return AccountFact(*(_decode_text(value[name], name) or "" for name in ("account_id", "owner_scope_id", "institution", "account_type", "currency")), _decode_text(value["source_name"], "source_name", nullable=True), _decode_text(value["user_alias"], "user_alias", nullable=True), _decode_text(value["custodian_or_dp"], "custodian_or_dp", nullable=True), _decode_text(value["execution_broker"], "execution_broker", nullable=True), _decode_text(value["masked_identifier"], "masked_identifier", nullable=True), _decode_provenance(value["provenance"]), _decode_text(value["portfolio_id"], "portfolio_id") or "", history)


def _decode_holding(value: Any) -> OpeningHoldingFact:
    expected = {"fact_id", "account_id", "owner_scope_id", "instrument_name", "isin", "quantity", "as_of", "currency", "documented_cost", "provenance", "portfolio_id"}
    extended = expected | {"voided"}
    if not isinstance(value, dict) or set(value) not in (expected, extended) or ("voided" in value and not isinstance(value["voided"], bool)):
        raise ValueError("holding")
    return OpeningHoldingFact(_decode_text(value["fact_id"], "fact_id") or "", _decode_text(value["account_id"], "account_id") or "", _decode_text(value["owner_scope_id"], "owner_scope_id") or "", _decode_text(value["instrument_name"], "instrument_name") or "", _decode_text(value["isin"], "isin", nullable=True), _decode_decimal(value["quantity"]), _decode_date(value["as_of"]), _decode_text(value["currency"], "currency") or "", _decode_decimal(value["documented_cost"], nullable=True), _decode_provenance(value["provenance"]), _decode_text(value["portfolio_id"], "portfolio_id") or "", value.get("voided", False))


def _decode_cash_flow(value: Any) -> CashFlowFact:
    expected = {"fact_id", "account_id", "owner_scope_id", "effective_date", "amount", "currency", "flow_type", "note", "provenance", "portfolio_id"}
    extended = expected | {"voided"}
    if not isinstance(value, dict) or set(value) not in (expected, extended) or ("voided" in value and not isinstance(value["voided"], bool)):
        raise ValueError("cash flow")
    return CashFlowFact(_decode_text(value["fact_id"], "fact_id") or "", _decode_text(value["account_id"], "account_id") or "", _decode_text(value["owner_scope_id"], "owner_scope_id") or "", _decode_date(value["effective_date"]), _decode_decimal(value["amount"]), _decode_text(value["currency"], "currency") or "", _decode_text(value["flow_type"], "flow_type") or "", _decode_text(value["note"], "note", nullable=True), _decode_provenance(value["provenance"]), _decode_text(value["portfolio_id"], "portfolio_id") or "", value.get("voided", False))


def _require_exact_revision_sequence(revisions: list[Any], label: str) -> None:
    if not revisions or any(item.provenance.revision != index for index, item in enumerate(revisions, start=1)):
        raise ValueError(label)


def _fact_revision_identity(item: OpeningHoldingFact | CashFlowFact) -> tuple[Any, ...]:
    return (item.owner_scope_id, item.portfolio_id, item.fact_id, item.account_id, item.currency)


def _fact_payload_without_audit(item: OpeningHoldingFact | CashFlowFact) -> tuple[Any, ...]:
    return tuple((field.name, getattr(item, field.name)) for field in fields(item) if field.name not in {"provenance", "voided"})


def _require_fact_revision_chain(revisions: list[OpeningHoldingFact] | list[CashFlowFact], label: str) -> None:
    _require_exact_revision_sequence(revisions, label)
    first = revisions[0]
    if first.provenance.source_kind != "manual" or first.voided:
        raise ValueError(label)
    if any(item.provenance.source_kind != "manual" or _fact_revision_identity(item) != _fact_revision_identity(first) for item in revisions):
        raise ValueError(label)
    for previous, item in zip(revisions, revisions[1:]):
        if previous.voided:
            raise ValueError(label)
        if item.voided:
            # A void records the exact prior fact plus a new manual provenance;
            # it cannot quietly alter a holding or cash-flow at the same time.
            if _fact_payload_without_audit(previous) != _fact_payload_without_audit(item):
                raise ValueError(label)


def _install_decoded_fact_chain(store: AccountDataStore, revisions: list[OpeningHoldingFact] | list[CashFlowFact], *, holding: bool) -> None:
    first = revisions[0]
    store._require_account(first.owner_scope_id, first.account_id, first.portfolio_id)
    key = (first.owner_scope_id, first.portfolio_id, first.fact_id)
    if holding:
        if key in store._holdings:
            raise ValueError("holding revisions")
        store._holdings[key] = revisions[-1]
        store._holding_revisions[key] = tuple(revisions)
    else:
        if key in store._flows:
            raise ValueError("cash-flow revisions")
        store._flows[key] = revisions[-1]
        store._flow_revisions[key] = tuple(revisions)


def _decode_document(value: Any) -> tuple[AccountDataStore, dict[tuple[str, str, str, str], dict[str, Any]]]:
    legacy = {"schemaVersion", "accountRevisions", "openingHoldings", "cashFlows", "receipts"}
    legacy_extended = legacy | {"derivedCache"}
    current = {"schemaVersion", "accountRevisions", "holdingRevisions", "cashFlowRevisions", "receipts", "derivedCache"}
    keys = set(value) if isinstance(value, dict) else set()
    schema_version = value.get("schemaVersion") if isinstance(value, dict) else None
    durable_list_keys = keys - {"schemaVersion", "derivedCache"}
    if not isinstance(value, dict) or schema_version not in {1, 2, _SCHEMA_VERSION} or keys not in (legacy, legacy_extended, current) or any(not isinstance(value[key], list) for key in durable_list_keys) or (schema_version == _SCHEMA_VERSION and not isinstance(value.get("derivedCache"), list)):
        raise ValueError("document")
    store = AccountDataStore()
    for revisions in value["accountRevisions"]:
        if not isinstance(revisions, list) or not revisions:
            raise ValueError("account revisions")
        decoded = [_decode_account(item) for item in revisions]
        first = decoded[0]
        _require_exact_revision_sequence(decoded, "account revisions")
        if any(
            item.owner_scope_id != first.owner_scope_id
            or item.portfolio_id != first.portfolio_id
            or item.account_id != first.account_id
            for item in decoded
        ):
            raise ValueError("account revisions")
        for current, candidate in zip(decoded, decoded[1:]):
            _require_manual_account_update_is_metadata_only(current, candidate)
        for account in decoded:
            store.put_account(account)
    holding_groups = value.get("holdingRevisions")
    if holding_groups is None:
        holding_groups = [[item] for item in value["openingHoldings"]]
    for revisions in holding_groups:
        if not isinstance(revisions, list) or not revisions:
            raise ValueError("holding revisions")
        decoded = [_decode_holding(item) for item in revisions]
        _require_fact_revision_chain(decoded, "holding revisions")
        _install_decoded_fact_chain(store, decoded, holding=True)
    flow_groups = value.get("cashFlowRevisions")
    if flow_groups is None:
        flow_groups = [[item] for item in value["cashFlows"]]
    for revisions in flow_groups:
        if not isinstance(revisions, list) or not revisions:
            raise ValueError("cash-flow revisions")
        decoded = [_decode_cash_flow(item) for item in revisions]
        _require_fact_revision_chain(decoded, "cash-flow revisions")
        _install_decoded_fact_chain(store, decoded, holding=False)
    receipts: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for item in value["receipts"]:
        expected_receipt = {"route", "ownerScopeId", "portfolioId", "key", "requestDigest", "resultKind", "resultId", "revision"}
        if not isinstance(item, dict) or set(item) != expected_receipt or not all(isinstance(item[key], str) and item[key].isascii() and item[key] for key in ("route", "ownerScopeId", "portfolioId", "key", "requestDigest", "resultKind", "resultId")) or item["resultKind"] not in {"account", "opening_holding", "cash_flow"} or not isinstance(item["revision"], int) or isinstance(item["revision"], bool) or item["revision"] < 1:
            raise ValueError("receipt")
        key = (item["route"], item["ownerScopeId"], item["portfolioId"], item["key"])
        if key in receipts or len(receipts) >= _MAX_RECEIPTS:
            raise ValueError("receipt")
        receipts[key] = {"requestDigest": item["requestDigest"], "resultKind": item["resultKind"], "resultId": item["resultId"], "revision": item["revision"]}
    for (route, owner, portfolio, key), receipt in receipts.items():
        LocalAccountDataStore._resolve_receipt(store, receipt, owner, portfolio)
    # Schema v1/v2 cache entries predate the current calculation wire contract.
    # They are derived, rebuildable results and never evidence of a durable fact;
    # retain/validate facts and receipts while deliberately invalidating that cache.
    for item in value.get("derivedCache", []) if schema_version == _SCHEMA_VERSION else []:
        expected_cache = {"ownerScopeId", "portfolioId", "kind", "asOf", "inputDigest", "result"}
        if not isinstance(item, dict) or set(item) != expected_cache or not all(isinstance(item[key], str) and item[key] for key in expected_cache):
            raise ValueError("derived cache")
        store.cache_derived(item["ownerScopeId"], item["portfolioId"], item["kind"], item["asOf"], item["inputDigest"], json.loads(item["result"], object_pairs_hook=_unique_object, parse_constant=_reject_constant))
    return store, receipts
