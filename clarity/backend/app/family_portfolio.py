"""Server-owned family portfolio authorization; request selectors confer no authority."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping
import re


READ = "READ"
WRITE = "WRITE"
OWNER = "OWNER"
HELPER = "HELPER"
MEMBER = "MEMBER"
_CAPABILITIES = frozenset({READ, WRITE, OWNER, HELPER, MEMBER})
_OPAQUE = re.compile(r"^[a-z][a-z0-9_-]{15,127}$")


class FamilyPortfolioDenied(Exception):
    pass


@dataclass(frozen=True)
class FamilyPortfolio:
    portfolio_id: str
    scope_id: str
    owner_uid: str
    label: str


@dataclass(frozen=True)
class FamilyGrant:
    uid: str
    portfolio_id: str
    capabilities: frozenset[str]
    active: bool = True


@dataclass(frozen=True)
class AuthorizedFamilyPortfolio:
    portfolio: FamilyPortfolio
    actor_uid: str
    capabilities: frozenset[str]
    actor_label: str = "Member"
    family_id: str | None = None

    def allows(self, capability: str) -> bool:
        return capability in self.capabilities or OWNER in self.capabilities


class FamilyPortfolioRegistry:
    """Immutable injected registry, re-read by the app on every request."""

    def __init__(self, portfolios: Iterable[FamilyPortfolio], grants: Iterable[FamilyGrant]) -> None:
        portfolio_values = tuple(portfolios)
        grant_values = tuple(grants)
        self._portfolios = {item.portfolio_id: item for item in portfolio_values}
        self._grants = {(item.uid, item.portfolio_id): item for item in grant_values}
        if not self._portfolios or len(self._portfolios) != len(portfolio_values) or len(self._grants) != len(grant_values):
            raise ValueError("invalid family registry")
        for portfolio in self._portfolios.values():
            if not all(isinstance(value, str) and value.isascii() and value for value in (portfolio.portfolio_id, portfolio.scope_id, portfolio.owner_uid, portfolio.label)):
                raise ValueError("invalid family registry")
        for key, grant in self._grants.items():
            if key[1] not in self._portfolios or not isinstance(grant.active, bool) or not isinstance(grant.uid, str) or not grant.uid or not grant.capabilities or not grant.capabilities <= _CAPABILITIES:
                raise ValueError("invalid family registry")

    @classmethod
    def singleton(cls, identities: Mapping[tuple[str, str], object]) -> "FamilyPortfolioRegistry":
        portfolios: list[FamilyPortfolio] = []
        grants: list[FamilyGrant] = []
        for (uid, portfolio_id), identity in identities.items():
            if getattr(identity, "uid", None) != uid or getattr(identity, "portfolio_id", None) != portfolio_id:
                raise ValueError("invalid private identity")
            portfolios.append(FamilyPortfolio(portfolio_id, uid, uid, portfolio_id))
            grants.append(FamilyGrant(uid, portfolio_id, frozenset({OWNER, READ, WRITE})))
        return cls(portfolios, grants)

    def authorize(self, uid: str, portfolio_id: str, capability: str) -> AuthorizedFamilyPortfolio:
        if capability not in {READ, WRITE} or not isinstance(uid, str) or not isinstance(portfolio_id, str):
            raise FamilyPortfolioDenied()
        portfolio = self._portfolios.get(portfolio_id)
        grant = self._grants.get((uid, portfolio_id))
        if portfolio is None or grant is None or not grant.active:
            raise FamilyPortfolioDenied()
        label = "Sharan" if uid == "sharan_uid" else "Dad" if uid == "dad_uid" else "Member"
        authorized = AuthorizedFamilyPortfolio(portfolio, uid, grant.capabilities, label)
        if not authorized.allows(capability):
            raise FamilyPortfolioDenied()
        return authorized

    def visible(self, uid: str) -> tuple[AuthorizedFamilyPortfolio, ...]:
        result = []
        for portfolio_id in self._portfolios:
            try:
                result.append(self.authorize(uid, portfolio_id, READ))
            except FamilyPortfolioDenied:
                continue
        return tuple(result)


class FirestoreFamilyPortfolioRegistry(FamilyPortfolioRegistry):
    """Fresh server-only registry reader; injected fakes exercise this seam."""

    COLLECTION = "private_family_registry"
    DOCUMENT = "two_person_v1"

    def __init__(self, client: object) -> None:
        self.client = client
        super().__init__((FamilyPortfolio("bootstrap", "bootstrap", "bootstrap", "Bootstrap"),), (FamilyGrant("bootstrap", "bootstrap", frozenset({READ})),))

    def _current(self) -> "FamilyPortfolioRegistry":
        try:
            snapshot = self.client.collection(self.COLLECTION).document(self.DOCUMENT).get()
            value = snapshot.to_dict() if snapshot.exists else None
            if not isinstance(value, dict) or set(value) != {"familyId", "portfolios", "grants"} or not isinstance(value["familyId"], str) or not _OPAQUE.fullmatch(value["familyId"]):
                raise ValueError()
            portfolios = []
            for portfolio_id, row in value["portfolios"].items():
                if not isinstance(row, dict) or set(row) != {"scopeId", "ownerUid", "label"}:
                    raise ValueError()
                portfolios.append(FamilyPortfolio(portfolio_id, row["scopeId"], row["ownerUid"], row["label"]))
            if len(portfolios) != 3 or {item.label for item in portfolios} != {"Sharan", "Dad", "Joint"} or len({item.scope_id for item in portfolios}) != 3 or any(not _OPAQUE.fullmatch(item.portfolio_id) or not _OPAQUE.fullmatch(item.scope_id) for item in portfolios):
                raise ValueError()
            grants = []
            for key, row in value["grants"].items():
                if not isinstance(key, str) or not isinstance(row, dict) or set(row) != {"uid", "portfolioId", "capabilities", "active", "actorLabel"} or key != f"{row['uid']}:{row['portfolioId']}":
                    raise ValueError()
                capabilities = row["capabilities"]
                if not isinstance(capabilities, list) or len(set(capabilities)) != len(capabilities):
                    raise ValueError()
                grants.append(FamilyGrant(row["uid"], row["portfolioId"], frozenset(capabilities), row["active"]))
            registry = FamilyPortfolioRegistry(portfolios, grants)
            registry.family_id = value["familyId"]
            registry._actor_labels = {f"{row['uid']}:{row['portfolioId']}": row["actorLabel"] for row in value["grants"].values() if isinstance(row.get("actorLabel"), str) and row["actorLabel"] in {"Sharan", "Dad"}}
            if len(registry._actor_labels) != len(grants):
                raise ValueError()
            return registry
        except Exception as error:
            raise FamilyPortfolioDenied() from error

    def authorize(self, uid: str, portfolio_id: str, capability: str) -> AuthorizedFamilyPortfolio:
        current = self._current()
        item = current.authorize(uid, portfolio_id, capability)
        return AuthorizedFamilyPortfolio(item.portfolio, item.actor_uid, item.capabilities, current._actor_labels[f"{uid}:{portfolio_id}"], current.family_id)

    def visible(self, uid: str) -> tuple[AuthorizedFamilyPortfolio, ...]:
        current = self._current()
        return tuple(AuthorizedFamilyPortfolio(item.portfolio, item.actor_uid, item.capabilities, current._actor_labels[f"{uid}:{item.portfolio.portfolio_id}"], current.family_id) for item in current.visible(uid))
