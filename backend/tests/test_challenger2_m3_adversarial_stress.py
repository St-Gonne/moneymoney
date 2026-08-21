"""
Milestone 3 Challenger 2 Adversarial Stress Test Suite
Adversarially tests:
1. RBI Forex Rate Engine (ForexEngine):
   - Weekend lookback resolution (Saturday/Sunday -> Friday fallback)
   - Holiday clusters and missing date interpolation
   - Rule 115 preceding month-end calculations across all 12 calendar months
   - Leap year month-end calculations (2024-02-29 vs 2023-02-28)
   - January year rollover transitions (Jan -> Dec 31 of prior year)
   - Out-of-bounds dates and default fallback handling
   - USD to INR sub-cent precision, zero, micro, and large amounts
   - Foreign dividend & IRS 1042-S 25% withholding tax Rule 115 conversions
2. Finance Act 2024 FIFO Tax Lot Engine (FIFOTaxEngine):
   - Chronological multi-year lot depletion (FY21, FY22, FY23, FY24)
   - Partial lot depletions and multi-stage depletion lifecycle (ACTIVE -> PARTIALLY_DEPLETED -> EXHAUSTED)
   - Micro-fractional mutual fund units precision (3-4 decimal places)
   - Zero-cost acquisitions (bonus shares, gifts, ESOPs with ₹0.00 cost basis)
   - Corporate actions / SIP tranches spanning mixed holding periods (LTCG > 12m vs STCG <= 12m)
   - Section 112A ₹1,25,000 annual exemption exact boundary tests (< ₹1.25L, == ₹1.25L, > ₹1.25L, multi-scrip, loss handling)
   - Section 50AA Debt Mutual Fund sales (acquired post 1-Apr-2023: deemed STCG at 30% slab rate regardless of holding period)
   - Sovereign Gold Bonds (SGB, Section 47) maturity redemption: 100% tax exempt
   - Foreign Equities (Charles Schwab US / Schedule FA) 24-month threshold (730 days vs 731 days)
   - Oversell protection, zero inventory defense, and error propagation
   - Multi-entity family vault isolation (Alex, Robert, Margaret, HUF)
"""

import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal
import unittest

from backend.app.config import (
    DEFAULT_USD_INR_RATE,
    HISTORICAL_RBI_FOREX_RATES,
)
from backend.app.engines.fifo_tax_engine import FIFOTaxEngine
from backend.app.engines.forex_engine import ForexEngine, convert_usd_to_inr, lookup_rbi_rate
from backend.app.engines.ledger_service import LedgerService
from backend.app.models.ledger import TaxAssetType, TaxLotStatus


class TestAdversarialForexEngine(unittest.TestCase):
    """Adversarial stress test suite for RBI Reference Forex Rate Engine."""

    def setUp(self):
        # Dedicated custom rates table for controlled stress testing
        self.custom_rates = {
            date(2023, 1, 31): Decimal("81.74"),
            date(2023, 2, 28): Decimal("82.60"),
            date(2023, 3, 31): Decimal("82.22"),
            date(2023, 4, 28): Decimal("81.80"),  # Friday
            date(2023, 5, 18): Decimal("82.35"),  # Thursday
            date(2023, 5, 19): Decimal("82.40"),  # Friday
            date(2023, 5, 31): Decimal("82.68"),
            date(2023, 6, 30): Decimal("82.04"),
            date(2023, 7, 31): Decimal("82.25"),
            date(2023, 8, 31): Decimal("82.75"),
            date(2023, 9, 29): Decimal("83.05"),  # Friday (Sep 30 is Sat)
            date(2023, 10, 31): Decimal("83.25"),
            date(2023, 11, 15): Decimal("83.25"),
            date(2023, 11, 30): Decimal("83.35"),
            date(2023, 12, 29): Decimal("83.12"),  # Friday (Dec 31 is Sun)
            date(2024, 1, 31): Decimal("83.05"),
            date(2024, 2, 29): Decimal("82.90"),  # Leap Year Feb 29
            date(2024, 3, 28): Decimal("83.37"),  # Thursday before Good Friday
            date(2024, 4, 30): Decimal("83.45"),
            date(2024, 5, 31): Decimal("83.42"),
            date(2024, 6, 28): Decimal("83.56"),  # Friday
            date(2024, 7, 31): Decimal("83.72"),
            date(2024, 8, 9): Decimal("83.85"),   # Friday
            date(2024, 8, 14): Decimal("83.95"),  # Wednesday
            date(2024, 12, 31): Decimal("84.25"),
        }
        self.engine = ForexEngine(rates_table=self.custom_rates, default_rate=Decimal("84.50"))

    def test_weekend_lookback_saturday_and_sunday(self):
        """Saturday (2024-08-10) and Sunday (2024-08-11) must resolve to Friday (2024-08-09) rate."""
        friday_rate = self.engine.lookup_rate(date(2024, 8, 9), mode="SPOT")
        sat_rate = self.engine.lookup_rate(date(2024, 8, 10), mode="SPOT")
        sun_rate = self.engine.lookup_rate(date(2024, 8, 11), mode="SPOT")

        self.assertEqual(friday_rate, Decimal("83.85"))
        self.assertEqual(sat_rate, Decimal("83.85"))
        self.assertEqual(sun_rate, Decimal("83.85"))

    def test_extended_holiday_cluster_fallback(self):
        """Holiday cluster (e.g. Friday Good Friday 2024-03-29 to Easter Sunday 2024-03-31) resolves to Thursday 2024-03-28."""
        thursday_rate = self.engine.lookup_rate(date(2024, 3, 28), mode="SPOT")
        good_friday_rate = self.engine.lookup_rate(date(2024, 3, 29), mode="SPOT")
        easter_sat_rate = self.engine.lookup_rate(date(2024, 3, 30), mode="SPOT")
        easter_sun_rate = self.engine.lookup_rate(date(2024, 3, 31), mode="SPOT")

        self.assertEqual(thursday_rate, Decimal("83.37"))
        self.assertEqual(good_friday_rate, Decimal("83.37"))
        self.assertEqual(easter_sat_rate, Decimal("83.37"))
        self.assertEqual(easter_sun_rate, Decimal("83.37"))

    def test_rule_115_all_twelve_calendar_months(self):
        """Rule 115 preceding month-end must correctly return the last calendar day of prior month for months 2-12."""
        expected_preceding = {
            2: date(2023, 1, 31),
            3: date(2023, 2, 28),
            4: date(2023, 3, 31),
            5: date(2023, 4, 30),
            6: date(2023, 5, 31),
            7: date(2023, 6, 30),
            8: date(2023, 7, 31),
            9: date(2023, 8, 31),
            10: date(2023, 9, 30),
            11: date(2023, 10, 31),
            12: date(2023, 11, 30),
        }
        for month, exp_date in expected_preceding.items():
            tx_d = date(2023, month, 15)
            calc_d = self.engine.get_preceding_month_end(tx_d)
            self.assertEqual(calc_d, exp_date, f"Failed for month {month}: expected {exp_date}, got {calc_d}")

    def test_rule_115_leap_year_february_29(self):
        """Leap year February 2024 must return 2024-02-29 for March 2024 transactions."""
        # Leap year 2024
        march_tx_leap = date(2024, 3, 15)
        self.assertEqual(self.engine.get_preceding_month_end(march_tx_leap), date(2024, 2, 29))
        self.assertEqual(self.engine.lookup_rate(march_tx_leap, mode="RULE_115"), Decimal("82.90"))

        # Non-leap year 2023
        march_tx_non_leap = date(2023, 3, 15)
        self.assertEqual(self.engine.get_preceding_month_end(march_tx_non_leap), date(2023, 2, 28))
        self.assertEqual(self.engine.lookup_rate(march_tx_non_leap, mode="RULE_115"), Decimal("82.60"))

    def test_rule_115_january_year_boundary_rollover(self):
        """January transactions (e.g. 2024-01-10) must rollover to previous year's 31-Dec (2023-12-31)."""
        jan_tx = date(2024, 1, 10)
        preceding_d = self.engine.get_preceding_month_end(jan_tx)
        self.assertEqual(preceding_d, date(2023, 12, 31))

        # Lookup rate for 2023-12-31 should fall back to Friday 2023-12-29 rate (83.12)
        rate = self.engine.lookup_rate(jan_tx, mode="RULE_115")
        self.assertEqual(rate, Decimal("83.12"))

    def test_date_format_polymorphism_and_string_parsing(self):
        """ForexEngine must seamlessly accept string dates, datetime objects, and date objects."""
        r_str = self.engine.lookup_rate("2024-08-14", mode="SPOT")
        r_iso = self.engine.lookup_rate("2024-08-14T09:30:00Z", mode="SPOT")
        r_dt = self.engine.lookup_rate(datetime(2024, 8, 14, 15, 30), mode="SPOT")
        r_d = self.engine.lookup_rate(date(2024, 8, 14), mode="SPOT")

        self.assertEqual(r_str, Decimal("83.95"))
        self.assertEqual(r_iso, Decimal("83.95"))
        self.assertEqual(r_dt, Decimal("83.95"))
        self.assertEqual(r_d, Decimal("83.95"))

    def test_malformed_string_date_graceful_fallback(self):
        """Malformed date string must not raise unhandled exceptions and should return default rate."""
        rate = self.engine.lookup_rate("NOT-A-DATE", mode="SPOT")
        self.assertIsInstance(rate, Decimal)
        self.assertGreater(rate, Decimal("0.00"))

    def test_ancient_and_future_out_of_bounds_dates(self):
        """Dates earlier than table start return earliest rate; dates beyond table end return latest rate."""
        ancient_date = date(1995, 1, 1)
        future_date = date(2035, 1, 1)

        rate_ancient = self.engine.lookup_rate(ancient_date, mode="SPOT")
        rate_future = self.engine.lookup_rate(future_date, mode="SPOT")

        # Earliest in custom table is 2023-01-31 (81.74)
        self.assertEqual(rate_ancient, Decimal("81.74"))
        # Latest in custom table is 2024-12-31 (84.25)
        self.assertEqual(rate_future, Decimal("84.25"))

    def test_empty_rates_table_returns_default_rate(self):
        """An empty rates table must return the configured default rate."""
        empty_engine = ForexEngine(rates_table={}, default_rate=Decimal("85.00"))
        rate = empty_engine.lookup_rate(date(2024, 8, 14), mode="SPOT")
        self.assertEqual(rate, Decimal("85.00"))

    def test_usd_to_inr_sub_cent_quantization_and_large_values(self):
        """Test exact Decimal rounding, zero USD, micro amounts, and large values."""
        # 1. Exact zero
        zero_inr = self.engine.convert_usd_to_inr(Decimal("0.00"), date(2024, 8, 14))
        self.assertEqual(zero_inr, Decimal("0.00"))

        # 2. Micro fraction (e.g. SEC fee $0.0134)
        sec_fee_inr = self.engine.convert_usd_to_inr(Decimal("0.0134"), date(2024, 8, 14))
        # 0.0134 * 83.95 = 1.12493 -> quantizes to 1.12
        self.assertEqual(sec_fee_inr, Decimal("1.12"))

        # 3. Round-up case: 0.015 * 83.95 = 1.25925 -> 1.26
        round_up_inr = self.engine.convert_usd_to_inr(Decimal("0.015"), date(2024, 8, 14))
        self.assertEqual(round_up_inr, Decimal("1.26"))

        # 4. Large trade: $1,250,000.00 @ 83.95 = ₹10,49,37,500.00
        large_inr = self.engine.convert_usd_to_inr(Decimal("1250000.00"), date(2024, 8, 14))
        self.assertEqual(large_inr, Decimal("104937500.00"))

    def test_dividend_and_withholding_tax_rule_115_conversion(self):
        """Foreign dividend and IRS 1042-S 25% tax converted at Rule 115 rate."""
        # Transaction on 2023-11-15 -> Preceding month end is 2023-10-31 (rate 83.25)
        gross_inr, tax_inr, rate = self.engine.convert_dividend_and_withholding(
            gross_dividend_usd="100.00",
            tax_withheld_usd="25.00",
            tx_date=date(2023, 11, 15),
        )
        self.assertEqual(rate, Decimal("83.25"))
        self.assertEqual(gross_inr, Decimal("8325.00"))
        self.assertEqual(tax_inr, Decimal("2081.25"))
        self.assertEqual(gross_inr - tax_inr, Decimal("6243.75"))


class TestAdversarialFIFOTaxEngine(unittest.TestCase):
    """Adversarial stress test suite for Finance Act 2024 FIFO Tax Lot Accounting Engine."""

    def setUp(self):
        self.engine = FIFOTaxEngine()
        self.engine.reset_state()

    def test_strict_chronological_multi_year_lot_depletion(self):
        """
        Verify strict FIFO depletion across 4 distinct financial years:
        Lot 1: 2021-05-10 (100 units @ ₹100) -> LTCG (>12m)
        Lot 2: 2022-05-10 (100 units @ ₹200) -> LTCG (>12m)
        Lot 3: 2023-05-10 (100 units @ ₹300) -> LTCG (>12m)
        Lot 4: 2024-05-10 (100 units @ ₹400) -> STCG (<=12m on 2024-08-14)
        Sale: 250 units on 2024-08-14 @ ₹500
        """
        self.engine.buy_lot("port_primary", "INFY", "EQUITY", date(2021, 5, 10), Decimal("100"), Decimal("100.00"))
        self.engine.buy_lot("port_primary", "INFY", "EQUITY", date(2022, 5, 10), Decimal("100"), Decimal("200.00"))
        self.engine.buy_lot("port_primary", "INFY", "EQUITY", date(2023, 5, 10), Decimal("100"), Decimal("300.00"))
        self.engine.buy_lot("port_primary", "INFY", "EQUITY", date(2024, 5, 10), Decimal("100"), Decimal("400.00"))

        disps = self.engine.sell_units("port_primary", "INFY", "EQUITY", date(2024, 8, 14), Decimal("250"), Decimal("500.00"))

        # Must generate 3 disposition records (100 from Lot 1, 100 from Lot 2, 50 from Lot 3)
        self.assertEqual(len(disps), 3)

        # Disposition 1 (Lot 1): 100 units, gain = 100 * (500 - 100) = 40,000 (LTCG 12.5%)
        self.assertEqual(disps[0]["matched_quantity"], Decimal("100"))
        self.assertEqual(disps[0]["cost_basis_inr"], Decimal("10000.00"))
        self.assertEqual(disps[0]["realized_gain_inr"], Decimal("40000.00"))
        self.assertTrue(disps[0]["is_long_term"])
        self.assertEqual(disps[0]["tax_rate_pct"], Decimal("12.50"))

        # Disposition 2 (Lot 2): 100 units, gain = 100 * (500 - 200) = 30,000 (LTCG 12.5%)
        self.assertEqual(disps[1]["matched_quantity"], Decimal("100"))
        self.assertEqual(disps[1]["cost_basis_inr"], Decimal("20000.00"))
        self.assertEqual(disps[1]["realized_gain_inr"], Decimal("30000.00"))
        self.assertTrue(disps[1]["is_long_term"])

        # Disposition 3 (Lot 3): 50 units, gain = 50 * (500 - 300) = 10,000 (LTCG 12.5%)
        self.assertEqual(disps[2]["matched_quantity"], Decimal("50"))
        self.assertEqual(disps[2]["cost_basis_inr"], Decimal("15000.00"))
        self.assertEqual(disps[2]["realized_gain_inr"], Decimal("10000.00"))
        self.assertTrue(disps[2]["is_long_term"])

        # Verify active lots remaining
        open_lots = self.engine.get_open_lots("port_primary", "INFY")
        self.assertEqual(len(open_lots), 2)
        # Lot 3 has 50 remaining
        self.assertEqual(open_lots[0]["remaining_quantity"], Decimal("50"))
        self.assertEqual(open_lots[0]["status"], "PARTIALLY_DEPLETED")
        # Lot 4 has 100 remaining
        self.assertEqual(open_lots[1]["remaining_quantity"], Decimal("100"))
        self.assertEqual(open_lots[1]["status"], "ACTIVE")

    def test_multi_stage_lot_depletion_lifecycle(self):
        """Test transitioning lot through ACTIVE -> PARTIALLY_DEPLETED -> EXHAUSTED across multiple partial sells."""
        self.engine.buy_lot("port_primary", "TCS", "EQUITY", date(2023, 1, 1), Decimal("100"), Decimal("3000.00"))

        # Sell 1: 30 units -> 70 remaining (PARTIALLY_DEPLETED)
        d1 = self.engine.sell_units("port_primary", "TCS", "EQUITY", date(2024, 1, 1), Decimal("30"), Decimal("3500.00"))
        self.assertEqual(len(d1), 1)
        lots = self.engine.get_open_lots("port_primary", "TCS")
        self.assertEqual(len(lots), 1)
        self.assertEqual(lots[0]["remaining_quantity"], Decimal("70"))
        self.assertEqual(lots[0]["status"], "PARTIALLY_DEPLETED")

        # Sell 2: 40 units -> 30 remaining (PARTIALLY_DEPLETED)
        d2 = self.engine.sell_units("port_primary", "TCS", "EQUITY", date(2024, 2, 1), Decimal("40"), Decimal("3600.00"))
        self.assertEqual(len(d2), 1)
        lots = self.engine.get_open_lots("port_primary", "TCS")
        self.assertEqual(lots[0]["remaining_quantity"], Decimal("30"))
        self.assertEqual(lots[0]["status"], "PARTIALLY_DEPLETED")

        # Sell 3: 30 units -> 0 remaining (EXHAUSTED)
        d3 = self.engine.sell_units("port_primary", "TCS", "EQUITY", date(2024, 3, 1), Decimal("30"), Decimal("3700.00"))
        self.assertEqual(len(d3), 1)
        lots = self.engine.get_open_lots("port_primary", "TCS")
        self.assertEqual(len(lots), 0)

    def test_micro_fractional_mutual_fund_units_precision(self):
        """Test mutual fund units with 3-4 decimal places without loss of precision."""
        self.engine.buy_lot("port_primary", "HDFC_TOP_100", "MUTUAL_FUND", date(2023, 1, 1), Decimal("154.382"), Decimal("500.00"))
        self.engine.buy_lot("port_primary", "HDFC_TOP_100", "MUTUAL_FUND", date(2023, 6, 1), Decimal("89.618"), Decimal("550.00"))

        # Total units = 154.382 + 89.618 = 244.000
        # Sell 200.000 units
        disps = self.engine.sell_units("port_primary", "HDFC_TOP_100", "MUTUAL_FUND", date(2024, 8, 14), Decimal("200.000"), Decimal("600.00"))

        self.assertEqual(len(disps), 2)
        # Lot 1: 154.382 units
        self.assertEqual(disps[0]["matched_quantity"], Decimal("154.382"))
        # Lot 2: 45.618 units (200 - 154.382)
        self.assertEqual(disps[1]["matched_quantity"], Decimal("45.618"))

        # Remaining units in Lot 2: 89.618 - 45.618 = 44.000
        open_lots = self.engine.get_open_lots("port_primary", "HDFC_TOP_100")
        self.assertEqual(len(open_lots), 1)
        self.assertEqual(open_lots[0]["remaining_quantity"], Decimal("44.000"))

    def test_zero_cost_acquisitions_bonus_shares_and_gifts(self):
        """Zero cost acquisitions (e.g. 1:1 Bonus issue @ ₹0.00) must compute full sale price as capital gain."""
        # 100 shares bought @ ₹500
        self.engine.buy_lot("port_primary", "RELIANCE", "EQUITY", date(2022, 1, 1), Decimal("100"), Decimal("500.00"))
        # 100 bonus shares received @ ₹0.00
        self.engine.buy_lot("port_primary", "RELIANCE", "EQUITY", date(2022, 6, 1), Decimal("100"), Decimal("0.00"))

        # Sell all 200 shares @ ₹1000 on 2024-08-14
        disps = self.engine.sell_units("port_primary", "RELIANCE", "EQUITY", date(2024, 8, 14), Decimal("200"), Decimal("1000.00"))
        self.assertEqual(len(disps), 2)

        # Lot 1: Cost basis = 100 * 500 = ₹50,000, Proceeds = ₹100,000, Gain = ₹50,000
        self.assertEqual(disps[0]["cost_basis_inr"], Decimal("50000.00"))
        self.assertEqual(disps[0]["realized_gain_inr"], Decimal("50000.00"))

        # Lot 2 (Bonus): Cost basis = 100 * 0 = ₹0.00, Proceeds = ₹100,000, Gain = ₹100,000
        self.assertEqual(disps[1]["cost_basis_inr"], Decimal("0.00"))
        self.assertEqual(disps[1]["realized_gain_inr"], Decimal("100000.00"))

    def test_sip_tranches_mixed_holding_periods(self):
        """12 monthly SIPs: early tranches (> 365 days) taxed as LTCG 12.5%, recent tranches (<= 365 days) taxed as STCG 20%."""
        # Ingest 12 monthly SIPs of 10 units each from 2023-08-01 to 2024-07-01
        for i in range(12):
            m = (8 + i - 1) % 12 + 1
            y = 2023 if i < 5 else 2024
            sip_date = date(y, m, 1)
            self.engine.buy_lot("port_primary", "NIFTY_50_INDEX", "MUTUAL_FUND", sip_date, Decimal("10"), Decimal("100.00"))

        # Redeem 50 units on 2024-08-14
        # Tranches 1 (2023-08-01): 379 days (>365) -> LTCG
        # Tranches 2 (2023-09-01): 348 days (<=365) -> STCG
        # Tranches 3 (2023-10-01): 318 days (<=365) -> STCG
        # Tranches 4 (2023-11-01): 287 days (<=365) -> STCG
        # Tranches 5 (2023-12-01): 257 days (<=365) -> STCG
        disps = self.engine.sell_units("port_primary", "NIFTY_50_INDEX", "MUTUAL_FUND", date(2024, 8, 14), Decimal("50"), Decimal("150.00"))

        self.assertEqual(len(disps), 5)
        # Tranche 1: LTCG @ 12.5%
        self.assertTrue(disps[0]["is_long_term"])
        self.assertEqual(disps[0]["tax_rate_pct"], Decimal("12.50"))
        self.assertEqual(disps[0]["section"], "112A")

        # Tranches 2-5: STCG @ 20%
        for d in disps[1:]:
            self.assertFalse(d["is_long_term"])
            self.assertEqual(d["tax_rate_pct"], Decimal("20.00"))
            self.assertEqual(d["section"], "111A")

    def test_section_112a_exemption_exact_threshold_boundary_cases(self):
        """Test Section 112A ₹1,25,000 statutory exemption across all boundary conditions."""
        # Case A: LTCG exactly ₹1,24,999.00 (Below threshold)
        self.engine.reset_state()
        self.engine.buy_lot("port_primary", "S1", "EQUITY", date(2022, 1, 1), Decimal("1"), Decimal("1.00"))
        self.engine.sell_units("port_primary", "S1", "EQUITY", date(2024, 8, 14), Decimal("1"), Decimal("125000.00"))
        sum_a = self.engine.compute_capital_gains_summary("port_primary", "FY2024-25")
        self.assertEqual(sum_a.total_ltcg_inr, Decimal("124999.00"))
        self.assertEqual(sum_a.section_112a_exemption_inr, Decimal("124999.00"))
        self.assertEqual(sum_a.taxable_ltcg_inr, Decimal("0.00"))
        self.assertEqual(sum_a.total_tax_inr, Decimal("0.00"))

        # Case B: LTCG exactly ₹1,25,000.00 (Exact threshold)
        self.engine.reset_state()
        self.engine.buy_lot("port_primary", "S2", "EQUITY", date(2022, 1, 1), Decimal("1"), Decimal("0.00"))
        self.engine.sell_units("port_primary", "S2", "EQUITY", date(2024, 8, 14), Decimal("1"), Decimal("125000.00"))
        sum_b = self.engine.compute_capital_gains_summary("port_primary", "FY2024-25")
        self.assertEqual(sum_b.total_ltcg_inr, Decimal("125000.00"))
        self.assertEqual(sum_b.section_112a_exemption_inr, Decimal("125000.00"))
        self.assertEqual(sum_b.taxable_ltcg_inr, Decimal("0.00"))
        self.assertEqual(sum_b.total_tax_inr, Decimal("0.00"))

        # Case C: LTCG ₹1,25,001.00 (₹1 above threshold -> Tax = 12.5% * ₹1 = ₹0.125 -> Banker's rounding to ₹0.12)
        self.engine.reset_state()
        self.engine.buy_lot("port_primary", "S3", "EQUITY", date(2022, 1, 1), Decimal("1"), Decimal("0.00"))
        self.engine.sell_units("port_primary", "S3", "EQUITY", date(2024, 8, 14), Decimal("1"), Decimal("125001.00"))
        sum_c = self.engine.compute_capital_gains_summary("port_primary", "FY2024-25")
        self.assertEqual(sum_c.total_ltcg_inr, Decimal("125001.00"))
        self.assertEqual(sum_c.section_112a_exemption_inr, Decimal("125000.00"))
        self.assertEqual(sum_c.taxable_ltcg_inr, Decimal("1.00"))
        self.assertEqual(sum_c.total_tax_inr, Decimal("0.12"))

        # Case D: LTCG ₹2,25,000.00 (₹1,00,000 taxable -> Tax = ₹12,500.00)
        self.engine.reset_state()
        self.engine.buy_lot("port_primary", "S4", "EQUITY", date(2022, 1, 1), Decimal("100"), Decimal("100.00"))
        self.engine.sell_units("port_primary", "S4", "EQUITY", date(2024, 8, 14), Decimal("100"), Decimal("2350.00"))
        sum_d = self.engine.compute_capital_gains_summary("port_primary", "FY2024-25")
        self.assertEqual(sum_d.total_ltcg_inr, Decimal("225000.00"))
        self.assertEqual(sum_d.section_112a_exemption_inr, Decimal("125000.00"))
        self.assertEqual(sum_d.taxable_ltcg_inr, Decimal("100000.00"))
        self.assertEqual(sum_d.total_tax_inr, Decimal("12500.00"))

    def test_section_112a_capital_loss_does_not_create_negative_exemption(self):
        """Capital loss (Proceeds < Cost Basis) must produce 0 tax and 0 exemption without crashing."""
        self.engine.buy_lot("port_primary", "LOSS_MAKER", "EQUITY", date(2022, 1, 1), Decimal("100"), Decimal("500.00"))
        disps = self.engine.sell_units("port_primary", "LOSS_MAKER", "EQUITY", date(2024, 8, 14), Decimal("100"), Decimal("300.00"))

        self.assertEqual(disps[0]["realized_gain_inr"], Decimal("-20000.00"))
        self.assertEqual(disps[0]["estimated_tax_inr"], Decimal("0.00"))

        summary = self.engine.compute_capital_gains_summary("port_primary", "FY2024-25")
        self.assertEqual(summary.total_ltcg_inr, Decimal("-20000.00"))
        self.assertEqual(summary.section_112a_exemption_inr, Decimal("0.00"))
        self.assertEqual(summary.taxable_ltcg_inr, Decimal("0.00"))
        self.assertEqual(summary.total_tax_inr, Decimal("0.00"))

    def test_section_50aa_debt_mf_always_stcg_slab_rate(self):
        """Specified Debt MFs acquired post 1-Apr-2023 are deemed STCG taxed at 30% slab rate regardless of holding period."""
        # Holding period: 3.5 years (1280 days)
        self.engine.buy_lot("port_primary", "ICICI_DEBT_FUND", "DEBT_MUTUAL_FUND", date(2023, 4, 15), Decimal("1000"), Decimal("20.00"))
        disps = self.engine.sell_units("port_primary", "ICICI_DEBT_FUND", "DEBT_MUTUAL_FUND", date(2026, 10, 15), Decimal("1000"), Decimal("26.00"))

        self.assertEqual(len(disps), 1)
        self.assertFalse(disps[0]["is_long_term"])
        self.assertEqual(disps[0]["section"], "50AA")
        self.assertEqual(disps[0]["tax_rate_pct"], Decimal("30.00"))
        self.assertEqual(disps[0]["realized_gain_inr"], Decimal("6000.00"))
        self.assertEqual(disps[0]["estimated_tax_inr"], Decimal("1800.00"))

    def test_sgb_maturity_redemption_100pct_tax_exempt_section_47(self):
        """Sovereign Gold Bonds held to maturity (Section 47) are 100% tax exempt (0% tax)."""
        self.engine.buy_lot("port_father", "SGB_2018_SERIES", "SGB_MATURITY", date(2018, 10, 23), Decimal("50"), Decimal("3146.00"))
        disps = self.engine.sell_units("port_father", "SGB_2018_SERIES", "SGB_MATURITY", date(2026, 10, 23), Decimal("50"), Decimal("7800.00"))

        self.assertEqual(len(disps), 1)
        self.assertTrue(disps[0]["is_long_term"])
        self.assertEqual(disps[0]["section"], "47")
        self.assertEqual(disps[0]["tax_rate_pct"], Decimal("0.00"))
        self.assertEqual(disps[0]["estimated_tax_inr"], Decimal("0.00"))

        # Verify excluded from taxable LTCG
        summary = self.engine.compute_capital_gains_summary("port_father", "FY2026-27")
        self.assertEqual(summary.taxable_ltcg_inr, Decimal("0.00"))
        self.assertEqual(summary.total_tax_inr, Decimal("0.00"))

    def test_foreign_equity_schwab_24_month_exact_boundary(self):
        """Foreign unlisted/US equities: <= 730 days is STCG @ 30%, > 730 days is LTCG @ 12.5%."""
        # 1. Exact 730 days holding (2022-08-14 to 2024-08-13): STCG 30%
        self.engine.buy_lot("port_primary", "AAPL", "US_EQUITY", date(2022, 8, 14), Decimal("10"), Decimal("150.00"), forex_rate=Decimal("80.00"))
        d_stcg = self.engine.sell_units("port_primary", "AAPL", "US_EQUITY", date(2024, 8, 13), Decimal("10"), Decimal("220.00"), forex_rate=Decimal("84.00"))
        self.assertEqual(d_stcg[0]["holding_days"], 730)
        self.assertFalse(d_stcg[0]["is_long_term"])
        self.assertEqual(d_stcg[0]["tax_rate_pct"], Decimal("30.00"))

        # 2. 731 days holding (2022-08-14 to 2024-08-14): LTCG 12.5%
        self.engine.buy_lot("port_primary", "MSFT", "US_EQUITY", date(2022, 8, 14), Decimal("10"), Decimal("250.00"), forex_rate=Decimal("80.00"))
        d_ltcg = self.engine.sell_units("port_primary", "MSFT", "US_EQUITY", date(2024, 8, 14), Decimal("10"), Decimal("400.00"), forex_rate=Decimal("84.00"))
        self.assertEqual(d_ltcg[0]["holding_days"], 731)
        self.assertTrue(d_ltcg[0]["is_long_term"])
        self.assertEqual(d_ltcg[0]["tax_rate_pct"], Decimal("12.50"))

    def test_foreign_tax_credit_tracking_for_withholding(self):
        """Foreign sales with IRS 1042-S tax withholding must compute FTC correctly in INR."""
        self.engine.buy_lot("port_primary", "NVDA", "US_EQUITY", date(2023, 1, 1), Decimal("10"), Decimal("100.00"), forex_rate=Decimal("82.00"))
        disps = self.engine.sell_units(
            portfolio_id="port_primary",
            asset_id="NVDA",
            asset_type="US_EQUITY",
            sell_date=date(2024, 8, 14),
            quantity=Decimal("10"),
            sell_price=Decimal("150.00"),
            forex_rate=Decimal("84.00"),
            foreign_tax_withheld_usd=Decimal("25.00"),
        )
        self.assertTrue(disps[0]["foreign_tax_credit_eligible"])
        # 25 USD * 84.00 = 2100.00 INR
        self.assertEqual(disps[0]["foreign_tax_withheld_inr"], Decimal("2100.00"))

        summary = self.engine.compute_capital_gains_summary("port_primary", "FY2024-25")
        self.assertEqual(summary.total_foreign_tax_credit_inr, Decimal("2100.00"))

    def test_oversell_and_zero_inventory_adversarial_rejection(self):
        """Selling more units than available or selling from non-existent assets must fail-closed with ValueError."""
        # 1. Oversell by 1 unit
        self.engine.buy_lot("port_primary", "LT", "EQUITY", date(2023, 1, 1), Decimal("50"), Decimal("2000.00"))
        with self.assertRaises(ValueError) as ctx1:
            self.engine.sell_units("port_primary", "LT", "EQUITY", date(2024, 1, 1), Decimal("51"), Decimal("2500.00"))
        self.assertIn("Oversell condition", str(ctx1.exception))

        # 2. Sell from non-existent asset
        with self.assertRaises(ValueError) as ctx2:
            self.engine.sell_units("port_primary", "GHOST_ASSET", "EQUITY", date(2024, 1, 1), Decimal("10"), Decimal("100.00"))
        self.assertIn("Oversell condition", str(ctx2.exception))

    def test_multi_portfolio_family_vault_isolation(self):
        """Cross-portfolio mutations must be strictly isolated between family members."""
        # Alex buys RELIANCE @ ₹2000
        self.engine.buy_lot("port_primary", "RELIANCE", "EQUITY", date(2023, 1, 1), Decimal("100"), Decimal("2000.00"))
        # Robert buys RELIANCE @ ₹2500
        self.engine.buy_lot("port_father", "RELIANCE", "EQUITY", date(2023, 1, 1), Decimal("50"), Decimal("2500.00"))
        # Margaret buys RELIANCE @ ₹2800
        self.engine.buy_lot("port_mother", "RELIANCE", "EQUITY", date(2023, 1, 1), Decimal("25"), Decimal("2800.00"))
        # HUF buys RELIANCE @ ₹3000
        self.engine.buy_lot("port_trust", "RELIANCE", "EQUITY", date(2023, 1, 1), Decimal("10"), Decimal("3000.00"))

        # Alex sells 100 units
        self.engine.sell_units("port_primary", "RELIANCE", "EQUITY", date(2024, 8, 14), Decimal("100"), Decimal("3200.00"))

        # Alex lots must be 0
        self.assertEqual(len(self.engine.get_open_lots("port_primary", "RELIANCE")), 0)

        # Robert, Margaret, HUF lots must be completely intact
        robert_lots = self.engine.get_open_lots("port_father", "RELIANCE")
        margaret_lots = self.engine.get_open_lots("port_mother", "RELIANCE")
        huf_lots = self.engine.get_open_lots("port_trust", "RELIANCE")

        self.assertEqual(len(robert_lots), 1)
        self.assertEqual(robert_lots[0]["remaining_quantity"], Decimal("50"))
        self.assertEqual(robert_lots[0]["cost_per_unit"], Decimal("2500.00"))

        self.assertEqual(len(margaret_lots), 1)
        self.assertEqual(margaret_lots[0]["remaining_quantity"], Decimal("25"))

    def test_comprehensive_mixed_asset_class_tax_summary_workload(self):
        """
        Comprehensive Finance Act 2024 mixed-asset annual capital gains workload:
        1. Indian Listed Equity LTCG (>12m): ₹2,00,000 gain (Section 112A)
        2. Indian Listed Equity STCG (<=12m): ₹50,000 gain (Section 111A @ 20%)
        3. Foreign US Equity LTCG (>24m): ₹1,00,000 gain (Schedule FA @ 12.5% unindexed, no 112A exemption)
        4. Section 50AA Debt Mutual Fund (Acquired post 1-Apr-2023): ₹30,000 gain (Deemed STCG @ 30%)
        5. SGB Maturity (Section 47): ₹40,000 gain (100% Tax Exempt)
        """
        # 1. Indian Equity LTCG
        self.engine.buy_lot("port_primary", "HDFCBANK", "EQUITY", date(2022, 1, 1), Decimal("100"), Decimal("1000.00"))
        self.engine.sell_units("port_primary", "HDFCBANK", "EQUITY", date(2024, 8, 14), Decimal("100"), Decimal("3000.00"))  # Gain = ₹2,00,000

        # 2. Indian Equity STCG
        self.engine.buy_lot("port_primary", "TCS_STCG", "EQUITY", date(2024, 5, 1), Decimal("50"), Decimal("3000.00"))
        self.engine.sell_units("port_primary", "TCS_STCG", "EQUITY", date(2024, 8, 14), Decimal("50"), Decimal("4000.00"))  # Gain = ₹50,000

        # 3. Foreign US Equity LTCG (>24m)
        self.engine.buy_lot("port_primary", "GOOGL", "US_EQUITY", date(2022, 1, 1), Decimal("10"), Decimal("100.00"), forex_rate=Decimal("80.00"))  # Cost = ₹80,000
        self.engine.sell_units("port_primary", "GOOGL", "US_EQUITY", date(2024, 8, 14), Decimal("10"), Decimal("225.00"), forex_rate=Decimal("80.00"))  # Proceeds = ₹1,80,000, Gain = ₹1,00,000

        # 4. Debt Mutual Fund (Section 50AA)
        self.engine.buy_lot("port_primary", "SBI_DEBT", "DEBT_MUTUAL_FUND", date(2023, 5, 1), Decimal("1000"), Decimal("10.00"))  # Cost = ₹10,000
        self.engine.sell_units("port_primary", "SBI_DEBT", "DEBT_MUTUAL_FUND", date(2024, 8, 14), Decimal("1000"), Decimal("40.00"))  # Proceeds = ₹40,000, Gain = ₹30,000

        # 5. SGB Maturity (Section 47)
        self.engine.buy_lot("port_primary", "SGB_SERIES_V", "SGB_MATURITY", date(2016, 8, 14), Decimal("10"), Decimal("3100.00"))  # Cost = ₹31,000
        self.engine.sell_units("port_primary", "SGB_SERIES_V", "SGB_MATURITY", date(2024, 8, 14), Decimal("10"), Decimal("7100.00"))  # Proceeds = ₹71,000, Gain = ₹40,000

        summary = self.engine.compute_capital_gains_summary("port_primary", "FY2024-25")

        # Invariant checks:
        # Total Indian Equity LTCG = ₹2,00,000
        # Section 112A Exemption = ₹1,25,000
        self.assertEqual(summary.section_112a_exemption_inr, Decimal("125000.00"))
        # Taxable Indian LTCG = 2,00,000 - 1,25,000 = 75,000 -> Tax @ 12.5% = 9,375.00
        # Taxable Foreign LTCG = 1,00,000 (No 112A exemption) -> Tax @ 12.5% = 12,500.00
        # Total Taxable LTCG = 75,000 + 100,000 = 175,000
        self.assertEqual(summary.taxable_ltcg_inr, Decimal("175000.00"))
        # Total STCG = 50,000 (Indian @ 20% = 10,000) + 30,000 (Debt @ 30% = 9,000) = 80,000
        self.assertEqual(summary.total_stcg_inr, Decimal("80000.00"))
        # Total Tax = 9,375 (112A) + 12,500 (Foreign LTCG) + 10,000 (111A) + 9,000 (50AA) = 40,875.00
        self.assertEqual(summary.total_tax_inr, Decimal("40875.00"))
        # Verify 5 total disposition records
        self.assertEqual(len(summary.dispositions), 5)

    def test_multi_year_separate_fy_exemption_isolation(self):
        """Capital gains exemptions in FY2023-24 must not leak or bleed into FY2024-25 computations."""
        # FY2023-24 trade: ₹1,50,000 LTCG
        self.engine.buy_lot("port_primary", "INFY", "EQUITY", date(2021, 1, 1), Decimal("100"), Decimal("1000.00"))
        self.engine.sell_units("port_primary", "INFY", "EQUITY", date(2023, 8, 14), Decimal("100"), Decimal("2500.00"))

        # FY2024-25 trade: ₹1,50,000 LTCG
        self.engine.buy_lot("port_primary", "WIPRO", "EQUITY", date(2022, 1, 1), Decimal("100"), Decimal("1000.00"))
        self.engine.sell_units("port_primary", "WIPRO", "EQUITY", date(2024, 8, 14), Decimal("100"), Decimal("2500.00"))

        # Summary for FY2023-24
        sum_fy23 = self.engine.compute_capital_gains_summary("port_primary", "FY2023-24")
        self.assertEqual(sum_fy23.total_ltcg_inr, Decimal("150000.00"))
        self.assertEqual(sum_fy23.section_112a_exemption_inr, Decimal("125000.00"))
        self.assertEqual(sum_fy23.taxable_ltcg_inr, Decimal("25000.00"))
        self.assertEqual(sum_fy23.total_tax_inr, Decimal("3125.00"))

        # Summary for FY2024-25 (should also get fresh ₹1,25,000 exemption)
        sum_fy24 = self.engine.compute_capital_gains_summary("port_primary", "FY2024-25")
        self.assertEqual(sum_fy24.total_ltcg_inr, Decimal("150000.00"))
        self.assertEqual(sum_fy24.section_112a_exemption_inr, Decimal("125000.00"))
        self.assertEqual(sum_fy24.taxable_ltcg_inr, Decimal("25000.00"))
        self.assertEqual(sum_fy24.total_tax_inr, Decimal("3125.00"))

    def test_same_day_multiple_lots_fifo_ordering(self):
        """Lots acquired on the same day must deplete in registration order."""
        self.engine.buy_lot("port_primary", "ITC", "EQUITY", date(2024, 1, 1), Decimal("50"), Decimal("300.00"))
        self.engine.buy_lot("port_primary", "ITC", "EQUITY", date(2024, 1, 1), Decimal("50"), Decimal("400.00"))

        # Sell 75 units
        disps = self.engine.sell_units("port_primary", "ITC", "EQUITY", date(2024, 8, 14), Decimal("75"), Decimal("500.00"))
        self.assertEqual(len(disps), 2)
        # Lot 1 (cost 300) fully depleted
        self.assertEqual(disps[0]["matched_quantity"], Decimal("50"))
        self.assertEqual(disps[0]["cost_basis_inr"], Decimal("15000.00"))

        # Lot 2 (cost 400) partially depleted by 25 units
        self.assertEqual(disps[1]["matched_quantity"], Decimal("25"))
        self.assertEqual(disps[1]["cost_basis_inr"], Decimal("10000.00"))

class TestAdversarialLedgerServiceIntegration(unittest.TestCase):
    """End-to-end integration stress tests combining all 4 gates, ForexEngine, FIFO Tax Engine, and LedgerService."""

    def setUp(self):
        self.ledger_svc = LedgerService()
        self.ledger_svc.reset_state()

    def test_e2e_schwab_us_trade_forex_and_fifo_integration(self):
        """Schwab US trades must automatically look up historical RBI reference rates and register FIFO tax lots."""
        from backend.tests.fixtures.sample_schwab import build_valid_schwab_statement
        from backend.tests.fixtures.sample_emails import create_schwab_mime

        schwab_stmt = build_valid_schwab_statement()
        # Ensure trade date is 2023-05-18 (which maps to rate 82.35)
        mime_bytes = create_schwab_mime(
            forwarder="alex.taylor@example.com",
            csv_bytes=schwab_stmt.to_csv_string().encode("utf-8"),
        )

        res = self.ledger_svc.ingest_inbound_email(mime_bytes, forwarder_email="alex.taylor@example.com")
        self.assertTrue(res["success"])
        self.assertEqual(res["portfolio_id"], "port_primary")
        self.assertEqual(res["new_transactions_committed"], 5)

        # Check that transactions in ledger have converted INR amounts
        txs = self.ledger_svc.get_transactions(portfolio_id="port_primary")
        self.assertEqual(len(txs), 5)
        for tx in txs:
            if tx.currency == "USD":
                self.assertGreater(tx.forex_rate, Decimal("1.00"))
                self.assertGreater(abs(tx.net_amount_inr), Decimal("0.00"))

        # Check active tax lots for NVDA (150 bought - 50 sold = 100 remaining)
        nvda_lots = self.ledger_svc.get_active_tax_lots(portfolio_id="port_primary", asset_id="NVDA")
        self.assertEqual(len(nvda_lots), 1)
        self.assertEqual(nvda_lots[0]["symbol"], "NVDA")
        self.assertEqual(nvda_lots[0]["remaining_quantity"], Decimal("100.0000"))
        # Cost per unit in USD: $62.40. Rate: 82.35. Cost per unit INR: 5138.64
        self.assertEqual(nvda_lots[0]["cost_per_unit_inr"], Decimal("5138.64"))

    def test_e2e_portfolio_balances_and_weighted_average_cost(self):
        """Portfolio asset balance query accurately calculates aggregate quantities and weighted average cost basis."""
        # Buy 100 shares of INFY @ ₹1000
        self.ledger_svc.fifo_engine.buy_lot("port_primary", "INFY", "EQUITY", date(2023, 1, 1), Decimal("100"), Decimal("1000.00"))
        # Buy 100 shares of INFY @ ₹1500
        self.ledger_svc.fifo_engine.buy_lot("port_primary", "INFY", "EQUITY", date(2023, 6, 1), Decimal("100"), Decimal("1500.00"))

        balances = self.ledger_svc.get_portfolio_balances(portfolio_id="port_primary")
        self.assertEqual(len(balances), 1)
        b = balances[0]
        self.assertEqual(b.asset_id, "INFY")
        self.assertEqual(b.total_quantity, Decimal("200"))
        # Total cost = 100*1000 + 100*1500 = 250,000. Avg cost = 250,000 / 200 = 1250.00
        self.assertEqual(b.total_cost_basis_inr, Decimal("250000.00"))
        self.assertEqual(b.average_cost_inr, Decimal("1250.00"))

        # Sell 50 shares (depletes from Lot 1 @ 1000)
        self.ledger_svc.fifo_engine.sell_units("port_primary", "INFY", "EQUITY", date(2024, 1, 1), Decimal("50"), Decimal("1600.00"))

        # Remaining: 50 @ 1000 (50,000) + 100 @ 1500 (150,000) = 200,000 / 150 = 1333.33
        balances_after = self.ledger_svc.get_portfolio_balances(portfolio_id="port_primary")
        b_after = balances_after[0]
        self.assertEqual(b_after.total_quantity, Decimal("150"))
        self.assertEqual(b_after.total_cost_basis_inr, Decimal("200000.00"))
        self.assertEqual(b_after.average_cost_inr, Decimal("1333.33"))


if __name__ == "__main__":
    unittest.main()


