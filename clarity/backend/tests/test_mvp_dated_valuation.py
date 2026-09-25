import os
import json
import unittest
from types import SimpleNamespace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("MONEYMONEY_PRIVATE_PREVIEW_UIDS", "synthetic_uid")
os.environ.setdefault("MONEYMONEY_PORTFOLIO_GRANTS_JSON", '{"synthetic_uid":["synthetic_portfolio"]}')

from fastapi.testclient import TestClient

from app.account_data_store import LocalAccountDataStore, STORE_UNAVAILABLE
from app.models.account_data import AccountDataError, AccountFact, CashFlowFact, OpeningHoldingFact, manual_provenance
from app.models.valuation import SyntheticDailyPrice, ValuationError
from app.private_nsdl_app import create_private_nsdl_app
from app.private_nsdl_identity import PrivateNsdlIdentity
from app.nsdl_store import PersistentFakeNsdlStore
from app.valuation_service import LocalValuationService, SyntheticDailyPriceSource


OWNER, PORTFOLIO = "synthetic_uid", "synthetic_portfolio"


def seeded(path: Path, *, price="12.50", revision="price-r1", flow_amount="-100", flow_date=date(2026, 1, 1), valuation_date=date(2026, 9, 9)):
    store = LocalAccountDataStore(path)
    account = AccountFact("acct", OWNER, "Synthetic", "demat", "INR", "Synthetic", None, None, None, None, manual_provenance("account"), PORTFOLIO, True)
    holding = OpeningHoldingFact("holding", "acct", OWNER, "Synthetic fund", "INF000A", Decimal("2"), date(2026, 1, 1), "INR", Decimal("100"), manual_provenance("holding"), PORTFOLIO)
    flow = CashFlowFact("flow", "acct", OWNER, flow_date, Decimal(flow_amount), "INR", "contribution", None, manual_provenance("flow"), PORTFOLIO)
    store.commit_account(account, route="/accounts", idempotency_key="account", request_digest="a", expected_revision=None)
    store.commit_opening_holding(holding, route="/holdings", idempotency_key="holding", request_digest="h")
    store.commit_cash_flow(flow, route="/flows", idempotency_key="flow", request_digest="f")
    source = SyntheticDailyPriceSource((SyntheticDailyPrice("holding", OWNER, PORTFOLIO, Decimal(price), "INR", valuation_date, "AMFI", "DAILY_NAV", revision),))
    return store, LocalValuationService(source)


class CountingSource(SyntheticDailyPriceSource):
    def __init__(self, records):
        super().__init__(records)
        self.calls = 0

    def records(self, owner, portfolio, as_of):
        self.calls += 1
        return super().records(owner, portfolio, as_of)


class CountingStore:
    def __init__(self, store):
        self.store, self.list_calls, self.cache_reads, self.cache_writes = store, 0, 0, 0

    def list_scope(self, *args):
        self.list_calls += 1
        return self.store.list_scope(*args)

    def cached_derived(self, *args):
        self.cache_reads += 1
        return self.store.cached_derived(*args)

    def cache_derived(self, *args):
        self.cache_writes += 1
        return self.store.cache_derived(*args)


class CountingNsdlStore(PersistentFakeNsdlStore):
    def __init__(self, snapshot):
        super().__init__()
        self.snapshot, self.reads = snapshot, 0

    def read_current(self, uid, portfolio_id):
        self.reads += 1
        return self.snapshot


class Verifier:
    def verify(self, _token):
        return {"uid": OWNER, "email": "synthetic@example.test", "email_verified": True}


class DatedValuationTests(unittest.TestCase):
    def test_local_valuation_performance_restart_and_price_revision_invalidate_cache(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "accounts.json"
            store, service = seeded(path)
            valuation = service.valuation(store, OWNER, PORTFOLIO, date(2026, 9, 9))
            self.assertEqual(valuation["holdings"], [{"holdingId": "holding", "accountScopeId": "acct", "holdingSource": "MANUAL", "reconciliationStatus": "CLEAR", "status": "CALCULATED", "quantity": "2", "price": "12.50", "currency": "INR", "priceDate": "2026-09-09", "source": "AMFI", "priceStatus": "DAILY_NAV", "currentValue": "25.00"}])
            self.assertEqual(valuation["summaryByCurrency"], [{"currency": "INR", "calculatedValue": "25.00", "statementValue": "0", "totalIncludedValue": "25.00", "calculatedAsOf": "2026-09-09", "statementAsOf": None, "excludedForReconciliationCount": 0}])
            performance = service.performance(store, OWNER, PORTFOLIO, date(2026, 9, 9))
            self.assertEqual((performance["gain"]["status"], performance["gain"]["value"], performance["xirr"]["status"]), ("CALCULATED", "-75.00", "CALCULATED"))
            restarted = LocalAccountDataStore(path)
            same = service.valuation(restarted, OWNER, PORTFOLIO, date(2026, 9, 9))
            self.assertEqual(same, valuation)
            changed = seeded(Path(directory) / "other.json", price="15.00", revision="price-r2")[1].valuation(restarted, OWNER, PORTFOLIO, date(2026, 9, 9))
            self.assertEqual((changed["holdings"][0]["currentValue"], changed["inputDigest"] == valuation["inputDigest"]), ("30.00", False))

    def test_as_of_bounds_and_each_persisted_input_revision_invalidate_only_eligible_cache(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "accounts.json"
            store, service = seeded(path)
            as_of = date(2026, 9, 9)
            baseline = service.performance(store, OWNER, PORTFOLIO, as_of)
            account = store._store.get_account(OWNER, "acct", PORTFOLIO)
            store.commit_account(AccountFact(account.account_id, account.owner_scope_id, account.institution, account.account_type, account.currency, account.source_name, "Revised", account.custodian_or_dp, account.execution_broker, account.masked_identifier, manual_provenance("account-r2"), PORTFOLIO, True), route="/accounts", idempotency_key="account-r2", request_digest="r2", expected_revision=1)
            account_changed = service.performance(store, OWNER, PORTFOLIO, as_of)
            self.assertNotEqual(account_changed["inputDigest"], baseline["inputDigest"])
            store.commit_cash_flow(CashFlowFact("flow-2", "acct", OWNER, date(2026, 2, 1), Decimal("-1"), "INR", "contribution", None, manual_provenance("flow-2"), PORTFOLIO), route="/flows", idempotency_key="flow-2", request_digest="flow-2")
            cash_changed = service.performance(store, OWNER, PORTFOLIO, as_of)
            self.assertNotEqual(cash_changed["inputDigest"], account_changed["inputDigest"])
            store.commit_opening_holding(OpeningHoldingFact("holding-2", "acct", OWNER, "Second fund", "INF000B", Decimal("1"), date(2026, 2, 1), "INR", None, manual_provenance("holding-2"), PORTFOLIO), route="/holdings", idempotency_key="holding-2", request_digest="holding-2")
            holding_source = LocalValuationService(SyntheticDailyPriceSource((
                SyntheticDailyPrice("holding", OWNER, PORTFOLIO, Decimal("12.50"), "INR", as_of, "AMFI", "DAILY_NAV", "price-r1"),
                SyntheticDailyPrice("holding-2", OWNER, PORTFOLIO, Decimal("1"), "INR", as_of, "NSE", "EOD_CLOSE", "price-r1"),
            )))
            holding_changed = holding_source.performance(store, OWNER, PORTFOLIO, as_of)
            self.assertNotEqual(holding_changed["inputDigest"], cash_changed["inputDigest"])
            snapshot_one = type("Snapshot", (), {"revision_id": "snapshot-r1", "as_of_date": as_of, "holdings": (object(),)})()
            snapshot_two = type("Snapshot", (), {"revision_id": "snapshot-r2", "as_of_date": as_of, "holdings": (object(),)})()
            first_snapshot = holding_source.performance(store, OWNER, PORTFOLIO, as_of, snapshot_one)
            second_snapshot = holding_source.performance(store, OWNER, PORTFOLIO, as_of, snapshot_two)
            self.assertNotEqual(first_snapshot["inputDigest"], second_snapshot["inputDigest"])
            store.commit_opening_holding(OpeningHoldingFact("future-holding", "acct", OWNER, "Future fund", "INF000C", Decimal("1"), date(2026, 9, 10), "INR", None, manual_provenance("future-holding"), PORTFOLIO), route="/holdings", idempotency_key="future-holding", request_digest="future-holding")
            store.commit_cash_flow(CashFlowFact("future-flow", "acct", OWNER, date(2026, 9, 10), Decimal("-10"), "INR", "contribution", None, manual_provenance("future-flow"), PORTFOLIO), route="/flows", idempotency_key="future-flow", request_digest="future-flow")
            before_future = holding_source.performance(store, OWNER, PORTFOLIO, as_of)
            later_snapshot = type("Snapshot", (), {"revision_id": "snapshot-later", "as_of_date": date(2026, 9, 10), "holdings": (object(),)})()
            after_future = holding_source.performance(store, OWNER, PORTFOLIO, as_of, later_snapshot)
            self.assertEqual((after_future["inputDigest"], after_future["gain"], after_future["xirr"]), (before_future["inputDigest"], before_future["gain"], before_future["xirr"]))

    def test_snapshot_and_manual_rows_are_a_union_with_only_stable_id_reconciliation(self):
        with TemporaryDirectory() as directory:
            store, _service = seeded(Path(directory) / "accounts.json")
            as_of = date(2026, 9, 9)
            store.commit_opening_holding(OpeningHoldingFact("manual-extra", "acct", OWNER, "Manual US listing", "US0000000001", Decimal("3"), date(2026, 1, 1), "USD", None, manual_provenance("manual-extra"), PORTFOLIO), route="/holdings", idempotency_key="manual-extra", request_digest="manual-extra")
            service = LocalValuationService(SyntheticDailyPriceSource((
                SyntheticDailyPrice("holding", OWNER, PORTFOLIO, Decimal("12.50"), "INR", as_of, "AMFI", "DAILY_NAV", "price-r1"),
                SyntheticDailyPrice("manual-extra", OWNER, PORTFOLIO, Decimal("20"), "USD", as_of, "NSE", "EOD_CLOSE", "price-r1"),
            )))
            snapshot = SimpleNamespace(
                revision_id="snapshot-r1", as_of_date=as_of,
                holdings=(SimpleNamespace(holding_id="holding", account_scope_id="statement-acct", quantity="2", currency="INR", statement_price="10", statement_value="20"),),
            )
            valuation = service.valuation(store, OWNER, PORTFOLIO, as_of, snapshot)
            self.assertEqual([(row["holdingId"], row["holdingSource"], row["status"]) for row in valuation["holdings"]], [("manual-extra", "MANUAL", "CALCULATED"), ("holding", "STATEMENT", "STATEMENT_VALUE")])
            self.assertEqual(valuation["summaryByCurrency"], [
                {"currency": "INR", "calculatedValue": "0", "statementValue": "20", "totalIncludedValue": "20", "calculatedAsOf": None, "statementAsOf": "2026-09-09", "excludedForReconciliationCount": 0},
                {"currency": "USD", "calculatedValue": "60", "statementValue": "0", "totalIncludedValue": "60", "calculatedAsOf": "2026-09-09", "statementAsOf": None, "excludedForReconciliationCount": 0},
            ])

    def test_same_account_isin_overlap_is_visible_but_excluded_pending_reconciliation(self):
        with TemporaryDirectory() as directory:
            store, _service = seeded(Path(directory) / "accounts.json")
            as_of = date(2026, 9, 9)
            service = LocalValuationService(SyntheticDailyPriceSource((SyntheticDailyPrice("holding", OWNER, PORTFOLIO, Decimal("12.50"), "INR", as_of, "AMFI", "DAILY_NAV", "price-r1"),)))
            snapshot = SimpleNamespace(revision_id="snapshot-r1", as_of_date=as_of, holdings=(SimpleNamespace(holding_id="statement-copy", account_scope_id="acct", isin="INF000A", quantity="2", currency="INR", statement_price="10", statement_value="20"),))
            valuation = service.valuation(store, OWNER, PORTFOLIO, as_of, snapshot)
            manual = next(row for row in valuation["holdings"] if row["holdingId"] == "holding")
            self.assertEqual((manual["reconciliationStatus"], valuation["summaryByCurrency"][0]["calculatedValue"], valuation["summaryByCurrency"][0]["excludedForReconciliationCount"]), ("REVIEW_REQUIRED", "0", 1))
            performance = service.performance(store, OWNER, PORTFOLIO, as_of, snapshot)
            self.assertEqual((performance["gain"], performance["xirr"], performance["coverage"]["reasons"]), ({"status": "INSUFFICIENT_DATA", "reason": "RECONCILIATION_REQUIRED"}, {"status": "UNAVAILABLE", "reason": "RECONCILIATION_REQUIRED"}, ["RECONCILIATION_REQUIRED"]))
            account_performance = service.performance(store, OWNER, PORTFOLIO, as_of, snapshot, account_id="acct")
            self.assertEqual((account_performance["gain"], account_performance["xirr"], account_performance["coverage"]["reasons"]), ({"status": "INSUFFICIENT_DATA", "reason": "RECONCILIATION_REQUIRED"}, {"status": "UNAVAILABLE", "reason": "RECONCILIATION_REQUIRED"}, ["RECONCILIATION_REQUIRED"]))

    def test_insufficient_history_and_atomic_cache_failure_are_fixed(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "accounts.json"
            store, service = seeded(path)
            account = store._store.get_account(OWNER, "acct", PORTFOLIO)
            store.commit_account(AccountFact(account.account_id, account.owner_scope_id, account.institution, account.account_type, account.currency, account.source_name, account.user_alias, account.custodian_or_dp, account.execution_broker, account.masked_identifier, manual_provenance("account-r2"), PORTFOLIO, False), route="/accounts", idempotency_key="account-r2", request_digest="r2", expected_revision=1)
            result = service.performance(store, OWNER, PORTFOLIO, date(2026, 9, 9))
            self.assertEqual((result["gain"]["status"], result["xirr"]["reason"]), ("INSUFFICIENT_DATA", "MISSING_HISTORY"))
            with patch("app.account_data_store.os.replace", side_effect=OSError("synthetic")):
                with self.assertRaisesRegex(AccountDataError, STORE_UNAVAILABLE):
                    store.cache_derived(OWNER, PORTFOLIO, "valuation", "2026-09-09", "d" * 64, {"calculationVersion": "mvp-dated-valuation-v1", "inputDigest": "d" * 64, "asOf": "2026-09-09", "holdings": [], "summaryByCurrency": []})

    def test_malformed_semantic_cache_and_unavailable_results_fail_closed(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "accounts.json"
            store, service = seeded(path)
            service.valuation(store, OWNER, PORTFOLIO, date(2026, 9, 9))
            document = json.loads(path.read_text(encoding="utf-8"))
            document["derivedCache"][0]["result"] = json.dumps({"calculationVersion": "mvp-dated-valuation-v0", "inputDigest": document["derivedCache"][0]["inputDigest"], "asOf": "2026-09-09", "holdings": []})
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(AccountDataError, STORE_UNAVAILABLE):
                LocalAccountDataStore(path)
            store, _service = seeded(Path(directory) / "values.json", price="0")
            nonpositive = _service.performance(store, OWNER, PORTFOLIO, date(2026, 9, 9))
            self.assertEqual((nonpositive["gain"], nonpositive["xirr"]), ({"status": "INSUFFICIENT_DATA", "reason": "NON_POSITIVE_TERMINAL_VALUE"}, {"status": "UNAVAILABLE", "reason": "NON_POSITIVE_TERMINAL_VALUE"}))
            store, _service = seeded(Path(directory) / "solver.json", price="5000")
            solver = _service.performance(store, OWNER, PORTFOLIO, date(2026, 9, 9))
            self.assertEqual((solver["gain"], solver["xirr"]), ({"status": "INSUFFICIENT_DATA", "reason": "SOLVER_FAILURE"}, {"status": "UNAVAILABLE", "reason": "SOLVER_FAILURE"}))

    def test_semantically_corrupt_matching_cache_is_recomputed_canonically(self):
        with TemporaryDirectory() as directory:
            store, service = seeded(Path(directory) / "accounts.json")
            as_of = date(2026, 9, 9)
            canonical = service.valuation(store, OWNER, PORTFOLIO, as_of)
            canonical_performance = service.performance(store, OWNER, PORTFOLIO, as_of)
            cache_key = (OWNER, PORTFOLIO, "valuation", as_of.isoformat())
            digest, encoded = store._store._derived_cache[cache_key]
            corrupted = json.loads(encoded)
            corrupted["holdings"][0]["priceDate"] = "2026-09-08"
            corrupted["holdings"][0]["currentValue"] = "999.00"
            store._store._derived_cache[cache_key] = (digest, json.dumps(corrupted))
            with self.assertRaisesRegex(AccountDataError, STORE_UNAVAILABLE):
                store.cached_derived(OWNER, PORTFOLIO, "valuation", as_of.isoformat(), digest)
            self.assertEqual(service.valuation(store, OWNER, PORTFOLIO, as_of), canonical)
            performance_key = (OWNER, PORTFOLIO, "performance", as_of.isoformat())
            performance_digest, performance_encoded = store._store._derived_cache[performance_key]
            corrupted_performance = json.loads(performance_encoded)
            corrupted_performance["gain"]["value"] = "-999.00"
            corrupted_performance["xirr"]["valuePct"] = "999.00"
            store._store._derived_cache[performance_key] = (performance_digest, json.dumps(corrupted_performance))
            self.assertEqual(store.cached_derived(OWNER, PORTFOLIO, "performance", as_of.isoformat(), performance_digest), corrupted_performance)
            self.assertEqual(service.performance(store, OWNER, PORTFOLIO, as_of), canonical_performance)

    def test_selected_account_ignores_unrelated_price_currency_and_orders_recomputed_rows(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "accounts.json"
            store, _service = seeded(path)
            as_of = date(2026, 9, 9)
            unrelated = AccountFact("other", OWNER, "Other", "demat", "USD", "Synthetic", None, None, None, None, manual_provenance("other-account"), PORTFOLIO, True)
            store.commit_account(unrelated, route="/accounts", idempotency_key="other-account", request_digest="other-account", expected_revision=None)
            store.commit_opening_holding(OpeningHoldingFact("a-holding", "acct", OWNER, "Earlier sort key", "INF000B", Decimal("3"), date(2026, 1, 2), "INR", None, manual_provenance("a-holding"), PORTFOLIO), route="/holdings", idempotency_key="a-holding", request_digest="a-holding")
            store.commit_opening_holding(OpeningHoldingFact("other-holding", "other", OWNER, "Other currency", "INF000C", Decimal("1"), date(2026, 1, 1), "USD", None, manual_provenance("other-holding"), PORTFOLIO), route="/holdings", idempotency_key="other-holding", request_digest="other-holding")
            records = (
                SyntheticDailyPrice("holding", OWNER, PORTFOLIO, Decimal("12.50"), "INR", as_of, "AMFI", "DAILY_NAV", "price-r1"),
                SyntheticDailyPrice("a-holding", OWNER, PORTFOLIO, Decimal("2"), "INR", as_of, "NSE", "EOD_CLOSE", "price-r1"),
                SyntheticDailyPrice("other-holding", OWNER, PORTFOLIO, Decimal("7"), "USD", as_of, "NSE", "EOD_CLOSE", "price-r1"),
            )
            service = LocalValuationService(SyntheticDailyPriceSource(records))
            valuation = service.valuation(store, OWNER, PORTFOLIO, as_of, account_id="acct")
            performance = service.performance(store, OWNER, PORTFOLIO, as_of, account_id="acct")
            self.assertEqual([row["holdingId"] for row in valuation["holdings"]], ["a-holding", "holding"])
            self.assertEqual((performance["gain"]["status"], performance["xirr"]["status"]), ("CALCULATED", "CALCULATED"))
            restarted = LocalAccountDataStore(path)
            self.assertEqual(service.valuation(restarted, OWNER, PORTFOLIO, as_of, account_id="acct"), valuation)
            recomputed = LocalValuationService(SyntheticDailyPriceSource((
                SyntheticDailyPrice("holding", OWNER, PORTFOLIO, Decimal("15"), "INR", as_of, "AMFI", "DAILY_NAV", "price-r2"),
                SyntheticDailyPrice("a-holding", OWNER, PORTFOLIO, Decimal("2"), "INR", as_of, "NSE", "EOD_CLOSE", "price-r1"),
                SyntheticDailyPrice("other-holding", OWNER, PORTFOLIO, Decimal("7"), "USD", as_of, "NSE", "EOD_CLOSE", "price-r1"),
            ))).valuation(restarted, OWNER, PORTFOLIO, as_of, account_id="acct")
            self.assertEqual(([row["holdingId"] for row in recomputed["holdings"]], recomputed["holdings"][1]["currentValue"], recomputed["inputDigest"] == valuation["inputDigest"]), (["a-holding", "holding"], "30", False))

    def test_scoped_observation_dates_and_currency_valuation_never_mix_series(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "accounts.json"
            store = LocalAccountDataStore(path)
            inr_account = AccountFact("inr-account", OWNER, "INR institution", "demat", "INR", "Synthetic", None, None, None, None, manual_provenance("inr-account"), PORTFOLIO, True)
            usd_account = AccountFact("usd-account", OWNER, "USD institution", "other", "USD", "Synthetic", None, None, None, None, manual_provenance("usd-account"), PORTFOLIO, True)
            store.commit_account(inr_account, route="/accounts", idempotency_key="inr-account", request_digest="inr-account", expected_revision=None)
            store.commit_account(usd_account, route="/accounts", idempotency_key="usd-account", request_digest="usd-account", expected_revision=None)
            store.commit_opening_holding(OpeningHoldingFact("inr-holding", "inr-account", OWNER, "INR fund", None, Decimal("2"), date(2026, 1, 1), "INR", None, manual_provenance("inr-holding"), PORTFOLIO), route="/holdings", idempotency_key="inr-holding", request_digest="inr-holding")
            store.commit_opening_holding(OpeningHoldingFact("usd-holding", "usd-account", OWNER, "USD ETF", None, Decimal("3"), date(2026, 1, 1), "USD", None, manual_provenance("usd-holding"), PORTFOLIO), route="/holdings", idempotency_key="usd-holding", request_digest="usd-holding")
            dates = (date(2026, 3, 2), date(2026, 6, 1), date(2026, 9, 9))
            service = LocalValuationService(SyntheticDailyPriceSource(tuple(
                SyntheticDailyPrice("inr-holding", OWNER, PORTFOLIO, Decimal(str(10 + index)), "INR", observed, "AMFI", "DAILY_NAV", f"inr-{index}")
                for index, observed in enumerate(dates)
            ) + tuple(
                SyntheticDailyPrice("usd-holding", OWNER, PORTFOLIO, Decimal(str(20 + (index * 2))), "USD", observed, "NSE", "EOD_CLOSE", f"usd-{index}")
                for index, observed in enumerate(dates)
            )))
            self.assertEqual(service.observation_dates(store, OWNER, PORTFOLIO, currency="INR"), dates)
            self.assertEqual(service.observation_dates(store, OWNER, PORTFOLIO, currency="USD"), dates)
            self.assertEqual(service.observation_dates(store, OWNER, PORTFOLIO, account_id="inr-account", currency="USD"), ())
            inr = service.valuation(store, OWNER, PORTFOLIO, dates[-1], currency="INR")
            usd = service.valuation(store, OWNER, PORTFOLIO, dates[-1], currency="USD")
            self.assertEqual(([row["holdingId"] for row in inr["holdings"]], inr["summaryByCurrency"]), (["inr-holding"], [{"currency": "INR", "calculatedValue": "24", "statementValue": "0", "totalIncludedValue": "24", "calculatedAsOf": "2026-09-09", "statementAsOf": None, "excludedForReconciliationCount": 0}]))
            self.assertEqual(([row["holdingId"] for row in usd["holdings"]], usd["summaryByCurrency"]), (["usd-holding"], [{"currency": "USD", "calculatedValue": "72", "statementValue": "0", "totalIncludedValue": "72", "calculatedAsOf": "2026-09-09", "statementAsOf": None, "excludedForReconciliationCount": 0}]))
            identity = PrivateNsdlIdentity(OWNER, "family", PORTFOLIO, "ZZZZZ9999Z")
            app = create_private_nsdl_app(identities={(OWNER, PORTFOLIO): identity}, store=PersistentFakeNsdlStore(), account_data_store=store, valuation_service=service, membership_reader=lambda _uid: {"uid": OWNER, "familyId": "family", "role": "ADMIN", "active": True})
            app.state.auth_verifier = Verifier()
            client = TestClient(app)
            headers = {"Authorization": "Bearer synthetic"}
            self.assertEqual(client.get("/api/nsdl/valuation?portfolio_id=synthetic_portfolio&currency=USD&observations=1", headers=headers).json(), {"observationDates": [item.isoformat() for item in dates]})
            self.assertEqual(client.get("/api/nsdl/valuation?portfolio_id=synthetic_portfolio&as_of=2026-09-09&currency=USD", headers=headers).json()["holdings"][0]["holdingId"], "usd-holding")
            self.assertEqual(client.get("/api/nsdl/valuation?portfolio_id=synthetic_portfolio&observations=1", headers=headers).json(), {"detail": "ERR_ACCOUNT_REQUEST_INVALID"})

    def test_records_only_source_returns_empty_observation_history_instead_of_unavailable(self):
        class RecordsOnlySource:
            def records(self, _owner, _portfolio, _as_of):
                return ()

        with TemporaryDirectory() as directory:
            store, _service = seeded(Path(directory) / "accounts.json")
            service = LocalValuationService(RecordsOnlySource())
            self.assertEqual(service.observation_dates(store, OWNER, PORTFOLIO, currency="INR"), ())

    def test_compact_range_is_scoped_bounded_and_endpoint_invariant(self):
        with TemporaryDirectory() as directory:
            store, _service = seeded(Path(directory) / "range.json")
            dates = (date(2026, 1, 2), date(2026, 1, 31), date(2026, 2, 2))
            source = CountingSource((SyntheticDailyPrice("holding", OWNER, PORTFOLIO, Decimal("9"), "INR", date(2025, 12, 31), "AMFI", "DAILY_NAV", "outside-selected-range"),) + tuple(
                SyntheticDailyPrice("holding", OWNER, PORTFOLIO, Decimal(str(10 + index)), "INR", observed, "AMFI", "DAILY_NAV", f"range-{index}")
                for index, observed in enumerate(dates)
            ))
            service = LocalValuationService(source)
            daily = service.valuation_range(store, OWNER, PORTFOLIO, None, "acct", "INR", dates[0], dates[-1], "daily")
            monthly = service.valuation_range(store, OWNER, PORTFOLIO, None, "acct", "INR", dates[0], dates[-1], "monthly")
            self.assertEqual([point["asOf"] for point in daily["points"]], [item.isoformat() for item in dates])
            self.assertEqual([point["asOf"] for point in monthly["points"]], ["2026-01-31", "2026-02-02"])
            self.assertEqual((daily["first"], daily["last"], daily["coverage"]["observedCount"], daily["scope"]), (monthly["first"], monthly["last"], monthly["coverage"]["observedCount"], {"accountId": "acct", "currency": "INR"}))
            self.assertEqual((daily["coverage"]["availableStart"], daily["coverage"]["selectedObservedCount"], source.calls), ("2025-12-31", 3, 6), "out-of-range source dates are indexed but never valued")
            self.assertNotIn("holdings", daily)
            self.assertEqual(store._store._derived_cache, {}, "range work does not persist full holding arrays per date")

            identity = PrivateNsdlIdentity(OWNER, "family", PORTFOLIO, "ZZZZZ9999Z")
            app = create_private_nsdl_app(identities={(OWNER, PORTFOLIO): identity}, store=PersistentFakeNsdlStore(), account_data_store=store, valuation_service=service, membership_reader=lambda _uid: {"uid": OWNER, "familyId": "family", "role": "ADMIN", "active": True})
            app.state.auth_verifier = Verifier()
            client = TestClient(app)
            calls_before = source.calls
            self.assertEqual(client.get("/api/nsdl/valuation-range?portfolio_id=synthetic_portfolio&currency=INR&granularity=daily").status_code, 401)
            self.assertEqual(source.calls, calls_before, "authorization precedes range work")
            headers = {"Authorization": "Bearer synthetic"}
            response = client.get("/api/nsdl/valuation-range?portfolio_id=synthetic_portfolio&account_id=acct&currency=INR&start=2026-01-02&end=2026-02-02&granularity=monthly", headers=headers)
            self.assertEqual((response.status_code, response.json()["points"], response.json()["first"]["asOf"], response.json()["last"]["asOf"]), (200, monthly["points"], "2026-01-02", "2026-02-02"))
            self.assertEqual(client.get("/api/nsdl/valuation-range?portfolio_id=synthetic_portfolio&currency=INR&start=2026-01-02&granularity=daily", headers=headers).json(), {"detail": "ERR_ACCOUNT_REQUEST_INVALID"})
            self.assertEqual(client.get("/api/nsdl/valuation-range?portfolio_id=synthetic_portfolio&currency=INR&start=2020-01-01&end=2031-01-01&granularity=daily", headers=headers).json(), {"detail": "ERR_ACCOUNT_REQUEST_INVALID"})

    def test_daily_range_limit_is_explicit_and_never_silently_truncates(self):
        class DenseSource:
            def __init__(self):
                self.dates = tuple(date(2026, 1, 1) + timedelta(days=index) for index in range(1001))
                self.calls = 0

            def observation_dates(self, _owner, _portfolio):
                return self.dates

            def records(self, owner, portfolio, as_of):
                self.calls += 1
                return (SyntheticDailyPrice("holding", owner, portfolio, Decimal("12.50"), "INR", as_of, "AMFI", "DAILY_NAV", as_of.isoformat()),)

        with TemporaryDirectory() as directory:
            store, _service = seeded(Path(directory) / "dense.json")
            dense = DenseSource()
            service = LocalValuationService(dense)
            identity = PrivateNsdlIdentity(OWNER, "family", PORTFOLIO, "ZZZZZ9999Z")
            app = create_private_nsdl_app(identities={(OWNER, PORTFOLIO): identity}, store=PersistentFakeNsdlStore(), account_data_store=store, valuation_service=service, membership_reader=lambda _uid: {"uid": OWNER, "familyId": "family", "role": "ADMIN", "active": True})
            app.state.auth_verifier = Verifier()
            response = TestClient(app).get("/api/nsdl/valuation-range?portfolio_id=synthetic_portfolio&currency=INR&granularity=daily", headers={"Authorization": "Bearer synthetic"})
            self.assertEqual(response.json(), {"detail": "ERR_ACCOUNT_RANGE_LIMIT"})
            self.assertEqual(dense.calls, 0, "range limits are enforced before date valuation work")

    def test_range_with_representative_large_holding_count_keeps_full_rows_out_of_derived_cache(self):
        """128 holdings × 2 observations is deliberately close to source's 256-record cap.

        A normal point valuation's full holding response can exceed the store's
        16 KiB derived-result cap.  Range calculation must therefore keep only
        compact request-local points and must not turn that pre-existing point
        cache safety limit into a history failure.
        """
        with TemporaryDirectory() as directory:
            store = LocalAccountDataStore(Path(directory) / "large-range.json")
            account = AccountFact("acct", OWNER, "Synthetic", "demat", "INR", "Synthetic", None, None, None, None, manual_provenance("account"), PORTFOLIO, True)
            store.commit_account(account, route="/accounts", idempotency_key="account", request_digest="a", expected_revision=None)
            observed = (date(2026, 9, 1), date(2026, 9, 2))
            holdings = tuple(
                OpeningHoldingFact(f"holding-{index:03d}", "acct", OWNER, f"Synthetic fund {index}", f"INF{index:07d}", Decimal("1"), date(2026, 1, 1), "INR", None, manual_provenance(f"holding-{index:03d}"), PORTFOLIO)
                for index in range(128)
            )
            for holding in holdings:
                store.commit_opening_holding(holding, route="/holdings", idempotency_key=holding.fact_id, request_digest=holding.fact_id)
            source = SyntheticDailyPriceSource(tuple(
                SyntheticDailyPrice(holding.fact_id, OWNER, PORTFOLIO, Decimal("10"), "INR", observed_at, "AMFI", "DAILY_NAV", f"{holding.fact_id}-{observed_at.isoformat()}")
                for observed_at in observed for holding in holdings
            ))
            result = LocalValuationService(source).valuation_range(store, OWNER, PORTFOLIO, None, "acct", "INR", observed[0], observed[-1], "daily")
            self.assertEqual(([point["calculatedValue"] for point in result["points"]], result["coverage"]["selectedObservedCount"]), (["1280", "1280"], 2))
            self.assertEqual(store._store._derived_cache, {}, "range does not persist full 128-holding rows")

    def test_missing_price_mixed_currency_and_nsdl_snapshot_never_fabricate_performance(self):
        with TemporaryDirectory() as directory:
            store, _service = seeded(Path(directory) / "accounts.json")
            missing = LocalValuationService(SyntheticDailyPriceSource(())).performance(store, OWNER, PORTFOLIO, date(2026, 9, 9))
            self.assertEqual((missing["gain"]["status"], missing["gain"]["reason"]), ("INSUFFICIENT_DATA", "MISSING_PRICE"))
            mixed_source = SyntheticDailyPriceSource((SyntheticDailyPrice("holding", OWNER, PORTFOLIO, Decimal("12"), "USD", date(2026, 9, 9), "NSE", "EOD_CLOSE", "r2"),))
            mixed = LocalValuationService(mixed_source).performance(store, OWNER, PORTFOLIO, date(2026, 9, 9))
            self.assertEqual(mixed["gain"]["reason"], "MIXED_CURRENCY")
            class Snapshot: revision_id = "snapshot-r1"; as_of_date = date(2026, 9, 9); holdings = (object(),)
            nsdl = _service.performance(store, OWNER, PORTFOLIO, date(2026, 9, 9), Snapshot())
            self.assertEqual((nsdl["gain"]["status"], nsdl["gain"]["value"], nsdl["xirr"]["status"]), ("CALCULATED", "-75.00", "CALCULATED"))

    def test_omitted_attestation_invalid_price_and_non_numeric_xirr_outcomes_are_explicit(self):
        with TemporaryDirectory() as directory:
            store, service = seeded(Path(directory) / "omitted.json")
            account = store._store.get_account(OWNER, "acct", PORTFOLIO)
            omitted = AccountFact(account.account_id, account.owner_scope_id, account.institution, account.account_type, account.currency, account.source_name, account.user_alias, account.custodian_or_dp, account.execution_broker, account.masked_identifier, manual_provenance("omitted"), PORTFOLIO)
            store.commit_account(omitted, route="/accounts", idempotency_key="omitted", request_digest="omitted", expected_revision=1)
            result = service.performance(store, OWNER, PORTFOLIO, date(2026, 9, 9))
            self.assertEqual((omitted.manual_history_complete, result["gain"], result["xirr"]), (False, {"status": "INSUFFICIENT_DATA", "reason": "MISSING_HISTORY"}, {"status": "UNAVAILABLE", "reason": "MISSING_HISTORY"}))
            with self.assertRaises(ValuationError):
                SyntheticDailyPrice("bad", OWNER, PORTFOLIO, Decimal("NaN"), "INR", date(2026, 9, 9), "AMFI", "DAILY_NAV", "bad")
            one_sided_store, one_sided_service = seeded(Path(directory) / "one-sided.json", flow_amount="100")
            one_sided = one_sided_service.performance(one_sided_store, OWNER, PORTFOLIO, date(2026, 9, 9))
            self.assertEqual((one_sided["gain"], one_sided["xirr"]), ({"status": "INSUFFICIENT_DATA", "reason": "INVALID_CASHFLOW"}, {"status": "UNAVAILABLE", "reason": "INVALID_CASHFLOW"}))
            same_day_store, same_day_service = seeded(Path(directory) / "same-day.json", flow_date=date(2026, 9, 9))
            same_day = same_day_service.performance(same_day_store, OWNER, PORTFOLIO, date(2026, 9, 9))
            self.assertEqual((same_day["gain"], same_day["xirr"]), ({"status": "INSUFFICIENT_DATA", "reason": "SAME_DAY_ONLY"}, {"status": "UNAVAILABLE", "reason": "SAME_DAY_ONLY"}))

    def test_private_routes_authorize_before_local_service_and_have_fixed_contract(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "accounts.json"
            store, initial_service = seeded(path)
            source = CountingSource(initial_service._source._records)
            service = LocalValuationService(source)
            identity = PrivateNsdlIdentity(OWNER, "family", PORTFOLIO, "ZZZZZ9999Z")
            counted_store = CountingStore(store)
            snapshot = type("Snapshot", (), {"revision_id": "snapshot-r1", "as_of_date": date(2026, 9, 9), "holdings": (object(),)})()
            nsdl_store = CountingNsdlStore(snapshot)
            app = create_private_nsdl_app(identities={(OWNER, PORTFOLIO): identity}, store=nsdl_store, account_data_store=counted_store, valuation_service=service, membership_reader=lambda _uid: {"uid": OWNER, "familyId": "family", "role": "ADMIN", "active": True})
            app.state.auth_verifier = Verifier()
            client = TestClient(app)
            self.assertEqual(client.get("/api/nsdl/valuation?portfolio_id=synthetic_portfolio&as_of=2026-09-09").status_code, 401)
            self.assertEqual((source.calls, counted_store.list_calls, counted_store.cache_reads, nsdl_store.reads), (0, 0, 0, 0))
            headers = {"Authorization": "Bearer synthetic"}
            valuation = client.get("/api/nsdl/valuation?portfolio_id=synthetic_portfolio&as_of=2026-09-09", headers=headers)
            performance = client.get("/api/nsdl/performance?portfolio_id=synthetic_portfolio&as_of=2026-09-09", headers=headers)
            self.assertEqual((valuation.status_code, valuation.json()["holdings"][0]["currentValue"], performance.status_code, performance.json()["gain"]["status"]), (200, "25.00", 200, "CALCULATED"))
            source_before, cache_before, nsdl_before = source.calls, counted_store.cache_reads, nsdl_store.reads
            account_performance = client.get("/api/nsdl/performance?portfolio_id=synthetic_portfolio&as_of=2026-09-09&account_id=acct", headers=headers)
            self.assertEqual((account_performance.status_code, account_performance.json()["gain"]["status"], account_performance.json()["xirr"]["status"], nsdl_store.reads), (200, "CALCULATED", "CALCULATED", nsdl_before + 1))
            invalid_account = client.get("/api/nsdl/performance?portfolio_id=synthetic_portfolio&as_of=2026-09-09&account_id=missing", headers=headers)
            self.assertEqual((invalid_account.json(), source.calls == source_before + 2, counted_store.cache_reads >= cache_before), ({"detail": "ERR_ACCOUNT_REQUEST_INVALID"}, True, True))
            self.assertEqual(client.get("/api/nsdl/valuation?portfolio_id=synthetic_portfolio&as_of=bad", headers=headers).json(), {"detail": "ERR_ACCOUNT_REQUEST_INVALID"})
            disabled = create_private_nsdl_app(identities={(OWNER, PORTFOLIO): identity}, store=PersistentFakeNsdlStore(), membership_reader=lambda _uid: {"uid": OWNER, "familyId": "family", "role": "ADMIN", "active": True})
            disabled.state.auth_verifier = Verifier()
            self.assertEqual(TestClient(disabled).get("/api/nsdl/valuation?portfolio_id=synthetic_portfolio&as_of=2026-09-09", headers=headers).json(), {"detail": "ERR_ACCOUNT_STORE_UNAVAILABLE"})


if __name__ == "__main__":
    unittest.main()
