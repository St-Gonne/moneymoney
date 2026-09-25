"""Deterministic evidence for the isolated synthetic portfolio coverage demo."""
from __future__ import annotations

import json
import stat
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
from private_nsdl_connected_backend import (  # noqa: E402
    AS_OF_DATE,
    HDFC_BALANCED_ADVANTAGE_HOLDING_ID,
    HDFC_ACCOUNT_ID,
    HDFC_BHARAT_BOND_HOLDING_ID,
    HDFC_NIFTY_ETF_HOLDING_ID,
    INCOMPLETE_ACCOUNT_ID,
    INCOMPLETE_HOLDING_ID,
    OTHER_ACCOUNT_ID,
    OTHER_GOLD_ETF_HOLDING_ID,
    OTHER_LT_FINANCE_HOLDING_ID,
    OTHER_REC_BOND_HOLDING_ID,
    OVERLAP_ACCOUNT_ID,
    OVERLAP_HOLDING_ID,
    PORTFOLIO,
    SYNTHETIC_DATED_OBSERVATIONS,
    TOKEN,
    ZERODHA_ACCOUNT_ID,
    ZERODHA_ICICI_BANK_HOLDING_ID,
    ZERODHA_INFOSYS_HOLDING_ID,
    ZERODHA_RELIANCE_HOLDING_ID,
    US_ACCOUNT_ID,
    US_APPLE_HOLDING_ID,
    create_connected_demo_app,
)


EXPECTED_CURRENT_VALUES = {
    ZERODHA_RELIANCE_HOLDING_ID: Decimal("210000"),
    ZERODHA_INFOSYS_HOLDING_ID: Decimal("136000"),
    ZERODHA_ICICI_BANK_HOLDING_ID: Decimal("560000"),
    HDFC_BALANCED_ADVANTAGE_HOLDING_ID: Decimal("390000"),
    HDFC_NIFTY_ETF_HOLDING_ID: Decimal("110250"),
    HDFC_BHARAT_BOND_HOLDING_ID: Decimal("52500"),
    OTHER_LT_FINANCE_HOLDING_ID: Decimal("17000"),
    OTHER_REC_BOND_HOLDING_ID: Decimal("120000"),
    OTHER_GOLD_ETF_HOLDING_ID: Decimal("34000"),
    US_APPLE_HOLDING_ID: Decimal("2000"),
}
EXPECTED_HOLDING_QUANTITIES = {
    ZERODHA_RELIANCE_HOLDING_ID: Decimal("150"),
    ZERODHA_INFOSYS_HOLDING_ID: Decimal("80"),
    ZERODHA_ICICI_BANK_HOLDING_ID: Decimal("350"),
    HDFC_BALANCED_ADVANTAGE_HOLDING_ID: Decimal("3000"),
    HDFC_NIFTY_ETF_HOLDING_ID: Decimal("450"),
    HDFC_BHARAT_BOND_HOLDING_ID: Decimal("500"),
    OTHER_LT_FINANCE_HOLDING_ID: Decimal("100"),
    OTHER_REC_BOND_HOLDING_ID: Decimal("120"),
    OTHER_GOLD_ETF_HOLDING_ID: Decimal("400"),
}
EXPECTED_OBSERVATION_TOTALS = {
    date(2026, 3, 2): Decimal("1458050"),
    date(2026, 6, 1): Decimal("1517400"),
    AS_OF_DATE: Decimal("1629750"),
}
EXPECTED_US_OBSERVATIONS = {
    date(2026, 3, 2): Decimal("1800"),
    date(2026, 6, 1): Decimal("1900"),
    AS_OF_DATE: Decimal("2000"),
}
EXPECTED_ACCOUNT_RESULTS = {
    ZERODHA_ACCOUNT_ID: ("146000", "19.970496929400"),
    HDFC_ACCOUNT_ID: ("62750", "17.453648919400"),
    OTHER_ACCOUNT_ID: ("21000", "26.488659061400"),
}


def headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def query(path: str, as_of: str = AS_OF_DATE.isoformat(), account_id: str | None = None) -> str:
    suffix = f"?portfolio_id={PORTFOLIO}&as_of={as_of}"
    return f"{path}{suffix}{f'&account_id={account_id}' if account_id else ''}"


with TemporaryDirectory(prefix="moneymoney-connected-proof-") as raw_directory:
    directory = Path(raw_directory)
    data_path = directory / "connected-account-data.json"
    client = TestClient(create_connected_demo_app(data_path))

    # The actual AuthPerimeter rejects both missing credentials and an ungranted
    # portfolio before the loopback store is read.
    assert client.get(f"/api/nsdl/account-data?portfolio_id={PORTFOLIO}").status_code == 401
    assert client.get("/api/nsdl/account-data?portfolio_id=ungranted-demo", headers=headers()).status_code == 403

    facts = client.get(f"/api/nsdl/account-data?portfolio_id={PORTFOLIO}", headers=headers())
    assert facts.status_code == 200
    assert {account["account_id"] for account in facts.json()["accounts"]} == {HDFC_ACCOUNT_ID, INCOMPLETE_ACCOUNT_ID, OTHER_ACCOUNT_ID, OVERLAP_ACCOUNT_ID, US_ACCOUNT_ID, ZERODHA_ACCOUNT_ID}
    history_flags = {account["account_id"]: account["manual_history_complete"] for account in facts.json()["accounts"]}
    assert history_flags[INCOMPLETE_ACCOUNT_ID] is False
    assert history_flags[OVERLAP_ACCOUNT_ID] is False
    assert all(history_flags[account_id] is True for account_id in (HDFC_ACCOUNT_ID, OTHER_ACCOUNT_ID, US_ACCOUNT_ID, ZERODHA_ACCOUNT_ID))
    assert {holding["fact_id"] for holding in facts.json()["openingHoldings"]} == set(EXPECTED_CURRENT_VALUES) | {INCOMPLETE_HOLDING_ID, OVERLAP_HOLDING_ID}
    assert len(facts.json()["cashFlows"]) == 10

    # Independent fixture reconciliation: the manual holdings and external cash
    # flows remain source facts; current values and returns remain service output.
    observed = SYNTHETIC_DATED_OBSERVATIONS[AS_OF_DATE]
    assert sum((EXPECTED_HOLDING_QUANTITIES[key] * observed[key] for key in EXPECTED_HOLDING_QUANTITIES), Decimal("0")) == Decimal("1629750")
    assert sum((Decimal(flow["amount"]) for flow in facts.json()["cashFlows"] if flow["currency"] == "INR"), Decimal("0")) == Decimal("-1400000")

    summary = client.get(f"/api/nsdl/portfolio?portfolio_id={PORTFOLIO}", headers=headers())
    assert summary.status_code == 200
    snapshot = summary.json()["snapshot"]
    assert snapshot["coverage"]["complete"] is True
    assert len(snapshot["holdings"]) == 2
    assert len(snapshot["accounts"]) == 1
    assert snapshot["parserVersion"] == "synthetic-imported-statement-v1"
    assert snapshot["coverage"]["warnings"] == ["Synthetic imported-statement evidence; no actual PDF was used in this local demo."]

    for observed_date, expected_total in EXPECTED_OBSERVATION_TOTALS.items():
        dated = client.get(query("/api/nsdl/valuation", observed_date.isoformat()), headers=headers())
        assert dated.status_code == 200
        calculated = [row for row in dated.json()["holdings"] if row["status"] == "CALCULATED" and row.get("reconciliationStatus") == "CLEAR"]
        assert len(calculated) == len(EXPECTED_CURRENT_VALUES)
        assert sum((Decimal(row["currentValue"]) for row in calculated if row["currency"] == "INR"), Decimal("0")) == expected_total
        assert sum((Decimal(row["currentValue"]) for row in calculated if row["currency"] == "USD"), Decimal("0")) == EXPECTED_US_OBSERVATIONS[observed_date]
        assert {row["source"] for row in calculated} == {"SYNTHETIC_FIXTURE"}
        assert {row["priceStatus"] for row in calculated} == {"SYNTHETIC_DATED_OBSERVATION"}

    valuation = client.get(query("/api/nsdl/valuation"), headers=headers())
    performance = client.get(query("/api/nsdl/performance"), headers=headers())
    assert valuation.status_code == performance.status_code == 200
    values = {row["holdingId"]: Decimal(row["currentValue"]) for row in valuation.json()["holdings"] if row["status"] == "CALCULATED" and row.get("reconciliationStatus") == "CLEAR"}
    assert values == EXPECTED_CURRENT_VALUES
    assert sum(value for holding_id, value in values.items() if holding_id != US_APPLE_HOLDING_ID) == Decimal("1629750")
    assert values[US_APPLE_HOLDING_ID] == Decimal("2000")
    assert valuation.json()["summaryByCurrency"] == [
        {"currency": "INR", "calculatedValue": "1629750", "statementValue": "400000", "totalIncludedValue": "2029750", "calculatedAsOf": "2026-09-09", "statementAsOf": "2026-09-09", "excludedForReconciliationCount": 1},
        {"currency": "USD", "calculatedValue": "2000", "statementValue": "0", "totalIncludedValue": "2000", "calculatedAsOf": "2026-09-09", "statementAsOf": None, "excludedForReconciliationCount": 0},
    ]
    assert performance.json()["coverage"] == {"historyComplete": False, "cashflowCount": 10, "reasons": ["RECONCILIATION_REQUIRED", "MISSING_HISTORY", "MIXED_CURRENCY"], "scope": "manual_complete_history_only"}
    assert performance.json()["gain"] == {"status": "INSUFFICIENT_DATA", "reason": "RECONCILIATION_REQUIRED"}
    assert performance.json()["xirr"] == {"status": "UNAVAILABLE", "reason": "RECONCILIATION_REQUIRED"}

    for account_id, (expected_gain, expected_xirr) in EXPECTED_ACCOUNT_RESULTS.items():
        account_performance = client.get(query("/api/nsdl/performance", account_id=account_id), headers=headers())
        assert account_performance.status_code == 200
        assert account_performance.json()["coverage"]["historyComplete"] is True
        assert account_performance.json()["gain"] == {"status": "CALCULATED", "value": expected_gain, "currency": "INR"}
        assert account_performance.json()["xirr"] == {"status": "CALCULATED", "valuePct": expected_xirr}

    us_performance = client.get(query("/api/nsdl/performance", account_id=US_ACCOUNT_ID), headers=headers())
    assert us_performance.status_code == 200
    assert us_performance.json()["coverage"] == {"historyComplete": True, "cashflowCount": 1, "reasons": [], "scope": "manual_complete_history_only"}
    assert us_performance.json()["gain"] == {"status": "CALCULATED", "value": "400", "currency": "USD"}
    assert us_performance.json()["xirr"]["status"] == "CALCULATED"

    incomplete_account = client.get(query("/api/nsdl/performance", account_id=INCOMPLETE_ACCOUNT_ID), headers=headers())
    assert incomplete_account.status_code == 200
    assert incomplete_account.json()["coverage"] == {"historyComplete": False, "cashflowCount": 0, "reasons": ["MISSING_HISTORY", "MISSING_PRICE", "NON_POSITIVE_TERMINAL_VALUE"], "scope": "manual_complete_history_only"}
    assert incomplete_account.json()["gain"] == {"status": "INSUFFICIENT_DATA", "reason": "MISSING_HISTORY"}
    assert incomplete_account.json()["xirr"] == {"status": "UNAVAILABLE", "reason": "MISSING_HISTORY"}

    overlap = next(row for row in valuation.json()["holdings"] if row["holdingId"] == OVERLAP_HOLDING_ID)
    assert overlap["status"] == "CALCULATED"
    assert overlap["currentValue"] == "250000"
    assert overlap["reconciliationStatus"] == "REVIEW_REQUIRED"

    # This deliberately has no synthetic observation. The existing numerical
    # service leaves the secondary/incomplete path value-free and names why.
    incomplete = client.get(query("/api/nsdl/performance", "2026-04-01"), headers=headers())
    assert incomplete.status_code == 200
    assert incomplete.json()["coverage"] == {"historyComplete": False, "cashflowCount": 5, "reasons": ["MISSING_HISTORY", "MIXED_CURRENCY", "MISSING_PRICE", "NON_POSITIVE_TERMINAL_VALUE"], "scope": "manual_complete_history_only"}
    assert incomplete.json()["gain"] == {"status": "INSUFFICIENT_DATA", "reason": "MISSING_HISTORY"}
    assert incomplete.json()["xirr"] == {"status": "UNAVAILABLE", "reason": "MISSING_HISTORY"}

    assert stat.S_IMODE(data_path.stat().st_mode) == 0o600
    restored = TestClient(create_connected_demo_app(data_path))
    restored_facts = restored.get(f"/api/nsdl/account-data?portfolio_id={PORTFOLIO}", headers=headers())
    assert restored_facts.status_code == 200
    assert {account["account_id"] for account in restored_facts.json()["accounts"]} == {HDFC_ACCOUNT_ID, INCOMPLETE_ACCOUNT_ID, OTHER_ACCOUNT_ID, OVERLAP_ACCOUNT_ID, US_ACCOUNT_ID, ZERODHA_ACCOUNT_ID}
    assert {holding["fact_id"] for holding in restored_facts.json()["openingHoldings"]} == set(EXPECTED_CURRENT_VALUES) | {INCOMPLETE_HOLDING_ID, OVERLAP_HOLDING_ID}
    assert {flow["fact_id"] for flow in restored_facts.json()["cashFlows"]} == {flow["fact_id"] for flow in facts.json()["cashFlows"]}
    assert restored.get(query("/api/nsdl/valuation"), headers=headers()).json() == valuation.json()
    assert restored.get(query("/api/nsdl/performance"), headers=headers()).json() == performance.json()
    assert json.loads(data_path.read_text(encoding="utf-8"))["schemaVersion"] == 3

print("V3_SYNTHETIC_PORTFOLIO_COVERAGE_DEMO=PASS")
