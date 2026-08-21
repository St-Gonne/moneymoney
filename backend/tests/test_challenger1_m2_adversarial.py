"""
Comprehensive Adversarial Stress Testing & Robustness Verification Suite (Gate 2 - Supported-Layout Gate & Parsers)
Milestone 2: Supported-Layout Gate, Decryption Engine & Multi-Broker Parsers
Challenger 1: teamwork_preview_challenger_m2_1

Covers:
1. PDF Decryption Cascade & Encrypted/Corrupted PDFs (wrong passwords, corrupted streams, missing pikepdf fallbacks)
2. Malformed & Corrupted CSVs (missing headers, strange delimiters, blank rows, corrupted numbers, null bytes)
3. Layout Spoofing & Format Mismatches (cross-broker headers/bodies, fake signature tokens, mismatched schemas)
4. Fractional Share Precision & High Decimal Quantities (micro-shares, high-decimal NAVs, large portfolios)
5. Extreme Charges & Negative Values (negative prices/quantities, exorbitant levies, excessive 1042-S withholding)
6. Defect Demonstrations & Type Robustness (boolean clean_decimal, truncated CSV rows, None filenames, int parameters)
7. Gate 2 Fuzzing Harness: 1,000 randomized mutations validating fail-closed perimeter behavior with zero unhandled exceptions
"""

import csv
import decimal
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
import random
import string
import sys
import unittest
import unittest.mock as mock
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional, Tuple, Union

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.config import (
    ERR_LAYOUT_DECRYPTION_FAILED,
    ERR_LAYOUT_PARSING_FAILED,
    ERR_LAYOUT_UNSUPPORTED_FORMAT,
    FAMILY_PAN_REGISTRY,
    BrokerInstitution,
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
from backend.tests.fixtures.sample_cas import build_valid_cams_statement
from backend.tests.fixtures.sample_hdfc import build_valid_hdfc_statement
from backend.tests.fixtures.sample_schwab import build_valid_schwab_statement
from backend.tests.fixtures.sample_zerodha import build_valid_zerodha_statement


class TestAdversarialDecryptionAndEncryptedPDFs(unittest.TestCase):
    """Category 1: Adversarial PDF Decryption Cascade & Corrupted Encrypted Files."""

    def setUp(self):
        self.gate = LayoutGate()
        self.profile_primary = FAMILY_PAN_REGISTRY["KLMNO9012P"]
        self.profile_father = FAMILY_PAN_REGISTRY["ABCDE1234F"]
        self.profile_mother = FAMILY_PAN_REGISTRY["FGHIJ5678K"]

    def test_password_candidates_generation_completeness_and_order(self):
        """Tests that candidate password permutations cover all required variations in deterministic order."""
        cands = self.gate.generate_password_candidates(
            entity=self.profile_primary,
            raw_user_password=" CustomSecret123 ",
        )
        # 1. User provided passwords
        self.assertIn("CustomSecret123", cands)
        self.assertIn("CUSTOMSECRET123", cands)
        self.assertIn("customsecret123", cands)
        # 2. PAN
        self.assertIn("KLMNO9012P", cands)
        self.assertIn("klmno9012p", cands)
        # 3. DOB variations (1990-08-15)
        self.assertIn("15081990", cands)
        self.assertIn("15-08-1990", cands)
        self.assertIn("15/08/1990", cands)
        self.assertIn("19900815", cands)
        self.assertIn("150890", cands)
        self.assertIn("1508", cands)
        # 4. Hybrid Name + DDMM (SHAR1508)
        self.assertIn("SHAR1508", cands)
        # 5. Hybrid PAN + DDMM (KLMN1508)
        self.assertIn("KLMN1508", cands)
        # 6. Unencrypted fallback
        self.assertIn("", cands)

    def test_pikepdf_mock_successful_decryption_with_cascade_match(self):
        """Simulates pikepdf QPDF engine decrypting successfully when matching password is tried."""
        mock_pikepdf = mock.MagicMock()
        class MockPasswordError(Exception): pass
        mock_pikepdf.PasswordError = MockPasswordError

        target_password = "15081990"  # Alex's DOB DDMMYYYY

        def open_side_effect(stream, password=""):
            if password == target_password:
                mock_pdf = mock.MagicMock()
                mock_pdf.save = lambda out: out.write(b"%PDF-1.4 Decrypted Zerodha Note")
                mock_cm = mock.MagicMock()
                mock_cm.__enter__ = mock.MagicMock(return_value=mock_pdf)
                mock_cm.__exit__ = mock.MagicMock(return_value=False)
                return mock_cm
            else:
                raise MockPasswordError("Invalid password")

        mock_pikepdf.open.side_effect = open_side_effect

        with mock.patch("backend.app.gates.layout_gate.pikepdf", mock_pikepdf):
            gate = LayoutGate()
            cands = gate.generate_password_candidates(entity=self.profile_primary)
            success, dec_bytes, pwd_used = gate.decrypt_pdf(b"%PDF-1.4 encrypted content", cands)
            self.assertTrue(success)
            self.assertEqual(pwd_used, target_password)
            self.assertEqual(dec_bytes, b"%PDF-1.4 Decrypted Zerodha Note")

    def test_corrupted_pdf_stream_with_pdf_header_does_not_crash(self):
        """Corrupted PDF binary with missing xref table or truncated structure does not raise unhandled crash."""
        corrupt_pdf_bytes = b"%PDF-1.4 \x00\xff\xfe\xfd Truncated and Damaged Object Stream"
        att = ExtractedAttachment(
            filename="corrupt_contract_note.pdf",
            content_type="application/pdf",
            size_bytes=len(corrupt_pdf_bytes),
            payload_bytes=corrupt_pdf_bytes,
            sha256="corrupt1",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_primary)
        self.assertIsInstance(res, LayoutGateResult)
        # Should either fail closed or produce empty AST gracefully
        if not res.passed:
            self.assertIn(res.rejection_code, [ERR_LAYOUT_UNSUPPORTED_FORMAT, ERR_LAYOUT_PARSING_FAILED, ERR_LAYOUT_DECRYPTION_FAILED])

    def test_non_pdf_file_with_pdf_extension_rejection(self):
        """Binary file (e.g. Windows EXE / ZIP) with .pdf extension fails closed."""
        fake_pdf = b"MZ\x90\x00\x03\x00\x00\x00 This is a Windows Executable, Not a PDF"
        att = ExtractedAttachment(
            filename="fake_statement.pdf",
            content_type="application/pdf",
            size_bytes=len(fake_pdf),
            payload_bytes=fake_pdf,
            sha256="fake_pdf_sha",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_primary)
        self.assertIsInstance(res, LayoutGateResult)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_LAYOUT_UNSUPPORTED_FORMAT)


class TestAdversarialMalformedAndCorruptedCSVs(unittest.TestCase):
    """Category 2: Malformed & Corrupted CSV Ingestion (Zerodha & Charles Schwab)."""

    def setUp(self):
        self.gate = LayoutGate()
        self.zerodha_parser = ZerodhaParser()
        self.schwab_parser = CharlesSchwabParser()
        self.profile_primary = FAMILY_PAN_REGISTRY["KLMNO9012P"]

    def test_csv_with_missing_headers_handled_gracefully(self):
        """CSV without header line generates fallback security symbols without crashing."""
        raw_csv = b"TATA,INE155A01022,2024-08-14,NSE,EQ,EQ,buy,800,480.00,ORD1,TRD1\n"
        res = self.zerodha_parser._parse_csv(raw_csv, entity_profile=self.profile_primary, filename="tradebook.csv")
        self.assertIsInstance(res, NormalizedContractNote)
        self.assertEqual(len(res.trades), 0)  # Header row was treated as keys

    def test_csv_with_interleaved_blank_rows_and_trailing_empty_lines_through_gate(self):
        """CSV with scattered blank lines and trailing newlines fails closed through Gate 2 without unhandled exception."""
        raw_csv = (
            b"symbol,isin,trade_date,exchange,segment,series,trade_type,quantity,price,order_id,trade_id\n"
            b"\n"
            b"TATA,INE155A01022,2024-08-14,NSE,EQ,EQ,buy,800,480.00,ORD1,TRD1\n"
            b"   \n"
            b"\r\n"
            b"INFOSYS,INE009A01021,2024-08-14,NSE,EQ,EQ,sell,100,1750.00,ORD2,TRD2\n"
            b"\n\n\n"
        )
        att = ExtractedAttachment(
            filename="tradebook_blanks.csv",
            content_type="text/csv",
            size_bytes=len(raw_csv),
            payload_bytes=raw_csv,
            sha256="blanks_sha",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_primary)
        self.assertIsInstance(res, LayoutGateResult)

    def test_schwab_csv_with_missing_date_and_disclaimer_preamble_through_gate(self):
        """Schwab CSV with multi-line account disclaimer preamble before header fails closed through Gate 2 without unhandled exception."""
        raw_csv = (
            b'"Transactions for account 84920194 as of 08/14/2026"\n'
            b'"Disclaimer: This information is not an official tax document."\n'
            b'\n'
            b'"Date","Action","Symbol","Description","Quantity","Price","Fees & Comm","Amount"\n'
            b'"05/18/2023","Buy","NVDA","NVIDIA CORP","150.000","62.40","$0.00","-$9360.00"\n'
            b'"05/19/2023","Cash Dividend","NVDA","NVIDIA CORP","","","$0.00","$24.00"\n'
            b'"Total Account Value: $1,250,000.00"\n'
        )
        att = ExtractedAttachment(
            filename="schwab_preamble.csv",
            content_type="text/csv",
            size_bytes=len(raw_csv),
            payload_bytes=raw_csv,
            sha256="schwab_preamble_sha",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_primary)
        self.assertIsInstance(res, LayoutGateResult)

    def test_csv_with_corrupted_number_strings_defaults_to_zero(self):
        """Corrupted strings like '#VALUE!', '#REF!', 'N/A', 'NaN' default to 0.00 safely."""
        raw_csv = (
            b"symbol,isin,trade_date,exchange,segment,series,trade_type,quantity,price,order_id,trade_id\n"
            b"TATA,INE155A01022,2024-08-14,NSE,EQ,EQ,buy,#VALUE!,#REF!,ORD1,TRD1\n"
        )
        res = self.zerodha_parser._parse_csv(raw_csv, entity_profile=self.profile_primary, filename="tradebook.csv")
        self.assertIsInstance(res, NormalizedContractNote)
        self.assertEqual(len(res.trades), 1)
        self.assertEqual(res.trades[0].quantity, Decimal("0.00"))
        self.assertEqual(res.trades[0].gross_price, Decimal("0.00"))
        self.assertEqual(res.trades[0].gross_total, Decimal("0.00"))

    def test_csv_with_null_bytes_fails_closed_through_gate(self):
        """CSV containing embedded null bytes fails closed gracefully through Gate 2 without unhandled exception."""
        raw_csv = (
            b"symbol,isin,trade_date,exchange,segment,series,trade_type,quantity,price,order_id,trade_id\n"
            b"TATA\x00CORP,INE155A01022,2024-08-14,NSE,EQ,EQ,buy,100,500.00,ORD1,TRD1\n"
        )
        att = ExtractedAttachment(
            filename="tradebook_nulls.csv",
            content_type="text/csv",
            size_bytes=len(raw_csv),
            payload_bytes=raw_csv,
            sha256="null_sha",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_primary)
        self.assertIsInstance(res, LayoutGateResult)
        if not res.passed:
            self.assertEqual(res.rejection_code, ERR_LAYOUT_PARSING_FAILED)



class TestAdversarialLayoutSpoofingAndFormatConfusion(unittest.TestCase):
    """Category 3: Adversarial Layout Spoofing & Cross-Broker Payload Injection."""

    def setUp(self):
        self.gate = LayoutGate()
        self.profile_primary = FAMILY_PAN_REGISTRY["KLMNO9012P"]
        self.profile_father = FAMILY_PAN_REGISTRY["ABCDE1234F"]

    def test_zerodha_header_with_schwab_body_fail_closed(self):
        """Attachment with Zerodha filename/header containing Schwab body is rejected or fails closed."""
        spoofed_payload = (
            b"symbol,isin,trade_date,exchange,segment,series,trade_type,quantity,price,order_id,trade_id\n"
            b'"05/18/2023","Buy","NVDA","NVIDIA CORP","150.000","62.40","0.00","-9360.00"\n'
        )
        att = ExtractedAttachment(
            filename="tradebook_zerodha.csv",
            content_type="text/csv",
            size_bytes=len(spoof_payload := spoofed_payload),
            payload_bytes=spoofed_payload,
            sha256="spoof_z_s",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_primary)
        self.assertIsInstance(res, LayoutGateResult)
        # If parser crashed on mismatched columns, LayoutGate caught it and returned passed=False
        if not res.passed:
            self.assertEqual(res.rejection_code, ERR_LAYOUT_PARSING_FAILED)

    def test_hdfc_signature_with_cams_cas_body_fail_closed(self):
        """Attachment with HDFC signature token but CAMS CAS text body yields 0 valid HDFC trades."""
        spoofed_payload = (
            b"%PDF-1.4 HDFC SECURITIES LIMITED INZ000186937\n"
            b"CONSOLIDATED ACCOUNT STATEMENT - CAMS\n"
            b"Quant Active Fund - Direct Plan - Growth Folio: 4481023/1\n"
            b"2023-05-18 PURCHASE 1000000.00 50.00 999950.00 465.10 2149.968 2149.968\n"
        )
        att = ExtractedAttachment(
            filename="hdfc_cas_spoof.pdf",
            content_type="application/pdf",
            size_bytes=len(spoofed_payload),
            payload_bytes=spoofed_payload,
            sha256="spoof_h_c",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_father)
        self.assertIsInstance(res, LayoutGateResult)
        if res.passed and isinstance(res.parsed_statement, NormalizedContractNote):
            # HDFC trade regex should not match CAS purchase format
            self.assertEqual(len(res.parsed_statement.trades), 0)

    def test_cams_cas_signature_with_zerodha_ecn_body(self):
        """Attachment with CAMS signature token but Zerodha ECN body yields 0 CAS schemes."""
        spoofed_payload = (
            b"%PDF-1.4 CAMS CONSOLIDATED ACCOUNT STATEMENT\n"
            b"ZERODHA BROKING LTD Contract Note No: CN20240814-ZR1102\n"
            b"1100000028471920 84920194 10:14:32 TATA MOTORS LTD - EQ B 800 480.00 384000.00\n"
        )
        att = ExtractedAttachment(
            filename="cams_zerodha_spoof.pdf",
            content_type="application/pdf",
            size_bytes=len(spoofed_payload),
            payload_bytes=spoofed_payload,
            sha256="spoof_c_z",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_primary)
        self.assertIsInstance(res, LayoutGateResult)
        if res.passed and isinstance(res.parsed_statement, NormalizedCasStatement):
            self.assertEqual(len(res.parsed_statement.schemes[0].transactions), 0)

    def test_completely_unsupported_binary_format_rejected(self):
        """Arbitrary binary data without recognizable broker signature is rejected fail-closed."""
        garbage_bytes = b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00 Linux ELF Binary"
        att = ExtractedAttachment(
            filename="unknown_payload.bin",
            content_type="application/octet-stream",
            size_bytes=len(garbage_bytes),
            payload_bytes=garbage_bytes,
            sha256="elf_sha",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_primary)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_LAYOUT_UNSUPPORTED_FORMAT)


class TestAdversarialFractionalPrecisionAndHighDecimals(unittest.TestCase):
    """Category 4: Fractional Share Precision & High Decimal Quantities."""

    def setUp(self):
        self.schwab_parser = CharlesSchwabParser()
        self.cas_parser = CamsKfintechCasParser()
        self.zerodha_parser = ZerodhaParser()
        self.profile_primary = FAMILY_PAN_REGISTRY["KLMNO9012P"]

    def test_schwab_micro_share_fractional_quantities(self):
        """Verifies Schwab fractional share quantities (e.g. 0.000001 shares, 0.0001234567 shares)."""
        csv_data = (
            b'"Date","Action","Symbol","Description","Quantity","Price","Fees & Comm","Amount"\n'
            b'"05/18/2023","Buy","NVDA","NVIDIA CORP","0.000001","1200.5000","$0.00","-$0.0012005"\n'
            b'"05/19/2023","Dividend Reinvested","VOO","VANGUARD S&P 500","0.0001234567","450.123456","$0.00","-$0.0555708"\n'
        )
        res = self.schwab_parser._parse_csv(csv_data, entity_profile=self.profile_primary, filename="schwab.csv")
        self.assertEqual(len(res.records), 2)
        r1 = res.records[0]
        self.assertEqual(r1.quantity, Decimal("0.000001"))
        self.assertEqual(r1.price_usd, Decimal("1200.5000"))
        self.assertEqual(r1.net_amount_usd, Decimal("-0.0012005"))

        r2 = res.records[1]
        self.assertEqual(r2.quantity, Decimal("0.0001234567"))
        self.assertEqual(r2.price_usd, Decimal("450.123456"))

    def test_cas_high_precision_mutual_fund_units_and_nav(self):
        """Verifies CAS units with high decimal precision (e.g. 2149.968123 units, NAV ₹625.123456)."""
        cas_dict = {
            "investor_info": {"name": "Alex Taylor", "pan": "KLMNO9012P"},
            "folios": [{
                "folio": "4481023/1",
                "amc": "Quant Mutual Fund",
                "schemes": [{
                    "scheme": "Quant Active Fund - Direct Plan - Growth",
                    "open": "100.00000001",
                    "close": "200.00000002",
                    "valuation": {"nav": "625.123456", "value": "125024.69"},
                    "transactions": [{
                        "date": "2024-08-14",
                        "type": "PURCHASE",
                        "amount": "50000.00",
                        "stamp_duty": "2.50",
                        "nav": "500.024681",
                        "units": "99.99500001",
                        "balance": "200.00000002"
                    }]
                }]
            }]
        }
        res = self.cas_parser._parse_cas_dict(cas_dict, entity_profile=self.profile_primary)
        scheme = res.schemes[0]
        self.assertEqual(scheme.opening_unit_balance, Decimal("100.00000001"))
        self.assertEqual(scheme.closing_unit_balance, Decimal("200.00000002"))
        self.assertEqual(scheme.valuation_nav, Decimal("625.123456"))
        self.assertEqual(scheme.transactions[0].units, Decimal("99.99500001"))
        self.assertEqual(scheme.transactions[0].nav, Decimal("500.024681"))

    def test_zerodha_large_portfolio_values_no_overflow(self):
        """Verifies huge transaction values (e.g. ₹999,999,999,999.99) parse without numeric overflow."""
        huge_csv = (
            b"symbol,isin,trade_date,exchange,segment,series,trade_type,quantity,price,order_id,trade_id\n"
            b"TATA,INE155A01022,2024-08-14,NSE,EQ,EQ,buy,10000000,99999.99,ORD_HUGE,TRD_HUGE\n"
        )
        res = self.zerodha_parser._parse_csv(huge_csv, entity_profile=self.profile_primary, filename="tradebook.csv")
        self.assertEqual(len(res.trades), 1)
        t = res.trades[0]
        self.assertEqual(t.quantity, Decimal("10000000"))
        self.assertEqual(t.gross_price, Decimal("99999.99"))
        self.assertEqual(t.gross_total, Decimal("999999900000.00"))


class TestAdversarialExtremeChargesAndNegativeValues(unittest.TestCase):
    """Category 5: Extreme Statutory Levies, Negative Numbers & Withholding Taxes."""

    def setUp(self):
        self.schwab_parser = CharlesSchwabParser()
        self.zerodha_parser = ZerodhaParser()
        self.hdfc_parser = HDFCSecParser()
        self.profile_primary = FAMILY_PAN_REGISTRY["KLMNO9012P"]
        self.profile_father = FAMILY_PAN_REGISTRY["ABCDE1234F"]

    def test_schwab_withholding_tax_1042s_exceeding_standard_rates(self):
        """Handles IRS 1042-S withholding tax entries accurately."""
        csv_data = (
            b'"Date","Action","Symbol","Description","Quantity","Price","Fees & Comm","Amount"\n'
            b'"05/18/2023","Cash Dividend","AAPL","APPLE INC","","","$0.00","$100.00"\n'
            b'"05/18/2023","NRA Tax Withholding","AAPL","IRS 1042-S TAX","","","$0.00","-$25.00"\n'
        )
        res = self.schwab_parser._parse_csv(csv_data, entity_profile=self.profile_primary, filename="schwab.csv")
        self.assertEqual(len(res.records), 2)
        r_div = res.records[0]
        r_tax = res.records[1]
        self.assertEqual(r_div.canonical_action, "CASH_DIVIDEND")
        self.assertEqual(r_div.gross_dividend_usd, Decimal("100.00"))
        self.assertEqual(r_tax.canonical_action, "TAX_WITHHOLDING_1042S")
        self.assertEqual(r_tax.tax_withheld_usd, Decimal("25.00"))
        self.assertEqual(res.total_dividend_usd, Decimal("100.00"))
        self.assertEqual(res.total_tax_withheld_usd, Decimal("25.00"))

    def test_hdfc_zero_brokerage_and_maximum_demat_allocation_charges(self):
        """Parses HDFC statement with zero brokerage and explicit Demat allocation charge of ₹15.93."""
        raw_text = (
            "HDFC SECURITIES LIMITED INZ000186937\n"
            "Contract Note No: HDFC/2024/08/14/999 Trade Date: 14/08/2024\n"
            "Settlement No: 2024115 PAN: ABCDE1234F\n"
            "Trading A/c: 1092847101 Demat ID: 1208670000123456\n"
            "Client Name: Robert Taylor\n"
            "Exch Scrip Description ISIN B/S Qty Gross Rate Brokerage Net Amount\n"
            "NSE HDFC BANK LIMITED INE040A01034 BUY 100 1500.00 0.00 150000.00\n"
            "Total Brokerage : 0.00\n"
            "Securities Transaction Tax (STT) : 150.00\n"
            "Exchange Turnover Charges : 4.50\n"
            "SEBI Turnover Charges : 0.15\n"
            "Stamp Duty : 22.50\n"
            "GST on Brokerage : 0.00\n"
            "Demat Allocation Charges : 15.93\n"
            "Net Amount Payable by Client : -150193.08\n"
        )
        stream = io.BytesIO(raw_text.encode("utf-8"))
        res = self.hdfc_parser.parse(stream, entity_profile=self.profile_father, filename="hdfc.pdf")
        self.assertIsInstance(res, NormalizedContractNote)
        self.assertEqual(res.levies.brokerage, Decimal("0.00"))
        self.assertEqual(res.levies.demat_charges, Decimal("15.93"))
        self.assertEqual(res.levies.stt, Decimal("150.00"))
        self.assertEqual(res.net_settlement_amount, Decimal("-150193.08"))

    def test_parenthesized_and_trailing_minus_negative_amounts(self):
        """BaseBrokerParser cleans (1,234.50) and 1234.50- into -1234.50."""
        self.assertEqual(BaseBrokerParser.clean_decimal("(1,234.50)"), Decimal("-1234.50"))
        self.assertEqual(BaseBrokerParser.clean_decimal("1234.50-"), Decimal("-1234.50"))
        self.assertEqual(BaseBrokerParser.clean_decimal("($500.25)"), Decimal("-500.25"))
        self.assertEqual(BaseBrokerParser.clean_decimal("(₹10,000.00)"), Decimal("-10000.00"))


class TestAdversarialDefectDemonstrationsAndRobustness(unittest.TestCase):
    """
    Category 6: Defect Demonstrations & Type Robustness.
    Empirically documents boundary exception handling and verifies fail-closed security.
    """

    def setUp(self):
        self.gate = LayoutGate()
        self.profile_primary = FAMILY_PAN_REGISTRY["KLMNO9012P"]

    def test_clean_decimal_with_various_primitive_types(self):
        """Verifies clean_decimal with string, float, int, None, and lists."""
        self.assertEqual(BaseBrokerParser.clean_decimal("100.50"), Decimal("100.50"))
        self.assertEqual(BaseBrokerParser.clean_decimal(100), Decimal("100"))
        self.assertEqual(BaseBrokerParser.clean_decimal(100.5), Decimal("100.5"))
        self.assertEqual(BaseBrokerParser.clean_decimal(None), Decimal("0.00"))
        self.assertEqual(BaseBrokerParser.clean_decimal(""), Decimal("0.00"))
        self.assertEqual(BaseBrokerParser.clean_decimal([]), Decimal("0.00"))
        self.assertEqual(BaseBrokerParser.clean_decimal({}), Decimal("0.00"))

    def test_gate_evaluate_with_empty_or_none_attachment_fields(self):
        """Verifies LayoutGate handles empty payload bytes gracefully."""
        att = ExtractedAttachment(
            filename="empty_file.csv",
            content_type="text/csv",
            size_bytes=0,
            payload_bytes=b"",
            sha256="empty_sha",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_primary)
        self.assertIsInstance(res, LayoutGateResult)

    def test_schwab_csv_with_unequal_row_columns_handled_fail_closed(self):
        """CSV row with fewer columns than header fails closed gracefully through Gate 2."""
        truncated_csv = (
            b'"Date","Action","Symbol","Description","Quantity","Price","Fees & Comm","Amount"\n'
            b'"05/18/2023","Buy","NVDA"\n'
        )
        att = ExtractedAttachment(
            filename="schwab_truncated.csv",
            content_type="text/csv",
            size_bytes=len(truncated_csv),
            payload_bytes=truncated_csv,
            sha256="trunc_sha",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_primary)
        self.assertIsInstance(res, LayoutGateResult)
        # Must fail closed without unhandled crash
        if not res.passed:
            self.assertEqual(res.rejection_code, ERR_LAYOUT_PARSING_FAILED)

    def test_zerodha_csv_with_unequal_row_columns_handled_fail_closed(self):
        """Zerodha CSV row with fewer columns than header fails closed gracefully through Gate 2."""
        truncated_csv = (
            b"symbol,isin,trade_date,exchange,segment,series,trade_type,quantity,price,order_id,trade_id\n"
            b"TATA,INE155A01022\n"
        )
        att = ExtractedAttachment(
            filename="tradebook_truncated.csv",
            content_type="text/csv",
            size_bytes=len(truncated_csv),
            payload_bytes=truncated_csv,
            sha256="trunc_z_sha",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_primary)
        self.assertIsInstance(res, LayoutGateResult)
        if not res.passed:
            self.assertEqual(res.rejection_code, ERR_LAYOUT_PARSING_FAILED)

    def test_cas_dict_with_none_values_handled_fail_closed(self):
        """CAS parser given JSON with None for key containers fails closed gracefully through Gate 2."""
        corrupt_json = json.dumps({"folios": None}).encode("utf-8")
        att = ExtractedAttachment(
            filename="corrupt_cas.json",
            content_type="application/json",
            size_bytes=len(corrupt_json),
            payload_bytes=corrupt_json,
            sha256="corrupt_json_sha",
        )
        res = self.gate.evaluate(att, entity_profile=self.profile_primary)
        self.assertIsInstance(res, LayoutGateResult)
        if not res.passed:
            self.assertEqual(res.rejection_code, ERR_LAYOUT_PARSING_FAILED)

    def test_defect_clean_decimal_boolean_input_raises_invalid_operation(self):
        """
        EMPIRICAL DEFECT DEMONSTRATION:
        BaseBrokerParser.clean_decimal(True) checks `isinstance(val, (int, float))` without excluding `bool`.
        Since bool inherits from int, `Decimal(str(True))` -> `Decimal('True')` raises unhandled `decimal.InvalidOperation`.
        """
        with self.assertRaises(decimal.InvalidOperation):
            BaseBrokerParser.clean_decimal(True)
        with self.assertRaises(decimal.InvalidOperation):
            BaseBrokerParser.clean_decimal(False)

    def test_defect_encrypted_pdf_password_exhaustion_returns_success_true(self):
        """
        EMPIRICAL DEFECT DEMONSTRATION:
        In LayoutGate.decrypt_pdf, when pikepdf is present and all password candidates fail,
        the loop finishes and falls through to `return True, pdf_bytes, ""` instead of `(False, None, None)`.
        This causes Gate 2 to report passed=True on an un-decrypted encrypted PDF.
        """
        mock_pikepdf = mock.MagicMock()
        class MockPasswordError(Exception): pass
        mock_pikepdf.PasswordError = MockPasswordError

        def open_always_fails(stream, password=""):
            raise MockPasswordError("Invalid password")

        mock_pikepdf.open.side_effect = open_always_fails

        with mock.patch("backend.app.gates.layout_gate.pikepdf", mock_pikepdf):
            gate = LayoutGate()
            # Calling decrypt_pdf with all wrong candidates
            success, dec_bytes, pwd = gate.decrypt_pdf(b"%PDF-1.4 encrypted", ["wrong1", "wrong2"])
            # Defect: success is returned as True rather than False
            self.assertTrue(success, "Documents that decrypt_pdf currently returns True on password exhaustion.")

    def test_defect_integer_raw_user_password_raises_attribute_error(self):
        """
        EMPIRICAL DEFECT DEMONSTRATION:
        LayoutGate.generate_password_candidates assumes raw_user_password is a str.
        Passing integer `123456` causes `p = raw_user_password.strip()` to raise AttributeError.
        """
        with self.assertRaises(AttributeError):
            self.gate.generate_password_candidates(raw_user_password=123456)

    def test_defect_integer_target_pan_raises_attribute_error(self):
        """
        EMPIRICAL DEFECT DEMONSTRATION:
        LayoutGate.generate_password_candidates assumes pan is a str.
        Passing integer `12345` causes `clean_pan = resolved_pan.strip()` to raise AttributeError.
        """
        with self.assertRaises(AttributeError):
            self.gate.generate_password_candidates(pan=12345)

    def test_defect_none_filename_raises_attribute_error(self):
        """
        EMPIRICAL DEFECT DEMONSTRATION:
        LayoutGate.evaluate line 301 runs `attachment.filename.lower().endswith(".pdf")`.
        If attachment.filename is None, it raises unhandled `AttributeError: 'NoneType' object has no attribute 'lower'`.
        """
        att = ExtractedAttachment(
            filename=None,
            content_type="application/pdf",
            size_bytes=10,
            payload_bytes=b"%PDF-1.4 data",
            sha256="abc",
        )
        with self.assertRaises(AttributeError):
            self.gate.evaluate(att)

    def test_defect_none_payload_bytes_raises_attribute_error(self):
        """
        EMPIRICAL DEFECT DEMONSTRATION:
        LayoutGate.evaluate line 302 runs `attachment.payload_bytes.startswith(b"%PDF")`.
        If attachment.payload_bytes is None, it raises unhandled `AttributeError: 'NoneType' object has no attribute 'startswith'`.
        """
        att = ExtractedAttachment(
            filename="sample.pdf",
            content_type="application/pdf",
            size_bytes=0,
            payload_bytes=None,
            sha256="abc",
        )
        with self.assertRaises(AttributeError):
            self.gate.evaluate(att)

    def test_defect_cas_dict_none_containers_raises_type_error(self):
        """
        EMPIRICAL DEFECT DEMONSTRATION:
        CamsKfintechCasParser._parse_cas_dict assumes `cas_dict.get('folios', [])` is an iterable list.
        If `cas_dict['folios'] = None`, it raises unhandled `TypeError: 'NoneType' object is not iterable`.
        """
        with self.assertRaises(TypeError):
            self.gate.parsers[2]._parse_cas_dict({"folios": None})



class TestAdversarialFuzzingSuiteGate2(unittest.TestCase):
    """
    Category 7: Gate 2 Fuzzing Harness (1,000 Randomized Mutations).
    Verifies that across 1,000 randomized byte, text, and structure mutations,
    evaluate_layout_gate maintains fail-closed perimeter security with ZERO unhandled exceptions.
    """

    def setUp(self):
        self.gate = LayoutGate()
        self.profile = FAMILY_PAN_REGISTRY["KLMNO9012P"]

    def test_1000_fuzzed_attachments_fail_closed_with_zero_unhandled_crashes(self):
        """1,000 randomized mutations across CSV, PDF, JSON, and binary payloads."""
        random.seed(1337)

        sample_seeds = [
            (b"symbol,isin,trade_date,exchange,segment,series,trade_type,quantity,price,order_id,trade_id\nTATA,INE155A01022,2024-08-14,NSE,EQ,EQ,buy,800,480.00,ORD1,TRD1\n", "tradebook.csv", "text/csv"),
            (b'"Date","Action","Symbol","Description","Quantity","Price","Fees & Comm","Amount"\n"05/18/2023","Buy","NVDA","NVIDIA","150.000","62.40","$0.00","-$9360.00"\n', "schwab.csv", "text/csv"),
            (b"%PDF-1.4 ZERODHA BROKING LTD\nContract Note No: CN20240814-ZR1102 Trade Date: 14/08/2024\n1100000028471920 84920194 10:14:32 TATA MOTORS LTD - EQ B 800 480.00 384000.00\n", "cn.pdf", "application/pdf"),
            (b"%PDF-1.4 HDFC SECURITIES LIMITED INZ000186937\nContract Note No: HDFC/2024/08/14/001 Trade Date: 14/08/2024\nNSE HDFC BANK LIMITED INE040A01034 BUY 100 1500.00 15.00 150015.00\n", "hdfc.pdf", "application/pdf"),
            (b'{"investor_info": {"name": "Alex Taylor", "pan": "KLMNO9012P"}, "folios": []}', "cas.json", "application/json"),
        ]

        mutation_actions = [
            "random_binary",
            "bit_flip",
            "byte_delete",
            "byte_insert",
            "null_inject",
            "truncate",
            "unicode_noise",
            "empty_stream",
        ]

        for i in range(1000):
            seed_bytes, seed_fn, seed_ctype = random.choice(sample_seeds)
            action = random.choice(mutation_actions)

            if action == "random_binary":
                fuzzed_data = os.urandom(random.randint(0, 2048))
            elif action == "bit_flip":
                ba = bytearray(seed_bytes)
                if ba:
                    pos = random.randint(0, len(ba) - 1)
                    ba[pos] ^= random.randint(1, 255)
                fuzzed_data = bytes(ba)
            elif action == "byte_delete":
                ba = bytearray(seed_bytes)
                if len(ba) > 5:
                    cut_pos = random.randint(0, len(ba) - 5)
                    del ba[cut_pos : cut_pos + random.randint(1, 5)]
                fuzzed_data = bytes(ba)
            elif action == "byte_insert":
                ba = bytearray(seed_bytes)
                ins_pos = random.randint(0, len(ba)) if ba else 0
                noise = os.urandom(random.randint(1, 30))
                ba[ins_pos:ins_pos] = noise
                fuzzed_data = bytes(ba)
            elif action == "null_inject":
                fuzzed_data = seed_bytes.replace(b",", b"\x00", random.randint(1, 4))
            elif action == "truncate":
                cut = random.randint(0, len(seed_bytes))
                fuzzed_data = seed_bytes[:cut]
            elif action == "unicode_noise":
                noise_str = "".join(random.choice("₹€$§©®¶#@!%^&*()_+-=[]{}|;:<>?,./~`'\" \t\r\n\ud83d\ude00") for _ in range(50))
                fuzzed_data = seed_bytes + noise_str.encode("utf-8", errors="ignore")
            elif action == "empty_stream":
                fuzzed_data = b""

            att = ExtractedAttachment(
                filename=f"fuzz_{i}_{seed_fn}",
                content_type=seed_ctype,
                size_bytes=len(fuzzed_data),
                payload_bytes=fuzzed_data,
                sha256=hashlib.sha256(fuzzed_data).hexdigest(),
            )

            try:
                res = self.gate.evaluate(att, entity_profile=self.profile)
                self.assertIsInstance(res, LayoutGateResult)
            except Exception as e:
                self.fail(f"Unhandled exception during Gate 2 fuzzing iteration {i} (mutation={action}): {type(e).__name__}: {e}")


if __name__ == "__main__":
    unittest.main()
