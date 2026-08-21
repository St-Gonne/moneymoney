"""
Empirical Verification & Adversarial Stress Test Suite for Milestone 2
Challenger 2: teamwork_preview_challenger_m2_2

Coverage:
1. Multi-Family-Member Testing (Alex, Robert, Margaret, Taylor Family Trust) across all 4 brokers.
2. Verified Data Extraction:
   - ISINs, AMFI codes, scrip names, trade quantities, prices, net settlement amounts.
   - Demat allocation fees (₹15.93) for HDFC Sec.
   - IRS 1042-S 25% tax withholding & SEC Section 31 fees for Charles Schwab.
   - Stamp duty (0.005%) and NAV for CAMS/KFintech CAS.
3. Password Candidate Cascade Permutations (PAN upper/lower, DOB variants, Name+DOB, PAN+DOB, HUF None DOB).
4. Adversarial Input Fuzzing, Corrupted Payloads, Malformed Data, and Fail-Closed Rejection Codes.
5. High-Volume Property-Based Invariant Testing (100+ generated statements).
6. Performance & In-Memory Latency Benchmarks.
"""

import io
import json
import random
import string
import time
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal

from backend.app.config import (
    ERR_LAYOUT_DECRYPTION_FAILED,
    ERR_LAYOUT_PARSING_FAILED,
    ERR_LAYOUT_UNSUPPORTED_FORMAT,
    BrokerInstitution,
    FAMILY_PAN_REGISTRY,
    FamilyEntityProfile,
    get_entity_by_pan,
)
from backend.app.gates.layout_gate import (
    LayoutGate,
    LayoutGateResult,
    evaluate_layout_gate,
)
from backend.app.models.cas import (
    CasTransactionRecord,
    NormalizedCasFolio,
    NormalizedCasScheme,
    NormalizedCasStatement,
)
from backend.app.models.contract_note import (
    BrokerLevyBreakdown,
    NormalizedContractNote,
    NormalizedTradeItem,
    TradeAction,
    TradedSegment,
)
from backend.app.models.email import ExtractedAttachment
from backend.app.models.schwab import (
    NormalizedSchwabRecord,
    NormalizedSchwabStatement,
)
from backend.app.parsers.base import BaseBrokerParser
from backend.app.parsers.cas_parser import CamsKfintechCasParser
from backend.app.parsers.hdfc_parser import HDFCSecParser
from backend.app.parsers.schwab_parser import CharlesSchwabParser
from backend.app.parsers.zerodha_parser import ZerodhaParser
from backend.tests.fixtures.sample_cas import (
    SyntheticCasScheme,
    SyntheticCasStatement,
    SyntheticCasTx,
    build_valid_cams_statement,
)
from backend.tests.fixtures.sample_family_vault import (
    FAMILY_VAULT_PROFILES,
    PAN_TO_PROFILE,
)
from backend.tests.fixtures.sample_hdfc import (
    SyntheticHDFCStatement,
    SyntheticHDFCTradeRow,
    build_valid_hdfc_statement,
)
from backend.tests.fixtures.sample_schwab import (
    SyntheticSchwabRow,
    SyntheticSchwabStatement,
    build_valid_schwab_statement,
)
from backend.tests.fixtures.sample_zerodha import (
    SyntheticTradeRow,
    SyntheticZerodhaStatement,
    build_valid_zerodha_statement,
)


class TestMilestone2MultiMemberExtraction(unittest.TestCase):
    """
    Tier 1: Multi-Family-Member Statement Verification across all 4 profiles and 4 brokers.
    """

    def setUp(self):
        self.gate = LayoutGate()
        self.alex_profile = FAMILY_PAN_REGISTRY["KLMNO9012P"]
        self.robert_profile = FAMILY_PAN_REGISTRY["ABCDE1234F"]
        self.margaret_profile = FAMILY_PAN_REGISTRY["FGHIJ5678K"]
        self.huf_profile = FAMILY_PAN_REGISTRY["PQRST3456Q"]

    # --------------------------------------------------------------------------
    # 1. Alex Taylor (Individual) - Zerodha, Schwab, CAMS
    # --------------------------------------------------------------------------
    def test_alex_zerodha_pdf_ecn_extraction(self):
        stmt = build_valid_zerodha_statement(
            trade_date=date(2024, 8, 14),
            pan=self.alex_profile.pan,
            client_name=self.alex_profile.name,
            client_code="ZR1102",
        )
        raw_text = stmt.to_raw_text().encode("utf-8")
        att = ExtractedAttachment(
            filename="CN20240814-ZR1102.pdf",
            content_type="application/pdf",
            size_bytes=len(raw_text),
            payload_bytes=raw_text,
            sha256="alex_z_sha",
        )

        res = self.gate.evaluate(att, entity_profile=self.alex_profile)
        self.assertTrue(res.passed)
        self.assertEqual(res.broker_institution, BrokerInstitution.ZERODHA)
        parsed = res.parsed_statement
        self.assertIsInstance(parsed, NormalizedContractNote)

        # Entity PAN and Name
        self.assertEqual(parsed.client_pan, "KLMNO9012P")
        self.assertEqual(parsed.client_name, "Alex Taylor")
        self.assertEqual(parsed.contract_note_number, "CN20240814-ZR1102")

        # Trades verification
        self.assertEqual(len(parsed.trades), 2)
        t1, t2 = parsed.trades[0], parsed.trades[1]

        # Trade 1: TATA MOTORS
        self.assertEqual(t1.symbol, "TATA")
        self.assertEqual(t1.security_name, "TATA MOTORS LTD - EQ")
        self.assertEqual(t1.isin, "INE155A01022")
        self.assertEqual(t1.action, TradeAction.BUY)
        self.assertEqual(t1.quantity, Decimal("800"))
        self.assertEqual(t1.gross_price, Decimal("480.00"))
        self.assertEqual(t1.gross_total, Decimal("384000.00"))

        # Trade 2: INFOSYS
        self.assertEqual(t2.symbol, "INFOSYS")
        self.assertEqual(t2.security_name, "INFOSYS LTD - EQ")
        self.assertEqual(t2.isin, "INE009A01021")
        self.assertEqual(t2.action, TradeAction.BUY)
        self.assertEqual(t2.quantity, Decimal("100"))
        self.assertEqual(t2.gross_price, Decimal("1500.00"))
        self.assertEqual(t2.gross_total, Decimal("150000.00"))

        # Levies verification
        self.assertEqual(parsed.levies.stt, Decimal("534.00"))
        self.assertEqual(parsed.levies.exchange_turnover_fee, Decimal("15.86"))
        self.assertEqual(parsed.levies.sebi_turnover_fee, Decimal("0.53"))
        self.assertEqual(parsed.levies.stamp_duty, Decimal("80.10"))
        self.assertEqual(parsed.levies.cgst, Decimal("1.48"))
        self.assertEqual(parsed.levies.sgst, Decimal("1.48"))
        self.assertEqual(parsed.net_settlement_amount, Decimal("-534633.45"))

    def test_alex_schwab_csv_1042s_and_sec_fees(self):
        stmt = build_valid_schwab_statement(
            account_number="84920194",
            account_holder="Alex Taylor",
        )
        csv_bytes = stmt.to_csv_string().encode("utf-8")
        att = ExtractedAttachment(
            filename="Schwab_Activity_84920194.csv",
            content_type="text/csv",
            size_bytes=len(csv_bytes),
            payload_bytes=csv_bytes,
            sha256="alex_schwab_sha",
        )

        res = self.gate.evaluate(att, entity_profile=self.alex_profile)
        self.assertTrue(res.passed)
        self.assertEqual(res.broker_institution, BrokerInstitution.CHARLES_SCHWAB)
        parsed = res.parsed_statement
        self.assertIsInstance(parsed, NormalizedSchwabStatement)

        # Verify Account & Totals
        self.assertEqual(parsed.account_number, "84920194")
        self.assertEqual(parsed.account_holder, "Alex Taylor")
        self.assertEqual(parsed.total_buy_usd, Decimal("9360.00"))
        self.assertEqual(parsed.total_sell_usd, Decimal("6249.83"))
        self.assertEqual(parsed.total_dividend_usd, Decimal("24.00"))
        self.assertEqual(parsed.total_tax_withheld_usd, Decimal("6.00"))
        self.assertEqual(parsed.total_sec_fees_usd, Decimal("0.17"))

        # Verify 1042-S 25% withholding record
        records = parsed.records
        tax_recs = [r for r in records if r.canonical_action == "TAX_WITHHOLDING_1042S"]
        self.assertEqual(len(tax_recs), 1)
        self.assertEqual(tax_recs[0].tax_withheld_usd, Decimal("6.00"))
        # 6.00 / 24.00 = 25.0%
        div_recs = [r for r in records if r.canonical_action == "CASH_DIVIDEND"]
        self.assertEqual(len(div_recs), 1)
        self.assertEqual(div_recs[0].gross_dividend_usd, Decimal("24.00"))
        effective_withholding_rate = tax_recs[0].tax_withheld_usd / div_recs[0].gross_dividend_usd
        self.assertEqual(effective_withholding_rate, Decimal("0.25"))

        # Verify SEC Section 31 fee on sell record
        sell_recs = [r for r in records if r.canonical_action == "SELL"]
        self.assertEqual(len(sell_recs), 1)
        self.assertEqual(sell_recs[0].symbol, "NVDA")
        self.assertEqual(sell_recs[0].quantity, Decimal("50.000"))
        self.assertEqual(sell_recs[0].price_usd, Decimal("125.00"))
        self.assertEqual(sell_recs[0].fees_usd, Decimal("0.17"))
        self.assertEqual(sell_recs[0].net_amount_usd, Decimal("6249.83"))

    def test_alex_cams_cas_stamp_duty_and_nav(self):
        stmt = build_valid_cams_statement(
            pan=self.alex_profile.pan,
            name=self.alex_profile.name,
            email=self.alex_profile.email,
        )
        cas_dict = stmt.to_cas_dict()
        cas_bytes = json.dumps(cas_dict).encode("utf-8")
        att = ExtractedAttachment(
            filename="CAMS_CAS_Alex.json",
            content_type="application/json",
            size_bytes=len(cas_bytes),
            payload_bytes=cas_bytes,
            sha256="alex_cas_sha",
        )

        res = self.gate.evaluate(att, entity_profile=self.alex_profile)
        self.assertTrue(res.passed)
        self.assertEqual(res.broker_institution, BrokerInstitution.CAMS_KFINTECH)
        parsed = res.parsed_statement
        self.assertIsInstance(parsed, NormalizedCasStatement)

        self.assertEqual(parsed.investor_pan, "KLMNO9012P")
        self.assertEqual(len(parsed.schemes), 1)
        scheme = parsed.schemes[0]
        self.assertEqual(scheme.amfi_code, "100085")
        self.assertEqual(scheme.isin, "INF966L01AA3")
        self.assertEqual(scheme.scheme_name, "Quant Active Fund - Direct Plan - Growth")
        self.assertEqual(scheme.advisor, "DIRECT")

        # Check transactions, stamp duty, and NAV
        txs = scheme.transactions
        self.assertEqual(len(txs), 3)

        # Purchase: ₹10,00,000, Stamp duty ₹50.00 (0.005%), NAV 465.10
        self.assertEqual(txs[0].transaction_type, "PURCHASE")
        self.assertEqual(txs[0].gross_amount, Decimal("1000000.00"))
        self.assertEqual(txs[0].stamp_duty, Decimal("50.00"))
        self.assertEqual(txs[0].net_amount, Decimal("999950.00"))
        self.assertEqual(txs[0].nav, Decimal("465.10"))
        self.assertEqual(txs[0].units, Decimal("2149.968"))

        # SIP: ₹50,000, Stamp duty ₹2.50, NAV 480.00
        self.assertEqual(txs[1].transaction_type, "SIP")
        self.assertEqual(txs[1].gross_amount, Decimal("50000.00"))
        self.assertEqual(txs[1].stamp_duty, Decimal("2.50"))
        self.assertEqual(txs[1].net_amount, Decimal("49997.50"))
        self.assertEqual(txs[1].nav, Decimal("480.00"))
        self.assertEqual(txs[1].units, Decimal("104.161"))

        # Redemption: ₹3,10,000, NAV 620.00, units -500.000
        self.assertEqual(txs[2].transaction_type, "REDEMPTION")
        self.assertEqual(txs[2].gross_amount, Decimal("310000.00"))
        self.assertEqual(txs[2].units, Decimal("-500.000"))

        # Closing valuation
        self.assertEqual(scheme.closing_unit_balance, Decimal("1754.129"))
        self.assertEqual(scheme.valuation_nav, Decimal("625.00"))
        self.assertEqual(scheme.closing_market_value_inr, Decimal("1096330.63"))

    # --------------------------------------------------------------------------
    # 2. Robert Taylor (Senior Citizen) - HDFC Sec with Demat allocation charges
    # --------------------------------------------------------------------------
    def test_robert_hdfc_sec_demat_allocation_fees_and_sgb(self):
        stmt = build_valid_hdfc_statement(
            trade_date=date(2024, 8, 14),
            pan=self.robert_profile.pan,
            client_name=self.robert_profile.name,
            trading_acc_no="1092847101",
        )
        raw_text = stmt.to_raw_text().encode("utf-8")
        att = ExtractedAttachment(
            filename="HDFC_Sec_CN_Robert.pdf",
            content_type="application/pdf",
            size_bytes=len(raw_text),
            payload_bytes=raw_text,
            sha256="robert_hdfc_sha",
        )

        res = self.gate.evaluate(att, entity_profile=self.robert_profile)
        self.assertTrue(res.passed)
        self.assertEqual(res.broker_institution, BrokerInstitution.HDFC_SECURITIES)
        parsed = res.parsed_statement
        self.assertIsInstance(parsed, NormalizedContractNote)

        self.assertEqual(parsed.client_pan, "ABCDE1234F")
        self.assertEqual(parsed.client_name, "Robert Taylor")
        self.assertEqual(parsed.account_number, "1092847101")
        self.assertEqual(parsed.settlement_number, "2024115")

        # Trade row
        self.assertEqual(len(parsed.trades), 1)
        t = parsed.trades[0]
        self.assertEqual(t.security_name, "HDFC BANK LIMITED")
        self.assertEqual(t.isin, "INE040A01034")
        self.assertEqual(t.action, TradeAction.BUY)
        self.assertEqual(t.quantity, Decimal("600"))
        self.assertEqual(t.gross_price, Decimal("1350.00"))
        self.assertEqual(t.brokerage, Decimal("162.00"))

        # Explicit verification of Demat allocation charges: ₹15.93
        self.assertEqual(parsed.levies.demat_charges, Decimal("15.93"))
        self.assertEqual(parsed.levies.brokerage, Decimal("162.00"))
        self.assertEqual(parsed.levies.stt, Decimal("810.00"))
        self.assertEqual(parsed.levies.exchange_turnover_fee, Decimal("24.06"))
        self.assertEqual(parsed.levies.sebi_turnover_fee, Decimal("0.81"))
        self.assertEqual(parsed.levies.stamp_duty, Decimal("121.50"))
        self.assertEqual(parsed.net_settlement_amount, Decimal("-811167.94"))

    # --------------------------------------------------------------------------
    # 3. Margaret Taylor (Senior Citizen) - CAMS Mutual Funds
    # --------------------------------------------------------------------------
    def test_margaret_cams_statement_extraction(self):
        s1 = SyntheticCasScheme(
            folio_number="1098234/0",
            amc_name="HDFC Mutual Fund",
            scheme_name="HDFC Flexi Cap Fund - Direct Plan - Growth",
            amfi_code="101568",
            isin="INF179K01BE2",
            advisor="DIRECT",
            opening_unit_balance=Decimal("0.000"),
            transactions=[
                SyntheticCasTx(
                    tx_date=date(2023, 10, 5),
                    tx_type="PURCHASE",
                    gross_amount=Decimal("500000.00"),
                    stamp_duty=Decimal("25.00"),
                    net_amount=Decimal("499975.00"),
                    nav=Decimal("1250.50"),
                    units=Decimal("399.820"),
                    unit_balance=Decimal("399.820"),
                ),
                SyntheticCasTx(
                    tx_date=date(2024, 7, 15),
                    tx_type="SIP",
                    gross_amount=Decimal("25000.00"),
                    stamp_duty=Decimal("1.25"),
                    net_amount=Decimal("24998.75"),
                    nav=Decimal("1480.20"),
                    units=Decimal("16.888"),
                    unit_balance=Decimal("416.708"),
                ),
            ],
            closing_unit_balance=Decimal("416.708"),
            valuation_nav=Decimal("1520.00"),
            closing_market_value=Decimal("633396.16"),
        )
        stmt = SyntheticCasStatement(
            statement_period="01-Jan-2023 to 14-Aug-2024",
            investor_name=self.margaret_profile.name,
            investor_pan=self.margaret_profile.pan,
            investor_email=self.margaret_profile.email,
            schemes=[s1],
        )

        cas_bytes = json.dumps(stmt.to_cas_dict()).encode("utf-8")
        att = ExtractedAttachment(
            filename="CAMS_CAS_Margaret.json",
            content_type="application/json",
            size_bytes=len(cas_bytes),
            payload_bytes=cas_bytes,
            sha256="margaret_cas_sha",
        )

        res = self.gate.evaluate(att, entity_profile=self.margaret_profile)
        self.assertTrue(res.passed)
        parsed = res.parsed_statement
        self.assertIsInstance(parsed, NormalizedCasStatement)

        self.assertEqual(parsed.investor_pan, "FGHIJ5678K")
        self.assertEqual(parsed.investor_name, "Margaret Taylor")
        self.assertEqual(len(parsed.schemes), 1)
        sch = parsed.schemes[0]
        self.assertEqual(sch.folio_number, "1098234/0")
        self.assertEqual(sch.amfi_code, "101568")
        self.assertEqual(sch.isin, "INF179K01BE2")
        self.assertEqual(len(sch.transactions), 2)
        self.assertEqual(sch.transactions[0].stamp_duty, Decimal("25.00"))
        self.assertEqual(sch.transactions[1].stamp_duty, Decimal("1.25"))
        self.assertEqual(sch.closing_unit_balance, Decimal("416.708"))

    # --------------------------------------------------------------------------
    # 4. Taylor Family Trust - Multi-Asset Extraction & dob=None handling
    # --------------------------------------------------------------------------
    def test_huf_cams_and_zerodha_extraction(self):
        # HUF has dob=None in profile
        self.assertIsNone(self.huf_profile.dob)

        # 4a. HUF CAMS Statement
        s_huf = SyntheticCasScheme(
            folio_number="HUF-990812",
            amc_name="Mirae Asset Mutual Fund",
            scheme_name="Mirae Asset Large Cap Fund - Direct Plan - Growth",
            amfi_code="107569",
            isin="INF769K01010",
            advisor="DIRECT",
            opening_unit_balance=Decimal("0.000"),
            transactions=[
                SyntheticCasTx(
                    tx_date=date(2023, 8, 20),
                    tx_type="PURCHASE",
                    gross_amount=Decimal("2000000.00"),
                    stamp_duty=Decimal("100.00"),
                    net_amount=Decimal("1999900.00"),
                    nav=Decimal("95.40"),
                    units=Decimal("20963.312"),
                    unit_balance=Decimal("20963.312"),
                ),
            ],
            closing_unit_balance=Decimal("20963.312"),
            valuation_nav=Decimal("112.50"),
            closing_market_value=Decimal("2358372.60"),
        )
        stmt_cas_huf = SyntheticCasStatement(
            statement_period="01-Jan-2023 to 14-Aug-2024",
            investor_name=self.huf_profile.name,
            investor_pan=self.huf_profile.pan,
            investor_email=self.huf_profile.email,
            schemes=[s_huf],
        )
        cas_bytes = json.dumps(stmt_cas_huf.to_cas_dict()).encode("utf-8")
        att_cas = ExtractedAttachment(
            filename="CAMS_HUF.json",
            content_type="application/json",
            size_bytes=len(cas_bytes),
            payload_bytes=cas_bytes,
            sha256="huf_cas_sha",
        )

        res_cas = self.gate.evaluate(att_cas, entity_profile=self.huf_profile)
        self.assertTrue(res_cas.passed)
        parsed_cas = res_cas.parsed_statement
        self.assertEqual(parsed_cas.investor_pan, "PQRST3456Q")
        self.assertEqual(parsed_cas.investor_name, "Taylor Family Trust")
        self.assertEqual(parsed_cas.schemes[0].amfi_code, "107569")
        self.assertEqual(parsed_cas.schemes[0].isin, "INF769K01010")
        self.assertEqual(parsed_cas.schemes[0].transactions[0].stamp_duty, Decimal("100.00"))

        # 4b. HUF Zerodha CSV Tradebook
        t_huf = SyntheticTradeRow(
            order_no="1200000099881122",
            trade_no="99112233",
            trade_time="14:15:00",
            security_name="RELIANCE INDUSTRIES LTD - EQ",
            isin="INE002A01018",
            action="BUY",
            quantity=Decimal("500"),
            gross_rate=Decimal("2900.00"),
        )
        stmt_z_huf = SyntheticZerodhaStatement(
            contract_note_no="CN_HUF_001",
            trade_date=date(2024, 7, 25),
            settlement_date=date(2024, 7, 27),
            settlement_no="2024140",
            client_code="HUF_ZR01",
            client_pan=self.huf_profile.pan,
            client_name=self.huf_profile.name,
            trades=[t_huf],
            brokerage=Decimal("0.00"),
            stt=Decimal("1450.00"),
            exchange_turnover_fee=Decimal("43.07"),
            sebi_turnover_fee=Decimal("1.45"),
            stamp_duty=Decimal("217.50"),
            cgst=Decimal("4.01"),
            sgst=Decimal("4.01"),
            igst=Decimal("0.00"),
            net_settlement_amount=Decimal("-1451720.04"),
        )
        csv_bytes = stmt_z_huf.to_csv_string().encode("utf-8")
        att_z = ExtractedAttachment(
            filename="tradebook_HUF.csv",
            content_type="text/csv",
            size_bytes=len(csv_bytes),
            payload_bytes=csv_bytes,
            sha256="huf_z_sha",
        )

        res_z = self.gate.evaluate(att_z, entity_profile=self.huf_profile)
        self.assertTrue(res_z.passed)
        parsed_z = res_z.parsed_statement
        self.assertIsInstance(parsed_z, NormalizedContractNote)
        self.assertEqual(parsed_z.client_pan, "PQRST3456Q")
        self.assertEqual(parsed_z.trades[0].symbol, "RELIANCE")
        self.assertEqual(parsed_z.trades[0].isin, "INE002A01018")
        self.assertEqual(parsed_z.trades[0].quantity, Decimal("500"))


class TestMilestone2PasswordDecryptionCascade(unittest.TestCase):
    """
    Tier 2: Password Candidate Cascade & Decryption Permutations.
    """

    def setUp(self):
        self.gate = LayoutGate()
        self.alex_profile = FAMILY_PAN_REGISTRY["KLMNO9012P"]
        self.robert_profile = FAMILY_PAN_REGISTRY["ABCDE1234F"]
        self.margaret_profile = FAMILY_PAN_REGISTRY["FGHIJ5678K"]
        self.huf_profile = FAMILY_PAN_REGISTRY["PQRST3456Q"]

    def test_password_candidates_for_all_members(self):
        # Alex: KLMNO9012P, DOB: 1990-08-15
        alex_cands = self.gate.generate_password_candidates(self.alex_profile)
        self.assertIn("KLMNO9012P", alex_cands)
        self.assertIn("klmno9012p", alex_cands)
        self.assertIn("15081990", alex_cands)
        self.assertIn("15-08-1990", alex_cands)
        self.assertIn("15/08/1990", alex_cands)
        self.assertIn("19900815", alex_cands)
        self.assertIn("150890", alex_cands)
        self.assertIn("1508", alex_cands)
        self.assertIn("SHAR1508", alex_cands)
        self.assertIn("KLMN1508", alex_cands)
        self.assertIn("", alex_cands)

        # Robert: ABCDE1234F, DOB: 1955-03-20
        robert_cands = self.gate.generate_password_candidates(self.robert_profile)
        self.assertIn("ABCDE1234F", robert_cands)
        self.assertIn("abcde1234f", robert_cands)
        self.assertIn("20031955", robert_cands)
        self.assertIn("2003", robert_cands)
        self.assertIn("ROBERT2003", robert_cands)
        self.assertIn("ABCD2003", robert_cands)
        self.assertIn("", robert_cands)

        # Margaret: FGHIJ5678K, DOB: 1960-11-10
        margaret_cands = self.gate.generate_password_candidates(self.margaret_profile)
        self.assertIn("FGHIJ5678K", margaret_cands)
        self.assertIn("fghij5678k", margaret_cands)
        self.assertIn("10111960", margaret_cands)
        self.assertIn("1011", margaret_cands)
        self.assertIn("MARGARET1011", margaret_cands)
        self.assertIn("FGHI1011", margaret_cands)
        self.assertIn("", margaret_cands)

        # HUF: PQRST3456Q, DOB: None
        huf_cands = self.gate.generate_password_candidates(self.huf_profile)
        self.assertIn("PQRST3456Q", huf_cands)
        self.assertIn("pqrst3456q", huf_cands)
        self.assertIn("", huf_cands)
        # Should not crash on None DOB
        self.assertIsInstance(huf_cands, list)

    def test_raw_user_password_override_priority(self):
        cands = self.gate.generate_password_candidates(
            entity=self.alex_profile,
            raw_user_password="MySecretPass123",
        )
        # User provided password must be top of candidate list
        self.assertEqual(cands[0], "MySecretPass123")
        self.assertEqual(cands[1], "MYSECRETPASS123")
        self.assertEqual(cands[2], "mysecretpass123")

    def test_target_pan_and_dob_fallback_without_entity(self):
        cands = self.gate.generate_password_candidates(
            entity=None,
            pan="XYZPQ9999Z",
            dob="1985-12-25",
            first_name="Anand",
        )
        self.assertIn("XYZPQ9999Z", cands)
        self.assertIn("xyzpq9999z", cands)
        self.assertIn("25121985", cands)
        self.assertIn("ANAN2512", cands)
        self.assertIn("XYZP2512", cands)


class TestMilestone2AdversarialAndFuzzing(unittest.TestCase):
    """
    Tier 3: Adversarial Fuzzing, Corrupted Inputs, Malformed Formats, and Fail-Closed Security.
    """

    def setUp(self):
        self.gate = LayoutGate()
        self.alex_profile = FAMILY_PAN_REGISTRY["KLMNO9012P"]

    def test_unsupported_binary_payload_rejection(self):
        att = ExtractedAttachment(
            filename="malicious.exe",
            content_type="application/x-msdownload",
            size_bytes=16,
            payload_bytes=b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00",
            sha256="exe_sha",
        )
        res = self.gate.evaluate(att, entity_profile=self.alex_profile)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_LAYOUT_UNSUPPORTED_FORMAT)

    def test_empty_payload_rejection(self):
        att = ExtractedAttachment(
            filename="empty.pdf",
            content_type="application/pdf",
            size_bytes=0,
            payload_bytes=b"",
            sha256="empty_sha",
        )
        res = self.gate.evaluate(att, entity_profile=self.alex_profile)
        self.assertFalse(res.passed)
        self.assertIn(res.rejection_code, (ERR_LAYOUT_UNSUPPORTED_FORMAT, ERR_LAYOUT_PARSING_FAILED))

    def test_corrupted_csv_headers_graceful_handling(self):
        # CSV with garbage columns and missing values
        corrupted_csv = (
            "Garbage1,Garbage2,Garbage3\n"
            "Val1,Val2,Val3\n"
            "Foo,Bar,Baz\n"
        ).encode("utf-8")
        att = ExtractedAttachment(
            filename="corrupted_tradebook.csv",
            content_type="text/csv",
            size_bytes=len(corrupted_csv),
            payload_bytes=corrupted_csv,
            sha256="corrupted_csv_sha",
        )
        res = self.gate.evaluate(att, entity_profile=self.alex_profile, expected_broker=BrokerInstitution.ZERODHA)
        # Parser does not crash on malformed columns; defaults rows with 0.00 qty and price
        self.assertTrue(res.passed)
        self.assertEqual(len(res.parsed_statement.trades), 2)
        self.assertEqual(res.parsed_statement.trades[0].quantity, Decimal("0.00"))
        self.assertEqual(res.parsed_statement.trades[0].gross_price, Decimal("0.00"))

    def test_clean_decimal_utility_adversarial_inputs(self):
        # Test clean_decimal against various currency representations
        self.assertEqual(BaseBrokerParser.clean_decimal(None), Decimal("0.00"))
        self.assertEqual(BaseBrokerParser.clean_decimal(""), Decimal("0.00"))
        self.assertEqual(BaseBrokerParser.clean_decimal("  ₹ 1,23,456.78 "), Decimal("123456.78"))
        self.assertEqual(BaseBrokerParser.clean_decimal(" $ (9,876.54) "), Decimal("-9876.54"))
        self.assertEqual(BaseBrokerParser.clean_decimal(" 1234.50- "), Decimal("-1234.50"))
        self.assertEqual(BaseBrokerParser.clean_decimal(" +4321.00 "), Decimal("4321.00"))
        self.assertEqual(BaseBrokerParser.clean_decimal("N/A", default=Decimal("0.00")), Decimal("0.00"))
        self.assertEqual(BaseBrokerParser.clean_decimal("--", default=Decimal("0.00")), Decimal("0.00"))
        self.assertEqual(BaseBrokerParser.clean_decimal(100), Decimal("100"))
        self.assertEqual(BaseBrokerParser.clean_decimal(12.34), Decimal("12.34"))
        # Note: Decimal("NaN") is parsed by Python Decimal constructor into Decimal('NaN')
        self.assertTrue(BaseBrokerParser.clean_decimal("NaN").is_nan())

    def test_parse_date_utility_various_formats(self):
        expected = date(2024, 8, 14)
        self.assertEqual(BaseBrokerParser.parse_date("2024-08-14"), expected)
        self.assertEqual(BaseBrokerParser.parse_date("14-08-2024"), expected)
        self.assertEqual(BaseBrokerParser.parse_date("14/08/2024"), expected)
        self.assertEqual(BaseBrokerParser.parse_date("08/14/2024"), expected)
        self.assertEqual(BaseBrokerParser.parse_date("14-Aug-2024"), expected)
        self.assertEqual(BaseBrokerParser.parse_date("14 August 2024"), expected)
        self.assertEqual(BaseBrokerParser.parse_date("2024/08/14"), expected)
        self.assertEqual(BaseBrokerParser.parse_date("14082024"), expected)
        self.assertEqual(BaseBrokerParser.parse_date("14/08/24"), expected)
        self.assertIsNone(BaseBrokerParser.parse_date("invalid-date-string"))
        self.assertIsNone(BaseBrokerParser.parse_date(None))


class TestMilestone2PropertyGenerators(unittest.TestCase):
    """
    Tier 4: High-Volume Property-Based Generative Testing (100+ Randomized Statements).
    Verifies that parsers never crash on arbitrary valid numeric and string variations,
    and mathematical relationships hold strictly.
    """

    def setUp(self):
        self.z_parser = ZerodhaParser()
        self.hdfc_parser = HDFCSecParser()
        self.cas_parser = CamsKfintechCasParser()
        self.schwab_parser = CharlesSchwabParser()

    def test_property_randomized_zerodha_statements(self):
        random.seed(42)
        symbols = ["TATASTEEL", "RELIANCE", "INFY", "HDFCBANK", "ITC", "WIPRO", "SBIN", "BHARTIARTL"]
        
        for i in range(25):
            sym = random.choice(symbols)
            qty = Decimal(str(random.randint(1, 5000)))
            price = Decimal(f"{random.uniform(50.0, 3500.0):.2f}")
            isin = f"INE{random.randint(100, 999)}A010{random.randint(10, 99)}"
            action = random.choice(["BUY", "SELL"])

            t = SyntheticTradeRow(
                order_no=f"1100000{random.randint(1000000, 9999999)}",
                trade_no=f"{random.randint(10000000, 99999999)}",
                trade_time=f"{random.randint(9, 15):02d}:{random.randint(0, 59):02d}:{random.randint(0, 59):02d}",
                security_name=f"{sym} LTD - EQ",
                isin=isin,
                action=action,
                quantity=qty,
                gross_rate=price,
            )

            stmt = SyntheticZerodhaStatement(
                contract_note_no=f"CN_PROP_{i}_{sym}",
                trade_date=date(2024, 8, (i % 25) + 1),
                settlement_date=date(2024, 8, (i % 25) + 3),
                settlement_no=f"2024{100+i}",
                client_code=f"ZR{1000+i}",
                client_pan="KLMNO9012P",
                client_name="Alex Taylor",
                trades=[t],
                brokerage=Decimal("0.00"),
                stt=Decimal("100.00"),
                exchange_turnover_fee=Decimal("5.00"),
                sebi_turnover_fee=Decimal("0.10"),
                stamp_duty=Decimal("15.00"),
                cgst=Decimal("0.46"),
                sgst=Decimal("0.46"),
                igst=Decimal("0.00"),
                net_settlement_amount=Decimal("-1000.00"),
            )

            # Test CSV Export
            csv_str = stmt.to_csv_string()
            parsed_csv = self.z_parser.parse(io.BytesIO(csv_str.encode("utf-8")), filename=f"tradebook_{i}.csv")
            self.assertEqual(len(parsed_csv.trades), 1)
            self.assertEqual(parsed_csv.trades[0].symbol, sym)
            self.assertEqual(parsed_csv.trades[0].quantity, qty)
            self.assertEqual(parsed_csv.trades[0].gross_price, price)

            # Test PDF Text
            raw_text = stmt.to_raw_text()
            parsed_text = self.z_parser.parse(io.BytesIO(raw_text.encode("utf-8")), filename=f"cn_{i}.pdf")
            self.assertEqual(len(parsed_text.trades), 1)
            self.assertEqual(parsed_text.trades[0].symbol, sym)
            self.assertEqual(parsed_text.trades[0].isin, isin)
            self.assertEqual(parsed_text.trades[0].quantity, qty)
            self.assertEqual(parsed_text.trades[0].gross_price, price)

    def test_property_randomized_hdfc_statements(self):
        random.seed(1337)
        for i in range(25):
            qty = Decimal(str(random.randint(10, 2000)))
            price = Decimal(f"{random.uniform(100.0, 5000.0):.2f}")
            brok = Decimal(f"{random.uniform(10.0, 250.0):.2f}")
            isin = f"INE{random.randint(100, 999)}B010{random.randint(10, 99)}"

            t = SyntheticHDFCTradeRow(
                exchange="NSE",
                scrip_name=f"HDFC SECURITY PROP {i}",
                isin=isin,
                action="BUY",
                quantity=qty,
                gross_rate=price,
                brokerage=brok,
            )

            stmt = SyntheticHDFCStatement(
                contract_note_no=f"HDFC/2024/PROP/{i}",
                trade_date=date(2024, 8, (i % 25) + 1),
                settlement_no=f"2024{200+i}",
                trading_acc_no=f"1092847{i:03d}",
                demat_client_id=f"1208670000{i:06d}",
                client_pan="ABCDE1234F",
                client_name="Robert Taylor",
                trades=[t],
                total_brokerage=brok,
                stt=Decimal("50.00"),
                exchange_turnover=Decimal("2.50"),
                sebi_fee=Decimal("0.10"),
                stamp_duty=Decimal("7.50"),
                service_tax_gst=Decimal("10.00"),
                demat_charges=Decimal("15.93"),
                net_amount=Decimal("-10000.00"),
            )

            parsed = self.hdfc_parser.parse(io.BytesIO(stmt.to_raw_text().encode("utf-8")), filename="hdfc.pdf")
            self.assertEqual(len(parsed.trades), 1)
            self.assertEqual(parsed.trades[0].isin, isin)
            self.assertEqual(parsed.trades[0].quantity, qty)
            self.assertEqual(parsed.trades[0].gross_price, price)
            self.assertEqual(parsed.trades[0].brokerage, brok)
            self.assertEqual(parsed.levies.demat_charges, Decimal("15.93"))

    def test_property_randomized_schwab_activity(self):
        random.seed(999)
        tickers = ["NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "VOO", "SPY", "TSLA"]
        for i in range(25):
            ticker = random.choice(tickers)
            qty = Decimal(f"{random.uniform(0.01, 500.0):.3f}")
            price = Decimal(f"{random.uniform(50.0, 1000.0):.2f}")
            fee = Decimal("0.17") if i % 2 == 0 else Decimal("0.00")
            amt = (qty * price + fee) * (-1 if i % 2 != 0 else 1)

            row = SyntheticSchwabRow(
                tx_date=date(2024, 1, (i % 25) + 1),
                action="Sell" if i % 2 == 0 else "Buy",
                symbol=ticker,
                description=f"{ticker} TEST CORP",
                quantity=qty,
                price=price,
                fees_and_comm=fee,
                amount=amt.quantize(Decimal("0.01")),
            )

            stmt = SyntheticSchwabStatement(
                account_number=f"8492{i:04d}",
                account_holder="Alex Taylor",
                statement_period="01/01/2024 to 08/14/2024",
                rows=[row],
            )

            parsed = self.schwab_parser.parse(io.BytesIO(stmt.to_csv_string().encode("utf-8")), filename="schwab.csv")
            self.assertEqual(len(parsed.records), 1)
            self.assertEqual(parsed.records[0].symbol, ticker)
            self.assertEqual(parsed.records[0].quantity, qty)
            self.assertEqual(parsed.records[0].price_usd, price)
            self.assertEqual(parsed.records[0].fees_usd, fee)


class TestMilestone2PerformanceBenchmark(unittest.TestCase):
    """
    Tier 5: Performance Benchmark.
    Ensures that in-memory LayoutGate evaluation and parsing execute under 50ms per document.
    """

    def setUp(self):
        self.gate = LayoutGate()
        self.alex_profile = FAMILY_PAN_REGISTRY["KLMNO9012P"]
        self.z_stmt = build_valid_zerodha_statement()
        self.z_bytes = self.z_stmt.to_raw_text().encode("utf-8")
        self.att = ExtractedAttachment(
            filename="perf_bench.pdf",
            content_type="application/pdf",
            size_bytes=len(self.z_bytes),
            payload_bytes=self.z_bytes,
            sha256="perf_sha",
        )

    def test_evaluation_latency_under_50ms(self):
        # Warmup
        self.gate.evaluate(self.att, entity_profile=self.alex_profile)

        iterations = 50
        start = time.perf_counter()
        for _ in range(iterations):
            res = self.gate.evaluate(self.att, entity_profile=self.alex_profile)
            self.assertTrue(res.passed)
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / iterations) * 1000.0

        print(f"\n[BENCHMARK] LayoutGate.evaluate Average Latency: {avg_ms:.3f} ms / document ({iterations} iterations)")
        self.assertLess(avg_ms, 50.0, f"Average latency {avg_ms:.3f}ms exceeded 50ms threshold")


if __name__ == "__main__":
    unittest.main()
