"""
Unit Tests for Broker Statement Parsers & Gate 2 Layout Engine
Covers all 4 parsers (Zerodha, HDFC Sec, CAMS/KFintech CAS, Charles Schwab US),
password permutation cascade, and Gate 2 LayoutGate integration.
"""

import io
import unittest
from datetime import date
from decimal import Decimal

from backend.app.config import (
    ERR_LAYOUT_DECRYPTION_FAILED,
    ERR_LAYOUT_PARSING_FAILED,
    ERR_LAYOUT_UNSUPPORTED_FORMAT,
    BrokerInstitution,
    FAMILY_PAN_REGISTRY,
    FamilyEntityProfile,
)
from backend.app.gates.layout_gate import (
    LayoutGate,
    LayoutGateResult,
    evaluate_layout_gate,
)
from backend.app.models.contract_note import (
    NormalizedContractNote,
    NormalizedTradeItem,
    TradeAction,
    TradedSegment,
)
from backend.app.models.cas import (
    NormalizedCasStatement,
    NormalizedCasScheme,
)
from backend.app.models.schwab import (
    NormalizedSchwabStatement,
    NormalizedSchwabRecord,
)
from backend.app.models.email import ExtractedAttachment
from backend.app.parsers.cas_parser import CamsKfintechCasParser
from backend.app.parsers.hdfc_parser import HDFCSecParser
from backend.app.parsers.schwab_parser import CharlesSchwabParser
from backend.app.parsers.zerodha_parser import ZerodhaParser
from backend.tests.fixtures.sample_cas import (
    build_valid_cams_statement,
    SyntheticCasStatement,
)
from backend.tests.fixtures.sample_hdfc import (
    build_valid_hdfc_statement,
    SyntheticHDFCStatement,
)
from backend.tests.fixtures.sample_schwab import (
    build_valid_schwab_statement,
    SyntheticSchwabStatement,
)
from backend.tests.fixtures.sample_zerodha import (
    build_valid_zerodha_statement,
    SyntheticZerodhaStatement,
)


class TestZerodhaParser(unittest.TestCase):
    """Unit tests for ZerodhaContractNoteParser (PDF & CSV)."""

    def setUp(self):
        self.parser = ZerodhaParser()
        self.profile_primary = FAMILY_PAN_REGISTRY["KLMNO9012P"]

    def test_zerodha_can_parse(self):
        att_pdf = ExtractedAttachment(
            filename="CN20240814_KLMNO9012P.pdf",
            content_type="application/pdf",
            size_bytes=100,
            payload_bytes=b"%PDF-1.7 ZERODHA BROKING LTD CONTRACT NOTE",
            sha256="abc",
        )
        self.assertTrue(self.parser.can_parse(att_pdf))

        att_csv = ExtractedAttachment(
            filename="tradebook-ZR1102.csv",
            content_type="text/csv",
            size_bytes=100,
            payload_bytes=b"symbol,isin,trade_date,exchange,segment,series,trade_type,quantity,price,order_id,trade_id\nTATA,INE155A01022,2024-08-14,NSE,EQ,EQ,buy,800,480.00,1100000028471920,84920194",
            sha256="def",
        )
        self.assertTrue(self.parser.can_parse(att_csv))

    def test_parse_zerodha_ecn_text(self):
        synthetic = build_valid_zerodha_statement()
        raw_text = synthetic.to_raw_text()
        stream = io.BytesIO(raw_text.encode("utf-8"))

        res = self.parser.parse(stream, entity_profile=self.profile_primary, filename="CN_ZR1102.pdf")
        self.assertIsInstance(res, NormalizedContractNote)
        self.assertEqual(res.institution, BrokerInstitution.ZERODHA)
        self.assertEqual(res.contract_note_number, "CN20240814-ZR1102")
        self.assertEqual(res.client_pan, "KLMNO9012P")
        self.assertEqual(res.trade_date, date(2024, 8, 14))
        self.assertEqual(len(res.trades), 2)

        # Check Trade 1
        t1 = res.trades[0]
        self.assertEqual(t1.symbol, "TATA")
        self.assertEqual(t1.isin, "INE155A01022")
        self.assertEqual(t1.action, TradeAction.BUY)
        self.assertEqual(t1.quantity, Decimal("800"))
        self.assertEqual(t1.gross_price, Decimal("480.00"))
        self.assertEqual(t1.gross_total, Decimal("384000.00"))

        # Check Levies
        self.assertEqual(res.levies.stt, Decimal("534.00"))
        self.assertEqual(res.levies.exchange_turnover_fee, Decimal("15.86"))
        self.assertEqual(res.levies.sebi_turnover_fee, Decimal("0.53"))
        self.assertEqual(res.levies.stamp_duty, Decimal("80.10"))
        self.assertEqual(res.levies.cgst, Decimal("1.48"))
        self.assertEqual(res.levies.sgst, Decimal("1.48"))
        self.assertEqual(res.net_settlement_amount, Decimal("-534633.45"))

    def test_parse_zerodha_tradebook_csv(self):
        synthetic = build_valid_zerodha_statement()
        csv_text = synthetic.to_csv_string()
        stream = io.BytesIO(csv_text.encode("utf-8"))

        res = self.parser.parse(stream, entity_profile=self.profile_primary, filename="tradebook.csv")
        self.assertIsInstance(res, NormalizedContractNote)
        self.assertEqual(len(res.trades), 2)
        self.assertEqual(res.trades[0].symbol, "TATA")
        self.assertEqual(res.trades[0].quantity, Decimal("800"))
        self.assertEqual(res.trades[1].symbol, "INFOSYS")
        self.assertEqual(res.trades[1].quantity, Decimal("100"))


class TestHDFCSecParser(unittest.TestCase):
    """Unit tests for HDFCSecContractNoteParser."""

    def setUp(self):
        self.parser = HDFCSecParser()
        self.profile_father = FAMILY_PAN_REGISTRY["ABCDE1234F"]

    def test_hdfc_can_parse(self):
        att = ExtractedAttachment(
            filename="HDFC_CN_2024.pdf",
            content_type="application/pdf",
            size_bytes=100,
            payload_bytes=b"%PDF-1.6 HDFC SECURITIES LIMITED INZ000186937",
            sha256="abc",
        )
        self.assertTrue(self.parser.can_parse(att))

    def test_parse_hdfc_contract_note(self):
        synthetic = build_valid_hdfc_statement()
        raw_text = synthetic.to_raw_text()
        stream = io.BytesIO(raw_text.encode("utf-8"))

        res = self.parser.parse(stream, entity_profile=self.profile_father, filename="HDFC_CN.pdf")
        self.assertIsInstance(res, NormalizedContractNote)
        self.assertEqual(res.institution, BrokerInstitution.HDFC_SECURITIES)
        self.assertEqual(res.contract_note_number, "HDFC/2024/08/14/009182")
        self.assertEqual(res.settlement_number, "2024115")
        self.assertEqual(res.account_number, "1092847101")
        self.assertEqual(res.client_pan, "ABCDE1234F")
        self.assertEqual(len(res.trades), 1)

        t1 = res.trades[0]
        self.assertEqual(t1.security_name, "HDFC BANK LIMITED")
        self.assertEqual(t1.isin, "INE040A01034")
        self.assertEqual(t1.action, TradeAction.BUY)
        self.assertEqual(t1.quantity, Decimal("600"))
        self.assertEqual(t1.gross_price, Decimal("1350.00"))
        self.assertEqual(t1.brokerage, Decimal("162.00"))

        # Levies
        self.assertEqual(res.levies.brokerage, Decimal("162.00"))
        self.assertEqual(res.levies.stt, Decimal("810.00"))
        self.assertEqual(res.levies.exchange_turnover_fee, Decimal("24.06"))
        self.assertEqual(res.levies.sebi_turnover_fee, Decimal("0.81"))
        self.assertEqual(res.levies.stamp_duty, Decimal("121.50"))
        self.assertEqual(res.levies.demat_charges, Decimal("15.93"))
        self.assertEqual(res.net_settlement_amount, Decimal("-811167.94"))

    def test_parse_hdfc_sgb_trade(self):
        raw_text = (
            "HDFC SECURITIES LIMITED INZ000186937\n"
            "Contract Note No: HDFC/SGB/001 Trade Date: 14/08/2024\n"
            "Settlement No: 2024115 PAN: ABCDE1234F\n"
            "Trading A/c: 1092847101 Demat ID: 1208670000123456\n"
            "Client Name: Robert Taylor\n"
            "Exch Scrip Description ISIN B/S Qty Gross Rate Brokerage Net Amount\n"
            "NSE SGBMAY29 - EQ IN0020210040 BUY 50 6500.00 65.00 325065.00\n"
            "Total Brokerage : 65.00\n"
            "Securities Transaction Tax (STT) : 0.00\n"
            "Exchange Turnover Charges : 9.65\n"
            "SEBI Turnover Charges : 0.33\n"
            "Stamp Duty : 48.75\n"
            "GST on Brokerage & Charges (18%) : 13.50\n"
            "Demat Allocation Charges (inc GST) : 15.93\n"
            "Net Amount Payable by Client : -325153.16\n"
        )
        stream = io.BytesIO(raw_text.encode("utf-8"))
        res = self.parser.parse(stream, entity_profile=self.profile_father, filename="HDFC_SGB.pdf")
        self.assertEqual(len(res.trades), 1)
        self.assertEqual(res.trades[0].segment, TradedSegment.SGB)


class TestCamsKfintechCasParser(unittest.TestCase):
    """Unit tests for CAMS / KFintech CAS Parser."""

    def setUp(self):
        self.parser = CamsKfintechCasParser()
        self.profile_primary = FAMILY_PAN_REGISTRY["KLMNO9012P"]

    def test_cas_can_parse(self):
        att = ExtractedAttachment(
            filename="CAMS_CAS_July2024.pdf",
            content_type="application/pdf",
            size_bytes=100,
            payload_bytes=b"%PDF-1.4 CAMS Consolidated Account Statement",
            sha256="abc",
        )
        self.assertTrue(self.parser.can_parse(att))

    def test_parse_cas_dict_structure(self):
        synthetic = build_valid_cams_statement()
        cas_dict = synthetic.to_cas_dict()
        import json
        stream = io.BytesIO(json.dumps(cas_dict).encode("utf-8"))

        res = self.parser.parse(stream, entity_profile=self.profile_primary, filename="cas.json")
        self.assertIsInstance(res, NormalizedCasStatement)
        self.assertEqual(res.investor_pan, "KLMNO9012P")
        self.assertEqual(len(res.schemes), 1)

        scheme = res.schemes[0]
        self.assertEqual(scheme.folio_number, "4481023/1")
        self.assertEqual(scheme.amc_name, "Quant Mutual Fund")
        self.assertEqual(scheme.scheme_name, "Quant Active Fund - Direct Plan - Growth")
        self.assertEqual(scheme.amfi_code, "100085")
        self.assertEqual(scheme.isin, "INF966L01AA3")
        self.assertEqual(scheme.advisor, "DIRECT")
        self.assertEqual(len(scheme.transactions), 3)

        # Check transactions
        t1 = scheme.transactions[0]
        self.assertEqual(t1.transaction_type, "PURCHASE")
        self.assertEqual(t1.gross_amount, Decimal("1000000.00"))
        self.assertEqual(t1.stamp_duty, Decimal("50.00"))
        self.assertEqual(t1.units, Decimal("2149.968"))

        t2 = scheme.transactions[1]
        self.assertEqual(t2.transaction_type, "SIP")
        self.assertEqual(t2.gross_amount, Decimal("50000.00"))
        self.assertEqual(t2.stamp_duty, Decimal("2.50"))
        self.assertEqual(t2.units, Decimal("104.161"))

        t3 = scheme.transactions[2]
        self.assertEqual(t3.transaction_type, "REDEMPTION")
        self.assertEqual(t3.units, Decimal("-500.000"))

        self.assertEqual(scheme.closing_unit_balance, Decimal("1754.129"))
        self.assertEqual(scheme.valuation_nav, Decimal("625.00"))
        self.assertEqual(scheme.closing_market_value_inr, Decimal("1096330.63"))


class TestCharlesSchwabParser(unittest.TestCase):
    """Unit tests for Charles Schwab US CSV Activity Parser."""

    def setUp(self):
        self.parser = CharlesSchwabParser()
        self.profile_primary = FAMILY_PAN_REGISTRY["KLMNO9012P"]

    def test_schwab_can_parse(self):
        att = ExtractedAttachment(
            filename="Schwab_Activity.csv",
            content_type="text/csv",
            size_bytes=100,
            payload_bytes=b'"Date","Action","Symbol","Description","Quantity","Price","Fees & Comm","Amount"',
            sha256="abc",
        )
        self.assertTrue(self.parser.can_parse(att))

    def test_parse_schwab_csv_activity(self):
        synthetic = build_valid_schwab_statement()
        csv_str = synthetic.to_csv_string()
        stream = io.BytesIO(csv_str.encode("utf-8"))

        res = self.parser.parse(stream, entity_profile=self.profile_primary, filename="schwab.csv")
        self.assertIsInstance(res, NormalizedSchwabStatement)
        self.assertEqual(res.account_number, "84920194")
        self.assertEqual(len(res.records), 5)

        # Check Buy
        r1 = res.records[0]
        self.assertEqual(r1.canonical_action, "BUY")
        self.assertEqual(r1.symbol, "NVDA")
        self.assertEqual(r1.quantity, Decimal("150.000"))
        self.assertEqual(r1.price_usd, Decimal("62.40"))
        self.assertEqual(r1.net_amount_usd, Decimal("-9360.00"))

        # Check Dividend
        r2 = res.records[1]
        self.assertEqual(r2.canonical_action, "CASH_DIVIDEND")
        self.assertEqual(r2.gross_dividend_usd, Decimal("24.00"))

        # Check Tax Withholding
        r3 = res.records[2]
        self.assertEqual(r3.canonical_action, "TAX_WITHHOLDING_1042S")
        self.assertEqual(r3.tax_withheld_usd, Decimal("6.00"))

        # Check Reinvestment
        r4 = res.records[3]
        self.assertEqual(r4.canonical_action, "DIVIDEND_REINVEST")
        self.assertEqual(r4.symbol, "VOO")
        self.assertEqual(r4.quantity, Decimal("0.050"))

        # Check Sell with SEC fee
        r5 = res.records[4]
        self.assertEqual(r5.canonical_action, "SELL")
        self.assertEqual(r5.symbol, "NVDA")
        self.assertEqual(r5.quantity, Decimal("50.000"))
        self.assertEqual(r5.price_usd, Decimal("125.00"))
        self.assertEqual(r5.fees_usd, Decimal("0.17"))
        self.assertEqual(r5.net_amount_usd, Decimal("6249.83"))

        # Check Totals
        self.assertEqual(res.total_buy_usd, Decimal("9360.00"))
        self.assertEqual(res.total_sell_usd, Decimal("6249.83"))
        self.assertEqual(res.total_dividend_usd, Decimal("24.00"))
        self.assertEqual(res.total_tax_withheld_usd, Decimal("6.00"))
        self.assertEqual(res.total_sec_fees_usd, Decimal("0.17"))


class TestLayoutGateAndDecryption(unittest.TestCase):
    """Unit tests for Gate 2: Supported-Layout Gate & Password Permutations."""

    def setUp(self):
        self.gate = LayoutGate()
        self.profile_primary = FAMILY_PAN_REGISTRY["KLMNO9012P"]
        self.profile_father = FAMILY_PAN_REGISTRY["ABCDE1234F"]

    def test_password_candidates_generation(self):
        # Test Alex (DOB: 1990-08-15)
        cands_alex = self.gate.generate_password_candidates(self.profile_primary)
        self.assertIn("KLMNO9012P", cands_alex)
        self.assertIn("klmno9012p", cands_alex)
        self.assertIn("15081990", cands_alex)
        self.assertIn("15-08-1990", cands_alex)
        self.assertIn("15/08/1990", cands_alex)
        self.assertIn("1508", cands_alex)
        self.assertIn("SHAR1508", cands_alex)
        self.assertIn("KLMN1508", cands_alex)
        self.assertIn("", cands_alex)

        # Test Robert (DOB: 1955-03-20)
        cands_robert = self.gate.generate_password_candidates(self.profile_father)
        self.assertIn("ABCDE1234F", cands_robert)
        self.assertIn("20031955", cands_robert)
        self.assertIn("ROBERT2003", cands_robert)
        self.assertIn("ABCD2003", cands_robert)

    def test_layout_gate_evaluation_zerodha(self):
        synthetic = build_valid_zerodha_statement()
        raw_text = synthetic.to_raw_text().encode("utf-8")
        att = ExtractedAttachment(
            filename="CN_ZR1102.pdf",
            content_type="application/pdf",
            size_bytes=len(raw_text),
            payload_bytes=raw_text,
            sha256="hash1",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_primary)
        self.assertTrue(res.passed, f"Gate 2 failed: {res.rejection_reason}")
        self.assertEqual(res.layout_type, "ZERODHA_PDF")
        self.assertEqual(res.broker_institution, BrokerInstitution.ZERODHA)
        self.assertIsInstance(res.parsed_statement, NormalizedContractNote)

    def test_layout_gate_evaluation_hdfc(self):
        synthetic = build_valid_hdfc_statement()
        raw_text = synthetic.to_raw_text().encode("utf-8")
        att = ExtractedAttachment(
            filename="HDFC_CN.pdf",
            content_type="application/pdf",
            size_bytes=len(raw_text),
            payload_bytes=raw_text,
            sha256="hash2",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_father)
        self.assertTrue(res.passed)
        self.assertEqual(res.layout_type, "HDFC_PDF")
        self.assertEqual(res.broker_institution, BrokerInstitution.HDFC_SECURITIES)
        self.assertIsInstance(res.parsed_statement, NormalizedContractNote)

    def test_layout_gate_evaluation_cams(self):
        synthetic = build_valid_cams_statement()
        import json
        raw_json = json.dumps(synthetic.to_cas_dict()).encode("utf-8")
        att = ExtractedAttachment(
            filename="CAMS_CAS.json",
            content_type="application/json",
            size_bytes=len(raw_json),
            payload_bytes=raw_json,
            sha256="hash3",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_primary)
        self.assertTrue(res.passed)
        self.assertEqual(res.broker_institution, BrokerInstitution.CAMS_KFINTECH)
        self.assertIsInstance(res.parsed_statement, NormalizedCasStatement)

    def test_layout_gate_evaluation_schwab_csv(self):
        synthetic = build_valid_schwab_statement()
        raw_csv = synthetic.to_csv_string().encode("utf-8")
        att = ExtractedAttachment(
            filename="Schwab_Activity.csv",
            content_type="text/csv",
            size_bytes=len(raw_csv),
            payload_bytes=raw_csv,
            sha256="hash4",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_primary)
        self.assertTrue(res.passed)
        self.assertEqual(res.layout_type, "SCHWAB_CSV")
        self.assertEqual(res.broker_institution, BrokerInstitution.CHARLES_SCHWAB)
        self.assertIsInstance(res.parsed_statement, NormalizedSchwabStatement)

    def test_layout_gate_unsupported_format_rejected(self):
        att = ExtractedAttachment(
            filename="unsupported.bin",
            content_type="application/octet-stream",
            size_bytes=10,
            payload_bytes=b"\x00\x01\x02\x03\x04",
            sha256="hash5",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_primary)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_LAYOUT_UNSUPPORTED_FORMAT)

    def test_convenience_evaluate_layout_gate(self):
        synthetic = build_valid_zerodha_statement()
        raw_text = synthetic.to_raw_text().encode("utf-8")
        att = ExtractedAttachment(
            filename="CN.pdf",
            content_type="application/pdf",
            size_bytes=len(raw_text),
            payload_bytes=raw_text,
            sha256="hash6",
        )
        res = evaluate_layout_gate(att, entity_profile=self.profile_primary)
        self.assertTrue(res.passed)


if __name__ == "__main__":
    unittest.main()
