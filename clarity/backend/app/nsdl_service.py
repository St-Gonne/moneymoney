"""Private NSDL import service; no legacy ledger writes or process singleton state."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

from .models.account_data import AccountDataError, AccountFact, statement_provenance
from .models.nsdl_snapshot import NsdlSnapshotError, NsdlSnapshotV1, opaque_id
from dataclasses import replace
from .nsdl_store import NsdlStoreError
from .parsers.nsdl_parser import NsdlSnapshotParser
from .private_nsdl_identity import PrivateNsdlIdentity

IDEMPOTENCY_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)
MAX_PDF_BYTES = 12 * 1024 * 1024


@dataclass(frozen=True)
class NsdlImportResult:
    status: str
    receipt_id: str
    snapshot: NsdlSnapshotV1


@dataclass(frozen=True)
class NsdlImportPreview:
    snapshot: NsdlSnapshotV1
    preview_token: str
    # This is deliberately server-only.  API callers receive snapshot.to_wire().
    account_source_names: tuple[tuple[str, str], ...]


class NsdlService:
    def __init__(
        self,
        store: object,
        parser: NsdlSnapshotParser | None = None,
        password_resolver: Callable[[PrivateNsdlIdentity], str | None] | None = None,
    ) -> None:
        self.store = store
        self.parser = parser or NsdlSnapshotParser()
        self.password_resolver = password_resolver

    def _parse(self, identity: PrivateNsdlIdentity, raw_pdf: bytes, password: str) -> Any:
        if not raw_pdf.startswith(b"%PDF"):
            raise NsdlStoreError("ERR_NSDL_UPLOAD_INVALID")
        if len(raw_pdf) > MAX_PDF_BYTES:
            raise NsdlStoreError("ERR_NSDL_LIMIT_EXCEEDED")
        if self.password_resolver is not None:
            if password:
                raise NsdlStoreError("ERR_NSDL_UPLOAD_INVALID")
            try:
                password = self.password_resolver(identity)
            except Exception:
                raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE") from None
            if password is None:
                password = ""
            if not isinstance(password, str):
                raise NsdlStoreError("ERR_NSDL_PASSWORD_INVALID")
        try:
            return self.parser.parse_pdf_bytes(
                raw_pdf,
                password=password,
                expected_pan=identity.pan,
                portfolio_id=identity.portfolio_id,
                hmac_secret=self.store.secret,
                require_owner_pan=False,
            )
        except NsdlSnapshotError as error:
            raise NsdlStoreError(error.code) from None

    @staticmethod
    def _semantic(snapshot: NsdlSnapshotV1) -> str:
        wire = snapshot.to_wire()
        wire.pop("revisionId", None)
        wire.pop("importedAt", None)
        return hashlib.sha256(json.dumps(wire, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _review_digest(snapshot: NsdlSnapshotV1, names: tuple[tuple[str, str], ...]) -> str:
        payload = {"snapshot": NsdlService._semantic(snapshot), "sourceAccounts": list(names)}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()

    @staticmethod
    def _request_digest(raw_pdf: bytes, snapshot: NsdlSnapshotV1, names: tuple[tuple[str, str], ...]) -> str:
        return hashlib.sha256((hashlib.sha256(raw_pdf).hexdigest() + "\x1f" + NsdlService._review_digest(snapshot, names)).encode()).hexdigest()

    def _preview_token(self, identity: PrivateNsdlIdentity, raw_pdf: bytes, snapshot: NsdlSnapshotV1, names: tuple[tuple[str, str], ...], *, current_revision: str | None = None, expires_at: int | None = None) -> str:
        expiry = int(time.time()) + 600 if expires_at is None else expires_at
        payload = json.dumps({"v": 3, "u": identity.uid, "p": identity.portfolio_id, "b": hashlib.sha256(raw_pdf).hexdigest(), "m": self._review_digest(snapshot, names), "r": current_revision, "e": expiry}, sort_keys=True, separators=(",", ":")).encode()
        signature = hmac.new(self.store.secret, b"nsdl-preview-v1\x1f" + payload, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(payload + signature).decode().rstrip("=")

    def _validate_preview_token(self, identity: PrivateNsdlIdentity, raw_pdf: bytes, snapshot: NsdlSnapshotV1, names: tuple[tuple[str, str], ...], token: str) -> str | None:
        if not isinstance(token, str) or not token or len(token) > 1024:
            raise NsdlStoreError("ERR_NSDL_PREVIEW_INVALID")
        try:
            encoded = token.encode()
            raw = base64.urlsafe_b64decode(encoded + b"=" * (-len(encoded) % 4))
            payload, provided = raw[:-32], raw[-32:]
            expected = hmac.new(self.store.secret, b"nsdl-preview-v1\x1f" + payload, hashlib.sha256).digest()
            parsed = json.loads(payload)
            revision = parsed.get("r")
            valid = hmac.compare_digest(provided, expected) and (revision is None or isinstance(revision, str) and 0 < len(revision) <= 128) and parsed == {"v": 3, "u": identity.uid, "p": identity.portfolio_id, "b": hashlib.sha256(raw_pdf).hexdigest(), "m": self._review_digest(snapshot, names), "r": revision, "e": parsed.get("e")} and isinstance(parsed["e"], int) and parsed["e"] >= int(time.time())
        except (ValueError, TypeError, AttributeError, json.JSONDecodeError, KeyError):
            valid = False
        if not valid:
            raise NsdlStoreError("ERR_NSDL_PREVIEW_INVALID")
        return revision

    def preview_pdf(self, identity: PrivateNsdlIdentity, raw_pdf: bytes, password: str) -> NsdlImportPreview:
        parsed = self._parse(identity, raw_pdf, password)
        current = self.store.read_current(identity.uid, identity.portfolio_id)
        return NsdlImportPreview(parsed.snapshot, self._preview_token(identity, raw_pdf, parsed.snapshot, parsed.account_source_names, current_revision=current.revision_id if current else None), parsed.account_source_names)

    def import_pdf(self, identity: PrivateNsdlIdentity, raw_pdf: bytes, password: str, idempotency_key: str, preview_token: str, account_data_store: Any = None) -> NsdlImportResult:
        if not IDEMPOTENCY_RE.fullmatch(idempotency_key):
            raise NsdlStoreError("ERR_NSDL_IDEMPOTENCY_INVALID")
        preview = self.preview_pdf(identity, raw_pdf, password)
        expected_revision = self._validate_preview_token(identity, raw_pdf, preview.snapshot, preview.account_source_names, preview_token)
        current = self.store.read_current(identity.uid, identity.portfolio_id)
        account_set_change = current is not None and {account.account_scope_id for account in current.accounts} != {account.account_scope_id for account in preview.snapshot.accounts}
        if account_set_change:
            if account_data_store is None:
                raise NsdlStoreError("ERR_NSDL_ACCOUNT_SET_CONFLICT")
            try:
                graph = account_data_store.list_scope(identity.uid, identity.portfolio_id)
            except AccountDataError as error:
                raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE") from error
            if not isinstance(graph, dict) or set(graph) != {"accounts", "opening_holdings", "cash_flows"}:
                raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE")
            if any(graph.values()):
                raise NsdlStoreError("ERR_NSDL_ACCOUNT_SET_CONFLICT")
        # The request portfolio selector is never a persisted or returned identifier.
        redacted = replace(preview.snapshot, portfolio_id=opaque_id(self.store.secret, "portfolio", identity.uid, identity.portfolio_id))
        status, snapshot, receipt_id = self.store.commit(identity.uid, identity.portfolio_id, idempotency_key, redacted, request_digest=self._request_digest(raw_pdf, preview.snapshot, preview.account_source_names), expected_current_revision=expected_revision, allow_account_set_change=account_set_change, account_data_store=account_data_store if account_set_change else None)
        if account_data_store is not None:
            self._commit_statement_accounts(account_data_store, identity, preview.account_source_names, snapshot, receipt_id, idempotency_key)
        return NsdlImportResult(status, receipt_id, snapshot)

    def _commit_statement_accounts(self, account_data_store: Any, identity: PrivateNsdlIdentity, names: tuple[tuple[str, str], ...], snapshot: NsdlSnapshotV1, receipt_id: str, idempotency_key: str) -> None:
        name_by_scope = dict(names)
        if len(name_by_scope) != len(names) or set(name_by_scope) != {account.account_scope_id for account in snapshot.accounts}:
            raise NsdlStoreError("ERR_NSDL_PARSE_INCOMPLETE")
        digest = self._semantic(snapshot)
        try:
            existing = {account.account_id: account for account in account_data_store.list_scope(identity.uid, identity.portfolio_id)["accounts"]}
            for account in snapshot.accounts:
                prior = existing.get(account.account_scope_id)
                fact = AccountFact(
                    account.account_scope_id,
                    identity.uid,
                    prior.institution if prior else "NSDL",
                    prior.account_type if prior else account.section_type.lower(),
                    prior.currency if prior else "INR",
                    source_name=name_by_scope[account.account_scope_id],
                    user_alias=prior.user_alias if prior else None,
                    custodian_or_dp=prior.custodian_or_dp if prior else None,
                    execution_broker=prior.execution_broker if prior else None,
                    masked_identifier=prior.masked_identifier if prior else None,
                    provenance=statement_provenance(receipt_id),
                    portfolio_id=identity.portfolio_id,
                    manual_history_complete=prior.manual_history_complete if prior else False,
                )
                account_data_store.commit_account(fact, route="/api/nsdl/import", idempotency_key=f"{idempotency_key}:{account.account_scope_id}", request_digest=digest, expected_revision=prior.provenance.revision if prior else None)
        except AccountDataError as error:
            raise NsdlStoreError("ERR_NSDL_ACCOUNT_COMMIT_UNKNOWN", stage="account_sync", category="account_store") from error
        except Exception as error:
            raise NsdlStoreError("ERR_NSDL_ACCOUNT_COMMIT_UNKNOWN", stage="account_sync", category="unexpected") from error

    def current(self, identity: PrivateNsdlIdentity) -> NsdlSnapshotV1 | None:
        return self.store.read_current(identity.uid, identity.portfolio_id)
