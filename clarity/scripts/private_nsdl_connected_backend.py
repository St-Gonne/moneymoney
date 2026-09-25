"""Synthetic loopback-only private-NSDL app factory for connected local proof."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import uvicorn

from app.account_data_store import LocalAccountDataStore
from app.auth_perimeter import AuthenticationInvalid
from app.models.account_data import AccountFact, CashFlowFact, OpeningHoldingFact, Provenance, manual_provenance
from app.models.nsdl_snapshot import NsdlAccount, NsdlCoverage, NsdlHolding, NsdlSnapshotV1, NsdlTotal
from app.nsdl_store import NsdlStoreError
from app.private_nsdl_app import create_private_nsdl_app
from app.private_nsdl_identity import PrivateNsdlIdentity
from app.valuation_service import LocalValuationService

OWNER = "synthetic_connected_owner"
PORTFOLIO = "synthetic_connected_portfolio"
TOKEN = "synthetic-connected-token"
ZERODHA_ACCOUNT_ID = "synthetic-zerodha"
HDFC_ACCOUNT_ID = "synthetic-hdfc"
OTHER_ACCOUNT_ID = "synthetic-other"
US_ACCOUNT_ID = "synthetic-us-manual"
INCOMPLETE_ACCOUNT_ID = "synthetic-incomplete-manual"
OVERLAP_ACCOUNT_ID = "synthetic-nsdl-account"
ZERODHA_RELIANCE_HOLDING_ID = "synthetic-zerodha-reliance"
ZERODHA_INFOSYS_HOLDING_ID = "synthetic-zerodha-infosys"
ZERODHA_ICICI_BANK_HOLDING_ID = "synthetic-zerodha-icici-bank"
HDFC_BALANCED_ADVANTAGE_HOLDING_ID = "synthetic-hdfc-balanced-advantage"
HDFC_NIFTY_ETF_HOLDING_ID = "synthetic-hdfc-nifty-etf"
HDFC_BHARAT_BOND_HOLDING_ID = "synthetic-hdfc-bharat-bond"
OTHER_LT_FINANCE_HOLDING_ID = "synthetic-other-lt-finance"
OTHER_REC_BOND_HOLDING_ID = "synthetic-other-rec-bond"
OTHER_GOLD_ETF_HOLDING_ID = "synthetic-other-gold-etf"
US_APPLE_HOLDING_ID = "synthetic-us-apple"
INCOMPLETE_HOLDING_ID = "synthetic-incomplete-bond"
OVERLAP_HOLDING_ID = "synthetic-manual-overlap-larsen"
AS_OF_DATE = date(2026, 9, 9)
EQUAL_TIMESTAMP = datetime(2026, 9, 15, 0, 0, 0, tzinfo=timezone.utc)


def fixed_seed_provenance(reference: str) -> Provenance:
    """Create two-record equality cases without changing production provenance."""
    return Provenance("manual", reference, 1, EQUAL_TIMESTAMP)

# These are local fixture observations, never quote-provider records.  The
# date is an explicit observation date: the valuation service does not fill
# gaps, interpolate, or return a value for an unlisted date.
SYNTHETIC_DATED_OBSERVATIONS: dict[date, dict[str, Decimal]] = {
    date(2026, 3, 2): {
        ZERODHA_RELIANCE_HOLDING_ID: Decimal("1250"),
        ZERODHA_INFOSYS_HOLDING_ID: Decimal("1580"),
        ZERODHA_ICICI_BANK_HOLDING_ID: Decimal("1390"),
        HDFC_BALANCED_ADVANTAGE_HOLDING_ID: Decimal("115"),
        HDFC_NIFTY_ETF_HOLDING_ID: Decimal("225"),
        HDFC_BHARAT_BOND_HOLDING_ID: Decimal("101"),
        OTHER_LT_FINANCE_HOLDING_ID: Decimal("145"),
        OTHER_REC_BOND_HOLDING_ID: Decimal("960"),
        OTHER_GOLD_ETF_HOLDING_ID: Decimal("78"),
        US_APPLE_HOLDING_ID: Decimal("180"),
        OVERLAP_HOLDING_ID: Decimal("2400"),
    },
    date(2026, 6, 1): {
        ZERODHA_RELIANCE_HOLDING_ID: Decimal("1320"),
        ZERODHA_INFOSYS_HOLDING_ID: Decimal("1600"),
        ZERODHA_ICICI_BANK_HOLDING_ID: Decimal("1450"),
        HDFC_BALANCED_ADVANTAGE_HOLDING_ID: Decimal("121"),
        HDFC_NIFTY_ETF_HOLDING_ID: Decimal("232"),
        HDFC_BHARAT_BOND_HOLDING_ID: Decimal("102"),
        OTHER_LT_FINANCE_HOLDING_ID: Decimal("155"),
        OTHER_REC_BOND_HOLDING_ID: Decimal("980"),
        OTHER_GOLD_ETF_HOLDING_ID: Decimal("81"),
        US_APPLE_HOLDING_ID: Decimal("190"),
        OVERLAP_HOLDING_ID: Decimal("2450"),
    },
    AS_OF_DATE: {
        ZERODHA_RELIANCE_HOLDING_ID: Decimal("1400"),
        ZERODHA_INFOSYS_HOLDING_ID: Decimal("1700"),
        ZERODHA_ICICI_BANK_HOLDING_ID: Decimal("1600"),
        HDFC_BALANCED_ADVANTAGE_HOLDING_ID: Decimal("130"),
        HDFC_NIFTY_ETF_HOLDING_ID: Decimal("245"),
        HDFC_BHARAT_BOND_HOLDING_ID: Decimal("105"),
        OTHER_LT_FINANCE_HOLDING_ID: Decimal("170"),
        OTHER_REC_BOND_HOLDING_ID: Decimal("1000"),
        OTHER_GOLD_ETF_HOLDING_ID: Decimal("85"),
        US_APPLE_HOLDING_ID: Decimal("200"),
        OVERLAP_HOLDING_ID: Decimal("2500"),
    },
}


@dataclass(frozen=True)
class SyntheticFixturePrice:
    """Loopback-only price shape; never a provider or public-market record."""

    holding_id: str
    owner_scope_id: str
    portfolio_id: str
    price: Decimal
    currency: str
    price_date: date
    source: str
    status: str
    source_revision: str


class SyntheticFixtureAccountDataStore(LocalAccountDataStore):
    """Keep fixture-only provenance out of the production derived-cache schema."""

    def cache_derived(self, *_args: object, **_kwargs: object) -> None:
        # The shared persisted-cache contract correctly admits only AMFI/NSE
        # source rows. This isolated fixture returns its truthful local source
        # to the caller and deliberately does not persist a disguised cache row.
        return None


class SyntheticVerifier:
    """Accept exactly one local demo token through the existing perimeter seam."""

    def verify(self, token: str) -> dict[str, object]:
        if not hmac.compare_digest(token, TOKEN):
            raise AuthenticationInvalid()
        return {
            "uid": OWNER,
            "email": "synthetic.connected@example.test",
            "email_verified": True,
        }


class StaticPresentationStore:
    """Synthetic imported-statement evidence, separate from durable manual facts."""

    secret = b"connected-local-demo-synthetic-store"

    def __init__(self) -> None:
        self._snapshot = NsdlSnapshotV1(
            portfolio_id=PORTFOLIO,
            as_of_date=AS_OF_DATE,
            coverage=NsdlCoverage(
                complete=True,
                sections=("synthetic_nsdl_statement",),
                unsupported_sections=(),
                missing_values=0,
                warnings=("Synthetic imported-statement evidence; no actual PDF was used in this local demo.",),
            ),
            accounts=(
                NsdlAccount("synthetic-nsdl-account", "DEMAT", "Synthetic NSDL account"),
            ),
            holdings=(
                NsdlHolding("synthetic-nsdl-larsen", "synthetic-nsdl-account", "INE018A01030", "Larsen & Toubro", "Equity", "100", "INR", "2500", "250000"),
                NsdlHolding("synthetic-nsdl-sbi", "synthetic-nsdl-account", "INE062A01020", "SBI", "Equity", "300", "INR", "500", "150000"),
            ),
            totals_by_currency=(NsdlTotal("INR", "400000"),),
            parser_version="synthetic-imported-statement-v1",
            revision_id="synthetic-imported-statement-context",
            imported_at="2026-09-09T00:00:00+00:00",
        )

    def read_current(self, _uid: str, _portfolio_id: str) -> NsdlSnapshotV1:
        return self._snapshot

    def commit(self, *_args: object) -> object:
        raise NsdlStoreError("ERR_NSDL_STORE_UNAVAILABLE")


class EmptyQuoteService:
    """Prevent the normal quote seam from reading environment/provider state."""

    def quotes(self, _identity: object, _snapshot: object) -> list[dict[str, str]]:
        return []


class PersistedFactPriceSource:
    """Expose only the fixture's explicit synthetic dated observations."""

    def __init__(self, store: LocalAccountDataStore) -> None:
        self._store = store

    def observation_dates(self, owner: str, portfolio: str, holding_ids: set[str] | None = None, currency: str | None = None) -> tuple[date, ...]:
        """Return only the fixture's explicitly persisted synthetic dates."""
        if (owner, portfolio) != (OWNER, PORTFOLIO):
            return ()
        if holding_ids is None and currency is None:
            return tuple(sorted(SYNTHETIC_DATED_OBSERVATIONS))
        facts = self._store.list_scope(owner, portfolio)
        scoped_ids = holding_ids if holding_ids is not None else {holding.fact_id for holding in facts["opening_holdings"] if not getattr(holding, "voided", False) and (currency is None or holding.currency == currency)}
        return tuple(sorted(observed_at for observed_at, prices in SYNTHETIC_DATED_OBSERVATIONS.items() if any(holding_id in prices for holding_id in scoped_ids)))

    def records(self, owner: str, portfolio: str, as_of: date) -> tuple[SyntheticFixturePrice, ...]:
        if (owner, portfolio) != (OWNER, PORTFOLIO):
            return ()
        facts = self._store.list_scope(owner, portfolio)
        observations = SYNTHETIC_DATED_OBSERVATIONS.get(as_of, {})
        return tuple(
            SyntheticFixturePrice(
                holding_id=holding.fact_id,
                owner_scope_id=owner,
                portfolio_id=portfolio,
                price=observations[holding.fact_id],
                currency=holding.currency,
                price_date=as_of,
                source="SYNTHETIC_FIXTURE",
                status="SYNTHETIC_DATED_OBSERVATION",
                source_revision="synthetic-dated-observation-r1",
            )
            for holding in facts["opening_holdings"]
            if holding.as_of <= as_of and holding.fact_id in observations
        )


def _configure_synthetic_perimeter() -> None:
    """Supply only the existing perimeter's non-secret synthetic fixture inputs."""
    os.environ["MONEYMONEY_PRIVATE_PREVIEW_UIDS"] = OWNER
    os.environ["MONEYMONEY_PORTFOLIO_GRANTS_JSON"] = json.dumps({OWNER: [PORTFOLIO]}, separators=(",", ":"))


def _seed_key(kind: str, identifier: str) -> str:
    return f"synthetic-v2-{kind}-{identifier}"


def _seed_digest(kind: str, identifier: str) -> str:
    return hashlib.sha256(_seed_key(kind, identifier).encode("ascii")).hexdigest()


def _seed_demo_facts(store: LocalAccountDataStore) -> None:
    """Write this composition's complete synthetic facts only into an empty demo store."""
    existing = store.list_scope(OWNER, PORTFOLIO)
    if any(existing.values()):
        return

    accounts = (
        AccountFact(ZERODHA_ACCOUNT_ID, OWNER, "Zerodha", "demat", "INR", "Synthetic complete-history account", "Illustrative Zerodha", "Synthetic DP", "Synthetic Zerodha", "•••• 1001", fixed_seed_provenance(_seed_key("account", ZERODHA_ACCOUNT_ID)), PORTFOLIO, True),
        AccountFact(HDFC_ACCOUNT_ID, OWNER, "HDFC Securities", "demat", "INR", "Synthetic complete-history account", "Illustrative HDFC Securities", "Synthetic DP", "Synthetic HDFC Securities", "•••• 2002", fixed_seed_provenance(_seed_key("account", HDFC_ACCOUNT_ID)), PORTFOLIO, True),
        AccountFact(OTHER_ACCOUNT_ID, OWNER, "Other", "demat", "INR", "Synthetic complete-history account", "Illustrative Other", "Synthetic DP", "Synthetic Other", "•••• 3003", manual_provenance(_seed_key("account", OTHER_ACCOUNT_ID)), PORTFOLIO, True),
        AccountFact(US_ACCOUNT_ID, OWNER, "Charles Schwab", "other", "USD", "Synthetic complete-history account", "Illustrative Charles Schwab", None, "Charles Schwab", "•••• 4004", manual_provenance(_seed_key("account", US_ACCOUNT_ID)), PORTFOLIO, True),
        AccountFact(INCOMPLETE_ACCOUNT_ID, OWNER, "Manual INR account", "other", "INR", "Synthetic incomplete-history account", "Illustrative incomplete history", None, "Synthetic manual broker", "•••• 5005", manual_provenance(_seed_key("account", INCOMPLETE_ACCOUNT_ID)), PORTFOLIO, False),
        AccountFact(OVERLAP_ACCOUNT_ID, OWNER, "Manual correction review", "demat", "INR", "Synthetic manual/source overlap review", "Synthetic NSDL account", "Synthetic DP", "Synthetic manual broker", "•••• 6006", manual_provenance(_seed_key("account", OVERLAP_ACCOUNT_ID)), PORTFOLIO, False),
    )
    for account in accounts:
        store.commit_account(account, route="/synthetic-v2-seed/accounts", idempotency_key=_seed_key("account", account.account_id), request_digest=_seed_digest("account", account.account_id), expected_revision=None)

    holdings = (
        OpeningHoldingFact(ZERODHA_RELIANCE_HOLDING_ID, ZERODHA_ACCOUNT_ID, OWNER, "Reliance Industries", "INE002A01018", Decimal("150"), date(2025, 9, 12), "INR", Decimal("180000"), manual_provenance(_seed_key("holding", ZERODHA_RELIANCE_HOLDING_ID)), PORTFOLIO),
        OpeningHoldingFact(ZERODHA_INFOSYS_HOLDING_ID, ZERODHA_ACCOUNT_ID, OWNER, "Infosys", "INE009A01021", Decimal("80"), date(2025, 9, 12), "INR", Decimal("116000"), manual_provenance(_seed_key("holding", ZERODHA_INFOSYS_HOLDING_ID)), PORTFOLIO),
        OpeningHoldingFact(ZERODHA_ICICI_BANK_HOLDING_ID, ZERODHA_ACCOUNT_ID, OWNER, "ICICI Bank", "INE090A01021", Decimal("350"), date(2025, 9, 12), "INR", Decimal("420000"), manual_provenance(_seed_key("holding", ZERODHA_ICICI_BANK_HOLDING_ID)), PORTFOLIO),
        OpeningHoldingFact(HDFC_BALANCED_ADVANTAGE_HOLDING_ID, HDFC_ACCOUNT_ID, OWNER, "HDFC Balanced Advantage Fund", "INF179KB1XQ7", Decimal("3000"), date(2025, 11, 18), "INR", Decimal("330000"), manual_provenance(_seed_key("holding", HDFC_BALANCED_ADVANTAGE_HOLDING_ID)), PORTFOLIO),
        OpeningHoldingFact(HDFC_NIFTY_ETF_HOLDING_ID, HDFC_ACCOUNT_ID, OWNER, "SBI ETF Nifty 50", "INF200KA1S14", Decimal("450"), date(2025, 11, 18), "INR", Decimal("80000"), manual_provenance(_seed_key("holding", HDFC_NIFTY_ETF_HOLDING_ID)), PORTFOLIO),
        OpeningHoldingFact(HDFC_BHARAT_BOND_HOLDING_ID, HDFC_ACCOUNT_ID, OWNER, "Bharat Bond ETF", "INF754K01KT0", Decimal("500"), date(2025, 11, 18), "INR", Decimal("40000"), manual_provenance(_seed_key("holding", HDFC_BHARAT_BOND_HOLDING_ID)), PORTFOLIO),
        OpeningHoldingFact(OTHER_LT_FINANCE_HOLDING_ID, OTHER_ACCOUNT_ID, OWNER, "L&T Finance", "INE498L01015", Decimal("100"), date(2026, 1, 15), "INR", Decimal("16000"), manual_provenance(_seed_key("holding", OTHER_LT_FINANCE_HOLDING_ID)), PORTFOLIO),
        OpeningHoldingFact(OTHER_REC_BOND_HOLDING_ID, OTHER_ACCOUNT_ID, OWNER, "REC bond", "INE020B07GS3", Decimal("120"), date(2026, 1, 15), "INR", Decimal("120000"), manual_provenance(_seed_key("holding", OTHER_REC_BOND_HOLDING_ID)), PORTFOLIO),
        OpeningHoldingFact(OTHER_GOLD_ETF_HOLDING_ID, OTHER_ACCOUNT_ID, OWNER, "Gold ETF", "INF204KB14I2", Decimal("400"), date(2026, 1, 15), "INR", Decimal("34000"), manual_provenance(_seed_key("holding", OTHER_GOLD_ETF_HOLDING_ID)), PORTFOLIO),
        OpeningHoldingFact(US_APPLE_HOLDING_ID, US_ACCOUNT_ID, OWNER, "Apple Inc.", "US0378331005", Decimal("10"), date(2025, 10, 1), "USD", Decimal("1600"), manual_provenance(_seed_key("holding", US_APPLE_HOLDING_ID)), PORTFOLIO),
        OpeningHoldingFact(INCOMPLETE_HOLDING_ID, INCOMPLETE_ACCOUNT_ID, OWNER, "Illustrative INR bond", "INE000A01001", Decimal("100"), date(2026, 9, 9), "INR", Decimal("10000"), manual_provenance(_seed_key("holding", INCOMPLETE_HOLDING_ID)), PORTFOLIO),
        OpeningHoldingFact(OVERLAP_HOLDING_ID, OVERLAP_ACCOUNT_ID, OWNER, "Larsen & Toubro", "INE018A01030", Decimal("100"), date(2026, 9, 9), "INR", Decimal("250000"), manual_provenance(_seed_key("holding", OVERLAP_HOLDING_ID)), PORTFOLIO),
    )
    for holding in holdings:
        store.commit_opening_holding(holding, route="/synthetic-v2-seed/opening-holdings", idempotency_key=_seed_key("holding", holding.fact_id), request_digest=_seed_digest("holding", holding.fact_id))

    flows = (
        CashFlowFact("synthetic-zerodha-initial-contribution", ZERODHA_ACCOUNT_ID, OWNER, date(2025, 9, 12), Decimal("-700000"), "INR", "contribution", "Synthetic external contribution", manual_provenance(_seed_key("flow", "synthetic-zerodha-initial-contribution")), PORTFOLIO),
        CashFlowFact("synthetic-zerodha-top-up", ZERODHA_ACCOUNT_ID, OWNER, date(2026, 3, 2), Decimal("-90000"), "INR", "contribution", "Synthetic external contribution", manual_provenance(_seed_key("flow", "synthetic-zerodha-top-up")), PORTFOLIO),
        CashFlowFact("synthetic-zerodha-withdrawal", ZERODHA_ACCOUNT_ID, OWNER, date(2026, 6, 1), Decimal("30000"), "INR", "withdrawal", "Synthetic external withdrawal", manual_provenance(_seed_key("flow", "synthetic-zerodha-withdrawal")), PORTFOLIO),
        CashFlowFact("synthetic-hdfc-initial-contribution", HDFC_ACCOUNT_ID, OWNER, date(2025, 11, 18), Decimal("-430000"), "INR", "contribution", "Synthetic external contribution", manual_provenance(_seed_key("flow", "synthetic-hdfc-initial-contribution")), PORTFOLIO),
        CashFlowFact("synthetic-hdfc-top-up", HDFC_ACCOUNT_ID, OWNER, date(2026, 6, 1), Decimal("-70000"), "INR", "contribution", "Synthetic external contribution", manual_provenance(_seed_key("flow", "synthetic-hdfc-top-up")), PORTFOLIO),
        CashFlowFact("synthetic-hdfc-withdrawal", HDFC_ACCOUNT_ID, OWNER, date(2026, 8, 15), Decimal("10000"), "INR", "withdrawal", "Synthetic external withdrawal", manual_provenance(_seed_key("flow", "synthetic-hdfc-withdrawal")), PORTFOLIO),
        CashFlowFact("synthetic-other-initial-contribution", OTHER_ACCOUNT_ID, OWNER, date(2026, 1, 15), Decimal("-120000"), "INR", "contribution", "Synthetic external contribution", manual_provenance(_seed_key("flow", "synthetic-other-initial-contribution")), PORTFOLIO),
        CashFlowFact("synthetic-other-top-up", OTHER_ACCOUNT_ID, OWNER, date(2026, 7, 15), Decimal("-35000"), "INR", "contribution", "Synthetic external contribution", manual_provenance(_seed_key("flow", "synthetic-other-top-up")), PORTFOLIO),
        CashFlowFact("synthetic-other-withdrawal", OTHER_ACCOUNT_ID, OWNER, date(2026, 8, 20), Decimal("5000"), "INR", "withdrawal", "Synthetic external withdrawal", manual_provenance(_seed_key("flow", "synthetic-other-withdrawal")), PORTFOLIO),
        CashFlowFact("synthetic-us-initial-contribution", US_ACCOUNT_ID, OWNER, date(2025, 10, 1), Decimal("-1600"), "USD", "contribution", "Synthetic external contribution", manual_provenance(_seed_key("flow", "synthetic-us-initial-contribution")), PORTFOLIO),
    )
    for flow in flows:
        store.commit_cash_flow(flow, route="/synthetic-v2-seed/cash-flows", idempotency_key=_seed_key("flow", flow.fact_id), request_digest=_seed_digest("flow", flow.fact_id))


def create_connected_demo_app(data_path: str | Path):
    """Build a fresh actual private app over a caller-owned local data file."""
    _configure_synthetic_perimeter()
    store = SyntheticFixtureAccountDataStore(data_path)
    _seed_demo_facts(store)
    identity = PrivateNsdlIdentity(OWNER, "synthetic_connected_family", PORTFOLIO, "ABCDE1234F")
    app = create_private_nsdl_app(
        identities={(OWNER, PORTFOLIO): identity},
        store=StaticPresentationStore(),
        membership_reader=lambda uid: {
            "uid": uid,
            "familyId": "synthetic_connected_family",
            "role": "ADMIN",
            "active": True,
        },
        quote_service=EmptyQuoteService(),
        account_data_store=store,
        valuation_service=LocalValuationService(PersistedFactPriceSource(store)),
    )
    app.state.auth_verifier = SyntheticVerifier()
    return app


def _private_data_path(raw: str) -> Path:
    candidate = Path(raw)
    if not candidate.is_absolute() or not candidate.is_dir():
        raise ValueError("data directory must already be an absolute directory")
    resolved = candidate.resolve(strict=True)
    if resolved.stat().st_mode & 0o077:
        raise ValueError("data directory must not be group/world accessible")
    return resolved / "connected-account-data.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="synthetic loopback-only private NSDL backend")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--port", type=int, default=8788)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        raise SystemExit("invalid loopback port")
    app = create_connected_demo_app(_private_data_path(args.data_dir))
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
