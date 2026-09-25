"""Atomic server-only private NSDL snapshot store with a testable backing map."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from threading import RLock
from typing import Any, MutableMapping

from .models.account_data import AccountDataError
from .models.nsdl_snapshot import NsdlAccount, NsdlCoverage, NsdlHolding, NsdlSnapshotV1, NsdlTotal, opaque_id

_UNSET_REVISION = object()


def _empty_account_graph(facts: Any) -> bool:
    if not isinstance(facts, dict) or set(facts) != {"accounts", "opening_holdings", "cash_flows"}:
        raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE")
    return not any(facts.values())


class NsdlStoreError(Exception):
    def __init__(self, code: str, *, stage: str = "snapshot_commit", category: str = "nsdl_store"):
        self.code = code
        self.stage = stage if stage in {"preview", "snapshot_commit", "account_sync"} else "snapshot_commit"
        self.category = category if category in {"nsdl_store", "account_store", "unexpected"} else "unexpected"


def _semantic(snapshot: NsdlSnapshotV1) -> str:
    wire = snapshot.to_wire()
    wire.pop("revisionId", None)
    wire.pop("importedAt", None)
    return hashlib.sha256(json.dumps(wire, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _encoded_snapshot_size(snapshot: NsdlSnapshotV1) -> int:
    return len(json.dumps(snapshot.to_wire(), sort_keys=True, separators=(",", ":")).encode("utf-8"))


def _from_wire(value: Any) -> NsdlSnapshotV1:
    """Rebuild only the frozen redacted wire shape from Firestore."""
    try:
        if not isinstance(value, dict) or value.get("schemaVersion") != 1:
            raise ValueError()
        coverage = value["coverage"]
        return NsdlSnapshotV1(
            portfolio_id=value["portfolioId"], as_of_date=datetime.fromisoformat(value["asOfDate"]).date(),
            coverage=NsdlCoverage(bool(coverage["complete"]), tuple(coverage["sections"]), tuple(coverage["unsupportedSections"]), int(coverage["missingValues"]), tuple(coverage.get("warnings", []))),
            accounts=tuple(NsdlAccount(row["accountScopeId"], row["sectionType"], row["maskedLabel"]) for row in value["accounts"]),
            holdings=tuple(NsdlHolding(row["holdingId"], row["accountScopeId"], row.get("isin"), row["instrumentName"], row["instrumentType"], row["quantity"], row.get("currency"), row.get("statementPrice"), row.get("statementValue")) for row in value["holdings"]),
            totals_by_currency=tuple(NsdlTotal(row["currency"], row["statementValue"]) for row in value["totalsByCurrency"]),
            parser_version=value["parserVersion"], revision_id=value.get("revisionId"), imported_at=value.get("importedAt"),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE") from error


class PersistentFakeNsdlStore:
    """Transaction-shaped backing store; reuse its backing map across service instances."""

    def __init__(self, backing: MutableMapping[str, Any] | None = None, secret: bytes = b"nsdl-store-test-secret") -> None:
        self.backing = backing if backing is not None else {}
        self.secret = secret
        self._lock = self.backing.setdefault("_lock", RLock())

    def commit(self, uid: str, portfolio_id: str, idempotency_key: str, snapshot: NsdlSnapshotV1, *, request_digest: str | None = None, expected_current_revision: str | None | object = _UNSET_REVISION, allow_account_set_change: bool = False, account_data_store: Any = None) -> tuple[str, NsdlSnapshotV1, str]:
        key = opaque_id(self.secret, "portfolio", uid, portfolio_id)
        receipt_key = opaque_id(self.secret, "receipt", uid, portfolio_id, idempotency_key)
        digest = request_digest or _semantic(snapshot)
        if not isinstance(digest, str) or len(digest) != 64:
            raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE")
        with self._lock:
            if self.backing.pop("fail_before_commit", False):
                raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE")
            root = self.backing.setdefault(key, {"snapshots": {}, "receipts": {}, "current": None})
            if receipt_key in root["receipts"]:
                receipt = root["receipts"][receipt_key]
                if receipt.get("requestDigest") != digest:
                    raise NsdlStoreError("ERR_NSDL_IDEMPOTENCY_CONFLICT")
                return "duplicate", root["snapshots"][receipt["revision"]], receipt_key
            if not snapshot.coverage.complete or not snapshot.holdings:
                raise NsdlStoreError("ERR_NSDL_PARSE_INCOMPLETE")
            if len(snapshot.holdings) > 500 or _encoded_snapshot_size(snapshot) > 512 * 1024:
                raise NsdlStoreError("ERR_NSDL_LIMIT_EXCEEDED")
            semantic = _semantic(snapshot)
            current_id = root["current"]
            if expected_current_revision is not _UNSET_REVISION and current_id != expected_current_revision:
                raise NsdlStoreError("ERR_NSDL_REVISION_CONFLICT")
            if current_id:
                current = root["snapshots"][current_id]
                if snapshot.as_of_date < current.as_of_date:
                    raise NsdlStoreError("ERR_NSDL_OLDER_STATEMENT")
                if snapshot.as_of_date == current.as_of_date:
                    if _semantic(current) == semantic:
                        root["receipts"][receipt_key] = {"revision": current_id, "requestDigest": digest}
                        return "duplicate", current, receipt_key
                    raise NsdlStoreError("ERR_NSDL_SAME_DATE_CONFLICT")
                if {a.account_scope_id for a in snapshot.accounts} != {a.account_scope_id for a in current.accounts}:
                    if not (allow_account_set_change and expected_current_revision is not _UNSET_REVISION and account_data_store is not None):
                        raise NsdlStoreError("ERR_NSDL_ACCOUNT_SET_CONFLICT")
                    try:
                        empty = _empty_account_graph(account_data_store.list_scope(uid, portfolio_id))
                    except AccountDataError as error:
                        raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE") from error
                    if not empty:
                        raise NsdlStoreError("ERR_NSDL_ACCOUNT_SET_CONFLICT")
            revision = opaque_id(self.secret, "revision", key, semantic, str(len(root["snapshots"])))
            stored = replace(snapshot, revision_id=revision, imported_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat())
            # These three writes occur under one lock/transaction boundary.
            root["snapshots"][revision] = stored
            root["receipts"][receipt_key] = {"revision": revision, "requestDigest": digest}
            root["current"] = revision
            if self.backing.pop("ambiguous_after_commit", False):
                raise NsdlStoreError("ERR_NSDL_COMMIT_UNKNOWN")
            return "imported", stored, receipt_key

    def read_current(self, uid: str, portfolio_id: str) -> NsdlSnapshotV1 | None:
        key = opaque_id(self.secret, "portfolio", uid, portfolio_id)
        with self._lock:
            root = self.backing.get(key)
            return root["snapshots"][root["current"]] if root and root["current"] else None


class FirestoreNsdlStore:
    """Production-only Admin SDK transaction store; tests must inject PersistentFakeNsdlStore."""
    def __init__(self, project_id: str, account_key: bytes, *, client: Any = None, firestore_module: Any = None) -> None:
        if len(account_key) != 32:
            raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE")
        if client is None:
            try:
                from firebase_admin import firestore
                from .auth_perimeter import FirebaseAdminTokenVerifier
                # Bind to the named Certificate-initialized app; never permit default-app ADC.
                self.client = firestore.client(FirebaseAdminTokenVerifier(project_id)._app())
                self._firestore = firestore
            except Exception as error:
                raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE") from error
        elif firestore_module is None:
            raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE")
        else:
            # Tests inject a transaction-shaped local adapter; no Firebase client is contacted.
            self.client, self._firestore = client, firestore_module
        self.project_id, self.secret = project_id, account_key

    def _root(self, uid: str, portfolio_id: str):
        return self.client.collection("private_nsdl_portfolios").document(opaque_id(self.secret, "portfolio", uid, portfolio_id))

    @staticmethod
    def _transaction_document(transaction: Any, reference: Any) -> Any:
        """Read exactly one document through the active public transaction."""
        result = transaction.get(reference)
        if hasattr(result, "exists"):
            return result
        return next(iter(result), None)

    def _binding(self, uid: str, portfolio_id: str) -> tuple[str, str, str]:
        root_key = opaque_id(self.secret, "portfolio", uid, portfolio_id)
        return root_key, opaque_id(self.secret, "uid", uid), root_key

    def _validate_root(self, root_snapshot: Any, uid: str, portfolio_id: str) -> None:
        if not root_snapshot or not root_snapshot.exists:
            return
        root_key, uid_key, portfolio_key = self._binding(uid, portfolio_id)
        values = root_snapshot.to_dict()
        if not isinstance(values, dict) or values.get("uidKey") != uid_key or values.get("portfolioKey") != portfolio_key or root_key != portfolio_key:
            raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE")

    def _validate_snapshot_binding(self, snapshot: NsdlSnapshotV1, uid: str, portfolio_id: str) -> None:
        expected = opaque_id(self.secret, "portfolio", uid, portfolio_id)
        if snapshot.portfolio_id != expected:
            raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE")

    def commit(self, uid: str, portfolio_id: str, idempotency_key: str, snapshot: NsdlSnapshotV1, *, request_digest: str | None = None, expected_current_revision: str | None | object = _UNSET_REVISION, allow_account_set_change: bool = False, account_data_store: Any = None) -> tuple[str, NsdlSnapshotV1, str]:
        if not snapshot.coverage.complete or not snapshot.holdings:
            raise NsdlStoreError("ERR_NSDL_PARSE_INCOMPLETE")
        if len(snapshot.holdings) > 500 or _encoded_snapshot_size(snapshot) > 512 * 1024:
            raise NsdlStoreError("ERR_NSDL_LIMIT_EXCEEDED")
        self._validate_snapshot_binding(snapshot, uid, portfolio_id)
        digest = request_digest or _semantic(snapshot)
        if not isinstance(digest, str) or len(digest) != 64:
            raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE")
        receipt_id = opaque_id(self.secret, "receipt", uid, portfolio_id, idempotency_key)
        root = self._root(uid, portfolio_id)
        callback_started = False
        callback_wrote = False

        def transactional_write(transaction: Any) -> tuple[str, NsdlSnapshotV1, str]:
            nonlocal callback_started, callback_wrote
            callback_started = True
            try:
                receipt = root.collection("receipts").document(receipt_id)
                root_snapshot = self._transaction_document(transaction, root)
                self._validate_root(root_snapshot, uid, portfolio_id)
                existing = self._transaction_document(transaction, receipt)
                if existing.exists:
                    receipt_values = existing.to_dict()
                    if receipt_values.get("requestDigest") != digest:
                        raise NsdlStoreError("ERR_NSDL_IDEMPOTENCY_CONFLICT")
                    revision = receipt_values.get("revisionId")
                    if not isinstance(revision, str):
                        raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE")
                    document = self._transaction_document(transaction, root.collection("snapshots").document(revision))
                    if not isinstance(revision, str) or not document.exists:
                        raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE")
                    stored = _from_wire(document.to_dict().get("snapshot"))
                    self._validate_snapshot_binding(stored, uid, portfolio_id)
                    return "duplicate", stored, receipt_id
                current = None
                if root_snapshot.exists:
                    current_revision = root_snapshot.to_dict().get("currentRevision")
                    if current_revision:
                        if not isinstance(current_revision, str):
                            raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE")
                        current_document = self._transaction_document(transaction, root.collection("snapshots").document(current_revision))
                        if not current_document.exists:
                            raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE")
                        current = _from_wire(current_document.to_dict().get("snapshot"))
                        self._validate_snapshot_binding(current, uid, portfolio_id)
                if expected_current_revision is not _UNSET_REVISION and (current.revision_id if current else None) != expected_current_revision:
                    raise NsdlStoreError("ERR_NSDL_REVISION_CONFLICT")
                if current:
                    if snapshot.as_of_date < current.as_of_date:
                        raise NsdlStoreError("ERR_NSDL_OLDER_STATEMENT")
                    if snapshot.as_of_date == current.as_of_date:
                        if _semantic(snapshot) == _semantic(current):
                            transaction.set(receipt, {"revisionId": current.revision_id, "requestDigest": digest})
                            callback_wrote = True
                            return "duplicate", current, receipt_id
                        raise NsdlStoreError("ERR_NSDL_SAME_DATE_CONFLICT")
                    if {a.account_scope_id for a in snapshot.accounts} != {a.account_scope_id for a in current.accounts}:
                        if not (allow_account_set_change and expected_current_revision is not _UNSET_REVISION and account_data_store is not None and getattr(account_data_store, "client", None) is self.client):
                            raise NsdlStoreError("ERR_NSDL_ACCOUNT_SET_CONFLICT")
                        try:
                            graph_document = self._transaction_document(transaction, account_data_store._root(uid, portfolio_id))
                            graph_store, _count = account_data_store._decode_root(graph_document, uid, portfolio_id)
                            empty = _empty_account_graph(graph_store.list_scope(uid, portfolio_id))
                        except AccountDataError as error:
                            raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE") from error
                        if not empty:
                            raise NsdlStoreError("ERR_NSDL_ACCOUNT_SET_CONFLICT")
                revision = opaque_id(self.secret, "revision", uid, portfolio_id, _semantic(snapshot))
                stored = replace(snapshot, revision_id=revision, imported_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat())
                snapshot_doc = root.collection("snapshots").document(revision)
                transaction.set(snapshot_doc, {"snapshot": stored.to_wire()})
                transaction.set(receipt, {"revisionId": revision, "requestDigest": digest})
                root_key, uid_key, portfolio_key = self._binding(uid, portfolio_id)
                transaction.set(root, {"uidKey": uid_key, "portfolioKey": portfolio_key, "currentRevision": revision}, merge=True)
                callback_wrote = True
                return "imported", stored, receipt_id
            except NsdlStoreError:
                raise
            except Exception as error:
                raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE") from error

        try:
            # This public wrapper begins and commits a real transaction; max_attempts is fixed at two.
            transaction = self.client.transaction(max_attempts=2)
            return self._firestore.transactional(transactional_write)(transaction)
        except NsdlStoreError:
            raise
        except ValueError as error:
            # google-cloud-firestore wraps exhausted ABORTED retries in ValueError.
            raise NsdlStoreError("ERR_NSDL_REVISION_CONFLICT") from error
        except Exception as error:
            if callback_started and callback_wrote:
                raise NsdlStoreError("ERR_NSDL_COMMIT_UNKNOWN") from error
            raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE") from error

    def read_current(self, uid: str, portfolio_id: str) -> NsdlSnapshotV1 | None:
        try:
            root = self._root(uid, portfolio_id).get()
            if not root.exists:
                return None
            self._validate_root(root, uid, portfolio_id)
            revision = root.to_dict().get("currentRevision")
            if not isinstance(revision, str):
                raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE")
            document = self._root(uid, portfolio_id).collection("snapshots").document(revision).get()
            if not document.exists:
                raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE")
            stored = _from_wire(document.to_dict().get("snapshot"))
            self._validate_snapshot_binding(stored, uid, portfolio_id)
            return stored
        except NsdlStoreError:
            raise
        except Exception as error:
            raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE") from error
