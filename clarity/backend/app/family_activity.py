"""Redacted, durable local Activity records for the family authorization seam."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
from typing import Any


class FamilyActivityError(RuntimeError):
    """A durable Activity failure that must never become a successful mutation response."""


class FamilyActivityReceiptConflict(FamilyActivityError):
    """The deterministic receipt key already belongs to different Activity facts."""


class FamilyActivityUnavailable(FamilyActivityError):
    """The durable Activity adapter could not safely complete its transaction."""


@dataclass(frozen=True)
class FamilyActivity:
    portfolio_id: str
    actor_uid: str
    actor_label: str
    operation: str
    recorded_at: str
    idempotency_key: str


class FamilyActivityStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._rows: list[FamilyActivity] = []
        if path is not None and path.exists():
            values = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(values, list):
                raise ValueError("invalid activity store")
            self._rows = [FamilyActivity(**item) for item in values]

    def append(self, portfolio_id: str, actor_uid: str, actor_label: str, operation: str, idempotency_key: str) -> None:
        if operation not in {"manual_account", "opening_holding", "cash_flow", "statement_import"}:
            raise ValueError("invalid activity operation")
        if not isinstance(idempotency_key, str) or not idempotency_key:
            raise ValueError("invalid activity key")
        if any(item.portfolio_id == portfolio_id and item.operation == operation and item.idempotency_key == idempotency_key for item in self._rows):
            return
        row = FamilyActivity(portfolio_id, actor_uid, actor_label, operation, datetime.now(timezone.utc).replace(microsecond=0).isoformat(), idempotency_key)
        self._rows.append(row)
        if self.path is not None:
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps([asdict(item) for item in self._rows], separators=(",", ":")), encoding="utf-8")
            temporary.replace(self.path)

    def list_scope(self, portfolio_id: str) -> list[dict[str, str]]:
        return [{"actor_uid": item.actor_label, "operation": item.operation, "recorded_at": item.recorded_at} for item in self._rows if item.portfolio_id == portfolio_id]


class FirestoreFamilyActivityStore:
    """Named-client durable activity/outbox seam; no browser-readable path exists."""
    COLLECTION = "private_family_activity"
    _OPERATIONS = frozenset({"manual_account", "opening_holding", "cash_flow", "statement_import"})
    _ACTOR_LABELS = frozenset({"Sharan", "Dad"})

    def __init__(self, client: object, firestore_module: object) -> None:
        if client is None or firestore_module is None:
            raise FamilyActivityUnavailable("activity adapter unavailable")
        self.client, self._firestore = client, firestore_module

    @classmethod
    def _payload(cls, portfolio_id: str, actor_uid: str, actor_label: str, operation: str, idempotency_key: str) -> dict[str, str]:
        if not all(isinstance(value, str) and value for value in (portfolio_id, actor_uid, idempotency_key)):
            raise FamilyActivityUnavailable("invalid activity input")
        if actor_label not in cls._ACTOR_LABELS or operation not in cls._OPERATIONS:
            raise FamilyActivityUnavailable("invalid activity input")
        return {
            "portfolioId": portfolio_id,
            "actorUid": actor_uid,
            "actorLabel": actor_label,
            "operation": operation,
            "idempotency": idempotency_key,
            "recordedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }

    @staticmethod
    def _transaction_snapshot(transaction: Any, document: Any) -> Any:
        value = transaction.get(document)
        if hasattr(value, "exists"):
            return value
        try:
            return next(iter(value))
        except StopIteration as error:
            raise FamilyActivityUnavailable("missing transaction snapshot") from error

    @staticmethod
    def _same_payload(existing: Any, intended: dict[str, str]) -> bool:
        if not isinstance(existing, dict) or set(existing) != set(intended):
            return False
        if not all(existing.get(key) == intended[key] for key in ("portfolioId", "actorUid", "actorLabel", "operation", "idempotency")):
            return False
        recorded_at = existing.get("recordedAt")
        if not isinstance(recorded_at, str) or not recorded_at:
            return False
        try:
            parsed = datetime.fromisoformat(recorded_at)
        except ValueError:
            return False
        return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed) and parsed.microsecond == 0 and parsed.isoformat() == recorded_at

    def append(self, portfolio_id: str, actor_uid: str, actor_label: str, operation: str, idempotency_key: str) -> None:
        payload = self._payload(portfolio_id, actor_uid, actor_label, operation, idempotency_key)
        key = hashlib.sha256(f"{portfolio_id}\x1f{operation}\x1f{idempotency_key}".encode()).hexdigest()
        document = self.client.collection(self.COLLECTION).document(key)

        def write(transaction: Any) -> None:
            existing = self._transaction_snapshot(transaction, document)
            if existing.exists:
                if not self._same_payload(existing.to_dict(), payload):
                    raise FamilyActivityReceiptConflict("activity receipt conflict")
                return
            transaction.set(document, payload)

        try:
            self._firestore.transactional(write)(self.client.transaction(max_attempts=2))
        except FamilyActivityError:
            raise
        except Exception as error:
            raise FamilyActivityUnavailable("activity unavailable") from error

    def list_scope(self, portfolio_id: str) -> list[dict[str, str]]:
        try:
            rows = self.client.collection(self.COLLECTION).where("portfolioId", "==", portfolio_id).stream()
            safe = []
            for row in rows:
                value = row.to_dict()
                if not isinstance(value, dict) or value.get("actorLabel") not in self._ACTOR_LABELS or value.get("operation") not in self._OPERATIONS or not isinstance(value.get("recordedAt"), str):
                    raise FamilyActivityUnavailable("invalid activity row")
                safe.append({"actor_uid": value["actorLabel"], "operation": value["operation"], "recorded_at": value["recordedAt"]})
            return safe
        except FamilyActivityError:
            raise
        except Exception as error:
            raise FamilyActivityUnavailable("activity unavailable") from error
