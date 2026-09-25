"""The sole private-NSDL release entrypoint; it never imports legacy main.py."""
from __future__ import annotations

import os
import base64
import json
import logging
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.account_data import correction_revision, idempotency_key, owner_facts, parse_account, parse_cash_flow, parse_opening_holding, public_error, record_wire, request_digest, strict_account_id, strict_as_of, strict_json_object, void_revision
from .api.nsdl import safe_error
from .models.account_data import AccountDataError
from .account_data_store import FirestoreAccountDataStore
from .auth_perimeter import AuthPerimeter, VerifiedPrincipal, requested_portfolio_id, require_verified_preview
from .membership import FirebaseMembershipStore, parse_membership
from .nsdl_service import NsdlService
from .nsdl_store import FirestoreNsdlStore, NsdlStoreError
from .parsers.schwab_snapshot import SnapshotError as SchwabSnapshotError, parse_pdf_bytes as parse_schwab_pdf_bytes
from .private_nsdl_identity import PrivateNsdlIdentity, PrivateNsdlIdentityUnavailable, load_private_nsdl_identities, validate_service_account_project
from .quote_service import QuoteService
from .valuation_service import LocalValuationService, SyntheticDailyPriceSource, ValuationRangeLimitError
from .family_portfolio import FamilyPortfolioDenied, FamilyPortfolioRegistry, HELPER, READ, WRITE
from .family_activity import FamilyActivityError, FirestoreFamilyActivityStore
from .family_two_person_config import (
    FixedTwoPersonAuthority,
    FamilyTwoPersonConfigurationError,
    load_family_two_person_email_config,
)

_PUBLIC_CONFIG_KEYS = frozenset({"apiKey", "authDomain", "projectId", "storageBucket", "messagingSenderId", "appId", "portfolioId"})
_IMPORT_LOGGER = logging.getLogger("moneymoney.private_nsdl.import")
_IMPORT_LOG_CODES = frozenset({
    "OK", "ERR_NSDL_UPLOAD_INVALID", "ERR_NSDL_IDEMPOTENCY_INVALID", "ERR_NSDL_LIMIT_EXCEEDED",
    "ERR_NSDL_PASSWORD_INVALID", "ERR_NSDL_UNSUPPORTED_LAYOUT", "ERR_NSDL_OWNER_MISMATCH",
    "ERR_NSDL_PARSE_INCOMPLETE", "ERR_NSDL_SAME_DATE_CONFLICT", "ERR_NSDL_OLDER_STATEMENT",
    "ERR_NSDL_ACCOUNT_SET_CONFLICT", "ERR_NSDL_REVISION_CONFLICT", "ERR_NSDL_STORE_UNAVAILABLE",
    "ERR_NSDL_COMMIT_UNKNOWN", "ERR_NSDL_ACCOUNT_COMMIT_UNKNOWN", "ERR_NSDL_IDEMPOTENCY_CONFLICT",
    "ERR_NSDL_PREVIEW_INVALID",
})
if not _IMPORT_LOGGER.handlers:
    _import_handler = logging.StreamHandler(sys.stdout)
    _import_handler.setLevel(logging.INFO)
    _import_handler.setFormatter(logging.Formatter("%(message)s"))
    _IMPORT_LOGGER.addHandler(_import_handler)
_IMPORT_LOGGER.setLevel(logging.INFO)
_IMPORT_LOGGER.propagate = False


def _import_event(*, stage: str, code: str, reference: str, status: int, started_at: float, category: str) -> None:
    """Write a bounded JSON event suitable for existing Render stdout logs.

    The fixed payload deliberately excludes request inputs, exception text and
    storage identifiers. `reference` is generated server-side per confirm.
    """
    payload = {
        "event": "private_nsdl_import",
        "stage": stage if stage in {"preview", "snapshot_commit", "account_sync", "complete"} else "snapshot_commit",
        "code": code if code in _IMPORT_LOG_CODES else "ERR_NSDL_STORE_UNAVAILABLE",
        "requestRef": reference,
        "status": status,
        "durationMs": max(0, int((time.monotonic() - started_at) * 1000)),
        "category": category if category in {"nsdl_store", "account_store", "unexpected", "success"} else "unexpected",
    }
    _IMPORT_LOGGER.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _public_runtime_config() -> dict[str, str]:
    try:
        value = json.loads(os.environ.get("MONEYMONEY_PRIVATE_NSDL_WEB_CONFIG_JSON", ""))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise PrivateNsdlIdentityUnavailable() from error
    if not isinstance(value, dict) or set(value) != _PUBLIC_CONFIG_KEYS or any(not isinstance(item, str) or not item for item in value.values()):
        raise PrivateNsdlIdentityUnavailable()
    if any("secret" in key.casefold() or "pan" in key.casefold() or "grant" in key.casefold() for key in value):
        raise PrivateNsdlIdentityUnavailable()
    return dict(value)


def create_private_nsdl_app(
    *, identities: Mapping[tuple[str, str], PrivateNsdlIdentity] | None = None,
    store: Any = None,
    membership_reader: Any = None,
    quote_service: QuoteService | None = None,
    account_data_store: Any = None,
    valuation_service: Any = None,
    family_registry: Any = None,
    activity_store: Any = None,
    family_admission: Any = None,
    migration_adapter: Any = None,
    allow_pending_family_admission: bool = False,
    family_email_authority: FixedTwoPersonAuthority | None = None,
    password_resolver: Callable[[PrivateNsdlIdentity], str | None] | None = None,
) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(AuthPerimeter)
    if identities is None or store is None or (membership_reader is None and family_email_authority is None):
        raise PrivateNsdlIdentityUnavailable()
    app.state.nsdl_identities = identities
    app.state.nsdl_service = NsdlService(store, password_resolver=password_resolver)
    app.state.quote_service = quote_service or QuoteService.from_environment()
    app.state.membership_reader = membership_reader
    app.state.account_data_store = account_data_store
    app.state.valuation_service = valuation_service
    app.state.family_registry = family_registry or FamilyPortfolioRegistry.singleton(identities)
    app.state.family_activity_store = activity_store
    app.state.family_admission = family_admission
    app.state.family_migration_adapter = migration_adapter
    app.state.allow_pending_family_admission = allow_pending_family_admission is True
    app.state.family_email_authority = family_email_authority
    static_root = Path(os.environ.get("MONEYMONEY_PRIVATE_NSDL_STATIC_DIR", "/app/static"))

    async def authorize(request: Request, capability: str = READ) -> tuple[PrivateNsdlIdentity, Any]:
        principal: VerifiedPrincipal = await require_verified_preview(request)
        portfolio_id = requested_portfolio_id(request)
        try:
            authority = request.app.state.family_email_authority
            access = authority.authorize(principal, portfolio_id, capability) if authority is not None else request.app.state.family_registry.authorize(principal.uid, portfolio_id, capability)
        except (FamilyPortfolioDenied, ValueError):
            raise HTTPException(status_code=403, detail="portfolio access denied")
        identity = next((candidate for (_uid, candidate_portfolio), candidate in request.app.state.nsdl_identities.items() if candidate_portfolio == portfolio_id), None)
        if identity is None:
            raise HTTPException(status_code=503, detail="authorization not configured")
        if authority is None:
            reader = request.app.state.membership_reader
            try:
                membership = parse_membership(reader(principal.uid), principal.uid)
            except Exception as error:
                raise HTTPException(status_code=503, detail="authorization not configured") from error
            if membership is None or not membership.active or membership.role not in {"ADMIN", "MEMBER"} or membership.family_id != identity.family_id or (access.family_id is not None and membership.family_id != access.family_id):
                raise HTTPException(status_code=403, detail="statement ingestion access denied")
        from dataclasses import replace
        return replace(identity, uid=access.portfolio.scope_id), access

    def record_activity(access: Any, operation: str, idempotency: str) -> None:
        store = app.state.family_activity_store
        if store is not None:
            try:
                store.append(access.portfolio.portfolio_id, access.actor_uid, access.actor_label, operation, idempotency)
            except FamilyActivityError as error:
                raise HTTPException(status_code=503, detail="activity unavailable") from error
            except Exception as error:
                raise HTTPException(status_code=503, detail="activity unavailable") from error

    @app.get("/api/nsdl/authorized-portfolios")
    async def authorized_portfolios(request: Request) -> dict[str, Any]:
        principal: VerifiedPrincipal = await require_verified_preview(request)
        authority = request.app.state.family_email_authority
        if authority is not None:
            try:
                visible = authority.visible(principal)
            except (FamilyPortfolioDenied, ValueError):
                raise HTTPException(status_code=403, detail="portfolio access denied")
        else:
            try:
                membership = parse_membership(request.app.state.membership_reader(principal.uid), principal.uid)
            except Exception as error:
                raise HTTPException(status_code=503, detail="authorization not configured") from error
            if membership is None or not membership.active or membership.role not in {"ADMIN", "MEMBER"}:
                raise HTTPException(status_code=403, detail="portfolio access denied")
            visible = app.state.family_registry.visible(principal.uid)
        if any(next((identity for (_uid, item_portfolio), identity in app.state.nsdl_identities.items() if item_portfolio == item.portfolio.portfolio_id), None) is None for item in visible):
            raise HTTPException(status_code=503, detail="authorization not configured")
        if authority is None and any(item.family_id is not None and item.family_id != membership.family_id for item in visible):
            raise HTTPException(status_code=403, detail="portfolio access denied")
        return {"portfolios": [{"portfolioId": item.portfolio.portfolio_id, "label": item.portfolio.label, "helping": HELPER in item.capabilities} for item in visible]}

    @app.get("/api/nsdl/admission")
    async def family_admission(request: Request) -> JSONResponse:
        principal: VerifiedPrincipal = await require_verified_preview(request)
        resolver = request.app.state.family_admission
        if resolver is None:
            raise HTTPException(status_code=503, detail="authorization not configured")
        return JSONResponse({"status": resolver.public_status(principal)}, headers={"Cache-Control": "no-store"})

    @app.get("/api/nsdl/activity")
    async def activity(request: Request) -> JSONResponse:
        _identity, access = await authorize(request)
        store = app.state.family_activity_store
        return JSONResponse({"activity": [] if store is None else store.list_scope(access.portfolio.portfolio_id)}, headers={"Cache-Control": "no-store"})

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/private-config.json", include_in_schema=False)
    async def private_config() -> dict[str, str]:
        return _public_runtime_config()

    @app.get("/api/nsdl/portfolio")
    async def portfolio(request: Request) -> dict[str, Any]:
        identity, _access = await authorize(request)
        try:
            snapshot = request.app.state.nsdl_service.current(identity)
        except NsdlStoreError as error:
            raise safe_error(error) from None
        return {"status": "ready", "snapshot": snapshot.to_wire()} if snapshot else {"status": "not_imported", "snapshot": None}

    @app.get("/api/nsdl/quotes")
    async def quotes(request: Request) -> list[dict[str, str]]:
        identity, _access = await authorize(request)
        try:
            return request.app.state.quote_service.quotes(identity, lambda: request.app.state.nsdl_service.current(identity))
        except NsdlStoreError as error:
            raise safe_error(error) from None

    def account_store(request: Request) -> Any:
        selected = request.app.state.account_data_store
        if selected is None:
            raise HTTPException(status_code=503, detail="ERR_ACCOUNT_STORE_UNAVAILABLE")
        return selected

    async def account_payload(request: Request) -> tuple[dict[str, Any], str]:
        content_types = request.headers.getlist("content-type")
        if len(content_types) != 1 or content_types[0].split(";", 1)[0].strip().lower() != "application/json":
            raise HTTPException(status_code=400, detail="ERR_ACCOUNT_REQUEST_INVALID")
        try:
            payload = strict_json_object(await request.body())
            return payload, idempotency_key(request.headers)
        except AccountDataError as error:
            status, detail = public_error(error)
            raise HTTPException(status_code=status, detail=detail) from None

    def account_failure(error: AccountDataError) -> None:
        status, detail = public_error(error)
        raise HTTPException(status_code=status, detail=detail)

    def strict_currency_scope(value: Any) -> str:
        if not isinstance(value, str) or len(value) != 3 or not value.isascii() or value != value.upper() or not value.isalpha():
            raise AccountDataError("ERR_ACCOUNT_REQUEST_INVALID")
        return value

    def valuation_date(request: Request, *, allow_account_id: bool = False, allow_currency: bool = False) -> tuple[Any, str | None, str | None]:
        pairs = list(request.query_params.multi_items())
        allowed = {"portfolio_id", "as_of"}
        if allow_account_id:
            allowed.add("account_id")
        if allow_currency:
            allowed.add("currency")
        if [key for key, _value in pairs].count("portfolio_id") != 1 or [key for key, _value in pairs].count("as_of") != 1 or [key for key, _value in pairs].count("account_id") > 1 or [key for key, _value in pairs].count("currency") > 1 or {key for key, _value in pairs} - allowed:
            raise HTTPException(status_code=400, detail="ERR_ACCOUNT_REQUEST_INVALID")
        try:
            account_id = strict_account_id(request.query_params.get("account_id")) if "account_id" in request.query_params else None
            currency = strict_currency_scope(request.query_params.get("currency")) if "currency" in request.query_params else None
            return strict_as_of(request.query_params.get("as_of")), account_id, currency
        except AccountDataError as error:
            account_failure(error)

    def observation_scope(request: Request) -> tuple[str | None, str]:
        pairs = list(request.query_params.multi_items())
        allowed = {"portfolio_id", "account_id", "currency", "observations"}
        if [key for key, _value in pairs].count("portfolio_id") != 1 or [key for key, _value in pairs].count("account_id") > 1 or [key for key, _value in pairs].count("currency") != 1 or [key for key, _value in pairs].count("observations") != 1 or request.query_params.get("observations") != "1" or {key for key, _value in pairs} - allowed:
            raise HTTPException(status_code=400, detail="ERR_ACCOUNT_REQUEST_INVALID")
        try:
            account_id = strict_account_id(request.query_params.get("account_id")) if "account_id" in request.query_params else None
            return account_id, strict_currency_scope(request.query_params.get("currency"))
        except AccountDataError as error:
            account_failure(error)

    def valuation_range_scope(request: Request) -> tuple[str | None, str, Any | None, Any | None, str]:
        pairs = list(request.query_params.multi_items())
        allowed = {"portfolio_id", "account_id", "currency", "start", "end", "granularity"}
        if [key for key, _value in pairs].count("portfolio_id") != 1 or [key for key, _value in pairs].count("account_id") > 1 or [key for key, _value in pairs].count("currency") != 1 or [key for key, _value in pairs].count("start") > 1 or [key for key, _value in pairs].count("end") > 1 or [key for key, _value in pairs].count("granularity") != 1 or {key for key, _value in pairs} - allowed:
            raise HTTPException(status_code=400, detail="ERR_ACCOUNT_REQUEST_INVALID")
        has_start = "start" in request.query_params
        has_end = "end" in request.query_params
        if has_start != has_end:
            raise HTTPException(status_code=400, detail="ERR_ACCOUNT_REQUEST_INVALID")
        try:
            account_id = strict_account_id(request.query_params.get("account_id")) if "account_id" in request.query_params else None
            currency = strict_currency_scope(request.query_params.get("currency"))
            start = strict_as_of(request.query_params.get("start")) if has_start else None
            end = strict_as_of(request.query_params.get("end")) if has_end else None
            granularity = request.query_params.get("granularity")
            if granularity not in {"daily", "monthly"}:
                raise AccountDataError("ERR_ACCOUNT_REQUEST_INVALID")
            return account_id, currency, start, end, granularity
        except AccountDataError as error:
            account_failure(error)

    def local_valuation(request: Request) -> Any:
        if request.app.state.account_data_store is None or request.app.state.valuation_service is None:
            raise HTTPException(status_code=503, detail="ERR_ACCOUNT_STORE_UNAVAILABLE")
        return request.app.state.valuation_service

    @app.get("/api/nsdl/account-data")
    async def get_account_data(request: Request) -> JSONResponse:
        identity, _access = await authorize(request)
        try:
            body = owner_facts(account_store(request), identity.uid, identity.portfolio_id)
        except AccountDataError as error:
            account_failure(error)
        return JSONResponse(body, headers={"Cache-Control": "no-store"})

    @app.post("/api/nsdl/account-data/accounts")
    async def save_account(request: Request) -> JSONResponse:
        identity, access = await authorize(request, WRITE)
        payload, key = await account_payload(request)
        try:
            account, expected_revision = parse_account(payload, owner_scope_id=identity.uid, portfolio_id=identity.portfolio_id, idempotency=key)
            result = account_store(request).commit_account(account, route="/api/nsdl/account-data/accounts", idempotency_key=key, request_digest=request_digest(payload), expected_revision=expected_revision)
        except AccountDataError as error:
            account_failure(error)
        record_activity(access, "manual_account", key)
        return JSONResponse({"record": record_wire(result)}, headers={"Cache-Control": "no-store"})

    @app.post("/api/nsdl/account-data/opening-holdings")
    async def save_opening_holding(request: Request) -> JSONResponse:
        identity, access = await authorize(request, WRITE)
        payload, key = await account_payload(request)
        try:
            if payload.get("void") is True:
                result = account_store(request).void_opening_holding(identity.uid, identity.portfolio_id, strict_account_id(payload.get("factId")), route="/api/nsdl/account-data/opening-holdings", idempotency_key=key, request_digest=request_digest(payload), expected_revision=void_revision({key_name: value for key_name, value in payload.items() if key_name not in {"void", "factId"}}))
            else:
                expected_revision = correction_revision(payload) if "expectedRevision" in payload else None
                fact = parse_opening_holding({key_name: value for key_name, value in payload.items() if key_name != "expectedRevision"}, owner_scope_id=identity.uid, portfolio_id=identity.portfolio_id, idempotency=key)
                result = account_store(request).revise_opening_holding(fact, route="/api/nsdl/account-data/opening-holdings", idempotency_key=key, request_digest=request_digest(payload), expected_revision=expected_revision) if expected_revision is not None else account_store(request).commit_opening_holding(fact, route="/api/nsdl/account-data/opening-holdings", idempotency_key=key, request_digest=request_digest(payload))
        except AccountDataError as error:
            account_failure(error)
        record_activity(access, "opening_holding", key)
        return JSONResponse({"record": record_wire(result)}, headers={"Cache-Control": "no-store"})

    @app.post("/api/nsdl/account-data/cash-flows")
    async def save_cash_flow(request: Request) -> JSONResponse:
        identity, access = await authorize(request, WRITE)
        payload, key = await account_payload(request)
        try:
            if payload.get("void") is True:
                result = account_store(request).void_cash_flow(identity.uid, identity.portfolio_id, strict_account_id(payload.get("factId")), route="/api/nsdl/account-data/cash-flows", idempotency_key=key, request_digest=request_digest(payload), expected_revision=void_revision({key_name: value for key_name, value in payload.items() if key_name not in {"void", "factId"}}))
            else:
                expected_revision = correction_revision(payload) if "expectedRevision" in payload else None
                fact = parse_cash_flow({key_name: value for key_name, value in payload.items() if key_name != "expectedRevision"}, owner_scope_id=identity.uid, portfolio_id=identity.portfolio_id, idempotency=key)
                result = account_store(request).revise_cash_flow(fact, route="/api/nsdl/account-data/cash-flows", idempotency_key=key, request_digest=request_digest(payload), expected_revision=expected_revision) if expected_revision is not None else account_store(request).commit_cash_flow(fact, route="/api/nsdl/account-data/cash-flows", idempotency_key=key, request_digest=request_digest(payload))
        except AccountDataError as error:
            account_failure(error)
        record_activity(access, "cash_flow", key)
        return JSONResponse({"record": record_wire(result)}, headers={"Cache-Control": "no-store"})

    @app.get("/api/nsdl/valuation")
    async def valuation(request: Request) -> JSONResponse:
        identity, _access = await authorize(request)
        if "observations" in request.query_params:
            account_id, currency = observation_scope(request)
            try:
                dates = local_valuation(request).observation_dates(account_store(request), identity.uid, identity.portfolio_id, request.app.state.nsdl_service.current(identity), account_id, currency)
            except AccountDataError as error:
                account_failure(error)
            except Exception:
                raise HTTPException(status_code=503, detail="ERR_ACCOUNT_STORE_UNAVAILABLE") from None
            return JSONResponse({"observationDates": [item.isoformat() for item in dates]}, headers={"Cache-Control": "no-store"})
        as_of, account_id, currency = valuation_date(request, allow_account_id=True, allow_currency=True)
        try:
            result = local_valuation(request).valuation(account_store(request), identity.uid, identity.portfolio_id, as_of, request.app.state.nsdl_service.current(identity), account_id, currency)
        except AccountDataError as error:
            account_failure(error)
        except Exception:
            raise HTTPException(status_code=503, detail="ERR_ACCOUNT_STORE_UNAVAILABLE") from None
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    @app.get("/api/nsdl/valuation-range")
    async def valuation_range(request: Request) -> JSONResponse:
        identity, _access = await authorize(request)
        account_id, currency, start, end, granularity = valuation_range_scope(request)
        try:
            result = local_valuation(request).valuation_range(account_store(request), identity.uid, identity.portfolio_id, request.app.state.nsdl_service.current(identity), account_id, currency, start, end, granularity)
        except ValuationRangeLimitError:
            raise HTTPException(status_code=422, detail="ERR_ACCOUNT_RANGE_LIMIT") from None
        except AccountDataError as error:
            account_failure(error)
        except Exception:
            raise HTTPException(status_code=503, detail="ERR_ACCOUNT_STORE_UNAVAILABLE") from None
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    @app.get("/api/nsdl/performance")
    async def performance(request: Request) -> JSONResponse:
        identity, _access = await authorize(request)
        as_of, account_id, _currency = valuation_date(request, allow_account_id=True)
        try:
            selected_store = account_store(request)
            selected_service = local_valuation(request)
            # Account-scoped performance needs its own statement rows for the
            # same conservative reconciliation check as whole-portfolio scope.
            snapshot = request.app.state.nsdl_service.current(identity)
            result = selected_service.performance(selected_store, identity.uid, identity.portfolio_id, as_of, snapshot, account_id)
        except AccountDataError as error:
            account_failure(error)
        except Exception:
            raise HTTPException(status_code=503, detail="ERR_ACCOUNT_STORE_UNAVAILABLE") from None
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    async def nsdl_upload(request: Request, *, require_idempotency: bool) -> tuple[bytes, str, str | None]:
        """Read one transient attachment only after the caller has authorized it."""
        values = request.headers.getlist("idempotency-key")
        if require_idempotency and len(values) != 1:
            raise HTTPException(status_code=400, detail="ERR_NSDL_IDEMPOTENCY_INVALID")
        if not require_idempotency and values:
            raise HTTPException(status_code=400, detail="ERR_NSDL_UPLOAD_INVALID")
        if request.headers.getlist("content-type") != [request.headers.get("content-type")] or not (request.headers.get("content-type") or "").lower().startswith("multipart/form-data;"):
            raise HTTPException(status_code=400, detail="ERR_NSDL_UPLOAD_INVALID")
        lengths = request.headers.getlist("content-length")
        if len(lengths) > 1:
            raise HTTPException(status_code=400, detail="ERR_NSDL_UPLOAD_INVALID")
        try:
            if lengths and (not lengths[0].isdigit() or int(lengths[0]) > 12 * 1024 * 1024 + 8192):
                raise ValueError()
            form = await request.form(max_files=1, max_fields=2)
        except Exception:
            raise HTTPException(status_code=400, detail="ERR_NSDL_UPLOAD_INVALID")
        items = list(form.multi_items())
        names = [name for name, _value in items]
        uploads = [value for _name, value in items if hasattr(value, "close")]
        if names.count("file") != 1 or names.count("password") > 1 or set(names) - {"file", "password"}:
            for candidate in uploads:
                await candidate.close()
            raise HTTPException(status_code=400, detail="ERR_NSDL_UPLOAD_INVALID")
        upload = next(value for name, value in items if name == "file")
        try:
            if getattr(upload, "content_type", None) != "application/pdf":
                raise HTTPException(status_code=400, detail="ERR_NSDL_UPLOAD_INVALID")
            password = str(form.get("password", ""))
            if password and (not password.isascii() or not password.isprintable() or not 1 <= len(password) <= 128):
                raise HTTPException(status_code=422, detail="ERR_NSDL_PASSWORD_INVALID")
            raw_pdf = await upload.read(12 * 1024 * 1024 + 1)
        finally:
            for candidate in uploads:
                await candidate.close()
        return raw_pdf, password, values[0] if require_idempotency else None

    @app.post("/api/nsdl/import-preview")
    async def import_preview(request: Request) -> dict[str, Any]:
        identity, _access = await authorize(request, WRITE)  # Deliberately before reading multipart bytes.
        raw_pdf, password, _unused = await nsdl_upload(request, require_idempotency=False)
        started_at = time.monotonic()
        try:
            preview = request.app.state.nsdl_service.preview_pdf(identity, raw_pdf, password)
        except NsdlStoreError as error:
            import_reference = f"im-{uuid.uuid4().hex}"
            response_error = safe_error(error, import_reference=import_reference)
            _import_event(stage="preview", code=error.code, reference=import_reference, status=response_error.status_code, started_at=started_at, category=error.category)
            raise response_error from None
        return {
            "snapshot": preview.snapshot.to_wire(),
            "previewToken": preview.preview_token,
            "sourceAccounts": [
                {"accountScopeId": scope, "displayName": name}
                for scope, name in preview.account_source_names
            ],
        }

    @app.post("/api/nsdl/schwab-preview")
    async def schwab_preview(request: Request) -> JSONResponse:
        _identity, _access = await authorize(request, WRITE)  # Authorize before reading PDF bytes.
        raw_pdf, password, _unused = await nsdl_upload(request, require_idempotency=False)
        if password:
            raise HTTPException(status_code=422, detail="ERR_SCHWAB_PASSWORD_UNSUPPORTED")
        try:
            result = parse_schwab_pdf_bytes(raw_pdf)
        except SchwabSnapshotError:
            raise HTTPException(status_code=422, detail="ERR_SCHWAB_PREVIEW_UNSUPPORTED") from None
        except Exception:
            raise HTTPException(status_code=422, detail="ERR_SCHWAB_PREVIEW_UNSUPPORTED") from None
        account_number = result.account_number
        if (
            result.printed_currency_glyph != "$"
            or result.iso_currency is not None
            or len(result.positions) != 3
            or len(account_number) != 9
            or account_number[4] != "-"
            or not (account_number[:4].isascii() and account_number[:4].isdigit() and account_number[5:].isascii() and account_number[5:].isdigit())
        ):
            raise HTTPException(status_code=422, detail="ERR_SCHWAB_PREVIEW_UNSUPPORTED")
        account_suffix = account_number[-4:]
        return JSONResponse({
            "status": "review_only",
            "source": "Schwab monthly statement",
            "scope": "this_pdf",
            "sourceAccountLabel": f"Schwab account ending •••• {account_suffix}",
            "asOfDate": result.as_of.isoformat(),
            "printedCurrencyGlyph": result.printed_currency_glyph,
            "isoCurrency": None,
            "cashValue": format(result.cash_value, "f"),
            "equityValue": format(result.equity_value, "f"),
            "fundValue": format(result.fund_value, "f"),
            "totalValue": format(result.total_value, "f"),
            "positions": [{
                "section": position.section,
                "symbol": position.symbol,
                "quantity": format(position.quantity, "f"),
                "printedPrice": format(position.printed_price, "f"),
                "marketValue": format(position.market_value, "f"),
            } for position in result.positions],
            "overlapWarning": "Possible overlaps with existing holdings and duplicate prior Schwab imports are not resolved. Keep these positions separate; no merge was performed.",
            "importAvailable": False,
        }, headers={"Cache-Control": "no-store"})

    @app.post("/api/nsdl/import")
    async def import_nsdl(request: Request) -> dict[str, Any]:
        identity, access = await authorize(request, WRITE)  # Deliberately before reading multipart bytes.
        tokens = request.headers.getlist("nsdl-preview-token")
        if len(tokens) != 1:
            raise HTTPException(status_code=400, detail="ERR_NSDL_PREVIEW_INVALID")
        raw_pdf, password, idempotency = await nsdl_upload(request, require_idempotency=True)
        started_at = time.monotonic()
        import_reference = f"im-{uuid.uuid4().hex}"
        try:
            result = request.app.state.nsdl_service.import_pdf(identity, raw_pdf, password, idempotency or "", tokens[0], request.app.state.account_data_store)
        except NsdlStoreError as error:
            response_error = safe_error(error, import_reference=import_reference)
            _import_event(stage=error.stage, code=error.code, reference=import_reference, status=response_error.status_code, started_at=started_at, category=error.category)
            raise response_error from None
        record_activity(access, "statement_import", idempotency or "")
        _import_event(stage="complete", code="OK", reference=import_reference, status=200, started_at=started_at, category="success")
        return {"status": result.status, "receiptId": result.receipt_id, "snapshot": result.snapshot.to_wire()}

    # Static files mount after the fixed API routes; no SPA fallback can capture /api paths.
    if static_root.is_dir() and (static_root / "index.html").is_file():
        @app.get("/", include_in_schema=False)
        async def private_index() -> FileResponse:
            return FileResponse(static_root / "index.html")
        app.mount("/assets", StaticFiles(directory=static_root / "assets"), name="private-assets")

    return app


def configured_private_nsdl_app() -> FastAPI:
    if os.environ.get("MONEYMONEY_RELEASE_MODE") != "private_nsdl":
        raise PrivateNsdlIdentityUnavailable()
    mode = os.environ.get("MONEYMONEY_PRIVATE_NSDL_FAMILY_MODE")
    if mode == "two_person":
        try:
            configuration = load_family_two_person_email_config()
        except FamilyTwoPersonConfigurationError as error:
            raise PrivateNsdlIdentityUnavailable() from error
    elif mode == "legacy_singleton":
        configuration = None
    else:
        raise PrivateNsdlIdentityUnavailable()
    # The dedicated browser entry fetches this non-secret, same-origin value at
    # runtime.  Validate it during private-mode startup so a release cannot
    # silently serve a page that lacks an authoritative portfolio selector.
    _public_runtime_config()
    project_id = os.environ.get("MONEYMONEY_FIREBASE_PROJECT_ID", "")
    validate_service_account_project(os.environ.get("MONEYMONEY_FIREBASE_SERVICE_ACCOUNT_JSON"), project_id)
    try:
        account_key = base64.b64decode(os.environ.get("MONEYMONEY_PRIVATE_NSDL_ACCOUNT_ID_KEY", ""), validate=True)
    except Exception as error:
        raise PrivateNsdlIdentityUnavailable() from error
    if len(account_key) != 32:
        raise PrivateNsdlIdentityUnavailable()
    from .auth_perimeter import FirebaseAdminTokenVerifier
    FirebaseAdminTokenVerifier(project_id)._app()
    identities = load_private_nsdl_identities()
    store = FirestoreNsdlStore(project_id, account_key)
    # The configured release reuses the one named Admin client created above.
    # It never selects a Render filesystem path or falls back to in-memory data.
    account_data_store = FirestoreAccountDataStore(project_id, account_key, client=store.client, firestore_module=store._firestore)
    valuation_service = LocalValuationService(SyntheticDailyPriceSource(()))
    if mode == "two_person":
        if len(identities) != 1:
            raise PrivateNsdlIdentityUnavailable()
        sharan_identity = next(iter(identities.values()))
        try:
            authority = FixedTwoPersonAuthority(configuration, sharan_identity)
        except FamilyTwoPersonConfigurationError as error:
            raise PrivateNsdlIdentityUnavailable() from error
        configured_identities = dict(identities)
        configured_identities.update(authority.empty_scope_identities())
        registry, activity = authority, FirestoreFamilyActivityStore(store.client, store._firestore)
        admission, migration, membership_reader = authority, None, None
    elif mode == "legacy_singleton":
        membership = FirebaseMembershipStore()
        registry, activity = FamilyPortfolioRegistry.singleton(identities), None
        admission, migration = None, None
        configured_identities, membership_reader, authority = identities, membership.read, None
    else:
        raise PrivateNsdlIdentityUnavailable()
    return create_private_nsdl_app(identities=configured_identities, store=store, membership_reader=membership_reader, account_data_store=account_data_store, valuation_service=valuation_service, family_registry=registry, activity_store=activity, family_admission=admission, migration_adapter=migration, allow_pending_family_admission=False, family_email_authority=authority)


# Uvicorn invokes the explicit factory in the isolated private image.  Keeping
# this module import inert prevents provider construction or credential parsing
# merely because an ASGI loader imports it; the factory still fails closed
# before serving if protected startup configuration is invalid.
app = None
