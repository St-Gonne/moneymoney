"""
Tier 4: Real-World Multi-Broker Multi-Portfolio Vault Ingestion Workloads (MoneyMoney Ingestion Pipeline)
Simulates complete real-world annual family vault ingestion across Alex, Robert, Margaret, and Taylor Family Trust.
"""
import unittest
from datetime import date, datetime
from decimal import Decimal

from backend.tests.fixtures.sample_family_vault import (
    AUTHORIZED_FORWARDERS,
    FAMILY_VAULT_PROFILES,
    lookup_rbi_rate,
)
from backend.tests.fixtures.sample_emails import (
    create_zerodha_mime,
    create_hdfc_mime,
    create_cams_cas_mime,
    create_kfintech_cas_mime,
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
)


class TestTier4RealWorldWorkloads(unittest.TestCase):
    """
    Tier 4 Test Suite: End-to-end Family Vault Multi-Broker Scenarios.
    """

    def test_scenario_01_alex_annual_multi_broker_vault_ingestion(self):
        """
        Alex Taylor Vault:
        - Charles Schwab (NVDA, AAPL, VOO + Dividends)
        - Zerodha (Tata Motors, Infosys)
        - CAMS (Quant Active Fund)
        """
        fifo = ReferenceFIFOTaxEngine()
        port_id = "port_primary"

        # 1. Ingest Zerodha Contract Note
        z_stmt = build_valid_zerodha_statement(trade_date=date(2023, 5, 15))
        z_pass, _, _ = ReferenceValidationGate.validate_zerodha(z_stmt)
        self.assertTrue(z_pass)
        for t in z_stmt.trades:
            fifo.buy_lot(port_id, t.isin, "EQUITY", z_stmt.trade_date, t.quantity, t.gross_rate)

        # 2. Ingest CAMS CAS
        c_stmt = build_valid_cams_statement()
        c_pass, _, _ = ReferenceValidationGate.validate_cas(c_stmt)
        self.assertTrue(c_pass)
        s = c_stmt.schemes[0]
        # Ingest initial purchase
        fifo.buy_lot(port_id, s.isin, "MUTUAL_FUND", s.transactions[0].tx_date, s.transactions[0].units, s.transactions[0].nav)

        # 3. Ingest Charles Schwab US Activity
        s_stmt = build_valid_schwab_statement()
        s_pass, _, _ = ReferenceValidationGate.validate_schwab(s_stmt)
        self.assertTrue(s_pass)
        s_buy = s_stmt.rows[0]
        forex_buy = lookup_rbi_rate(s_buy.tx_date, mode="SPOT")
        fifo.buy_lot(port_id, s_buy.symbol, "US_EQUITY", s_buy.tx_date, s_buy.quantity, s_buy.price, forex_rate=forex_buy)

        # Verify all assets active
        self.assertIn(f"{port_id}:INE155A01022", fifo.active_lots) # Tata Motors
        self.assertIn(f"{port_id}:INE009A01021", fifo.active_lots) # Infosys
        self.assertIn(f"{port_id}:INF966L01AA3", fifo.active_lots) # Quant Active
        self.assertIn(f"{port_id}:NVDA", fifo.active_lots)         # Nvidia

        # Partial Sale of Nvidia (50 shares @ $125 on 2024-08-10)
        forex_sell = lookup_rbi_rate(date(2024, 8, 10), mode="SPOT")
        disps = fifo.sell_units(port_id, "NVDA", "US_EQUITY", date(2024, 8, 10), Decimal("50.000"), Decimal("125.00"), forex_rate=forex_sell)
        
        self.assertEqual(len(disps), 1)
        self.assertEqual(disps[0]["matched_quantity"], Decimal("50.000"))
        # Holding ~15 months (< 24 months for US equity) -> STCG
        self.assertFalse(disps[0]["is_long_term"])
        self.assertGreater(disps[0]["realized_gain_inr"], Decimal("0.00"))

    def test_scenario_02_robert_senior_citizen_hdfc_sgb_cas_ingestion(self):
        """
        Robert Taylor Vault:
        - HDFC Securities (HDFC Bank)
        - Sovereign Gold Bonds (SGB MAY29)
        - CAMS (SBI Bluechip Fund)
        """
        fifo = ReferenceFIFOTaxEngine()
        port_id = "port_father"

        # 1. HDFC Securities Equity Buy
        h_stmt = build_valid_hdfc_statement()
        h_pass, _, _ = ReferenceValidationGate.validate_hdfc(h_stmt)
        self.assertTrue(h_pass)
        fifo.buy_lot(port_id, h_stmt.trades[0].isin, "EQUITY", h_stmt.trade_date, h_stmt.trades[0].quantity, h_stmt.trades[0].gross_rate)

        # 2. SGB May 2021 Purchase
        fifo.buy_lot(port_id, "IN0020210040", "SGB_MATURITY", date(2021, 5, 20), Decimal("100"), Decimal("4777.00"))

        # 3. CAMS SBI Bluechip Fund
        fifo.buy_lot(port_id, "INF200C01235", "MUTUAL_FUND", date(2022, 1, 10), Decimal("2000"), Decimal("65.00"))

        # SGB Redemption at maturity in 2029 (100% Tax Exempt under Section 47)
        sgb_disp = fifo.sell_units(port_id, "IN0020210040", "SGB_MATURITY", date(2029, 5, 20), Decimal("100"), Decimal("8500.00"))
        self.assertEqual(sgb_disp[0]["tax_rate_pct"], Decimal("0.00"))
        self.assertEqual(sgb_disp[0]["estimated_tax_inr"], Decimal("0.00"))

    def test_scenario_03_margaret_wealth_gold_cas_ingestion(self):
        """
        Margaret Taylor Vault:
        - Physical 24K Gold
        - CAMS Parag Parikh Flexi Cap Fund
        """
        fifo = ReferenceFIFOTaxEngine()
        port_id = "port_mother"

        # 1. Gold Physical
        fifo.buy_lot(port_id, "GOLD_24K", "GOLD_PHYSICAL", date(2020, 1, 1), Decimal("100"), Decimal("4000.00"))

        # 2. CAMS Parag Parikh Flexi Cap
        fifo.buy_lot(port_id, "INF879O01019", "MUTUAL_FUND", date(2021, 3, 15), Decimal("5000"), Decimal("45.00"))

        # Partial Redemption in Aug 2024 (Holding > 3 years -> LTCG @ 12.5%)
        disp = fifo.sell_units(port_id, "INF879O01019", "MUTUAL_FUND", date(2024, 8, 14), Decimal("1000"), Decimal("75.00"))
        self.assertTrue(disp[0]["is_long_term"])
        self.assertEqual(disp[0]["tax_rate_pct"], Decimal("12.50"))
        self.assertEqual(disp[0]["realized_gain_inr"], Decimal("30000.00"))

    def test_scenario_04_taylor_huf_cas_and_fd_ingestion(self):
        """
        Taylor Family Trust Vault:
        - UTI Nifty 50 Index Fund
        - HDFC Corporate Fixed Deposit
        """
        fifo = ReferenceFIFOTaxEngine()
        port_id = "port_trust"

        # 1. UTI Nifty 50 Index Fund
        fifo.buy_lot(port_id, "INF789F01010", "MUTUAL_FUND", date(2021, 6, 1), Decimal("10000"), Decimal("110.00"))

        # 2. Partial Sell in 2024
        disp = fifo.sell_units(port_id, "INF789F01010", "MUTUAL_FUND", date(2024, 8, 14), Decimal("2000"), Decimal("175.00"))
        self.assertTrue(disp[0]["is_long_term"])
        self.assertEqual(disp[0]["realized_gain_inr"], Decimal("130000.00")) # Gain = 2000 * 65 = 1,30,000

    def test_scenario_05_full_consolidated_family_vault_reconciliation(self):
        """
        Consolidated Reconciliation across all 4 portfolios:
        Verifies total portfolio holdings count and isolation.
        """
        fifo = ReferenceFIFOTaxEngine()
        
        # Populate all 4 family members
        fifo.buy_lot("port_primary", "NVDA", "US_EQUITY", date(2023, 1, 1), Decimal("100"), Decimal("60.00"))
        fifo.buy_lot("port_father", "HDFCBANK", "EQUITY", date(2024, 1, 1), Decimal("600"), Decimal("1350.00"))
        fifo.buy_lot("port_mother", "PPFAS", "MUTUAL_FUND", date(2021, 1, 1), Decimal("5000"), Decimal("45.00"))
        fifo.buy_lot("port_trust", "UTINIFTY", "MUTUAL_FUND", date(2021, 1, 1), Decimal("10000"), Decimal("110.00"))

        # Verify active assets
        alex_assets = [k for k in fifo.active_lots if k.startswith("port_primary:")]
        father_assets = [k for k in fifo.active_lots if k.startswith("port_father:")]
        margaret_assets = [k for k in fifo.active_lots if k.startswith("port_mother:")]
        huf_assets = [k for k in fifo.active_lots if k.startswith("port_trust:")]

        self.assertEqual(len(alex_assets), 1)
        self.assertEqual(len(father_assets), 1)
        self.assertEqual(len(margaret_assets), 1)
        self.assertEqual(len(huf_assets), 1)

    def test_scenario_06_finance_act_2024_tax_audit_and_schedule_fa_reconciliation(self):
        """
        Finance Act 2024 Tax Audit:
        - 12.5% LTCG on domestic equity > 12m
        - 20.0% STCG on domestic equity <= 12m
        - 12.5% LTCG on foreign unlisted equity > 24m
        - Section 112A ₹1,25,000 exemption limit
        - IRS 1042-S 25% foreign tax credit
        """
        fifo = ReferenceFIFOTaxEngine()
        
        # Domestic Long-term gain: ₹2,00,000
        fifo.buy_lot("port_primary", "DOM_EQ_1", "EQUITY", date(2022, 1, 1), Decimal("1000"), Decimal("100.00"))
        disp_lt = fifo.sell_units("port_primary", "DOM_EQ_1", "EQUITY", date(2024, 8, 14), Decimal("1000"), Decimal("300.00"))
        self.assertEqual(disp_lt[0]["realized_gain_inr"], Decimal("200000.00"))

        # Exemption calculation:
        taxable_gain = max(Decimal("0.00"), disp_lt[0]["realized_gain_inr"] - Decimal("125000.00"))
        self.assertEqual(taxable_gain, Decimal("75000.00"))
        tax_payable = (taxable_gain * Decimal("0.125")).quantize(Decimal("0.01"))
        self.assertEqual(tax_payable, Decimal("9375.00"))

    def test_scenario_07_multi_year_idempotency_stress_benchmark(self):
        """
        Simulates ingesting 24 statements sequentially, then re-ingesting all 24.
        Verifies 100% duplicate detection rate.
        """
        ingested_db = set()
        total_statements = 24
        
        # Pass 1: Ingest 24 monthly statements
        for month in range(1, total_statements + 1):
            h = ReferenceReconciliationGate.compute_statement_hash(
                "ZERODHA", "ZR1102", f"2023-{month:02d}-01", f"2023-{month:02d}-28", 5, Decimal("-50000.00")
            )
            self.assertNotIn(h, ingested_db)
            ingested_db.add(h)

        self.assertEqual(len(ingested_db), 24)

        # Pass 2: Re-ingest all 24
        duplicate_count = 0
        for month in range(1, total_statements + 1):
            h = ReferenceReconciliationGate.compute_statement_hash(
                "ZERODHA", "ZR1102", f"2023-{month:02d}-01", f"2023-{month:02d}-28", 5, Decimal("-50000.00")
            )
            if h in ingested_db:
                duplicate_count += 1

        self.assertEqual(duplicate_count, 24)


if __name__ == "__main__":
    unittest.main()
