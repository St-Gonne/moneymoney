"""Fixed, protected-email authority for the private two-person NSDL mode.

This module deliberately contains no provider client construction, network I/O,
or mutable membership/registry mechanism.  Its configuration is read only when
the private application explicitly composes ``two_person`` mode.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Mapping

from .auth_perimeter import VerifiedPrincipal
from .family_portfolio import (
    HELPER,
    OWNER,
    READ,
    WRITE,
    AuthorizedFamilyPortfolio,
    FamilyPortfolio,
    FamilyPortfolioDenied,
)
from .private_nsdl_identity import PrivateNsdlIdentity


FAMILY_EMAILS_ENV = "MONEYMONEY_PRIVATE_NSDL_FAMILY_EMAILS_JSON"
FAMILY_EMAILS_SCHEMA_VERSION = 1
DAD_PORTFOLIO_ID = "family-alpha-dad-v1"
JOINT_PORTFOLIO_ID = "family-alpha-joint-v1"
DAD_SCOPE_ID = "family-alpha-dad-scope-v1"
JOINT_SCOPE_ID = "family-alpha-joint-scope-v1"
_CONFIG_FIELDS = frozenset({"schemaVersion", "sharanEmail", "dadEmail"})
_EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")


class FamilyTwoPersonConfigurationError(Exception):
    """Protected two-person configuration is absent or structurally unsafe."""


def _without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise FamilyTwoPersonConfigurationError()
        result[key] = value
    return result


def normalize_family_email(value: object) -> str:
    """Normalize one protected email deterministically without preserving input."""
    if not isinstance(value, str):
        raise FamilyTwoPersonConfigurationError()
    normalized = value.strip().lower()
    try:
        encoded = normalized.encode("ascii")
    except UnicodeEncodeError as error:
        raise FamilyTwoPersonConfigurationError() from error
    if not normalized or len(encoded) > 254 or not _EMAIL_RE.fullmatch(normalized):
        raise FamilyTwoPersonConfigurationError()
    return normalized


@dataclass(frozen=True, repr=False)
class FamilyTwoPersonEmailConfig:
    """The two private addresses, intentionally never serializable publicly."""

    sharan_email: str
    dad_email: str

    def __repr__(self) -> str:
        return "FamilyTwoPersonEmailConfig(redacted=True)"


def load_family_two_person_email_config(raw: str | None = None) -> FamilyTwoPersonEmailConfig:
    """Parse exactly one protected JSON object; every ambiguity is fail-closed."""
    value = raw if raw is not None else os.environ.get(FAMILY_EMAILS_ENV)
    try:
        decoded = json.loads(
            value or "",
            object_pairs_hook=_without_duplicate_keys,
            parse_constant=lambda _value: (_ for _ in ()).throw(FamilyTwoPersonConfigurationError()),
        )
    except (TypeError, ValueError, json.JSONDecodeError, FamilyTwoPersonConfigurationError) as error:
        raise FamilyTwoPersonConfigurationError() from error
    if not isinstance(decoded, dict) or set(decoded) != _CONFIG_FIELDS or decoded.get("schemaVersion") != FAMILY_EMAILS_SCHEMA_VERSION:
        raise FamilyTwoPersonConfigurationError()
    sharan_email = normalize_family_email(decoded["sharanEmail"])
    dad_email = normalize_family_email(decoded["dadEmail"])
    if sharan_email == dad_email:
        raise FamilyTwoPersonConfigurationError()
    return FamilyTwoPersonEmailConfig(sharan_email=sharan_email, dad_email=dad_email)


class FixedTwoPersonAuthority:
    """Derive the sole two-person scopes after Firebase has verified a token."""

    def __init__(self, config: FamilyTwoPersonEmailConfig, sharan_identity: PrivateNsdlIdentity) -> None:
        if not isinstance(config, FamilyTwoPersonEmailConfig) or not isinstance(sharan_identity, PrivateNsdlIdentity):
            raise FamilyTwoPersonConfigurationError()
        if not all(isinstance(value, str) and value and value.isascii() for value in (sharan_identity.uid, sharan_identity.family_id, sharan_identity.portfolio_id)):
            raise FamilyTwoPersonConfigurationError()
        self._config = config
        self._sharan_identity = sharan_identity
        self._portfolios = {
            sharan_identity.portfolio_id: FamilyPortfolio(sharan_identity.portfolio_id, sharan_identity.uid, sharan_identity.uid, "Sharan"),
            DAD_PORTFOLIO_ID: FamilyPortfolio(DAD_PORTFOLIO_ID, DAD_SCOPE_ID, DAD_SCOPE_ID, "Dad"),
            JOINT_PORTFOLIO_ID: FamilyPortfolio(JOINT_PORTFOLIO_ID, JOINT_SCOPE_ID, JOINT_SCOPE_ID, "Joint"),
        }

    def __repr__(self) -> str:
        return "FixedTwoPersonAuthority(redacted=True)"

    def actor_label(self, principal: VerifiedPrincipal) -> str:
        if not isinstance(principal, VerifiedPrincipal):
            raise FamilyPortfolioDenied()
        email = normalize_family_email(principal.email)
        if email == self._config.sharan_email:
            return "Sharan"
        if email == self._config.dad_email:
            return "Dad"
        raise FamilyPortfolioDenied()

    def resolve(self, principal: VerifiedPrincipal) -> str:
        """AuthPerimeter uses this only after successful token verification."""
        return self.actor_label(principal)

    def public_status(self, principal: VerifiedPrincipal) -> str:
        self.actor_label(principal)
        return "admitted"

    def empty_scope_identities(self) -> Mapping[tuple[str, str], PrivateNsdlIdentity]:
        """In-memory identities for empty scopes; no source storage is copied."""
        family_id = self._sharan_identity.family_id
        return {
            (DAD_SCOPE_ID, DAD_PORTFOLIO_ID): PrivateNsdlIdentity(DAD_SCOPE_ID, family_id, DAD_PORTFOLIO_ID, ""),
            (JOINT_SCOPE_ID, JOINT_PORTFOLIO_ID): PrivateNsdlIdentity(JOINT_SCOPE_ID, family_id, JOINT_PORTFOLIO_ID, ""),
        }

    def _access(self, principal: VerifiedPrincipal, portfolio_id: str) -> AuthorizedFamilyPortfolio:
        label = self.actor_label(principal)
        portfolio = self._portfolios.get(portfolio_id)
        if portfolio is None:
            raise FamilyPortfolioDenied()
        if label == "Sharan":
            capabilities = {
                self._sharan_identity.portfolio_id: frozenset({OWNER, READ, WRITE}),
                DAD_PORTFOLIO_ID: frozenset({READ, WRITE, HELPER}),
                JOINT_PORTFOLIO_ID: frozenset({READ}),
            }.get(portfolio_id)
        else:
            capabilities = {
                DAD_PORTFOLIO_ID: frozenset({OWNER, READ}),
                JOINT_PORTFOLIO_ID: frozenset({READ}),
            }.get(portfolio_id)
        if capabilities is None:
            raise FamilyPortfolioDenied()
        return AuthorizedFamilyPortfolio(portfolio, principal.uid, capabilities, label, self._sharan_identity.family_id)

    def authorize(self, principal: VerifiedPrincipal, portfolio_id: str, capability: str) -> AuthorizedFamilyPortfolio:
        if capability not in {READ, WRITE} or not isinstance(portfolio_id, str):
            raise FamilyPortfolioDenied()
        access = self._access(principal, portfolio_id)
        if not access.allows(capability):
            raise FamilyPortfolioDenied()
        return access

    def visible(self, principal: VerifiedPrincipal) -> tuple[AuthorizedFamilyPortfolio, ...]:
        label = self.actor_label(principal)
        ordered_ids = (self._sharan_identity.portfolio_id, DAD_PORTFOLIO_ID, JOINT_PORTFOLIO_ID) if label == "Sharan" else (DAD_PORTFOLIO_ID, JOINT_PORTFOLIO_ID)
        return tuple(self.authorize(principal, portfolio_id, READ) for portfolio_id in ordered_ids)
