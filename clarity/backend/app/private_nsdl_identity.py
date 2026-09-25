"""Startup-frozen, server-owned private NSDL identity configuration."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Mapping

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


class PrivateNsdlIdentityUnavailable(Exception):
    pass


@dataclass(frozen=True)
class PrivateNsdlIdentity:
    uid: str
    family_id: str
    portfolio_id: str
    pan: str


def _without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PrivateNsdlIdentityUnavailable()
        result[key] = value
    return result


def load_private_nsdl_identities(raw: str | None = None) -> Mapping[tuple[str, str], PrivateNsdlIdentity]:
    raw = raw if raw is not None else os.environ.get("MONEYMONEY_PRIVATE_NSDL_IDENTITIES_JSON")
    try:
        values = json.loads(raw or "", object_pairs_hook=_without_duplicate_keys)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise PrivateNsdlIdentityUnavailable() from error
    if not isinstance(values, dict) or set(values) != {"schemaVersion", "portfolios"} or values.get("schemaVersion") != 1 or not isinstance(values["portfolios"], dict) or not values["portfolios"]:
        raise PrivateNsdlIdentityUnavailable()
    result: dict[tuple[str, str], PrivateNsdlIdentity] = {}
    for portfolio_id, value in values["portfolios"].items():
        if not isinstance(portfolio_id, str) or not isinstance(value, dict) or set(value) != {"ownerUid", "familyId", "pan"}:
            raise PrivateNsdlIdentityUnavailable()
        uid, family_id, pan = (value[key] for key in ("ownerUid", "familyId", "pan"))
        if not all(isinstance(item, str) and item.isascii() and item for item in (uid, family_id, portfolio_id, pan)):
            raise PrivateNsdlIdentityUnavailable()
        pan = pan.upper()
        if not PAN_RE.fullmatch(pan) or (uid, portfolio_id) in result:
            raise PrivateNsdlIdentityUnavailable()
        result[(uid, portfolio_id)] = PrivateNsdlIdentity(uid, family_id, portfolio_id, pan)
    return result


def validate_service_account_project(raw: str | None, expected_project_id: str) -> None:
    """Validate metadata only; credentials are never read or logged here."""
    try:
        value = json.loads(raw or "", object_pairs_hook=_without_duplicate_keys)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise PrivateNsdlIdentityUnavailable() from error
    if not isinstance(value, dict) or value.get("project_id") != expected_project_id:
        raise PrivateNsdlIdentityUnavailable()
