"""Fail-closed identity and preview-admission perimeter for private preview."""

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, MutableMapping, Optional
from types import MappingProxyType
from urllib.parse import parse_qsl, urlparse

try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth
    from firebase_admin import credentials as firebase_credentials
except ImportError:  # The perimeter remains fail-closed if the optional runtime is absent.
    firebase_admin = None
    firebase_auth = None
    firebase_credentials = None

try:
    from fastapi import HTTPException, Request
except ImportError:  # pragma: no cover - application imports FastAPI in supported runtime
    HTTPException = RuntimeError
    Request = Any


AUTH_REQUIRED = {"detail": "authentication required"}
AUTH_UNAVAILABLE = {"detail": "authentication service unavailable"}
PREVIEW_DENIED = {"detail": "preview access denied"}
AUTHORIZATION_UNCONFIGURED = {"detail": "authorization not configured"}
PORTFOLIO_DENIED = {"detail": "portfolio access denied"}
INVALID_PORTFOLIO_ID = {"detail": "invalid portfolio_id"}

PUBLIC_HEALTH = {("GET", "/health"), ("GET", "/api/health")}
DISABLED_PATHS = {"/docs", "/redoc", "/openapi.json", "/api/statements/inbound-email", "/api/statements/health"}
AI_STATUS = ("GET", "/api/ai/status")
MEMBERSHIP_MANAGEMENT = ("POST", "/api/admin/memberships")
PROTECTED_DISABLED_OPERATIONS = {
    ("POST", "/api/statements/inbound-mime"),
    ("POST", "/api/statements/parse-cas"),
    ("GET", "/api/ledger/statements"),
    ("POST", "/api/ledger/reset"),
    ("GET", "/api/market/sync-amfi-navs"),
}
AI_EFFECT_OPERATIONS = {
    ("POST", "/api/ai/chat"),
    ("POST", "/api/ai/live-token"),
}
INGESTION_EFFECT_OPERATIONS = {
    ("POST", "/api/statements/process-file"),
}
PORTFOLIO_SCOPED_READS = {
    ("GET", "/api/ledger/transactions"),
    ("GET", "/api/ledger/tax-lots"),
    ("GET", "/api/ledger/capital-gains"),
    ("GET", "/api/ledger/portfolio"),
}
PRIVATE_NSDL_OPERATIONS = {
    ("POST", "/api/nsdl/import-preview"),
    ("POST", "/api/nsdl/schwab-preview"),
    ("POST", "/api/nsdl/import"),
    ("GET", "/api/nsdl/portfolio"),
    ("GET", "/api/nsdl/quotes"),
    ("GET", "/api/nsdl/account-data"),
    ("POST", "/api/nsdl/account-data/accounts"),
    ("POST", "/api/nsdl/account-data/opening-holdings"),
    ("POST", "/api/nsdl/account-data/cash-flows"),
    ("GET", "/api/nsdl/valuation"),
    ("GET", "/api/nsdl/valuation-range"),
    ("GET", "/api/nsdl/performance"),
    ("GET", "/api/nsdl/authorized-portfolios"),
    ("GET", "/api/nsdl/activity"),
    ("GET", "/api/nsdl/admission"),
}
PROJECT_ID_RE = re.compile(r"^[a-z][a-z0-9-]{4,62}$")
PORTFOLIO_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
MAX_AUTHORIZATION_BYTES = 16 * 1024
MAX_GRANTS_BYTES = 64 * 1024
MAX_GRANT_UIDS = 100
MAX_PORTFOLIOS_PER_UID = 100
LOCAL_PREVIEW_ORIGINS = frozenset({"http://127.0.0.1:5173", "http://localhost:5173"})
logger = logging.getLogger(__name__)


class AuthenticationUnavailable(Exception):
    """The configured verifier cannot safely verify an identity."""


class AuthenticationInvalid(Exception):
    """The bearer value cannot establish an authenticated principal."""


class AuthorizationConfigurationInvalid(Exception):
    """The server-side portfolio grant configuration is absent or invalid."""


@dataclass(frozen=True)
class VerifiedPrincipal:
    uid: str
    email: str


@dataclass(frozen=True)
class AuthorizedPortfolio:
    principal: VerifiedPrincipal
    portfolio_id: str


def parse_cors_origins(value: Optional[str]) -> list[str]:
    """Return HTTPS origins plus the exact local preview origin; invalid config means none."""
    if not value or not value.strip():
        return []
    origins = []
    for raw_origin in value.split(","):
        origin = raw_origin.strip()
        parsed = urlparse(origin)
        is_preview_localhost = origin in LOCAL_PREVIEW_ORIGINS
        is_valid_https = (
            parsed.scheme == "https"
            and parsed.hostname
        )
        if (
            not origin
            or not (is_valid_https or is_preview_localhost)
            or parsed.username
            or parsed.password
            or parsed.path not in ("", "/")
            or parsed.params
            or parsed.query
            or parsed.fragment
        ):
            return []
        normalized = origin if is_preview_localhost else f"https://{parsed.netloc}"
        if normalized in origins:
            return []
        origins.append(normalized)
    return origins


def _preview_uids(value: Optional[str]) -> Optional[set[str]]:
    if value is None or not value.strip():
        return None
    entries = [entry.strip() for entry in value.split(",")]
    if not entries or any(not entry for entry in entries):
        return None
    return set(entries) if len(set(entries)) == len(entries) else None


def _identifier(value: Any) -> bool:
    return isinstance(value, str) and value.isascii() and bool(PORTFOLIO_IDENTIFIER_RE.fullmatch(value))


def parse_portfolio_grants(raw_value: Optional[str]) -> Mapping[str, frozenset[str]]:
    """Parse the exact server-only JSON grant schema without normalization."""
    if raw_value is None or raw_value == "":
        raise AuthorizationConfigurationInvalid()
    try:
        raw_bytes = raw_value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise AuthorizationConfigurationInvalid() from error
    if len(raw_bytes) > MAX_GRANTS_BYTES or not raw_value.isascii():
        raise AuthorizationConfigurationInvalid()

    def object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise AuthorizationConfigurationInvalid()
            result[key] = value
        return result

    try:
        decoded = json.loads(
            raw_value,
            object_pairs_hook=object_without_duplicate_keys,
            parse_constant=lambda _value: (_ for _ in ()).throw(AuthorizationConfigurationInvalid()),
        )
    except (json.JSONDecodeError, AuthorizationConfigurationInvalid, TypeError, ValueError) as error:
        raise AuthorizationConfigurationInvalid() from error
    if not isinstance(decoded, dict) or not decoded or len(decoded) > MAX_GRANT_UIDS:
        raise AuthorizationConfigurationInvalid()

    grants: dict[str, frozenset[str]] = {}
    for uid, portfolios in decoded.items():
        if not _identifier(uid) or not isinstance(portfolios, list) or not portfolios or len(portfolios) > MAX_PORTFOLIOS_PER_UID:
            raise AuthorizationConfigurationInvalid()
        if any(not _identifier(portfolio_id) for portfolio_id in portfolios):
            raise AuthorizationConfigurationInvalid()
        portfolio_set = frozenset(portfolios)
        if len(portfolio_set) != len(portfolios):
            raise AuthorizationConfigurationInvalid()
        grants[uid] = portfolio_set
    return MappingProxyType(grants)


def requested_portfolio_id(request: Request) -> str:
    """Accept one ASCII `portfolio_id` from the raw query string only."""
    try:
        raw_query = request.scope.get("query_string", b"").decode("ascii")
        pairs = parse_qsl(raw_query, keep_blank_values=True, strict_parsing=False, encoding="ascii", errors="strict")
    except (UnicodeDecodeError, UnicodeEncodeError, ValueError) as error:
        raise HTTPException(status_code=400, detail=INVALID_PORTFOLIO_ID["detail"]) from error
    values = [value for key, value in pairs if key == "portfolio_id"]
    if len(values) != 1 or not _identifier(values[0]):
        raise HTTPException(status_code=400, detail=INVALID_PORTFOLIO_ID["detail"])
    return values[0]


def route_policy(method: str, path: str) -> str:
    """Classify every route without treating unknown paths as authenticated."""
    route = (method.upper(), path)
    if route in PUBLIC_HEALTH:
        return "public-health"
    if path in DISABLED_PATHS:
        return "disabled-404"
    if route == AI_STATUS:
        return "verified-preview-status"
    if route == MEMBERSHIP_MANAGEMENT:
        return "verified-preview-membership-management"
    if route in AI_EFFECT_OPERATIONS:
        return "verified-preview-ai"
    if route in INGESTION_EFFECT_OPERATIONS:
        return "verified-preview-ingestion"
    if route in PORTFOLIO_SCOPED_READS:
        return "verified-preview-portfolio-read"
    if route in PRIVATE_NSDL_OPERATIONS:
        return "verified-preview-nsdl"
    if route in PROTECTED_DISABLED_OPERATIONS:
        return "verified-preview-disabled"
    return "unmatched"


def _authorization_token(headers: list[tuple[bytes, bytes]]) -> str:
    values = [value for name, value in headers if name.lower() == b"authorization"]
    if len(values) != 1 or len(values[0]) > MAX_AUTHORIZATION_BYTES:
        raise AuthenticationInvalid()
    try:
        value = values[0].decode("ascii")
    except UnicodeDecodeError as error:
        raise AuthenticationInvalid() from error
    match = re.fullmatch(r"Bearer ([^\t ]+)", value)
    if not match:
        raise AuthenticationInvalid()
    return match.group(1)


class FirebaseAdminTokenVerifier:
    """Production Firebase Admin adapter bound to an explicit trusted project."""

    app_name = "moneymoney-auth-perimeter"
    private_app_name = "moneymoney-private-nsdl-auth"

    def __init__(self, project_id: Optional[str] = None) -> None:
        self.project_id = project_id if project_id is not None else os.environ.get("MONEYMONEY_FIREBASE_PROJECT_ID")

    def _app(self) -> Any:
        if not self.project_id or not PROJECT_ID_RE.fullmatch(self.project_id):
            raise AuthenticationUnavailable()
        if os.environ.get("FIREBASE_AUTH_EMULATOR_HOST"):
            raise AuthenticationUnavailable()
        if firebase_admin is None or firebase_auth is None:
            raise AuthenticationUnavailable()
        is_private = os.environ.get("MONEYMONEY_RELEASE_MODE") == "private_nsdl"
        selected_name = self.private_app_name if is_private else self.app_name
        try:
            try:
                app = firebase_admin.get_app(selected_name)
            except ValueError:
                if is_private:
                    raw = os.environ.get("MONEYMONEY_FIREBASE_SERVICE_ACCOUNT_JSON")
                    try:
                        def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                            output: dict[str, Any] = {}
                            for key, value in pairs:
                                if key in output:
                                    raise ValueError()
                                output[key] = value
                            return output
                        service_account = json.loads(raw or "", object_pairs_hook=strict_object)
                    except (TypeError, ValueError, json.JSONDecodeError) as error:
                        raise AuthenticationUnavailable() from error
                    if not isinstance(service_account, dict) or service_account.get("project_id") != self.project_id or firebase_credentials is None:
                        raise AuthenticationUnavailable()
                    app = firebase_admin.initialize_app(
                        firebase_credentials.Certificate(service_account), options={"projectId": self.project_id}, name=selected_name
                    )
                else:
                    app = firebase_admin.initialize_app(options={"projectId": self.project_id}, name=selected_name)
            if app.options.get("projectId") != self.project_id:
                raise AuthenticationUnavailable()
            return app
        except AuthenticationUnavailable:
            raise
        except Exception as error:
            raise AuthenticationUnavailable() from error

    def verify(self, token: str) -> Mapping[str, Any]:
        app = self._app()
        try:
            return firebase_auth.verify_id_token(token, app=app, check_revoked=True)
        except Exception as error:
            invalid_errors = tuple(
                cls
                for cls in (
                    getattr(firebase_auth, "InvalidIdTokenError", None),
                    getattr(firebase_auth, "ExpiredIdTokenError", None),
                    getattr(firebase_auth, "RevokedIdTokenError", None),
                    getattr(firebase_auth, "UserDisabledError", None),
                )
                if isinstance(cls, type)
            )
            if invalid_errors and isinstance(error, invalid_errors):
                raise AuthenticationInvalid() from error
            category = "unknown"
            for error_name, safe_category in (
                ("CertificateFetchError", "certificate_fetch"),
                ("InsufficientPermissionError", "insufficient_permission"),
                ("UnexpectedResponseError", "unexpected_response"),
                ("UserNotFoundError", "user_not_found"),
            ):
                error_type = getattr(firebase_auth, error_name, None)
                if isinstance(error_type, type) and isinstance(error, error_type):
                    category = safe_category
                    break
            logger.warning("private_nsdl_auth_verification_failure category=%s", category)
            raise AuthenticationUnavailable() from error


def verified_principal(claims: Mapping[str, Any]) -> VerifiedPrincipal:
    uid = claims.get("uid")
    email = claims.get("email")
    if not isinstance(uid, str) or not uid.strip():
        raise AuthenticationInvalid()
    if not isinstance(email, str) or not email.strip() or claims.get("email_verified") is not True:
        raise AuthenticationInvalid()
    return VerifiedPrincipal(uid=uid, email=email.strip().lower())


async def require_verified_preview(request: Request) -> VerifiedPrincipal:
    principal = getattr(request.state, "verified_principal", None)
    if not isinstance(principal, VerifiedPrincipal):
        raise HTTPException(status_code=401, detail=AUTH_REQUIRED["detail"])
    return principal


async def require_authorized_portfolio(request: Request) -> AuthorizedPortfolio:
    """Authorize a single requested portfolio before any ledger service lookup."""
    principal = await require_verified_preview(request)
    portfolio_id = requested_portfolio_id(request)
    try:
        grants = parse_portfolio_grants(os.environ.get("MONEYMONEY_PORTFOLIO_GRANTS_JSON"))
    except AuthorizationConfigurationInvalid as error:
        raise HTTPException(status_code=503, detail=AUTHORIZATION_UNCONFIGURED["detail"]) from error
    if portfolio_id not in grants.get(principal.uid, frozenset()):
        raise HTTPException(status_code=403, detail=PORTFOLIO_DENIED["detail"])
    return AuthorizedPortfolio(principal=principal, portfolio_id=portfolio_id)


class AuthPerimeter:
    """Header-only ASGI middleware. It never reads denied request bodies."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    @staticmethod
    async def _respond(
        send: Callable[[MutableMapping[str, Any]], Awaitable[None]], status: int, body: Mapping[str, str]
    ) -> None:
        payload = json.dumps(body, separators=(",", ":")).encode("utf-8")
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(payload)).encode())],
        })
        await send({"type": "http.response.body", "body": payload})

    def _verifier(self, scope: Mapping[str, Any]) -> Any:
        app = scope.get("app")
        return getattr(getattr(app, "state", None), "auth_verifier", None) or FirebaseAdminTokenVerifier()

    async def __call__(self, scope: MutableMapping[str, Any], receive: Callable[..., Awaitable[Any]], send: Callable[..., Awaitable[None]]) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        method = scope["method"].upper()
        path = scope["path"]
        route = (method, path)
        policy = route_policy(method, path)
        if policy == "public-health" or method == "OPTIONS":
            await self.app(scope, receive, send)
            return
        if policy == "disabled-404":
            await self._respond(send, 404, {"detail": "Not Found"})
            return
        if policy == "unmatched":
            await self.app(scope, receive, send)
            return
        try:
            token = _authorization_token(scope.get("headers", []))
            claims = self._verifier(scope).verify(token)
            principal = verified_principal(claims)
        except AuthenticationInvalid:
            await self._respond(send, 401, AUTH_REQUIRED)
            return
        except (AuthenticationUnavailable, AttributeError, TypeError):
            await self._respond(send, 503, AUTH_UNAVAILABLE)
            return
        allowed_uids = _preview_uids(os.environ.get("MONEYMONEY_PRIVATE_PREVIEW_UIDS"))
        state = getattr(scope.get("app"), "state", None)
        fixed_family_authority = getattr(state, "family_email_authority", None)
        family_mode = getattr(state, "allow_pending_family_admission", False) is True
        pending_admission_route = route == ("GET", "/api/nsdl/admission") and family_mode
        family_admitted = False
        fixed_family_admitted = False
        if fixed_family_authority is not None and route in PRIVATE_NSDL_OPERATIONS:
            try:
                fixed_family_authority.resolve(principal)
                fixed_family_admitted = True
            except Exception:
                fixed_family_admitted = False
        if family_mode and route in PRIVATE_NSDL_OPERATIONS:
            resolver = getattr(state, "family_admission", None)
            try:
                resolver.resolve(principal)
                family_admitted = True
            except Exception:
                family_admitted = False
        if fixed_family_authority is not None and route in PRIVATE_NSDL_OPERATIONS and not fixed_family_admitted:
            await self._respond(send, 403, PREVIEW_DENIED)
            return
        if fixed_family_authority is None and (allowed_uids is None or principal.uid not in allowed_uids) and not pending_admission_route and not family_admitted:
            await self._respond(send, 403, PREVIEW_DENIED)
            return
        scope.setdefault("state", {})["verified_principal"] = principal
        if policy == "verified-preview-disabled":
            await self._respond(send, 503, AUTHORIZATION_UNCONFIGURED)
            return
        await self.app(scope, receive, send)
