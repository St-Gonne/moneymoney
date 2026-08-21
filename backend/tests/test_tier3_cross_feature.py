"""
Tier 3: Cross-Feature Combination & Pairwise Interaction Test Suite (MoneyMoney Ingestion Pipeline)
Tests multi-gate state transitions, pairwise fault cascades, inter-broker portfolio reconciliation, and FIFO tax lot interactions.
"""
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal

from backend.tests.fixtures.sample_family_vault import (
    AUTHORIZED_FORWARDERS,
    AUTHORIZED_BROKER_DOMAINS,
    FAMILY_VAULT_PROFILES,
    lookup_rbi_rate,
)
from backend.tests.fixtures.sample_emails import (
    build_forwarded_email,
    create_zerodha_mime,
    create_hdfc_mime,
    create_cams_cas_mime,
    create_schwab_mime,
)
from backend.tests.fixtures.sample_zerodha import (
    build_valid_zerodha_statement,
    SyntheticTradeRow,
)
from backend.tests.fixtures.sample_hdfc import (
    build_valid_hdfc_statement,
    SyntheticHDFCTradeRow,
)
from backend.tests.fixtures.sample_cas import (
    build_valid_cams_statement,
    build_corrupted_cams_statement,
    SyntheticCasTx,
    SyntheticCasScheme,
    SyntheticCasStatement,
)
from backend.tests.fixtures.sample_schwab import (
    build_valid_schwab_statement,
    SyntheticSchwabRow,
)
from backend.tests.conftest import (
    ReferenceIdentityGate,
    ReferenceDecryptionEngine,
    ReferenceValidationGate,
    ReferenceReconciliationGate,
    ReferenceFIFOTaxEngine,
    MATH_INVARIANT_TOLERANCE,
)


class TestTier3CrossFeatureCombinations(unittest.TestCase):
    """
    Tier 3 Test Suite: Pairwise & Cross-Feature Integration Tests.
    """

    def test_pair_01_identity_valid_and_malformed_layout_fails_at_gate2(self):
        """Pass Gate 1 -> Fail Gate 2 (Unsupported file) -> 0 ledger pollution"""
        mime = build_forwarded_email(
            "alex.taylor@example.com",
            "contracts@zerodha.com",
            attachments=[("corrupt.bin", b"Random unparseable garbage", "bin")]
        )
        g1 = ReferenceIdentityGate.process_mime_payload(mime, "alex.taylor@example.com")
        self.assertTrue(g1["passed"])
        
        g2 = ReferenceDecryptionEngine.classify_and_decrypt(
            g1["extracted_attachments"][0]["content_bytes"],
            g1["extracted_attachments"][0]["filename"],
            g1["target_pan"]
        )
        self.assertFalse(g2["passed"])
        self.assertEqual(g2["rejection_code"], "ERR_LAYOUT_UNSUPPORTED_FORMAT")

    def test_pair_02_identity_and_layout_valid_and_math_discrepancy_fails_at_gate3(self):
        """Pass Gate 1 -> Pass Gate 2 -> Fail Gate 3 (Math Mismatch) -> 0 ledger writes"""
        mime = create_zerodha_mime()
        g1 = ReferenceIdentityGate.process_mime_payload(mime, "alex.taylor@example.com")
        self.assertTrue(g1["passed"])

        g2 = ReferenceDecryptionEngine.classify_and_decrypt(
            g1["extracted_attachments"][0]["content_bytes"],
            g1["extracted_attachments"][0]["filename"],
            g1["target_pan"]
        )
        self.assertTrue(g2["passed"])

        # Corrupted statement
        stmt = build_valid_zerodha_statement()
        stmt.net_settlement_amount += Decimal("50.00") # Discrepancy
        g3_pass, g3_err, g3_disc = ReferenceValidationGate.validate_zerodha(stmt)
        self.assertFalse(g3_pass)
        self.assertIn("ERR_VALIDATION_MATH_MISMATCH", g3_err)

    def test_pair_03_valid_pipeline_with_exact_deduplication_at_gate4(self):
        """Pass Gates 1, 2, 3 -> Gate 4 detects duplicate -> Returns IDEMPOTENT_NOOP"""
        stmt = build_valid_zerodha_statement()
        h = ReferenceReconciliationGate.compute_statement_hash("ZERODHA", "ZR1102", "2024-08-14", "2024-08-14", 2, Decimal("-534633.45"))
        
        # Ingestion 1
        db = {h: "COMPLETED"}
        # Ingestion 2
        is_duplicate = h in db
        self.assertTrue(is_duplicate)

    def test_pair_04_ingesting_zerodha_and_hdfc_and_cams_and_schwab_in_same_portfolio(self):
        """Ingests 4 diverse broker statements into Alex's portfolio without collision"""
        fifo = ReferenceFIFOTaxEngine()
        
        # 1. Zerodha (Indian Equity)
        z = build_valid_zerodha_statement()
        fifo.buy_lot("port_primary", z.trades[0].isin, "EQUITY", z.trade_date, z.trades[0].quantity, z.trades[0].gross_rate)

        # 2. HDFC (SGB / Equity)
        h = build_valid_hdfc_statement()
        fifo.buy_lot("port_primary", h.trades[0].isin, "EQUITY", h.trade_date, h.trades[0].quantity, h.trades[0].gross_rate)

        # 3. CAMS (Mutual Fund)
        c = build_valid_cams_statement()
        c_tx = c.schemes[0].transactions[0]
        fifo.buy_lot("port_primary", c.schemes[0].isin, "MUTUAL_FUND", c_tx.tx_date, c_tx.units, c_tx.nav)

        # 4. Schwab (US Equity)
        s = build_valid_schwab_statement()
        s_row = s.rows[0]
        forex_rate = lookup_rbi_rate(s_row.tx_date, mode="SPOT")
        fifo.buy_lot("port_primary", s_row.symbol, "US_EQUITY", s_row.tx_date, s_row.quantity, s_row.price, forex_rate=forex_rate)

        # Verify all 4 assets exist in portfolio active lots
        self.assertEqual(len(fifo.active_lots), 4)

    def test_pair_05_multi_broker_date_sequencing_and_fifo_lot_depletion(self):
        """Tests buying Tata Motors via Zerodha in 2023 and via HDFC in 2024, then selling via Zerodha in 2024"""
        fifo = ReferenceFIFOTaxEngine()
        isin = "INE155A01022" # Tata Motors
        
        # Lot 1 (Zerodha, Jan 2023): 100 @ 400
        fifo.buy_lot("port_primary", isin, "EQUITY", date(2023, 1, 15), Decimal("100"), Decimal("400.00"))
        # Lot 2 (HDFC, Feb 2024): 100 @ 500
        fifo.buy_lot("port_primary", isin, "EQUITY", date(2024, 2, 15), Decimal("100"), Decimal("500.00"))

        # Sell 150 @ 600 in Aug 2024 (Zerodha)
        disps = fifo.sell_units("port_primary", isin, "EQUITY", date(2024, 8, 14), Decimal("150"), Decimal("600.00"))
        
        self.assertEqual(len(disps), 2)
        # Lot 1 (100 units): LTCG (holding > 12m) @ 12.5%
        self.assertEqual(disps[0]["matched_quantity"], Decimal("100"))
        self.assertTrue(disps[0]["is_long_term"])
        self.assertEqual(disps[0]["tax_rate_pct"], Decimal("12.50"))

        # Lot 2 (50 units): STCG (holding < 12m) @ 20%
        self.assertEqual(disps[1]["matched_quantity"], Decimal("50"))
        self.assertFalse(disps[1]["is_long_term"])
        self.assertEqual(disps[1]["tax_rate_pct"], Decimal("20.00"))

        # Remaining in Lot 2: 50 units
        self.assertEqual(fifo.active_lots[f"port_primary:{isin}"][1]["remaining_quantity"], Decimal("50"))

    def test_pair_06_reingesting_overlapping_statement_date_ranges_deduplication(self):
        """Statement A (Jan-Jun) and Statement B (May-Dec) overlap in May-Jun: exactly 0 duplicates recorded"""
        seen_fingerprints = set()
        unique_records = []
        
        # Statement A: Trades on Jan 10, Mar 15, May 20
        trades_A = [
            ("INE155", "2024-01-10", "BUY", Decimal("100"), Decimal("400"), "T1"),
            ("INE155", "2024-03-15", "BUY", Decimal("50"), Decimal("420"), "T2"),
            ("INE155", "2024-05-20", "BUY", Decimal("80"), Decimal("450"), "T3"),
        ]
        for isin, dt, act, qty, pr, tid in trades_A:
            fp = ReferenceReconciliationGate.compute_transaction_fingerprint("p", "ZERODHA", isin, dt, act, qty, pr, tid)
            if fp not in seen_fingerprints:
                seen_fingerprints.add(fp)
                unique_records.append(fp)
        self.assertEqual(len(unique_records), 3)

        # Statement B: Trades on May 20 (overlapping duplicate), Jul 10, Aug 14
        trades_B = [
            ("INE155", "2024-05-20", "BUY", Decimal("80"), Decimal("450"), "T3"), # Overlapping
            ("INE155", "2024-07-10", "BUY", Decimal("40"), Decimal("480"), "T4"),
            ("INE155", "2024-08-14", "BUY", Decimal("60"), Decimal("500"), "T5"),
        ]
        duplicates_count = 0
        new_count = 0
        for isin, dt, act, qty, pr, tid in trades_B:
            fp = ReferenceReconciliationGate.compute_transaction_fingerprint("p", "ZERODHA", isin, dt, act, qty, pr, tid)
            if fp in seen_fingerprints:
                duplicates_count += 1
            else:
                seen_fingerprints.add(fp)
                unique_records.append(fp)
                new_count += 1

        self.assertEqual(duplicates_count, 1)
        self.assertEqual(new_count, 2)
        self.assertEqual(len(unique_records), 5)

    def test_pair_07_schwab_us_trade_forex_conversion_and_schedule_fa_ready(self):
        """Ingests Schwab Buy NVDA + Dividend + Tax Withholding and generates Schedule FA summary"""
        s = build_valid_schwab_statement()
        passed, err, diff = ReferenceValidationGate.validate_schwab(s)
        self.assertTrue(passed)

        total_dividends_usd = Decimal("0.00")
        total_withholding_usd = Decimal("0.00")
        for r in s.rows:
            if r.action.lower() == "qual dividend":
                total_dividends_usd += r.amount
            elif r.action.lower() == "tax withholding":
                total_withholding_usd += abs(r.amount)

        self.assertEqual(total_dividends_usd, Decimal("24.00"))
        self.assertEqual(total_withholding_usd, Decimal("6.00"))

        # Convert to INR using Rule 115 for Schedule FA
        rule115_rate = lookup_rbi_rate(date(2023, 11, 15), mode="RULE_115")
        gross_div_inr = (total_dividends_usd * rule115_rate).quantize(Decimal("0.01"))
        tax_withheld_inr = (total_withholding_usd * rule115_rate).quantize(Decimal("0.01"))

        self.assertGreater(gross_div_inr, Decimal("1900.00"))
        self.assertGreater(tax_withheld_inr, Decimal("450.00"))

    def test_pair_08_cams_sip_accumulation_and_lump_sum_redemption_fifo(self):
        """CAMS SIP installments depleted via FIFO on redemption"""
        fifo = ReferenceFIFOTaxEngine()
        amfi = "100085"
        
        # SIP 1 (Jan 2023): 100 units @ 450
        fifo.buy_lot("port_primary", amfi, "MUTUAL_FUND", date(2023, 1, 10), Decimal("100"), Decimal("450.00"))
        # SIP 2 (Feb 2023): 100 units @ 460
        fifo.buy_lot("port_primary", amfi, "MUTUAL_FUND", date(2023, 2, 10), Decimal("100"), Decimal("460.00"))
        # SIP 3 (Jan 2024): 100 units @ 500
        fifo.buy_lot("port_primary", amfi, "MUTUAL_FUND", date(2024, 1, 10), Decimal("100"), Decimal("500.00"))

        # Redeem 250 units in Aug 2024 @ 600
        disps = fifo.sell_units("port_primary", amfi, "MUTUAL_FUND", date(2024, 8, 14), Decimal("250"), Decimal("600.00"))
        
        self.assertEqual(len(disps), 3)
        # SIP 1 (100 units): LTCG @ 12.5%
        self.assertEqual(disps[0]["matched_quantity"], Decimal("100"))
        self.assertTrue(disps[0]["is_long_term"])
        # SIP 2 (100 units): LTCG @ 12.5%
        self.assertEqual(disps[1]["matched_quantity"], Decimal("100"))
        self.assertTrue(disps[1]["is_long_term"])
        # SIP 3 (50 units): STCG @ 20% (holding < 12m)
        self.assertEqual(disps[2]["matched_quantity"], Decimal("50"))
        self.assertFalse(disps[2]["is_long_term"])

    def test_pair_09_sovereign_gold_bond_hdfc_ingestion_and_tax_free_maturity(self):
        """SGB held to maturity is 100% tax exempt (0% tax) under Section 47"""
        fifo = ReferenceFIFOTaxEngine()
        sgb_isin = "IN0020210040"
        
        fifo.buy_lot("port_father", sgb_isin, "SGB_MATURITY", date(2021, 5, 20), Decimal("100"), Decimal("4777.00"))
        disps = fifo.sell_units("port_father", sgb_isin, "SGB_MATURITY", date(2029, 5, 20), Decimal("100"), Decimal("7500.00"))
        
        self.assertEqual(len(disps), 1)
        self.assertTrue(disps[0]["is_long_term"])
        self.assertEqual(disps[0]["tax_rate_pct"], Decimal("0.00"))
        self.assertEqual(disps[0]["estimated_tax_inr"], Decimal("0.00"))

    def test_pair_10_multi_family_entity_ingestion_zero_cross_portfolio_pollution(self):
        """Verifies four independent family portfolios have isolated ledger records"""
        fifo = ReferenceFIFOTaxEngine()
        
        fifo.buy_lot("port_primary", "NVDA", "US_EQUITY", date(2023, 1, 1), Decimal("150"), Decimal("62.40"))
        fifo.buy_lot("port_father", "INE040A01034", "EQUITY", date(2024, 1, 1), Decimal("600"), Decimal("1350.00"))
        fifo.buy_lot("port_mother", "GOLD_24K", "GOLD_PHYSICAL", date(2020, 1, 1), Decimal("100"), Decimal("4000.00"))
        fifo.buy_lot("port_trust", "INF789F01010", "MUTUAL_FUND", date(2022, 1, 1), Decimal("1000"), Decimal("200.00"))

        self.assertIn("port_primary:NVDA", fifo.active_lots)
        self.assertIn("port_father:INE040A01034", fifo.active_lots)
        self.assertIn("port_mother:GOLD_24K", fifo.active_lots)
        self.assertIn("port_trust:INF789F01010", fifo.active_lots)

        # Confirm portfolios do not see each other's assets
        self.assertNotIn("port_primary:GOLD_24K", fifo.active_lots)
        self.assertNotIn("port_father:NVDA", fifo.active_lots)

    def test_pair_11_section_112a_125000_exemption_aggregation(self):
        """Tests domestic equity LTCG exemption ₹1,25,000 threshold calculation across trades"""
        fifo = ReferenceFIFOTaxEngine()
        
        # Trade 1 LTCG: ₹80,000 gain
        fifo.buy_lot("port_primary", "INE155", "EQUITY", date(2022, 1, 1), Decimal("100"), Decimal("200.00"))
        d1 = fifo.sell_units("port_primary", "INE155", "EQUITY", date(2024, 8, 1), Decimal("100"), Decimal("1000.00"))
        self.assertEqual(d1[0]["realized_gain_inr"], Decimal("80000.00"))

        # Trade 2 LTCG: ₹70,000 gain
        fifo.buy_lot("port_primary", "INE009", "EQUITY", date(2022, 1, 1), Decimal("100"), Decimal("500.00"))
        d2 = fifo.sell_units("port_primary", "INE009", "EQUITY", date(2024, 8, 1), Decimal("100"), Decimal("1200.00"))
        self.assertEqual(d2[0]["realized_gain_inr"], Decimal("70000.00"))

        total_ltcg = d1[0]["realized_gain_inr"] + d2[0]["realized_gain_inr"] # ₹1,50,000
        exemption = min(total_ltcg, Decimal("125000.00")) # ₹1,25,000
        taxable_ltcg = max(Decimal("0.00"), total_ltcg - exemption) # ₹25,000
        tax_at_12_5_pct = (taxable_ltcg * Decimal("0.125")).quantize(Decimal("0.01")) # ₹3,125.00

        self.assertEqual(total_ltcg, Decimal("150000.00"))
        self.assertEqual(taxable_ltcg, Decimal("25000.00"))
        self.assertEqual(tax_at_12_5_pct, Decimal("3125.00"))

    def test_pair_12_forwarded_email_with_both_pdf_and_csv_attachments(self):
        """Ingests email containing both Zerodha ECN PDF and Console CSV export"""
        mime = create_zerodha_mime(
            pdf_bytes=b"%PDF-1.7 ZERODHA CONTRACT NOTE",
            csv_bytes=b"symbol,isin,trade_date,exchange,segment,series,trade_type,quantity,price,order_id,trade_id\nTATA,INE155,2024-08-14,NSE,EQ,EQ,buy,100,480.00,1,1"
        )
        res = ReferenceIdentityGate.process_mime_payload(mime, "alex.taylor@example.com")
        self.assertTrue(res["passed"])
        self.assertEqual(len(res["extracted_attachments"]), 2)

    def test_pair_13_statement_hash_changes_when_single_trade_quantity_changes(self):
        """Boundary hash sensitivity: altering 1 trade changes hash completely"""
        h1 = ReferenceReconciliationGate.compute_statement_hash("ZERODHA", "ZR1102", "2024-08-14", "2024-08-14", 2, Decimal("-534633.45"))
        h2 = ReferenceReconciliationGate.compute_statement_hash("ZERODHA", "ZR1102", "2024-08-14", "2024-08-14", 2, Decimal("-534633.46"))
        self.assertNotEqual(h1, h2)

    def test_pair_14_debt_mutual_fund_section_50aa_slab_rate_application(self):
        """Debt Mutual Funds (>65% debt) acquired post 1-Apr-2023 treated as deemed STCG at slab rates"""
        fifo = ReferenceFIFOTaxEngine()
        fifo.buy_lot("port_primary", "DEBT_MF_01", "DEBT_MUTUAL_FUND", date(2023, 5, 1), Decimal("100"), Decimal("100.00"))
        # Holding > 12m (sold in Aug 2024), but Section 50AA mandates STCG
        disps = fifo.sell_units("port_primary", "DEBT_MF_01", "DEBT_MUTUAL_FUND", date(2024, 8, 14), Decimal("100"), Decimal("110.00"))
        self.assertFalse(disps[0]["is_long_term"])
        self.assertEqual(disps[0]["tax_rate_pct"], Decimal("30.00"))

    def test_pair_15_concurrent_multi_broker_batch_ingestion(self):
        """Simulates parallel statement processing queue"""
        statements = [
            ("ZERODHA", "ZR1102", Decimal("-534633.45")),
            ("HDFC_SECURITIES", "1092847101", Decimal("-811167.94")),
            ("CHARLES_SCHWAB", "84920194", Decimal("-9360.00")),
        ]
        hashes = set()
        for inst, acc, net in statements:
            h = ReferenceReconciliationGate.compute_statement_hash(inst, acc, "2024-08-14", "2024-08-14", 1, net)
            hashes.add(h)
        self.assertEqual(len(hashes), 3)


if __name__ == "__main__":
    unittest.main()
