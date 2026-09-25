import json
import os
from datetime import date
from decimal import Decimal
from dataclasses import replace
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.account_data_store import IDEMPOTENCY_CONFLICT, STORE_UNAVAILABLE, AccountDataStore, LocalAccountDataStore
from app.api.account_data import owner_facts, request_digest, stable_fact_key, strict_json_object
from app.models.account_data import AccountDataError, AccountFact, CashFlowFact, OpeningHoldingFact, manual_provenance, statement_provenance


@contextmanager
def raises(expected_error, match):
    try:
        yield
    except expected_error as error:
        assert match in str(error)
    else:
        raise AssertionError(f"expected {expected_error.__name__}: {match}")


def account(owner="owner-a", account_id="acct-1"):
    return AccountFact(account_id, owner, "Example Institution", "demat", "INR", "CAS source name", "Long-term", "DP-1", None, "****1234", manual_provenance("synthetic-account", 1))


def test_source_name_alias_and_broker_are_distinct():
    item = account()
    assert item.source_name == "CAS source name"
    assert item.user_alias == "Long-term"
    assert item.execution_broker is None
    assert item.display_name == "Long-term"


def test_manual_facts_are_owner_scoped_and_idempotent():
    store = AccountDataStore()
    store.put_account(account())
    holding = OpeningHoldingFact("hold-1", "acct-1", "owner-a", "Synthetic Fund", "INE000000000", Decimal("2"), date(2026, 1, 1), "INR", None, manual_provenance("synthetic-holding"))
    flow = CashFlowFact("flow-1", "acct-1", "owner-a", date(2026, 1, 2), Decimal("100"), "INR", "contribution", None, manual_provenance("synthetic-flow"))
    assert store.add_opening_holding(holding) == store.add_opening_holding(holding)
    assert store.add_cash_flow(flow) == flow
    assert len(owner_facts(store, "owner-a")["opening_holdings"]) == 1
    assert owner_facts(store, "owner-b") == {"accounts": [], "opening_holdings": [], "cash_flows": []}


def test_conflicting_duplicate_and_missing_account_fail_closed():
    store = AccountDataStore()
    store.put_account(account())
    original = CashFlowFact("flow-1", "acct-1", "owner-a", date(2026, 1, 2), Decimal("100"), "INR", "contribution", None, manual_provenance("original"))
    assert store.add_cash_flow(original) == original
    with raises(AccountDataError, "ERR_ACCOUNT_DUPLICATE_CONFLICT"):
        store.add_cash_flow(replace(original, amount=Decimal("101")))
    with raises(AccountDataError, "ERR_ACCOUNT_NOT_FOUND"):
        store.add_cash_flow(CashFlowFact("flow-2", "missing", "owner-a", date(2026, 1, 2), Decimal("100"), "INR", "contribution", None, manual_provenance("other")))


def test_unknown_cost_is_preserved_as_unknown():
    fact = OpeningHoldingFact("hold-1", "acct-1", "owner-a", "Synthetic Equity", None, Decimal("1"), date(2026, 1, 1), "INR", None, manual_provenance("synthetic"))
    assert fact.documented_cost is None


def test_changed_same_id_flow_conflicts_after_original_saved():
    store = AccountDataStore(); store.put_account(account())
    original = CashFlowFact("flow-1", "acct-1", "owner-a", date(2026, 1, 2), Decimal("100"), "INR", "contribution", None, manual_provenance("flow", 1))
    store.add_cash_flow(original)
    with raises(AccountDataError, "ERR_ACCOUNT_DUPLICATE_CONFLICT"):
        store.add_cash_flow(replace(original, amount=Decimal("101")))


def test_non_default_portfolio_binding_is_enforced():
    store = AccountDataStore()
    scoped = AccountFact("acct-p", "owner-a", "Example", "demat", "INR", "Source", None, None, None, None, manual_provenance("account", 1), "portfolio-a")
    store.put_account(scoped)
    valid = OpeningHoldingFact("hold-p", "acct-p", "owner-a", "Synthetic", None, Decimal("1"), date(2026, 1, 1), "INR", None, manual_provenance("holding", 1), "portfolio-a")
    assert store.add_opening_holding(valid) == valid
    with raises(AccountDataError, "ERR_ACCOUNT_NOT_FOUND"):
        store.add_opening_holding(replace(valid, portfolio_id="portfolio-b"))


def test_account_revision_is_append_only_and_numbered():
    store = AccountDataStore()
    original = store.put_account(account())
    revised = store.revise_account("owner-a", "acct-1", user_alias="Updated")
    assert revised.user_alias == "Updated"
    assert revised.source_name == original.source_name
    assert revised.provenance.revision == original.provenance.revision + 1
    assert len(store.account_revisions("owner-a", "acct-1")) == 2
    with raises(AccountDataError, "ERR_ACCOUNT_SOURCE_IMMUTABLE"):
        store.revise_account("owner-a", "acct-1", source_name="Changed source")


def test_public_identity_ignores_recorded_at_for_reconstructed_duplicate():
    first = account()
    reconstructed = AccountFact(first.account_id, first.owner_scope_id, first.institution, first.account_type, first.currency,
                                 first.source_name, first.user_alias, first.custodian_or_dp, first.execution_broker,
                                 first.masked_identifier, manual_provenance("synthetic-account"))
    assert stable_fact_key(first) == stable_fact_key(reconstructed)


def test_holding_and_cashflow_public_keys_retry_and_distinct_provenance_conflicts():
    holding = OpeningHoldingFact("hold-1", "acct-1", "owner-a", "Synthetic", None, Decimal("2"), date(2026, 1, 1), "INR", None, manual_provenance("holding", 1))
    holding_retry = OpeningHoldingFact("hold-1", "acct-1", "owner-a", "Synthetic", None, Decimal("2"), date(2026, 1, 1), "INR", None, manual_provenance("holding", 1))
    flow = CashFlowFact("flow-1", "acct-1", "owner-a", date(2026, 1, 2), Decimal("100"), "INR", "contribution", None, manual_provenance("flow", 1))
    flow_retry = CashFlowFact("flow-1", "acct-1", "owner-a", date(2026, 1, 2), Decimal("100"), "INR", "contribution", None, manual_provenance("flow", 1))
    assert stable_fact_key(holding) == stable_fact_key(holding_retry)
    assert stable_fact_key(flow) == stable_fact_key(flow_retry)
    assert stable_fact_key(holding) != stable_fact_key(replace(holding, provenance=manual_provenance("other", 1)))
    assert stable_fact_key(flow) != stable_fact_key(replace(flow, provenance=manual_provenance("other", 1)))


def _persisted_account(owner="owner-a", account_id="acct-p", portfolio="portfolio-a", reference="key-account", alias="Long-term", source_name="CAS source"):
    return AccountFact(account_id, owner, "Synthetic Institution", "demat", "INR", source_name, alias, "DP-1", None, "****1234", manual_provenance(reference, 1), portfolio)


def _digest(kind, identifier, amount=""):
    return request_digest({"kind": kind, "identifier": identifier, "amount": amount})


def test_injected_local_store_persists_facts_and_replays_receipts_after_restart():
    with TemporaryDirectory() as directory:
        path = Path(directory) / "accounts.json"
        store = LocalAccountDataStore(path)
        saved_account = store.commit_account(_persisted_account(), route="/accounts", idempotency_key="key-account", request_digest=_digest("account", "acct-p"), expected_revision=None)
        holding = OpeningHoldingFact("hold-p", "acct-p", "owner-a", "Synthetic Fund", None, Decimal("2"), date(2026, 1, 1), "INR", None, manual_provenance("key-holding", 1), "portfolio-a")
        flow = CashFlowFact("flow-p", "acct-p", "owner-a", date(2026, 1, 2), Decimal("100"), "INR", "contribution", None, manual_provenance("key-flow", 1), "portfolio-a")
        store.commit_opening_holding(holding, route="/holdings", idempotency_key="key-holding", request_digest=_digest("holding", "hold-p"))
        store.commit_cash_flow(flow, route="/flows", idempotency_key="key-flow", request_digest=_digest("flow", "flow-p"))
        store.commit_account(_persisted_account(owner="owner-b", account_id="acct-other", reference="key-other"), route="/accounts", idempotency_key="key-other", request_digest=_digest("account", "acct-other"), expected_revision=None)
        assert path.is_file() and path.stat().st_mode & 0o077 == 0
        restarted = LocalAccountDataStore(path)
        facts = owner_facts(restarted, "owner-a", "portfolio-a")
        assert [item["account_id"] for item in facts["accounts"]] == ["acct-p"]
        assert [item["fact_id"] for item in facts["openingHoldings"]] == ["hold-p"]
        assert [item["fact_id"] for item in facts["cashFlows"]] == ["flow-p"]
        assert [item["account_id"] for item in owner_facts(restarted, "owner-b", "portfolio-a")["accounts"]] == ["acct-other"]
        assert restarted.commit_account(_persisted_account(), route="/accounts", idempotency_key="key-account", request_digest=_digest("account", "acct-p"), expected_revision=None) == saved_account
        assert not list(path.parent.glob(".accounts.json.*.tmp"))
        owned_directory = Path(directory)
        assert owned_directory.exists()
    assert not owned_directory.exists()


def test_local_store_idempotency_conflicts_and_account_revisions_are_persistent():
    with TemporaryDirectory() as directory:
        store = LocalAccountDataStore(Path(directory) / "accounts.json")
        original = _persisted_account()
        store.commit_account(original, route="/accounts", idempotency_key="key-account", request_digest=_digest("account", "acct-p"), expected_revision=None)
        with raises(AccountDataError, IDEMPOTENCY_CONFLICT):
            store.commit_account(original, route="/accounts", idempotency_key="key-account", request_digest=_digest("account", "changed"), expected_revision=None)
        revised = _persisted_account(reference="key-revise", alias="Taxable")
        saved = store.commit_account(revised, route="/accounts", idempotency_key="key-revise", request_digest=_digest("account", "acct-p", "revision-2"), expected_revision=1)
        assert saved.provenance.revision == 2 and saved.user_alias == "Taxable"
        assert isinstance(json.loads((Path(directory) / "accounts.json").read_text(encoding="utf-8"))["accountRevisions"][0], list)
        with raises(AccountDataError, "ERR_ACCOUNT_REVISION_INVALID"):
            store.commit_account(_persisted_account(reference="key-source", source_name="Changed source"), route="/accounts", idempotency_key="key-source", request_digest=_digest("account", "acct-p", "source"), expected_revision=2)
        holding = OpeningHoldingFact("hold-p", "acct-p", "owner-a", "Synthetic Fund", None, Decimal("2"), date(2026, 1, 1), "INR", None, manual_provenance("key-holding", 1), "portfolio-a")
        store.commit_opening_holding(holding, route="/holdings", idempotency_key="key-holding", request_digest=_digest("holding", "hold-p"))
        with raises(AccountDataError, "ERR_ACCOUNT_DUPLICATE_CONFLICT"):
            store.commit_opening_holding(replace(holding, quantity=Decimal("3"), provenance=manual_provenance("key-holding-2", 1)), route="/holdings", idempotency_key="key-holding-2", request_digest=_digest("holding", "hold-p", "changed"))
        restarted = LocalAccountDataStore(Path(directory) / "accounts.json")
        assert [item.provenance.revision for item in restarted.account_revisions("owner-a", "acct-p", "portfolio-a")] == [1, 2]


def test_statement_account_refresh_preserves_alias_and_advances_only_statement_provenance():
    with TemporaryDirectory() as directory:
        path = Path(directory) / "accounts.json"
        store = LocalAccountDataStore(path)
        first = AccountFact("statement-account", "owner-a", "NSDL", "demat", "INR", "Depository One", "My long-term account", "saved DP", "saved broker", "••••1234", statement_provenance("receipt-1"), "portfolio-a", False)
        store.commit_account(first, route="/api/nsdl/import", idempotency_key="statement-1", request_digest=_digest("statement", "1"), expected_revision=None)
        refreshed = AccountFact("statement-account", "owner-a", "NSDL", "demat", "INR", "Depository Two", "My long-term account", "saved DP", "saved broker", "••••1234", statement_provenance("receipt-2"), "portfolio-a", False)
        saved = store.commit_account(refreshed, route="/api/nsdl/import", idempotency_key="statement-2", request_digest=_digest("statement", "2"), expected_revision=1)
        assert (saved.source_name, saved.user_alias, saved.custodian_or_dp, saved.execution_broker, saved.provenance.source_kind, saved.provenance.revision) == ("Depository Two", "My long-term account", "saved DP", "saved broker", "statement", 2)
        replay = store.commit_account(refreshed, route="/api/nsdl/import", idempotency_key="statement-2", request_digest=_digest("statement", "2"), expected_revision=1)
        assert replay == saved
        restarted = LocalAccountDataStore(path)
        assert [(item.source_name, item.provenance.source_reference, item.provenance.revision) for item in restarted.account_revisions("owner-a", "statement-account", "portfolio-a")] == [("Depository One", "receipt-1", 1), ("Depository Two", "receipt-2", 2)]
        assert restarted.commit_account(refreshed, route="/api/nsdl/import", idempotency_key="statement-2", request_digest=_digest("statement", "2"), expected_revision=1) == saved


def test_local_store_atomic_replace_failure_preserves_last_committed_document_and_cleans_temp():
    with TemporaryDirectory() as directory:
        path = Path(directory) / "accounts.json"
        store = LocalAccountDataStore(path)
        store.commit_account(_persisted_account(), route="/accounts", idempotency_key="key-account", request_digest=_digest("account", "acct-p"), expected_revision=None)
        flow = CashFlowFact("flow-p", "acct-p", "owner-a", date(2026, 1, 2), Decimal("100"), "INR", "contribution", None, manual_provenance("key-flow", 1), "portfolio-a")
        with patch("app.account_data_store.os.replace", side_effect=OSError("synthetic failure")):
            with raises(AccountDataError, STORE_UNAVAILABLE):
                store.commit_cash_flow(flow, route="/flows", idempotency_key="key-flow", request_digest=_digest("flow", "flow-p"))
        assert not list(path.parent.glob(".accounts.json.*.tmp"))
        restarted = LocalAccountDataStore(path)
        assert owner_facts(restarted, "owner-a", "portfolio-a")["cashFlows"] == []


def test_local_store_post_replace_directory_failure_keeps_reloaded_committed_state():
    with TemporaryDirectory() as directory:
        path = Path(directory) / "accounts.json"
        store = LocalAccountDataStore(path)
        store.commit_account(_persisted_account(), route="/accounts", idempotency_key="key-account", request_digest=_digest("account", "acct-p"), expected_revision=None)
        flow = CashFlowFact("flow-p", "acct-p", "owner-a", date(2026, 1, 2), Decimal("100"), "INR", "contribution", None, manual_provenance("key-flow", 1), "portfolio-a")
        real_open = os.open
        open_calls = 0

        def fail_directory_open(*args, **kwargs):
            nonlocal open_calls
            open_calls += 1
            if open_calls == 2:
                raise OSError("synthetic directory sync failure")
            return real_open(*args, **kwargs)

        with patch("app.account_data_store.os.open", side_effect=fail_directory_open):
            with raises(AccountDataError, STORE_UNAVAILABLE):
                store.commit_cash_flow(flow, route="/flows", idempotency_key="key-flow", request_digest=_digest("flow", "flow-p"))
        assert [item["fact_id"] for item in owner_facts(store, "owner-a", "portfolio-a")["cashFlows"]] == ["flow-p"]
        restarted = LocalAccountDataStore(path)
        assert [item["fact_id"] for item in owner_facts(restarted, "owner-a", "portfolio-a")["cashFlows"]] == ["flow-p"]
        assert restarted.commit_cash_flow(flow, route="/flows", idempotency_key="key-flow", request_digest=_digest("flow", "flow-p")) == flow
        assert not list(path.parent.glob(".accounts.json.*.tmp"))


def test_same_owner_can_reuse_all_opaque_ids_in_isolated_portfolios():
    with TemporaryDirectory() as directory:
        store = LocalAccountDataStore(Path(directory) / "accounts.json")
        for portfolio in ("portfolio-a", "portfolio-b"):
            account = _persisted_account(portfolio=portfolio)
            store.commit_account(account, route="/accounts", idempotency_key=f"key-account-{portfolio}", request_digest=_digest("account", "acct-p", portfolio), expected_revision=None)
            holding = OpeningHoldingFact("hold-p", "acct-p", "owner-a", "Synthetic Fund", None, Decimal("2"), date(2026, 1, 1), "INR", None, manual_provenance(f"key-holding-{portfolio}", 1), portfolio)
            flow = CashFlowFact("flow-p", "acct-p", "owner-a", date(2026, 1, 2), Decimal("100"), "INR", "contribution", None, manual_provenance(f"key-flow-{portfolio}", 1), portfolio)
            store.commit_opening_holding(holding, route="/holdings", idempotency_key=f"key-holding-{portfolio}", request_digest=_digest("holding", "hold-p", portfolio))
            store.commit_cash_flow(flow, route="/flows", idempotency_key=f"key-flow-{portfolio}", request_digest=_digest("flow", "flow-p", portfolio))
        first = owner_facts(store, "owner-a", "portfolio-a")
        second = owner_facts(store, "owner-a", "portfolio-b")
        assert [item["account_id"] for item in first["accounts"]] == ["acct-p"]
        assert [item["account_id"] for item in second["accounts"]] == ["acct-p"]
        assert [item["fact_id"] for item in first["openingHoldings"]] == ["hold-p"]
        assert [item["fact_id"] for item in second["cashFlows"]] == ["flow-p"]
        assert first["accountRevisions"][0]["revisions"][0]["portfolio_id"] == "portfolio-a"
        assert second["accountRevisions"][0]["revisions"][0]["portfolio_id"] == "portfolio-b"


def test_local_store_rejects_questionable_storage_before_write_and_wire_rejects_duplicate_json():
    with TemporaryDirectory() as directory:
        path = Path(directory) / "accounts.json"
        path.write_text('{"schemaVersion":1,"schemaVersion":1}', encoding="utf-8")
        path.chmod(0o600)
        with raises(AccountDataError, STORE_UNAVAILABLE):
            LocalAccountDataStore(path)
        assert path.read_text(encoding="utf-8") == '{"schemaVersion":1,"schemaVersion":1}'
    with raises(AccountDataError, "ERR_ACCOUNT_REQUEST_INVALID"):
        strict_json_object(b'{"accountId":"a","accountId":"b"}')


def test_manual_corrections_and_voids_are_append_only_idempotent_and_restart_safe():
    with TemporaryDirectory() as directory:
        path = Path(directory) / "accounts.json"
        store = LocalAccountDataStore(path)
        account = _persisted_account()
        store.commit_account(account, route="/accounts", idempotency_key="account-key", request_digest=_digest("account", "acct-p"), expected_revision=None)
        holding = OpeningHoldingFact("hold-p", "acct-p", "owner-a", "Synthetic Fund", None, Decimal("2"), date(2026, 1, 1), "INR", Decimal("200"), manual_provenance("holding-create"), "portfolio-a")
        flow = CashFlowFact("flow-p", "acct-p", "owner-a", date(2026, 1, 2), Decimal("-200"), "INR", "contribution", None, manual_provenance("flow-create"), "portfolio-a")
        store.commit_opening_holding(holding, route="/holdings", idempotency_key="holding-create", request_digest=_digest("holding", "create"))
        store.commit_cash_flow(flow, route="/flows", idempotency_key="flow-create", request_digest=_digest("flow", "create"))
        corrected_holding = replace(holding, quantity=Decimal("3"), documented_cost=Decimal("300"), provenance=manual_provenance("holding-correct"))
        saved_holding = store.revise_opening_holding(corrected_holding, route="/holdings/correction", idempotency_key="holding-correct", request_digest=_digest("holding", "correct"), expected_revision=1)
        assert (saved_holding.quantity, saved_holding.provenance.revision, saved_holding.voided) == (Decimal("3"), 2, False)
        assert store.revise_opening_holding(corrected_holding, route="/holdings/correction", idempotency_key="holding-correct", request_digest=_digest("holding", "correct"), expected_revision=1) == saved_holding
        with raises(AccountDataError, "ERR_ACCOUNT_REVISION_INVALID"):
            store.revise_opening_holding(replace(corrected_holding, currency="USD"), route="/holdings/correction", idempotency_key="currency-change", request_digest=_digest("holding", "currency"), expected_revision=2)
        saved_flow = store.void_cash_flow("owner-a", "portfolio-a", "flow-p", route="/flows/void", idempotency_key="flow-void", request_digest=_digest("flow", "void"), expected_revision=1)
        assert (saved_flow.voided, saved_flow.provenance.revision) == (True, 2)
        with raises(AccountDataError, "ERR_ACCOUNT_NOT_FOUND"):
            store.void_cash_flow("owner-a", "other-portfolio", "flow-p", route="/flows/void", idempotency_key="cross-portfolio", request_digest=_digest("flow", "cross"), expected_revision=2)
        restarted = LocalAccountDataStore(path)
        facts = owner_facts(restarted, "owner-a", "portfolio-a")
        assert facts["openingHoldings"][0]["quantity"] == "3"
        assert facts["cashFlows"][0]["voided"] is True
        assert [row["provenance"]["revision"] for row in facts["openingHoldingRevisions"][0]["revisions"]] == [1, 2]
        assert [row["provenance"]["revision"] for row in facts["cashFlowRevisions"][0]["revisions"]] == [1, 2]


def test_manual_account_alias_update_cannot_change_currency_or_identity_after_facts_exist():
    with TemporaryDirectory() as directory:
        store = LocalAccountDataStore(Path(directory) / "accounts.json")
        original = replace(_persisted_account(), currency="USD", user_alias="Schwab taxable")
        store.commit_account(original, route="/accounts", idempotency_key="account-create", request_digest=_digest("account", "usd"), expected_revision=None)
        holding = OpeningHoldingFact("usd-holding", "acct-p", "owner-a", "Synthetic US ETF", None, Decimal("2"), date(2026, 1, 1), "USD", Decimal("200"), manual_provenance("holding-create"), "portfolio-a")
        store.commit_opening_holding(holding, route="/holdings", idempotency_key="holding-create", request_digest=_digest("holding", "usd"))
        with raises(AccountDataError, "ERR_ACCOUNT_REVISION_INVALID"):
            store.commit_account(replace(original, currency="INR", user_alias="Renamed", provenance=manual_provenance("currency-change")), route="/accounts", idempotency_key="currency-change", request_digest=_digest("account", "currency-change"), expected_revision=1)
        saved = store.commit_account(replace(original, user_alias="Renamed", provenance=manual_provenance("alias-change")), route="/accounts", idempotency_key="alias-change", request_digest=_digest("account", "alias-change"), expected_revision=1)
        assert (saved.currency, saved.user_alias, saved.provenance.revision) == ("USD", "Renamed", 2)
        facts = owner_facts(store, "owner-a", "portfolio-a")
        assert (facts["accounts"][0]["currency"], facts["openingHoldings"][0]["currency"]) == ("USD", "USD")


def test_restart_preserves_exact_manual_audit_provenance_and_rejects_malformed_chain_without_rewrite():
    with TemporaryDirectory() as directory:
        path = Path(directory) / "accounts.json"
        store = LocalAccountDataStore(path)
        account = _persisted_account()
        store.commit_account(account, route="/accounts", idempotency_key="account-create", request_digest=_digest("account", "acct-p"), expected_revision=None)
        holding = OpeningHoldingFact("hold-p", "acct-p", "owner-a", "Synthetic Fund", None, Decimal("2"), date(2026, 1, 1), "INR", Decimal("200"), manual_provenance("holding-create"), "portfolio-a")
        flow = CashFlowFact("flow-p", "acct-p", "owner-a", date(2026, 1, 2), Decimal("-200"), "INR", "contribution", None, manual_provenance("flow-create"), "portfolio-a")
        store.commit_opening_holding(holding, route="/holdings", idempotency_key="holding-create", request_digest=_digest("holding", "create"))
        store.commit_cash_flow(flow, route="/flows", idempotency_key="flow-create", request_digest=_digest("flow", "create"))
        corrected = store.revise_opening_holding(replace(holding, quantity=Decimal("3"), provenance=manual_provenance("holding-correct")), route="/holdings", idempotency_key="holding-correct", request_digest=_digest("holding", "correct"), expected_revision=1)
        voided = store.void_cash_flow("owner-a", "portfolio-a", "flow-p", route="/flows", idempotency_key="flow-void", request_digest=_digest("flow", "void"), expected_revision=1)
        before = owner_facts(store, "owner-a", "portfolio-a")
        restarted = LocalAccountDataStore(path)
        after = owner_facts(restarted, "owner-a", "portfolio-a")
        assert after["openingHoldingRevisions"] == before["openingHoldingRevisions"]
        assert after["cashFlowRevisions"] == before["cashFlowRevisions"]
        assert restarted.revise_opening_holding(replace(holding, quantity=Decimal("3"), provenance=manual_provenance("holding-correct")), route="/holdings", idempotency_key="holding-correct", request_digest=_digest("holding", "correct"), expected_revision=1) == corrected
        assert restarted.void_cash_flow("owner-a", "portfolio-a", "flow-p", route="/flows", idempotency_key="flow-void", request_digest=_digest("flow", "void"), expected_revision=1) == voided
        malformed = json.loads(path.read_text(encoding="utf-8"))
        malformed["holdingRevisions"][0][1]["provenance"]["revision"] = 99
        path.write_text(json.dumps(malformed), encoding="utf-8")
        preserved = path.read_text(encoding="utf-8")
        with raises(AccountDataError, STORE_UNAVAILABLE):
            LocalAccountDataStore(path)
        assert path.read_text(encoding="utf-8") == preserved


def test_decoder_rejects_manual_account_structural_revisions_in_legacy_and_current_documents_without_rewrite():
    fixtures = Path(__file__).with_name("fixtures")
    mutations = (("currency", "USD"), ("institution", "Other institution"), ("account_type", "other"), ("custodian_or_dp", "Other DP"))
    with TemporaryDirectory() as directory:
        directory_path = Path(directory)
        for fixture in ("account_data_schema_v1_cache.json", "account_data_schema_v2_cache.json"):
            for field, replacement in mutations:
                path = directory_path / f"{fixture}-{field}.json"
                malformed = json.loads((fixtures / fixture).read_text(encoding="utf-8"))
                malformed["accountRevisions"][0][1][field] = replacement
                path.write_text(json.dumps(malformed), encoding="utf-8")
                path.chmod(0o600)
                preserved = path.read_text(encoding="utf-8")
                with raises(AccountDataError, STORE_UNAVAILABLE):
                    LocalAccountDataStore(path)
                assert path.read_text(encoding="utf-8") == preserved

        path = directory_path / "current.json"
        store = LocalAccountDataStore(path)
        original = _persisted_account()
        renamed = store.commit_account(replace(original, user_alias="Renamed", provenance=manual_provenance("account-alias")), route="/accounts", idempotency_key="account-alias", request_digest=_digest("account", "alias"), expected_revision=None)
        store.commit_account(replace(renamed, manual_history_complete=True, provenance=manual_provenance("account-history")), route="/accounts", idempotency_key="account-history", request_digest=_digest("account", "history"), expected_revision=1)
        valid_current = path.read_text(encoding="utf-8")
        for field, replacement in mutations:
            malformed = json.loads(valid_current)
            malformed["accountRevisions"][0][1][field] = replacement
            path.write_text(json.dumps(malformed), encoding="utf-8")
            preserved = path.read_text(encoding="utf-8")
            with raises(AccountDataError, STORE_UNAVAILABLE):
                LocalAccountDataStore(path)
            assert path.read_text(encoding="utf-8") == preserved


def test_restart_preserves_manual_nickname_history_attestation_revisions_and_receipt_replays_exactly():
    with TemporaryDirectory() as directory:
        path = Path(directory) / "accounts.json"
        store = LocalAccountDataStore(path)
        created = _persisted_account(reference="account-create")
        renamed = store.commit_account(created, route="/accounts", idempotency_key="account-create", request_digest=_digest("account", "create"), expected_revision=None)
        nickname = replace(renamed, user_alias="Retained nickname", provenance=manual_provenance("account-nickname"))
        nickname_saved = store.commit_account(nickname, route="/accounts", idempotency_key="account-nickname", request_digest=_digest("account", "nickname"), expected_revision=1)
        attested = replace(nickname_saved, manual_history_complete=True, provenance=manual_provenance("account-history"))
        attested_saved = store.commit_account(attested, route="/accounts", idempotency_key="account-history", request_digest=_digest("account", "history"), expected_revision=2)
        before = owner_facts(store, "owner-a", "portfolio-a")
        restarted = LocalAccountDataStore(path)
        after = owner_facts(restarted, "owner-a", "portfolio-a")
        assert after["accountRevisions"] == before["accountRevisions"]
        assert [(item.user_alias, item.manual_history_complete, item.provenance.source_reference, item.provenance.recorded_at, item.provenance.revision) for item in restarted.account_revisions("owner-a", "acct-p", "portfolio-a")] == [(item.user_alias, item.manual_history_complete, item.provenance.source_reference, item.provenance.recorded_at, item.provenance.revision) for item in (renamed, nickname_saved, attested_saved)]
        assert restarted.commit_account(created, route="/accounts", idempotency_key="account-create", request_digest=_digest("account", "create"), expected_revision=None) == renamed
        assert restarted.commit_account(nickname, route="/accounts", idempotency_key="account-nickname", request_digest=_digest("account", "nickname"), expected_revision=1) == nickname_saved
        assert restarted.commit_account(attested, route="/accounts", idempotency_key="account-history", request_digest=_digest("account", "history"), expected_revision=2) == attested_saved


def test_schema_v1_v2_cache_fixtures_keep_durable_facts_revisions_and_receipts():
    fixtures = Path(__file__).with_name("fixtures")
    for fixture in ("account_data_schema_v1_cache.json", "account_data_schema_v2_cache.json"):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "accounts.json"
            expected = json.loads((fixtures / fixture).read_text(encoding="utf-8"))["accountRevisions"]
            path.write_text((fixtures / fixture).read_text(encoding="utf-8"), encoding="utf-8")
            path.chmod(0o600)
            store = LocalAccountDataStore(path)
            facts = owner_facts(store, "fixture-owner", "fixture-portfolio")
            assert [item["account_id"] for item in facts["accounts"]] == ["fixture-account"]
            assert [row["revisions"] for row in facts["accountRevisions"]] == expected
            assert [row["provenance"]["revision"] for row in facts["accountRevisions"][0]["revisions"]] == [1, 2]
            assert [item["fact_id"] for item in facts["openingHoldings"]] == ["fixture-holding"]
            assert [item["fact_id"] for item in facts["cashFlows"]] == ["fixture-flow"]
            replay = store.commit_account(_persisted_account(owner="fixture-owner", account_id="fixture-account", portfolio="fixture-portfolio", reference="fixture-account-v2", alias="Fixture alias v2", source_name="Fixture source"), route="/accounts", idempotency_key="fixture-account-v2", request_digest="fixture-account-v2", expected_revision=1)
            assert (replay.provenance.revision, replay.user_alias) == (2, "Fixture alias v2")


class AccountDataStoreTests(unittest.TestCase):
    """Expose each direct contract assertion to unittest discovery."""


_DIRECT_TESTS = tuple(
    (name, value)
    for name, value in list(globals().items())
    if name.startswith("test_") and callable(value)
)
for _name, _test in _DIRECT_TESTS:
    setattr(AccountDataStoreTests, _name, staticmethod(_test))
    del globals()[_name]
del _name, _test
