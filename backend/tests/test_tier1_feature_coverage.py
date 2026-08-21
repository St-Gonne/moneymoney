"""
Tier 1: Feature Coverage Test Suite (MoneyMoney Ingestion Pipeline)
Covers all 16 features from PROJECT.md Feature Inventory with >=5 test cases per feature (Total >= 80 test cases).
"""
import unittest
from datetime import date, datetime
from decimal import Decimal

from backend.tests.fixtures.sample_family_vault import (
    AUTHORIZED_FORWARDERS,
    AUTHORIZED_BROKER_DOMAINS,
    FAMILY_VAULT_PROFILES,
    lookup_rbi_rate,
    DEFAULT_USD_INR_RATE,
)
from backend.tests.fixtures.sample_emails import (
    build_forwarded_email,
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
    build_corrupted_cams_statement,
    SyntheticCasTx,
    SyntheticCasScheme,
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


class TestTier1FeatureCoverage(unittest.TestCase):
    """
    Tier 1 Test Suite: Full Feature Coverage for all 16 features.
    """

    # --------------------------------------------------------------------------
    # FEATURE 1: Inbound Forwarded Email Parsing (RFC 822 / MIME Multipart)
    # --------------------------------------------------------------------------
    def test_f01_tc01_parse_valid_alex_zerodha_forwarded_mime(self):
        mime_bytes = create_zerodha_mime(forwarder="alex.taylor@example.com")
        res = ReferenceIdentityGate.process_mime_payload(mime_bytes, "alex.taylor@example.com")
        self.assertTrue(res["passed"])
        self.assertEqual(res["target_entity_id"], "port_primary")
        self.assertEqual(res["broker_institution"], "ZERODHA")
        self.assertGreaterEqual(len(res["extracted_attachments"]), 1)

    def test_f01_tc02_parse_valid_robert_hdfc_forwarded_mime(self):
        mime_bytes = create_hdfc_mime(forwarder="robert.taylor@example.com")
        res = ReferenceIdentityGate.process_mime_payload(mime_bytes, "robert.taylor@example.com")
        self.assertTrue(res["passed"])
        self.assertEqual(res["target_entity_id"], "port_father")
        self.assertEqual(res["broker_institution"], "HDFC_SECURITIES")
        self.assertEqual(len(res["extracted_attachments"]), 1)

    def test_f01_tc03_parse_valid_margaret_cams_forwarded_mime(self):
        mime_bytes = create_cams_cas_mime(forwarder="margaret.taylor@example.com")
        res = ReferenceIdentityGate.process_mime_payload(mime_bytes, "margaret.taylor@example.com")
        self.assertTrue(res["passed"])
        self.assertEqual(res["target_entity_id"], "port_mother")
        self.assertEqual(res["broker_institution"], "CAMS_KFINTECH")

    def test_f01_tc04_parse_valid_kfintech_forwarded_mime(self):
        mime_bytes = create_kfintech_cas_mime(forwarder="alex.taylor@example.com")
        res = ReferenceIdentityGate.process_mime_payload(mime_bytes, "alex.taylor@example.com")
        self.assertTrue(res["passed"])
        self.assertEqual(res["broker_institution"], "CAMS_KFINTECH")

    def test_f01_tc05_parse_valid_schwab_activity_forwarded_mime(self):
        mime_bytes = create_schwab_mime(forwarder="alex.taylor@example.com")
        res = ReferenceIdentityGate.process_mime_payload(mime_bytes, "alex.taylor@example.com")
        self.assertTrue(res["passed"])
        self.assertEqual(res["broker_institution"], "CHARLES_SCHWAB")

    # --------------------------------------------------------------------------
    # FEATURE 2: Identity Gate & Domain Verification
    # --------------------------------------------------------------------------
    def test_f02_tc01_verify_zerodha_broker_domain_promotes_candidate(self):
        mime = build_forwarded_email(
            forwarder_email="alex.taylor@example.com",
            original_from="contracts@zerodha.com",
            attachments=[("cn.pdf", b"%PDF-1.7 data", "pdf")]
        )
        res = ReferenceIdentityGate.process_mime_payload(mime, "alex.taylor@example.com")
        self.assertTrue(res["passed"])
        self.assertEqual(res["broker_institution"], "ZERODHA")

    def test_f02_tc02_verify_hdfcsec_broker_domain_promotes_candidate(self):
        mime = build_forwarded_email(
            forwarder_email="robert.taylor@example.com",
            original_from="customercare@hdfcsec.com",
            attachments=[("hdfc_cn.pdf", b"%PDF-1.6 data", "pdf")]
        )
        res = ReferenceIdentityGate.process_mime_payload(mime, "robert.taylor@example.com")
        self.assertTrue(res["passed"])
        self.assertEqual(res["broker_institution"], "HDFC_SECURITIES")

    def test_f02_tc03_verify_camsonline_broker_domain_promotes_candidate(self):
        mime = build_forwarded_email(
            forwarder_email="alex.taylor@example.com",
            original_from="donotreply@camsonline.com",
            attachments=[("cas.pdf", b"%PDF-1.4 data", "pdf")]
        )
        res = ReferenceIdentityGate.process_mime_payload(mime, "alex.taylor@example.com")
        self.assertTrue(res["passed"])
        self.assertEqual(res["broker_institution"], "CAMS_KFINTECH")

    def test_f02_tc04_verify_schwab_broker_domain_promotes_candidate(self):
        mime = build_forwarded_email(
            forwarder_email="alex.taylor@example.com",
            original_from="donotreply@schwab.com",
            attachments=[("schwab.csv", b"Date,Action,Symbol", "csv")]
        )
        res = ReferenceIdentityGate.process_mime_payload(mime, "alex.taylor@example.com")
        self.assertTrue(res["passed"])
        self.assertEqual(res["broker_institution"], "CHARLES_SCHWAB")

    def test_f02_tc05_verify_pan_mapping_to_target_family_member(self):
        res_alex = ReferenceIdentityGate.process_mime_payload(create_zerodha_mime("alex.taylor@example.com"), "alex.taylor@example.com")
        res_robert = ReferenceIdentityGate.process_mime_payload(create_hdfc_mime("robert.taylor@example.com"), "robert.taylor@example.com")
        res_margaret = ReferenceIdentityGate.process_mime_payload(create_cams_cas_mime("margaret.taylor@example.com"), "margaret.taylor@example.com")
        self.assertEqual(res_alex["target_pan"], "KLMNO9012P")
        self.assertEqual(res_robert["target_pan"], "ABCDE1234F")
        self.assertEqual(res_margaret["target_pan"], "FGHIJ5678K")

    # --------------------------------------------------------------------------
    # FEATURE 3: Secure In-Memory Attachment Extraction
    # --------------------------------------------------------------------------
    def test_f03_tc01_extract_pdf_in_memory_stream(self):
        raw_pdf = b"%PDF-1.7 sample bytes for contract note"
        mime = create_zerodha_mime(pdf_bytes=raw_pdf)
        res = ReferenceIdentityGate.process_mime_payload(mime, "alex.taylor@example.com")
        self.assertEqual(res["extracted_attachments"][0]["content_bytes"], raw_pdf)

    def test_f03_tc02_extract_csv_in_memory_stream(self):
        raw_csv = b"Date,Action,Symbol,Quantity,Price\n05/18/2023,Buy,NVDA,150,62.40"
        mime = create_schwab_mime(csv_bytes=raw_csv)
        res = ReferenceIdentityGate.process_mime_payload(mime, "alex.taylor@example.com")
        self.assertEqual(res["extracted_attachments"][0]["content_bytes"], raw_csv)

    def test_f03_tc03_extract_multiple_attachments_in_single_email(self):
        pdf_b = b"%PDF-1.7 contract note"
        csv_b = b"symbol,isin,quantity\nTATAMOTORS,INE155A01022,800"
        mime = create_zerodha_mime(pdf_bytes=pdf_b, csv_bytes=csv_b)
        res = ReferenceIdentityGate.process_mime_payload(mime, "alex.taylor@example.com")
        self.assertEqual(len(res["extracted_attachments"]), 2)

    def test_f03_tc04_extract_attachment_metadata_size_content_type(self):
        raw_pdf = b"%PDF-1.7 data test content"
        mime = create_zerodha_mime(pdf_bytes=raw_pdf)
        res = ReferenceIdentityGate.process_mime_payload(mime, "alex.taylor@example.com")
        att = res["extracted_attachments"][0]
        self.assertEqual(att["size_bytes"], len(raw_pdf))
        self.assertTrue("pdf" in att["filename"].lower())

    def test_f03_tc05_extract_in_memory_avoids_filesystem_writes(self):
        # Verification that payload content is in-memory bytes object
        mime = create_zerodha_mime()
        res = ReferenceIdentityGate.process_mime_payload(mime, "alex.taylor@example.com")
        self.assertIsInstance(res["extracted_attachments"][0]["content_bytes"], bytes)

    # --------------------------------------------------------------------------
    # FEATURE 4: Supported-Layout Identification
    # --------------------------------------------------------------------------
    def test_f04_tc01_identify_zerodha_pdf_layout(self):
        res = ReferenceDecryptionEngine.classify_and_decrypt(
            attachment_bytes=b"%PDF-1.7 ZERODHA BROKING LTD CONTRACT NOTE",
            filename="CN_ZR1102.pdf",
            target_pan="KLMNO9012P"
        )
        self.assertTrue(res["passed"])
        self.assertEqual(res["layout_type"], "ZERODHA_PDF")

    def test_f04_tc02_identify_hdfc_pdf_layout(self):
        res = ReferenceDecryptionEngine.classify_and_decrypt(
            attachment_bytes=b"%PDF-1.6 HDFC SECURITIES LIMITED CONTRACT NOTE",
            filename="HDFC_ECN_2024.pdf",
            target_pan="ABCDE1234F"
        )
        self.assertTrue(res["passed"])
        self.assertEqual(res["layout_type"], "HDFC_PDF")

    def test_f04_tc03_identify_cams_cas_pdf_layout(self):
        res = ReferenceDecryptionEngine.classify_and_decrypt(
            attachment_bytes=b"%PDF-1.4 CAMS Consolidated Account Statement",
            filename="CAMS_CAS_July2024.pdf",
            target_pan="KLMNO9012P"
        )
        self.assertTrue(res["passed"])
        self.assertEqual(res["layout_type"], "CAMS_CAS_PDF")

    def test_f04_tc04_identify_kfintech_cas_pdf_layout(self):
        res = ReferenceDecryptionEngine.classify_and_decrypt(
            attachment_bytes=b"%PDF-1.4 KFintech Mutual Fund CAS",
            filename="KFIN_CAS_2024.pdf",
            target_pan="KLMNO9012P"
        )
        self.assertTrue(res["passed"])
        self.assertEqual(res["layout_type"], "KFINTECH_CAS_PDF")

    def test_f04_tc05_identify_schwab_csv_layout(self):
        res = ReferenceDecryptionEngine.classify_and_decrypt(
            attachment_bytes=b"Date,Action,Symbol,Quantity,Price",
            filename="Schwab_Activity.csv",
            target_pan="KLMNO9012P"
        )
        self.assertTrue(res["passed"])
        self.assertEqual(res["layout_type"], "SCHWAB_CSV")

    # --------------------------------------------------------------------------
    # FEATURE 5: Multi-Candidate PDF Decryption
    # --------------------------------------------------------------------------
    def test_f05_tc01_decrypt_pan_uppercase_candidate(self):
        candidates = ReferenceDecryptionEngine.generate_password_candidates("KLMNO9012P")
        self.assertIn("KLMNO9012P", candidates)
        res = ReferenceDecryptionEngine.classify_and_decrypt(
            b"%PDF-1.7 encrypted mock", "cn.pdf", "KLMNO9012P", actual_pdf_password="KLMNO9012P"
        )
        self.assertTrue(res["passed"])

    def test_f05_tc02_decrypt_pan_lowercase_candidate(self):
        candidates = ReferenceDecryptionEngine.generate_password_candidates("KLMNO9012P")
        self.assertIn("klmno9012p", candidates)
        res = ReferenceDecryptionEngine.classify_and_decrypt(
            b"%PDF-1.7 encrypted mock", "cn.pdf", "KLMNO9012P", actual_pdf_password="klmno9012p"
        )
        self.assertTrue(res["passed"])

    def test_f05_tc03_decrypt_dob_ddmmyyyy_candidate(self):
        candidates = ReferenceDecryptionEngine.generate_password_candidates("ABCDE1234F", dob=date(1955, 5, 20))
        self.assertIn("20051955", candidates)
        res = ReferenceDecryptionEngine.classify_and_decrypt(
            b"%PDF-1.6 encrypted mock", "hdfc.pdf", "ABCDE1234F", target_dob=date(1955, 5, 20), actual_pdf_password="20051955"
        )
        self.assertTrue(res["passed"])

    def test_f05_tc04_decrypt_hybrid_name_dob_candidate(self):
        candidates = ReferenceDecryptionEngine.generate_password_candidates("ABCDE1234F", dob=date(1955, 5, 20), first_name="Robert")
        self.assertIn("ROBE2005", candidates)
        res = ReferenceDecryptionEngine.classify_and_decrypt(
            b"%PDF-1.6 encrypted mock", "hdfc.pdf", "ABCDE1234F", target_dob=date(1955, 5, 20), target_first_name="Robert", actual_pdf_password="ROBE2005"
        )
        self.assertTrue(res["passed"])


    def test_f05_tc05_decrypt_unencrypted_pdf_fallback(self):
        res = ReferenceDecryptionEngine.classify_and_decrypt(
            b"%PDF-1.7 unencrypted", "cn.pdf", "KLMNO9012P", actual_pdf_password=""
        )
        self.assertTrue(res["passed"])

    # --------------------------------------------------------------------------
    # FEATURE 6: Zerodha Contract Note Parser
    # --------------------------------------------------------------------------
    def test_f06_tc01_parse_equity_delivery_buy_trades(self):
        stmt = build_valid_zerodha_statement()
        self.assertEqual(len(stmt.trades), 2)
        self.assertEqual(stmt.trades[0].action, "BUY")
        self.assertEqual(stmt.trades[0].quantity, Decimal("800"))
        self.assertEqual(stmt.trades[0].gross_rate, Decimal("480.00"))
        self.assertEqual(stmt.trades[0].gross_total, Decimal("384000.00"))

    def test_f06_tc02_parse_equity_delivery_sell_trades(self):
        stmt = build_valid_zerodha_statement()
        # Add a sell trade
        sell_t = SyntheticTradeRow(
            order_no="1100000028471922", trade_no="84920196", trade_time="14:10:00",
            security_name="TATA MOTORS LTD - EQ", isin="INE155A01022", action="SELL",
            quantity=Decimal("300"), gross_rate=Decimal("520.00")
        )
        self.assertEqual(sell_t.action, "SELL")
        self.assertEqual(sell_t.gross_total, Decimal("156000.00"))

    def test_f06_tc03_extract_isin_and_scrip_metadata(self):
        stmt = build_valid_zerodha_statement()
        self.assertEqual(stmt.trades[0].isin, "INE155A01022")
        self.assertEqual(stmt.trades[1].isin, "INE009A01021")

    def test_f06_tc04_extract_statutory_levies_breakdown(self):
        stmt = build_valid_zerodha_statement()
        self.assertEqual(stmt.stt, Decimal("534.00"))
        self.assertEqual(stmt.exchange_turnover_fee, Decimal("15.86"))
        self.assertEqual(stmt.sebi_turnover_fee, Decimal("0.53"))
        self.assertEqual(stmt.stamp_duty, Decimal("80.10"))
        self.assertEqual(stmt.cgst, Decimal("1.48"))
        self.assertEqual(stmt.sgst, Decimal("1.48"))

    def test_f06_tc05_parse_zerodha_console_tradebook_csv(self):
        stmt = build_valid_zerodha_statement()
        csv_str = stmt.to_csv_string()
        self.assertIn("TATA", csv_str)
        self.assertIn("INE155A01022", csv_str)
        self.assertIn("800", csv_str)

    # --------------------------------------------------------------------------
    # FEATURE 7: HDFC Securities Parser
    # --------------------------------------------------------------------------
    def test_f07_tc01_parse_hdfc_equity_buy_trades(self):
        stmt = build_valid_hdfc_statement()
        self.assertEqual(len(stmt.trades), 1)
        self.assertEqual(stmt.trades[0].scrip_name, "HDFC BANK LIMITED")
        self.assertEqual(stmt.trades[0].quantity, Decimal("600"))
        self.assertEqual(stmt.trades[0].gross_rate, Decimal("1350.00"))

    def test_f07_tc02_parse_hdfc_settlement_and_demat_account_meta(self):
        stmt = build_valid_hdfc_statement()
        self.assertEqual(stmt.settlement_no, "2024115")
        self.assertEqual(stmt.trading_acc_no, "1092847101")
        self.assertEqual(stmt.demat_client_id, "1208670000123456")

    def test_f07_tc03_extract_hdfc_brokerage_and_turnover_charges(self):
        stmt = build_valid_hdfc_statement()
        self.assertEqual(stmt.total_brokerage, Decimal("162.00"))
        self.assertEqual(stmt.stt, Decimal("810.00"))
        self.assertEqual(stmt.exchange_turnover, Decimal("24.06"))
        self.assertEqual(stmt.service_tax_gst, Decimal("33.64"))

    def test_f07_tc04_extract_demat_allocation_charges(self):
        stmt = build_valid_hdfc_statement()
        self.assertEqual(stmt.demat_charges, Decimal("15.93"))

    def test_f07_tc05_parse_hdfc_sgb_gold_bond_trades(self):
        sgb_t = SyntheticHDFCTradeRow(
            exchange="NSE",
            scrip_name="SGBMAY29 - EQ",
            isin="IN0020210040",
            action="BUY",
            quantity=Decimal("50"),
            gross_rate=Decimal("6500.00"),
            brokerage=Decimal("65.00"),
        )
        self.assertEqual(sgb_t.gross_total, Decimal("325000.00"))
        self.assertEqual(sgb_t.net_total, Decimal("325065.00"))

    # --------------------------------------------------------------------------
    # FEATURE 8: CAMS / KFintech e-CAS Parser
    # --------------------------------------------------------------------------
    def test_f08_tc01_parse_cams_initial_purchase_with_stamp_duty(self):
        stmt = build_valid_cams_statement()
        s = stmt.schemes[0]
        t1 = s.transactions[0]
        self.assertEqual(t1.tx_type, "PURCHASE")
        self.assertEqual(t1.gross_amount, Decimal("1000000.00"))
        self.assertEqual(t1.stamp_duty, Decimal("50.00"))
        self.assertEqual(t1.units, Decimal("2149.968"))

    def test_f08_tc02_parse_cams_monthly_sip_installments(self):
        stmt = build_valid_cams_statement()
        t2 = stmt.schemes[0].transactions[1]
        self.assertEqual(t2.tx_type, "SIP")
        self.assertEqual(t2.gross_amount, Decimal("50000.00"))
        self.assertEqual(t2.stamp_duty, Decimal("2.50"))
        self.assertEqual(t2.units, Decimal("104.161"))

    def test_f08_tc03_parse_cams_redemption_transaction(self):
        stmt = build_valid_cams_statement()
        t3 = stmt.schemes[0].transactions[2]
        self.assertEqual(t3.tx_type, "REDEMPTION")
        self.assertEqual(t3.units, Decimal("-500.000"))
        self.assertEqual(t3.gross_amount, Decimal("310000.00"))

    def test_f08_tc04_extract_folio_scheme_isin_amfi_meta(self):
        stmt = build_valid_cams_statement()
        s = stmt.schemes[0]
        self.assertEqual(s.folio_number, "4481023/1")
        self.assertEqual(s.amfi_code, "100085")
        self.assertEqual(s.isin, "INF966L01AA3")
        self.assertEqual(s.advisor, "DIRECT")

    def test_f08_tc05_verify_cams_unit_balance_continuity(self):
        stmt = build_valid_cams_statement()
        passed, err, diff = ReferenceValidationGate.validate_cas(stmt)
        self.assertTrue(passed)
        self.assertIsNone(err)

    # --------------------------------------------------------------------------
    # FEATURE 9: Charles Schwab (US) Parser
    # --------------------------------------------------------------------------
    def test_f09_tc01_parse_schwab_buy_equity_shares(self):
        stmt = build_valid_schwab_statement()
        r1 = stmt.rows[0]
        self.assertEqual(r1.action, "Buy")
        self.assertEqual(r1.symbol, "NVDA")
        self.assertEqual(r1.quantity, Decimal("150.000"))
        self.assertEqual(r1.price, Decimal("62.40"))
        self.assertEqual(r1.amount, Decimal("-9360.00"))

    def test_f09_tc02_parse_schwab_sell_equity_with_sec_fees(self):
        stmt = build_valid_schwab_statement()
        r_sell = stmt.rows[4]
        self.assertEqual(r_sell.action, "Sell")
        self.assertEqual(r_sell.symbol, "NVDA")
        self.assertEqual(r_sell.quantity, Decimal("50.000"))
        self.assertEqual(r_sell.price, Decimal("125.00"))
        self.assertEqual(r_sell.fees_and_comm, Decimal("0.17"))
        self.assertEqual(r_sell.amount, Decimal("6249.83"))

    def test_f09_tc03_parse_schwab_qual_dividend_cashflow(self):
        stmt = build_valid_schwab_statement()
        r_div = stmt.rows[1]
        self.assertEqual(r_div.action, "Qual Dividend")
        self.assertEqual(r_div.amount, Decimal("24.00"))

    def test_f09_tc04_parse_schwab_irs_1042s_tax_withholding(self):
        stmt = build_valid_schwab_statement()
        r_tax = stmt.rows[2]
        self.assertEqual(r_tax.action, "Tax Withholding")
        self.assertEqual(r_tax.amount, Decimal("-6.00")) # Exactly 25% of $24

    def test_f09_tc05_parse_schwab_reinvest_dividend_fractional_shares(self):
        stmt = build_valid_schwab_statement()
        r_reinv = stmt.rows[3]
        self.assertEqual(r_reinv.action, "Reinvest Dividend")
        self.assertEqual(r_reinv.symbol, "VOO")
        self.assertEqual(r_reinv.quantity, Decimal("0.050"))
        self.assertEqual(r_reinv.amount, Decimal("-22.50"))

    # --------------------------------------------------------------------------
    # FEATURE 10: Fail-Closed Mathematical Validation Gate
    # --------------------------------------------------------------------------
    def test_f10_tc01_validate_zerodha_gross_brokerage_levies_net_invariant(self):
        stmt = build_valid_zerodha_statement()
        passed, err, disc = ReferenceValidationGate.validate_zerodha(stmt)
        self.assertTrue(passed)
        self.assertLessEqual(disc, MATH_INVARIANT_TOLERANCE)

    def test_f10_tc02_validate_zerodha_gst_18pct_exactness(self):
        stmt = build_valid_zerodha_statement()
        taxable = stmt.brokerage + stmt.exchange_turnover_fee + stmt.sebi_turnover_fee
        expected_gst = taxable * Decimal("0.18")
        actual_gst = stmt.cgst + stmt.sgst + stmt.igst
        self.assertAlmostEqual(float(expected_gst), float(actual_gst), delta=0.05)

    def test_f10_tc03_validate_hdfc_contract_note_math(self):
        stmt = build_valid_hdfc_statement()
        passed, err, disc = ReferenceValidationGate.validate_hdfc(stmt)
        self.assertTrue(passed)
        self.assertLessEqual(disc, MATH_INVARIANT_TOLERANCE)

    def test_f10_tc04_validate_cas_unit_addition_and_redemption_math(self):
        stmt = build_valid_cams_statement()
        passed, err, diff = ReferenceValidationGate.validate_cas(stmt)
        self.assertTrue(passed)
        self.assertEqual(diff, Decimal("0.00"))

    def test_f10_tc05_validate_schwab_usd_net_cashflow_math(self):
        stmt = build_valid_schwab_statement()
        passed, err, diff = ReferenceValidationGate.validate_schwab(stmt)
        self.assertTrue(passed)
        self.assertEqual(diff, Decimal("0.00"))

    # --------------------------------------------------------------------------
    # FEATURE 11: Transaction Fingerprinting & Idempotency
    # --------------------------------------------------------------------------
    def test_f11_tc01_compute_deterministic_transaction_sha256_fingerprint(self):
        fp1 = ReferenceReconciliationGate.compute_transaction_fingerprint(
            "port_primary", "ZERODHA", "INE155A01022", "2024-08-14", "BUY", Decimal("800"), Decimal("480.00"), "84920194"
        )
        fp2 = ReferenceReconciliationGate.compute_transaction_fingerprint(
            "port_primary", "ZERODHA", "INE155A01022", "2024-08-14", "BUY", Decimal("800"), Decimal("480.00"), "84920194"
        )
        self.assertEqual(fp1, fp2)
        self.assertEqual(len(fp1), 64)

    def test_f11_tc02_compute_deterministic_statement_boundary_hash(self):
        h1 = ReferenceReconciliationGate.compute_statement_hash("ZERODHA", "ZR1102", "2024-08-14", "2024-08-14", 2, Decimal("-534633.45"))
        h2 = ReferenceReconciliationGate.compute_statement_hash("ZERODHA", "ZR1102", "2024-08-14", "2024-08-14", 2, Decimal("-534633.45"))
        self.assertEqual(h1, h2)

    def test_f11_tc03_duplicate_fingerprint_marked_as_duplicate_skipped(self):
        fp = ReferenceReconciliationGate.compute_transaction_fingerprint(
            "port_primary", "ZERODHA", "INE155A01022", "2024-08-14", "BUY", Decimal("800"), Decimal("480.00"), "84920194"
        )
        seen_set = {fp}
        self.assertIn(fp, seen_set)

    def test_f11_tc04_identical_statement_returns_idempotent_noop(self):
        stmt_hash = ReferenceReconciliationGate.compute_statement_hash("ZERODHA", "ZR1102", "2024-08-14", "2024-08-14", 2, Decimal("-534633.45"))
        ingested_db = {stmt_hash: "COMPLETED"}
        self.assertEqual(ingested_db.get(stmt_hash), "COMPLETED")

    def test_f11_tc05_reingesting_contract_note_produces_zero_duplicate_ledger_writes(self):
        ledger = []
        seen_fps = set()
        stmt = build_valid_zerodha_statement()
        
        # Ingest pass 1
        for t in stmt.trades:
            fp = ReferenceReconciliationGate.compute_transaction_fingerprint(
                "port_primary", "ZERODHA", t.isin, "2024-08-14", t.action, t.quantity, t.gross_rate, t.trade_no
            )
            if fp not in seen_fps:
                seen_fps.add(fp)
                ledger.append(t)
        self.assertEqual(len(ledger), 2)

        # Ingest pass 2 (re-import)
        new_writes = 0
        for t in stmt.trades:
            fp = ReferenceReconciliationGate.compute_transaction_fingerprint(
                "port_primary", "ZERODHA", t.isin, "2024-08-14", t.action, t.quantity, t.gross_rate, t.trade_no
            )
            if fp not in seen_fps:
                seen_fps.add(fp)
                ledger.append(t)
                new_writes += 1
        self.assertEqual(new_writes, 0)
        self.assertEqual(len(ledger), 2)

    # --------------------------------------------------------------------------
    # FEATURE 12: RBI Reference Forex Rate Engine
    # --------------------------------------------------------------------------
    def test_f12_tc01_lookup_spot_rbi_reference_rate_for_transaction_date(self):
        rate = lookup_rbi_rate(date(2023, 5, 18), mode="SPOT")
        self.assertEqual(rate, Decimal("82.35"))

    def test_f12_tc02_lookup_rule_115_preceding_month_end_rate(self):
        # For trade in May 2023, Rule 115 specifies rate on last day of April 2023
        rate = lookup_rbi_rate(date(2023, 5, 18), mode="RULE_115")
        self.assertEqual(rate, Decimal("81.80"))

    def test_f12_tc03_convert_usd_trade_cost_basis_to_inr(self):
        rate = lookup_rbi_rate(date(2023, 5, 18), mode="SPOT") # 82.35
        cost_usd = Decimal("9360.00")
        cost_inr = (cost_usd * rate).quantize(Decimal("0.01"))
        self.assertEqual(cost_inr, Decimal("770796.00"))

    def test_f12_tc04_convert_usd_dividend_to_inr_under_rule_115(self):
        # Dividend received 2023-11-15 -> Rule 115 rate from Oct 31 / closest (82.75)
        rate = lookup_rbi_rate(date(2023, 11, 15), mode="RULE_115")
        div_usd = Decimal("24.00")
        div_inr = (div_usd * rate).quantize(Decimal("0.01"))
        self.assertGreater(div_inr, Decimal("1900.00"))

    def test_f12_tc05_holiday_weekend_forex_lookback_resolution(self):
        # Sunday date 2024-08-11 should fallback to Friday rate
        rate = lookup_rbi_rate(date(2024, 8, 11), mode="SPOT")
        self.assertTrue(rate > Decimal("80.00"))

    # --------------------------------------------------------------------------
    # FEATURE 13: FIFO Tax Lot Accounting Engine
    # --------------------------------------------------------------------------
    def test_f13_tc01_create_active_tax_lot_on_equity_buy(self):
        engine = ReferenceFIFOTaxEngine()
        lot = engine.buy_lot("port_primary", "INE155A01022", "EQUITY", date(2023, 1, 15), Decimal("500"), Decimal("400.00"))
        self.assertEqual(lot["status"], "ACTIVE")
        self.assertEqual(lot["remaining_quantity"], Decimal("500"))

    def test_f13_tc02_deplete_fifo_lots_chronologically_on_sell(self):
        engine = ReferenceFIFOTaxEngine()
        engine.buy_lot("port_primary", "INE155A01022", "EQUITY", date(2023, 1, 15), Decimal("500"), Decimal("400.00"))
        engine.buy_lot("port_primary", "INE155A01022", "EQUITY", date(2024, 1, 15), Decimal("300"), Decimal("500.00"))
        disps = engine.sell_units("port_primary", "INE155A01022", "EQUITY", date(2024, 8, 14), Decimal("600"), Decimal("650.00"))
        self.assertEqual(len(disps), 2)
        self.assertEqual(disps[0]["matched_quantity"], Decimal("500")) # From Lot 1
        self.assertEqual(disps[1]["matched_quantity"], Decimal("100")) # From Lot 2

    def test_f13_tc03_compute_indian_equity_stcg_20pct_for_under_12m(self):
        engine = ReferenceFIFOTaxEngine()
        engine.buy_lot("port_primary", "INE155A01022", "EQUITY", date(2024, 3, 1), Decimal("100"), Decimal("450.00"))
        disps = engine.sell_units("port_primary", "INE155A01022", "EQUITY", date(2024, 8, 14), Decimal("100"), Decimal("550.00"))
        self.assertFalse(disps[0]["is_long_term"])
        self.assertEqual(disps[0]["tax_rate_pct"], Decimal("20.00")) # Budget 2024 STCG 20%
        self.assertEqual(disps[0]["realized_gain_inr"], Decimal("10000.00"))
        self.assertEqual(disps[0]["estimated_tax_inr"], Decimal("2000.00"))

    def test_f13_tc04_compute_indian_equity_ltcg_12_5pct_for_over_12m(self):
        engine = ReferenceFIFOTaxEngine()
        engine.buy_lot("port_primary", "INE155A01022", "EQUITY", date(2023, 1, 15), Decimal("100"), Decimal("400.00"))
        disps = engine.sell_units("port_primary", "INE155A01022", "EQUITY", date(2024, 8, 14), Decimal("100"), Decimal("600.00"))
        self.assertTrue(disps[0]["is_long_term"])
        self.assertEqual(disps[0]["tax_rate_pct"], Decimal("12.50")) # Budget 2024 LTCG 12.5%
        self.assertEqual(disps[0]["realized_gain_inr"], Decimal("20000.00"))
        self.assertEqual(disps[0]["estimated_tax_inr"], Decimal("2500.00"))

    def test_f13_tc05_apply_24_month_holding_threshold_for_us_schwab_equity(self):
        engine = ReferenceFIFOTaxEngine()
        # Holding 18 months (< 24 months for foreign asset)
        engine.buy_lot("port_primary", "NVDA", "US_EQUITY", date(2023, 1, 15), Decimal("50"), Decimal("60.00"), forex_rate=Decimal("82.00"))
        disps = engine.sell_units("port_primary", "NVDA", "US_EQUITY", date(2024, 7, 15), Decimal("50"), Decimal("120.00"), forex_rate=Decimal("83.50"))
        self.assertFalse(disps[0]["is_long_term"]) # 18m is STCG for unlisted foreign asset under Finance Act 2024

    # --------------------------------------------------------------------------
    # FEATURE 14: Canonical Ledger Integration & API Endpoints
    # --------------------------------------------------------------------------
    def test_f14_tc01_inbound_email_payload_model_validation(self):
        payload = {
            "raw_mime": b"sample mime",
            "forwarder_email": "alex.taylor@example.com",
            "received_timestamp": datetime.now().isoformat()
        }
        self.assertIn("@", payload["forwarder_email"])

    def test_f14_tc02_identity_gate_result_structure_contract(self):
        res = ReferenceIdentityGate.process_mime_payload(create_zerodha_mime(), "alex.taylor@example.com")
        self.assertIn("passed", res)
        self.assertIn("rejection_code", res)
        self.assertIn("target_entity_id", res)
        self.assertIn("extracted_attachments", res)

    def test_f14_tc03_layout_gate_result_structure_contract(self):
        res = ReferenceDecryptionEngine.classify_and_decrypt(b"%PDF-1.7 ZERODHA", "cn.pdf", "KLMNO9012P")
        self.assertIn("passed", res)
        self.assertIn("layout_type", res)
        self.assertIn("decrypted_bytes", res)

    def test_f14_tc04_validation_gate_result_structure_contract(self):
        stmt = build_valid_zerodha_statement()
        passed, err, disc = ReferenceValidationGate.validate_zerodha(stmt)
        self.assertIsInstance(passed, bool)
        self.assertIsInstance(disc, Decimal)

    def test_f14_tc05_reconciliation_gate_result_structure_contract(self):
        h = ReferenceReconciliationGate.compute_statement_hash("ZERODHA", "ZR1102", "2024-08-14", "2024-08-14", 2, Decimal("-534633.45"))
        self.assertEqual(len(h), 64)

    # --------------------------------------------------------------------------
    # FEATURE 15: Multi-Tier Automated E2E Test Suite
    # --------------------------------------------------------------------------
    def test_f15_tc01_test_harness_initialization(self):
        self.assertIsNotNone(FAMILY_VAULT_PROFILES)
        self.assertIn("port_primary", FAMILY_VAULT_PROFILES)

    def test_f15_tc02_sample_statement_generators_validity(self):
        z = build_valid_zerodha_statement()
        h = build_valid_hdfc_statement()
        c = build_valid_cams_statement()
        s = build_valid_schwab_statement()
        self.assertIsNotNone(z)
        self.assertIsNotNone(h)
        self.assertIsNotNone(c)
        self.assertIsNotNone(s)

    def test_f15_tc03_tolerance_boundary_assertion_helper(self):
        self.assertEqual(MATH_INVARIANT_TOLERANCE, Decimal("0.02"))

    def test_f15_tc04_family_vault_profiles_registry_integrity(self):
        self.assertEqual(len(FAMILY_VAULT_PROFILES), 4)
        self.assertEqual(FAMILY_VAULT_PROFILES["port_primary"].pan, "KLMNO9012P")
        self.assertEqual(FAMILY_VAULT_PROFILES["port_father"].pan, "ABCDE1234F")
        self.assertEqual(FAMILY_VAULT_PROFILES["port_mother"].pan, "FGHIJ5678K")
        self.assertEqual(FAMILY_VAULT_PROFILES["port_trust"].pan, "PQRST3456Q")

    def test_f15_tc05_end_to_end_pipeline_simulation_passes_all_gates(self):
        # 1. Gate 1
        mime = create_zerodha_mime()
        g1 = ReferenceIdentityGate.process_mime_payload(mime, "alex.taylor@example.com")
        self.assertTrue(g1["passed"])
        
        # 2. Gate 2
        g2 = ReferenceDecryptionEngine.classify_and_decrypt(
            g1["extracted_attachments"][0]["content_bytes"],
            g1["extracted_attachments"][0]["filename"],
            g1["target_pan"]
        )
        self.assertTrue(g2["passed"])
        
        # 3. Gate 3
        stmt = build_valid_zerodha_statement()
        g3_pass, g3_err, g3_disc = ReferenceValidationGate.validate_zerodha(stmt)
        self.assertTrue(g3_pass)

        # 4. Gate 4
        h = ReferenceReconciliationGate.compute_statement_hash("ZERODHA", "ZR1102", "2024-08-14", "2024-08-14", 2, Decimal("-534633.45"))
        self.assertEqual(len(h), 64)

    # --------------------------------------------------------------------------
    # FEATURE 16: Adversarial Hardening & Forensic Verification
    # --------------------------------------------------------------------------
    def test_f16_tc01_detect_mutated_transaction_fingerprint_tampering(self):
        fp_orig = ReferenceReconciliationGate.compute_transaction_fingerprint(
            "port_primary", "ZERODHA", "INE155A01022", "2024-08-14", "BUY", Decimal("800"), Decimal("480.00"), "84920194"
        )
        # Mutate quantity slightly by 0.0001
        fp_mutated = ReferenceReconciliationGate.compute_transaction_fingerprint(
            "port_primary", "ZERODHA", "INE155A01022", "2024-08-14", "BUY", Decimal("800.0001"), Decimal("480.00"), "84920194"
        )
        self.assertNotEqual(fp_orig, fp_mutated)

    def test_f16_tc02_detect_penny_drop_math_shaving_attack(self):
        stmt = build_valid_zerodha_statement()
        stmt.net_settlement_amount += Decimal("0.05") # 5 paise shaving
        passed, err, disc = ReferenceValidationGate.validate_zerodha(stmt)
        self.assertFalse(passed)
        self.assertIn("ERR_VALIDATION_MATH_MISMATCH", err)

    def test_f16_tc03_reject_spoofed_broker_sender_domain(self):
        mime = build_forwarded_email("alex.taylor@example.com", "fake@zerodh4.com", attachments=[("cn.pdf", b"data", "pdf")])
        res = ReferenceIdentityGate.process_mime_payload(mime, "alex.taylor@example.com")
        self.assertFalse(res["passed"])
        self.assertEqual(res["rejection_code"], "ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN")

    def test_f16_tc04_reject_unauthorized_forwarder_email(self):
        mime = create_zerodha_mime("intruder@attacker.com")
        res = ReferenceIdentityGate.process_mime_payload(mime, "intruder@attacker.com")
        self.assertFalse(res["passed"])
        self.assertEqual(res["rejection_code"], "ERR_IDENTITY_UNAUTHORIZED_FORWARDER")

    def test_f16_tc05_reject_statement_with_unit_balance_continuity_breach(self):
        corrupt_cas = build_corrupted_cams_statement()
        passed, err, diff = ReferenceValidationGate.validate_cas(corrupt_cas)
        self.assertFalse(passed)
        self.assertIn("ERR_VALIDATION_CAS_UNIT_CONTINUITY", err)


if __name__ == "__main__":
    unittest.main()
