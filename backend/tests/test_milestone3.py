"""
Unit and Integration Test Suite for Milestone 3
Covers:
1. Gate 3: Fail-Closed Mathematical Validation Gate (Zerodha, HDFC, CAS, Schwab, math tampering)
2. Gate 4: Reconciliation Gate (SHA-256 fingerprinting, boundary hashing, deduplication & idempotency)
3. Forex Engine: Historical RBI reference rates, Rule 115 compliance, weekend lookback, USD->INR conversion
4. FIFO Tax Engine: Finance Act 2024 capital gains rules (12.5% LTCG, 20% STCG, ₹1.25L Sec 112A exemption, 24m US threshold, Sec 50AA debt MF, SGB Sec 47)
5. Canonical Ledger Service: End-to-end multi-gate orchestration, portfolio isolation, ledger persistence
6. FastAPI Endpoints: Statement ingestion, ledger transactions, tax lots, capital gains, and portfolio queries
"""

import io
import unittest
from datetime import date, datetime
from decimal import Decimal

from backend.app.config import (
    ERR_VALIDATION_CAS_CLOSING_BALANCE,
    ERR_VALIDATION_CAS_UNIT_CONTINUITY,
    ERR_VALIDATION_GST_MISMATCH,
    ERR_VALIDATION_MATH_MISMATCH,
    ERR_VALIDATION_SCHWAB_MATH,
    MATH_INVARIANT_TOLERANCE,
    BrokerInstitution,
)
from backend.app.engines.fifo_tax_engine import FIFOTaxEngine
from backend.app.engines.forex_engine import ForexEngine, convert_usd_to_inr, lookup_rbi_rate
from backend.app.engines.ledger_service import LedgerService, get_ledger_service
from backend.app.gates.identity_gate import evaluate_identity_gate
from backend.app.gates.layout_gate import evaluate_layout_gate
from backend.app.gates.reconciliation_gate import ReconciliationGate, evaluate_reconciliation_gate
from backend.app.gates.validation_gate import ValidationGate, evaluate_validation_gate
from backend.app.main import app
from backend.app.models.cas import CasTransactionRecord, NormalizedCasScheme, NormalizedCasStatement
from backend.app.models.contract_note import (
    BrokerLevyBreakdown,
    NormalizedContractNote,
    NormalizedTradeItem,
    TradeAction,
    TradedSegment,
)
from backend.app.models.email import ExtractedAttachment, InboundEmailPayload
from backend.app.models.ledger import CanonicalTransaction, TaxAssetType
from backend.app.models.schwab import NormalizedSchwabRecord, NormalizedSchwabStatement
from backend.tests.fixtures.sample_cas import build_corrupted_cams_statement, build_valid_cams_statement
from backend.tests.fixtures.sample_emails import create_hdfc_mime, create_schwab_mime, create_zerodha_mime
from backend.tests.fixtures.sample_hdfc import build_valid_hdfc_statement
from backend.tests.fixtures.sample_schwab import build_valid_schwab_statement
from backend.tests.fixtures.sample_zerodha import build_valid_zerodha_statement

try:
    from fastapi.testclient import TestClient
except ImportError:
    TestClient = None


class TestMilestone3ValidationGate(unittest.TestCase):
    """Tests for Gate 3: Fail-Closed Mathematical Invariant Checker."""

    def setUp(self):
        self.gate = ValidationGate()

    def test_zerodha_math_validation_pass(self):
        stmt = build_valid_zerodha_statement()
        res = self.gate.evaluate(stmt)
        self.assertTrue(res.passed)
        self.assertLessEqual(res.discrepancy, MATH_INVARIANT_TOLERANCE)

    def test_zerodha_math_tampering_fails_closed(self):
        stmt = build_valid_zerodha_statement()
        stmt.net_settlement_amount += Decimal("10.00")  # Tamper by ₹10
        res = self.gate.evaluate(stmt)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_VALIDATION_MATH_MISMATCH)
        self.assertGreater(res.discrepancy, Decimal("9.00"))

    def test_zerodha_penny_shaving_fails_closed(self):
        stmt = build_valid_zerodha_statement()
        stmt.net_settlement_amount += Decimal("0.05")  # Shave 5 paise
        res = self.gate.evaluate(stmt)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_VALIDATION_MATH_MISMATCH)

    def test_hdfc_math_validation_pass(self):
        stmt = build_valid_hdfc_statement()
        res = self.gate.evaluate(stmt)
        self.assertTrue(res.passed)
        self.assertLessEqual(res.discrepancy, MATH_INVARIANT_TOLERANCE)

    def test_hdfc_math_tampering_fails_closed(self):
        stmt = build_valid_hdfc_statement()
        stmt.net_amount -= Decimal("50.00")
        res = self.gate.evaluate(stmt)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_VALIDATION_MATH_MISMATCH)

    def test_cas_unit_continuity_pass(self):
        stmt = build_valid_cams_statement()
        res = self.gate.evaluate(stmt)
        self.assertTrue(res.passed)
        self.assertEqual(res.discrepancy, Decimal("0.00"))

    def test_cas_corrupted_unit_continuity_fails_closed(self):
        stmt = build_corrupted_cams_statement()
        res = self.gate.evaluate(stmt)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_VALIDATION_CAS_UNIT_CONTINUITY)

    def test_schwab_math_validation_pass(self):
        stmt = build_valid_schwab_statement()
        res = self.gate.evaluate(stmt)
        self.assertTrue(res.passed)
        self.assertEqual(res.discrepancy, Decimal("0.00"))

    def test_schwab_math_tampering_fails_closed(self):
        stmt = build_valid_schwab_statement()
        stmt.rows[0].amount += Decimal("1.00")  # Tamper trade 1 cashflow
        res = self.gate.evaluate(stmt)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_VALIDATION_SCHWAB_MATH)


class TestMilestone3ReconciliationGate(unittest.TestCase):
    """Tests for Gate 4: SHA-256 Fingerprinting, Statement Boundary Hashing, and Deduplication."""

    def setUp(self):
        self.recon = ReconciliationGate()

    def test_deterministic_fingerprint_generation(self):
        fp1 = self.recon.compute_transaction_fingerprint(
            portfolio_id="port_primary",
            institution="ZERODHA",
            isin_or_symbol="INE155A01022",
            trade_date="2024-08-14",
            action="BUY",
            quantity=Decimal("800.00"),
            unit_price=Decimal("480.00"),
            order_or_trade_id="84920194",
        )
        fp2 = self.recon.compute_transaction_fingerprint(
            portfolio_id="port_primary",
            institution="ZERODHA",
            isin_or_symbol="INE155A01022",
            trade_date="2024-08-14",
            action="BUY",
            quantity=Decimal("800.00"),
            unit_price=Decimal("480.00"),
            order_or_trade_id="84920194",
        )
        self.assertEqual(fp1, fp2)
        self.assertEqual(len(fp1), 64)

    def test_deterministic_boundary_hash_generation(self):
        h1 = self.recon.compute_statement_hash(
            institution="ZERODHA",
            account_or_folio="ZR1102",
            start_date="2024-08-14",
            end_date="2024-08-14",
            trades_count=2,
            net_amount=Decimal("-534633.45"),
        )
        h2 = self.recon.compute_statement_hash(
            institution="ZERODHA",
            account_or_folio="ZR1102",
            start_date="2024-08-14",
            end_date="2024-08-14",
            trades_count=2,
            net_amount=Decimal("-534633.45"),
        )
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_reingestion_yields_zero_duplicate_writes(self):
        stmt = build_valid_zerodha_statement()
        # Ingestion 1
        res1 = self.recon.reconcile(stmt, portfolio_id="port_primary", client_pan="KLMNO9012P")
        self.assertFalse(res1.is_duplicate_statement)
        self.assertEqual(res1.new_transactions_count, 2)
        self.assertEqual(res1.duplicate_transactions_count, 0)

        # Ingestion 2 (exact re-import)
        res2 = self.recon.reconcile(stmt, portfolio_id="port_primary", client_pan="KLMNO9012P")
        self.assertTrue(res2.is_duplicate_statement)
        self.assertTrue(res2.idempotent_noop)
        self.assertEqual(res2.new_transactions_count, 0)
        self.assertEqual(res2.duplicate_transactions_count, 2)


class TestMilestone3ForexEngine(unittest.TestCase):
    """Tests for RBI Forex Engine: Spot, Rule 115, and Currency Conversions."""

    def setUp(self):
        self.engine = ForexEngine()

    def test_spot_rbi_reference_rate_lookup(self):
        rate = self.engine.lookup_rate(date(2023, 5, 18), mode="SPOT")
        self.assertEqual(rate, Decimal("82.35"))

    def test_rule_115_preceding_month_end_lookup(self):
        # Trade on 18-May-2023 -> Preceding month end is 30-Apr-2023 -> Rate 81.80
        rate = self.engine.lookup_rate(date(2023, 5, 18), mode="RULE_115")
        self.assertEqual(rate, Decimal("81.80"))

    def test_rule_115_january_trade_preceding_december(self):
        # Trade on 15-Jan-2024 -> Preceding month end is 31-Dec-2023 -> Rate 83.12 (2023-12-29)
        rate = self.engine.lookup_rate(date(2024, 1, 15), mode="RULE_115")
        self.assertEqual(rate, Decimal("83.12"))

    def test_weekend_lookback_resolution(self):
        # Sunday 11-Aug-2024 falls back to Friday rate
        rate = self.engine.lookup_rate(date(2024, 8, 11), mode="SPOT")
        self.assertGreater(rate, Decimal("80.00"))

    def test_usd_amount_conversion_to_inr(self):
        cost_inr = self.engine.convert_usd_to_inr(
            usd_amount=Decimal("9360.00"),
            tx_date=date(2023, 5, 18),
            mode="SPOT",
        )
        self.assertEqual(cost_inr, Decimal("770796.00"))

    def test_dividend_and_withholding_tax_rule_115_conversion(self):
        gross_inr, tax_inr, rate = self.engine.convert_dividend_and_withholding(
            gross_dividend_usd=Decimal("24.00"),
            tax_withheld_usd=Decimal("6.00"),
            tx_date=date(2023, 11, 15),
        )
        self.assertGreater(gross_inr, Decimal("1900.00"))
        self.assertGreater(tax_inr, Decimal("450.00"))
        self.assertEqual(rate, Decimal("82.75"))


class TestMilestone3FIFOTaxEngine(unittest.TestCase):
    """Tests for FIFO Tax Lot and Capital Gains Accounting under Finance Act 2024."""

    def setUp(self):
        self.engine = FIFOTaxEngine()

    def test_indian_equity_buy_and_stcg_20pct_under_12m(self):
        self.engine.buy_lot(
            portfolio_id="port_primary",
            asset_id="INE155A01022",
            asset_type="EQUITY",
            buy_date=date(2024, 3, 1),
            quantity=Decimal("100"),
            price=Decimal("450.00"),
        )
        disps = self.engine.sell_units(
            portfolio_id="port_primary",
            asset_id="INE155A01022",
            asset_type="EQUITY",
            sell_date=date(2024, 8, 14),
            quantity=Decimal("100"),
            sell_price=Decimal("550.00"),
        )
        self.assertEqual(len(disps), 1)
        self.assertFalse(disps[0]["is_long_term"])
        self.assertEqual(disps[0]["tax_rate_pct"], Decimal("20.00"))
        self.assertEqual(disps[0]["realized_gain_inr"], Decimal("10000.00"))
        self.assertEqual(disps[0]["estimated_tax_inr"], Decimal("2000.00"))

    def test_indian_equity_ltcg_12_5pct_over_12m(self):
        self.engine.buy_lot(
            portfolio_id="port_primary",
            asset_id="INE155A01022",
            asset_type="EQUITY",
            buy_date=date(2023, 1, 15),
            quantity=Decimal("100"),
            price=Decimal("400.00"),
        )
        disps = self.engine.sell_units(
            portfolio_id="port_primary",
            asset_id="INE155A01022",
            asset_type="EQUITY",
            sell_date=date(2024, 8, 14),
            quantity=Decimal("100"),
            sell_price=Decimal("600.00"),
        )
        self.assertEqual(len(disps), 1)
        self.assertTrue(disps[0]["is_long_term"])
        self.assertEqual(disps[0]["tax_rate_pct"], Decimal("12.50"))
        self.assertEqual(disps[0]["realized_gain_inr"], Decimal("20000.00"))
        self.assertEqual(disps[0]["estimated_tax_inr"], Decimal("2500.00"))

    def test_section_112a_125000_annual_exemption(self):
        # Lot 1: ₹80,000 LTCG
        self.engine.buy_lot("port_primary", "INE155", "EQUITY", date(2022, 1, 1), Decimal("100"), Decimal("200.00"))
        self.engine.sell_units("port_primary", "INE155", "EQUITY", date(2024, 8, 1), Decimal("100"), Decimal("1000.00"))

        # Lot 2: ₹70,000 LTCG
        self.engine.buy_lot("port_primary", "INE009", "EQUITY", date(2022, 1, 1), Decimal("100"), Decimal("500.00"))
        self.engine.sell_units("port_primary", "INE009", "EQUITY", date(2024, 8, 1), Decimal("100"), Decimal("1200.00"))

        summary = self.engine.compute_capital_gains_summary("port_primary", "FY2024-25")
        self.assertEqual(summary.total_ltcg_inr, Decimal("150000.00"))
        self.assertEqual(summary.section_112a_exemption_inr, Decimal("125000.00"))
        self.assertEqual(summary.taxable_ltcg_inr, Decimal("25000.00"))
        self.assertEqual(summary.total_tax_inr, Decimal("3125.00"))

    def test_foreign_equity_24_month_threshold(self):
        # 18 months holding -> STCG at slab rate (30%)
        self.engine.buy_lot("port_primary", "NVDA", "US_EQUITY", date(2023, 1, 15), Decimal("50"), Decimal("60.00"), forex_rate=Decimal("82.00"))
        disps = self.engine.sell_units("port_primary", "NVDA", "US_EQUITY", date(2024, 7, 15), Decimal("50"), Decimal("120.00"), forex_rate=Decimal("83.50"))
        self.assertFalse(disps[0]["is_long_term"])
        self.assertEqual(disps[0]["tax_rate_pct"], Decimal("30.00"))

    def test_debt_mutual_fund_section_50aa_slab_rate(self):
        # Debt MF acquired post 1-Apr-2023 -> STCG at slab rate (30%) regardless of holding period
        self.engine.buy_lot("port_primary", "DEBT_MF_01", "DEBT_MUTUAL_FUND", date(2023, 5, 1), Decimal("100"), Decimal("100.00"))
        disps = self.engine.sell_units("port_primary", "DEBT_MF_01", "DEBT_MUTUAL_FUND", date(2024, 8, 14), Decimal("100"), Decimal("110.00"))
        self.assertFalse(disps[0]["is_long_term"])
        self.assertEqual(disps[0]["tax_rate_pct"], Decimal("30.00"))

    def test_sgb_maturity_tax_exemption_section_47(self):
        # SGB redemption at maturity -> 100% tax exempt
        self.engine.buy_lot("port_father", "IN0020210040", "SGB_MATURITY", date(2021, 5, 20), Decimal("100"), Decimal("4777.00"))
        disps = self.engine.sell_units("port_father", "IN0020210040", "SGB_MATURITY", date(2029, 5, 20), Decimal("100"), Decimal("7500.00"))
        self.assertTrue(disps[0]["is_long_term"])
        self.assertEqual(disps[0]["tax_rate_pct"], Decimal("0.00"))
        self.assertEqual(disps[0]["estimated_tax_inr"], Decimal("0.00"))

    def test_oversell_raises_value_error(self):
        self.engine.buy_lot("port_primary", "INE155", "EQUITY", date(2023, 1, 1), Decimal("50"), Decimal("100.00"))
        with self.assertRaises(ValueError):
            self.engine.sell_units("port_primary", "INE155", "EQUITY", date(2024, 1, 1), Decimal("100"), Decimal("200.00"))


class TestMilestone3LedgerService(unittest.TestCase):
    """Tests for Canonical Ledger Service orchestration and persistence."""

    def setUp(self):
        self.ledger_svc = LedgerService()
        self.ledger_svc.reset_state()

    def test_ingest_zerodha_mime_through_all_gates(self):
        z_stmt = build_valid_zerodha_statement()
        mime_bytes = create_zerodha_mime(
            forwarder="alex.taylor@example.com",
            pdf_bytes=z_stmt.to_raw_text().encode("utf-8"),
        )
        res = self.ledger_svc.ingest_inbound_email(mime_bytes, forwarder_email="alex.taylor@example.com")
        self.assertTrue(res["success"])
        self.assertEqual(res["portfolio_id"], "port_primary")
        self.assertEqual(res["new_transactions_committed"], 2)

        # Check transactions in ledger
        txs = self.ledger_svc.get_transactions(portfolio_id="port_primary")
        self.assertEqual(len(txs), 2)

        # Check tax lots in engine
        lots = self.ledger_svc.get_active_tax_lots(portfolio_id="port_primary")
        self.assertEqual(len(lots), 2)

    def test_reingest_email_produces_zero_duplicate_ledger_entries(self):
        z_stmt = build_valid_zerodha_statement()
        mime_bytes = create_zerodha_mime(
            forwarder="alex.taylor@example.com",
            pdf_bytes=z_stmt.to_raw_text().encode("utf-8"),
        )
        # Ingest 1
        res1 = self.ledger_svc.ingest_inbound_email(mime_bytes, forwarder_email="alex.taylor@example.com")
        self.assertEqual(res1["new_transactions_committed"], 2)

        # Ingest 2 (re-import)
        res2 = self.ledger_svc.ingest_inbound_email(mime_bytes, forwarder_email="alex.taylor@example.com")
        self.assertEqual(res2["new_transactions_committed"], 0)
        self.assertEqual(res2["duplicate_transactions_skipped"], 2)

        # Ledger remains exactly 2 transactions
        txs = self.ledger_svc.get_transactions(portfolio_id="port_primary")
        self.assertEqual(len(txs), 2)

    def test_multi_family_portfolio_isolation(self):
        # Alex Zerodha
        z_stmt = build_valid_zerodha_statement()
        mime_alex = create_zerodha_mime(
            "alex.taylor@example.com",
            pdf_bytes=z_stmt.to_raw_text().encode("utf-8"),
        )
        self.ledger_svc.ingest_inbound_email(mime_alex, "alex.taylor@example.com")

        # Robert HDFC
        h_stmt = build_valid_hdfc_statement()
        mime_robert = create_hdfc_mime(
            "robert.taylor@example.com",
            pdf_bytes=h_stmt.to_raw_text().encode("utf-8"),
        )
        self.ledger_svc.ingest_inbound_email(mime_robert, "robert.taylor@example.com")

        alex_txs = self.ledger_svc.get_transactions(portfolio_id="port_primary")
        robert_txs = self.ledger_svc.get_transactions(portfolio_id="port_father")

        self.assertEqual(len(alex_txs), 2)
        self.assertEqual(len(robert_txs), 1)
        self.assertEqual(alex_txs[0].broker, "ZERODHA")
        self.assertEqual(robert_txs[0].broker, "HDFC_SECURITIES")


class TestMilestone3FastAPIEndpoints(unittest.TestCase):
    """Tests for FastAPI HTTP Endpoints."""

    def setUp(self):
        if TestClient is not None and app is not None:
            self.client = TestClient(app)
        else:
            self.client = None
        get_ledger_service().reset_state()

    def test_health_endpoints(self):
        if not self.client:
            self.skipTest("FastAPI TestClient not available")
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "HEALTHY")

        resp_api = self.client.get("/api/health")
        self.assertEqual(resp_api.status_code, 200)

    def test_inbound_email_endpoint_success(self):
        if not self.client:
            self.skipTest("FastAPI TestClient not available")
        z_stmt = build_valid_zerodha_statement()
        mime_bytes = create_zerodha_mime(
            forwarder="alex.taylor@example.com",
            pdf_bytes=z_stmt.to_raw_text().encode("utf-8"),
        )
        resp = self.client.post(
            "/api/statements/inbound-mime",
            files={"raw_mime": ("forwarded.eml", mime_bytes, "message/rfc822")},
            data={"forwarder_email": "alex.taylor@example.com"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["portfolio_id"], "port_primary")

    def test_inbound_email_unauthorized_forwarder_fails(self):
        if not self.client:
            self.skipTest("FastAPI TestClient not available")
        mime_bytes = create_zerodha_mime(forwarder="intruder@badactor.com")
        resp = self.client.post(
            "/api/statements/inbound-mime",
            files={"raw_mime": ("forwarded.eml", mime_bytes, "message/rfc822")},
            data={"forwarder_email": "intruder@badactor.com"},
        )
        self.assertEqual(resp.status_code, 400)

    def test_ledger_query_endpoints(self):
        if not self.client:
            self.skipTest("FastAPI TestClient not available")
        # Ingest one statement
        z_stmt = build_valid_zerodha_statement()
        mime_bytes = create_zerodha_mime(
            forwarder="alex.taylor@example.com",
            pdf_bytes=z_stmt.to_raw_text().encode("utf-8"),
        )
        self.client.post(
            "/api/statements/inbound-mime",
            files={"raw_mime": ("forwarded.eml", mime_bytes, "message/rfc822")},
            data={"forwarder_email": "alex.taylor@example.com"},
        )


        # Query transactions
        resp_tx = self.client.get("/api/ledger/transactions?portfolio_id=port_primary")
        self.assertEqual(resp_tx.status_code, 200)
        self.assertEqual(resp_tx.json()["count"], 2)

        # Query tax lots
        resp_lots = self.client.get("/api/ledger/tax-lots?portfolio_id=port_primary")
        self.assertEqual(resp_lots.status_code, 200)
        self.assertEqual(resp_lots.json()["count"], 2)

        # Query portfolio balances
        resp_port = self.client.get("/api/ledger/portfolio?portfolio_id=port_primary")
        self.assertEqual(resp_port.status_code, 200)
        self.assertEqual(resp_port.json()["count"], 2)

        # Query capital gains
        resp_cg = self.client.get("/api/ledger/capital-gains?portfolio_id=port_primary&financial_year=FY2024-25")
        self.assertEqual(resp_cg.status_code, 200)
        self.assertIn("capital_gains_summary", resp_cg.json())


if __name__ == "__main__":
    unittest.main()
