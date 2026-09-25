"""Fail-closed server-owned membership provisioning boundary."""

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from fastapi import HTTPException, Request

from .auth_perimeter import VerifiedPrincipal, _preview_uids


INVALID_MEMBERSHIP_REQUEST = {"detail": "invalid membership request"}
MEMBERSHIP_DENIED = {"detail": "membership access denied"}
MEMBERSHIP_CONFLICT = {"detail": "membership conflict"}
MEMBERSHIP_UNAVAILABLE = {"detail": "membership service unavailable"}

MAX_MEMBERSHIP_BODY_BYTES = 16 * 1024
MAX_EMAIL_BYTES = 254
ALLOWED_ROLES = frozenset({"MEMBER", "VIEWER", "ADVISOR"})
ALL_ROLES = ALLOWED_ROLES | {"ADMIN"}
EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")


class MembershipUnavailable(Exception):
    """A server-owned directory or membership store cannot be used safely."""


class MembershipValidationError(Exception):
    """The untrusted request body does not satisfy the exact wire contract."""


@dataclass(frozen=True)
class DirectoryUser:
    uid: str
    email: str
    email_verified: bool


@dataclass(frozen=True)
class Membership:
    uid: str
    family_id: str
    role: str
    active: bool
    email: Optional[str]


@dataclass(frozen=True)
class MembershipCommand:
    action: str
    email: str
    role: Optional[str]


def _invalid() -> HTTPException:
    return HTTPException(status_code=400, detail=INVALID_MEMBERSHIP_REQUEST["detail"])


def _denied() -> HTTPException:
    return HTTPException(status_code=403, detail=MEMBERSHIP_DENIED["detail"])


def _conflict() -> HTTPException:
    return HTTPException(status_code=409, detail=MEMBERSHIP_CONFLICT["detail"])


def _unavailable() -> HTTPException:
    return HTTPException(status_code=503, detail=MEMBERSHIP_UNAVAILABLE["detail"])


def normalize_email(value: Any) -> str:
    """Validate raw email syntax and length before the only permitted normalization."""
    if not isinstance(value, str):
        raise MembershipValidationError()
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as error:
        raise MembershipValidationError() from error
    if not encoded or len(encoded) > MAX_EMAIL_BYTES or not EMAIL_RE.fullmatch(value):
        raise MembershipValidationError()
    return value.lower()


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MembershipValidationError()
        result[key] = value
    return result


async def parse_membership_command(request: Request) -> MembershipCommand:
    content_types = request.headers.getlist("content-type")
    if content_types != ["application/json"]:
        raise MembershipValidationError()
    content_lengths = request.headers.getlist("content-length")
    if len(content_lengths) > 1:
        raise MembershipValidationError()
    if content_lengths:
        try:
            if int(content_lengths[0]) < 0 or int(content_lengths[0]) > MAX_MEMBERSHIP_BODY_BYTES:
                raise MembershipValidationError()
        except ValueError as error:
            raise MembershipValidationError() from error
    raw_body = await request.body()
    if not raw_body or len(raw_body) > MAX_MEMBERSHIP_BODY_BYTES:
        raise MembershipValidationError()
    try:
        decoded = raw_body.decode("utf-8")
        body = json.loads(
            decoded,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=lambda _value: (_ for _ in ()).throw(MembershipValidationError()),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, MembershipValidationError, TypeError, ValueError) as error:
        raise MembershipValidationError() from error
    if not isinstance(body, dict) or not isinstance(body.get("action"), str):
        raise MembershipValidationError()
    action = body["action"]
    required_keys = {"action", "email", "role"} if action == "upsert" else {"action", "email"} if action == "deactivate" else set()
    if set(body) != required_keys:
        raise MembershipValidationError()
    email = normalize_email(body.get("email"))
    role = body.get("role")
    if action == "upsert" and (not isinstance(role, str) or role not in ALLOWED_ROLES):
        raise MembershipValidationError()
    return MembershipCommand(action=action, email=email, role=role if action == "upsert" else None)


def parse_membership(value: Any, expected_uid: str, expected_email: Optional[str] = None) -> Optional[Membership]:
    """Treat every absent or malformed stored record as untrusted and unusable."""
    if not isinstance(value, Mapping):
        return None
    uid = value.get("uid")
    family_id = value.get("familyId")
    role = value.get("role")
    active = value.get("active")
    if (
        not isinstance(uid, str)
        or uid != expected_uid
        or not isinstance(family_id, str)
        or not family_id.strip()
        or not isinstance(role, str)
        or role not in ALL_ROLES
        or type(active) is not bool
    ):
        return None
    email = value.get("email")
    if expected_email is not None:
        try:
            if normalize_email(email) != expected_email:
                return None
        except MembershipValidationError:
            return None
    elif email is not None:
        try:
            email = normalize_email(email)
        except MembershipValidationError:
            return None
    return Membership(uid=uid, family_id=family_id, role=role, active=active, email=email)


class FirebaseAuthDirectory:
    """Production Auth lookup adapter; tests inject a synthetic directory instead."""

    def resolve_by_email(self, email: str) -> Optional[DirectoryUser]:
        try:
            from firebase_admin import auth as firebase_auth
            from .auth_perimeter import FirebaseAdminTokenVerifier

            app = FirebaseAdminTokenVerifier()._app()
            try:
                user = firebase_auth.get_user_by_email(email, app=app)
            except firebase_auth.UserNotFoundError:
                return None
            return DirectoryUser(uid=user.uid, email=user.email, email_verified=user.email_verified)
        except MembershipUnavailable:
            raise
        except Exception as error:
            raise MembershipUnavailable() from error


class FirebaseMembershipStore:
    """Production Firestore adapter; no request-controlled collection or path is used."""

    @staticmethod
    def _collection() -> Any:
        try:
            from firebase_admin import firestore as firebase_firestore
            from .auth_perimeter import FirebaseAdminTokenVerifier

            app = FirebaseAdminTokenVerifier()._app()
            return firebase_firestore.client(app).collection("user_registry")
        except Exception as error:
            raise MembershipUnavailable() from error

    def read(self, uid: str) -> Optional[Mapping[str, Any]]:
        try:
            snapshot = self._collection().document(uid).get()
            return snapshot.to_dict() if snapshot.exists else None
        except MembershipUnavailable:
            raise
        except Exception as error:
            raise MembershipUnavailable() from error

    def replace(self, uid: str, document: Mapping[str, Any]) -> None:
        try:
            self._collection().document(uid).set(dict(document))
        except MembershipUnavailable:
            raise
        except Exception as error:
            raise MembershipUnavailable() from error

    def deactivate(self, uid: str) -> None:
        try:
            self._collection().document(uid).update({"active": False})
        except MembershipUnavailable:
            raise
        except Exception as error:
            raise MembershipUnavailable() from error


class MembershipService:
    """Coordinates server-resolved targets with a fixed registry-only store."""

    def __init__(self, directory: Any, store: Any) -> None:
        self.directory = directory
        self.store = store

    def actor_membership(self, uid: str) -> Optional[Membership]:
        try:
            return parse_membership(self.store.read(uid), uid)
        except MembershipUnavailable:
            raise
        except Exception as error:
            raise MembershipUnavailable() from error

    def target(self, email: str) -> Optional[DirectoryUser]:
        try:
            user = self.directory.resolve_by_email(email)
        except MembershipUnavailable:
            raise
        except Exception as error:
            raise MembershipUnavailable() from error
        if not isinstance(user, DirectoryUser):
            return None
        try:
            return user if user.email_verified is True and normalize_email(user.email) == email else None
        except MembershipValidationError:
            return None

    def existing_target_membership(self, uid: str, email: str) -> tuple[bool, Optional[Membership]]:
        try:
            value = self.store.read(uid)
        except MembershipUnavailable:
            raise
        except Exception as error:
            raise MembershipUnavailable() from error
        return value is not None, None if value is None else parse_membership(value, uid, email)

    def replace_target(self, membership: Membership) -> None:
        try:
            self.store.replace(membership.uid, {
                "uid": membership.uid,
                "familyId": membership.family_id,
                "role": membership.role,
                "active": True,
                "email": membership.email,
            })
        except MembershipUnavailable:
            raise
        except Exception as error:
            raise MembershipUnavailable() from error

    def deactivate_target(self, uid: str) -> None:
        try:
            self.store.deactivate(uid)
        except MembershipUnavailable:
            raise
        except Exception as error:
            raise MembershipUnavailable() from error


def membership_service(request: Request) -> MembershipService:
    configured = getattr(request.app.state, "membership_service", None)
    if isinstance(configured, MembershipService):
        return configured
    return MembershipService(FirebaseAuthDirectory(), FirebaseMembershipStore())


async def manage_membership(request: Request, principal: VerifiedPrincipal) -> dict[str, str]:
    """Run the request in authority order, reading JSON only after actor authorization."""
    service = membership_service(request)
    try:
        actor = service.actor_membership(principal.uid)
    except MembershipUnavailable as error:
        raise _unavailable() from error
    if actor is None or not actor.active or actor.role != "ADMIN":
        raise _denied()
    try:
        command = await parse_membership_command(request)
    except MembershipValidationError as error:
        raise _invalid() from error
    try:
        preview_uids = _preview_uids(os.environ.get("MONEYMONEY_PRIVATE_PREVIEW_UIDS"))
        if preview_uids is None:
            raise MembershipUnavailable()
        target = service.target(command.email)
        if target is None or target.uid == principal.uid or target.uid not in preview_uids:
            raise _denied()
        target_record_exists, existing = service.existing_target_membership(target.uid, command.email)
    except MembershipUnavailable as error:
        raise _unavailable() from error

    if command.action == "upsert":
        if target_record_exists and existing is None:
            raise _denied()
        if existing is not None and (existing.role == "ADMIN" or (existing.active and existing.family_id != actor.family_id)):
            raise _conflict()
        try:
            service.replace_target(Membership(target.uid, actor.family_id, command.role, True, command.email))
        except MembershipUnavailable as error:
            raise _unavailable() from error
        return {"status": "ok"}

    if (
        existing is None
        or existing.uid == principal.uid
        or existing.family_id != actor.family_id
        or existing.role == "ADMIN"
        or not existing.active
    ):
        raise _denied()
    try:
        service.deactivate_target(target.uid)
    except MembershipUnavailable as error:
        raise _unavailable() from error
    return {"status": "ok"}
