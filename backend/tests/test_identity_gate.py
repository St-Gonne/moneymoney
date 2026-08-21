"""
Unit Tests for Identity Gate (Gate 1)
Validates fail-closed perimeter security across all positive and negative test cases:
1. Positive flows for all 4 family members and all 4 broker institutions (Zerodha, HDFC Sec, CAMS/KFintech, Schwab).
2. Negative flows for spoofed senders, unauthorized forwarders, unapproved broker domains, missing attachments, and PAN mismatches.
3. In-memory attachment extraction verification (zero disk writes).
"""

import hashlib
import io
import unittest

from backend.app.config import (
    ERR_IDENTITY_MALFORMED_MIME,
    ERR_IDENTITY_NO_ATTACHMENTS,
    ERR_IDENTITY_PAN_MISMATCH,
    ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN,
    ERR_IDENTITY_UNAUTHORIZED_FORWARDER,
    BrokerInstitution,
)
from backend.app.fixtures.sample_statements import (
    MIME_CAMS_FORWARDED_MOTHER,
    MIME_HDFC_FORWARDED_FATHER,
    MIME_HUF_FORWARDED_PRIMARY,
    MIME_SCHWAB_FORWARDED_PRIMARY,
    MIME_ZERODHA_FORWARDED_PRIMARY,
    SAMPLE_CSV_CONTENT,
    SAMPLE_PDF_HEADER,
    create_direct_broker_email_mime,
    create_sample_forwarded_email_mime,
)
from backend.app.gates.identity_gate import IdentityGate, evaluate_identity_gate
from backend.app.models.email import InboundEmailPayload


class TestIdentityGatePositive(unittest.TestCase):
    """Positive end-to-end verification cases for Gate 1."""

    def setUp(self):
        self.gate = IdentityGate()

    def test_zerodha_forwarded_by_alex(self):
        """Valid Zerodha contract note forwarded by Alex passes Gate 1."""
        result = self.gate.evaluate(MIME_ZERODHA_FORWARDED_PRIMARY)

        self.assertTrue(result.passed, f"Gate failed with: {result.rejection_reason}")
        self.assertIsNone(result.rejection_code)
        self.assertEqual(result.target_entity_id, "port_primary")
        self.assertEqual(result.target_pan, "KLMNO9012P")
        self.assertEqual(result.broker_institution, BrokerInstitution.ZERODHA)
        self.assertEqual(len(result.extracted_attachments), 1)

        att = result.extracted_attachments[0]
        self.assertTrue(att.filename.endswith(".pdf"))
        self.assertEqual(att.content_type, "application/pdf")
        self.assertEqual(att.payload_bytes, SAMPLE_PDF_HEADER)
        self.assertEqual(att.sha256, hashlib.sha256(SAMPLE_PDF_HEADER).hexdigest())

        # Test in-memory stream
        stream = att.get_stream()
        self.assertIsInstance(stream, io.BytesIO)
        self.assertEqual(stream.read(), SAMPLE_PDF_HEADER)

    def test_hdfc_forwarded_by_robert(self):
        """Valid HDFC Securities contract note forwarded by Robert passes Gate 1."""
        result = self.gate.evaluate(MIME_HDFC_FORWARDED_FATHER)

        self.assertTrue(result.passed)
        self.assertEqual(result.target_entity_id, "port_father")
        self.assertEqual(result.target_pan, "ABCDE1234F")
        self.assertEqual(result.broker_institution, BrokerInstitution.HDFC_SECURITIES)
        self.assertEqual(len(result.extracted_attachments), 1)

    def test_cams_forwarded_by_margaret(self):
        """Valid CAMS e-CAS forwarded by Margaret passes Gate 1."""
        result = self.gate.evaluate(MIME_CAMS_FORWARDED_MOTHER)

        self.assertTrue(result.passed)
        self.assertEqual(result.target_entity_id, "port_mother")
        self.assertEqual(result.target_pan, "FGHIJ5678K")
        self.assertEqual(result.broker_institution, BrokerInstitution.CAMS_KFINTECH)
        self.assertEqual(len(result.extracted_attachments), 1)

    def test_schwab_forwarded_by_alex_csv(self):
        """Valid Charles Schwab trade export CSV forwarded by Alex passes Gate 1."""
        result = self.gate.evaluate(MIME_SCHWAB_FORWARDED_PRIMARY)

        self.assertTrue(result.passed)
        self.assertEqual(result.target_entity_id, "port_primary")
        self.assertEqual(result.target_pan, "KLMNO9012P")
        self.assertEqual(result.broker_institution, BrokerInstitution.CHARLES_SCHWAB)
        self.assertEqual(len(result.extracted_attachments), 1)
        self.assertEqual(result.extracted_attachments[0].content_type, "text/csv")
        self.assertEqual(result.extracted_attachments[0].payload_bytes, SAMPLE_CSV_CONTENT)

    def test_huf_cas_forwarded_by_alex(self):
        """HUF statement forwarded by Karta Alex is correctly mapped to HUF vault."""
        result = self.gate.evaluate(MIME_HUF_FORWARDED_PRIMARY)

        self.assertTrue(result.passed)
        self.assertEqual(result.target_entity_id, "port_trust")
        self.assertEqual(result.target_pan, "PQRST3456Q")
        self.assertEqual(result.broker_institution, BrokerInstitution.CAMS_KFINTECH)

    def test_broker_subdomain_support(self):
        """Broker sending from subdomains like e-contracts.zerodha.com or bounce.hdfcbank.net passes."""
        mime = create_sample_forwarded_email_mime(
            forwarder_email="alex.taylor@example.com",
            original_sender="Zerodha Automated <alerts@mailer.zerodha.com>",
            subject="Trade Confirmation",
            body_text="Your trade confirmation statement is attached.",
            attachments=[("trade_conf.pdf", "application/pdf", SAMPLE_PDF_HEADER)],
        )
        result = self.gate.evaluate(mime)
        self.assertTrue(result.passed)
        self.assertEqual(result.broker_institution, BrokerInstitution.ZERODHA)

    def test_multiple_attachments_extraction(self):
        """Email containing both PDF contract note and CSV trade summary extracts both into memory."""
        mime = create_sample_forwarded_email_mime(
            forwarder_email="robert.taylor@example.com",
            original_sender="HDFC Sec <support@hdfcsec.com>",
            subject="Contract Note and CSV Export",
            body_text="Both statements attached.",
            attachments=[
                ("cn.pdf", "application/pdf", SAMPLE_PDF_HEADER),
                ("trades.csv", "text/csv", SAMPLE_CSV_CONTENT),
            ],
        )
        result = self.gate.evaluate(mime)
        self.assertTrue(result.passed)
        self.assertEqual(len(result.extracted_attachments), 2)
        filenames = [att.filename for att in result.extracted_attachments]
        self.assertIn("cn.pdf", filenames)
        self.assertIn("trades.csv", filenames)

    def test_convenience_evaluate_function(self):
        """Functional evaluate_identity_gate interface behaves identically."""
        result = evaluate_identity_gate(MIME_ZERODHA_FORWARDED_PRIMARY)
        self.assertTrue(result.passed)
        self.assertEqual(result.target_entity_id, "port_primary")


class TestIdentityGateNegative(unittest.TestCase):
    """Negative, edge-case, and security perimeter test cases for Gate 1."""

    def setUp(self):
        self.gate = IdentityGate()

    def test_unauthorized_forwarder_rejected(self):
        """Email from unauthorized forwarder fails closed with ERR_IDENTITY_UNAUTHORIZED_FORWARDER."""
        mime = create_sample_forwarded_email_mime(
            forwarder_email="stranger@external.com",
            original_sender="contracts@zerodha.com",
            subject="Contract Note",
            body_text="Forwarding note.",
            attachments=[("cn.pdf", "application/pdf", SAMPLE_PDF_HEADER)],
        )
        result = self.gate.evaluate(mime)

        self.assertFalse(result.passed)
        self.assertEqual(result.rejection_code, ERR_IDENTITY_UNAUTHORIZED_FORWARDER)
        self.assertIn("not in authorized family whitelist", result.rejection_reason)

    def test_unauthorized_broker_domain_rejected(self):
        """Forwarder is authorized, but original sender is from unauthorized/phishing domain."""
        mime = create_sample_forwarded_email_mime(
            forwarder_email="alex.taylor@example.com",
            original_sender="phishing@fakeinvestments.com",
            subject="Important Account Statement",
            body_text="Please review.",
            attachments=[("statement.pdf", "application/pdf", SAMPLE_PDF_HEADER)],
        )
        result = self.gate.evaluate(mime)

        self.assertFalse(result.passed)
        self.assertEqual(result.rejection_code, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN)
        self.assertIn("not in authorized broker whitelist", result.rejection_reason)

    def test_missing_forwarded_headers_rejected(self):
        """Email from authorized family member without any forwarded broker header or broker address."""
        mime = create_sample_forwarded_email_mime(
            forwarder_email="alex.taylor@example.com",
            original_sender="alex.taylor@example.com",
            subject="Personal Notes",
            body_text="Just some personal notes without broker origin.",
            attachments=[("doc.pdf", "application/pdf", SAMPLE_PDF_HEADER)],
        )
        result = self.gate.evaluate(mime)

        self.assertFalse(result.passed)
        self.assertEqual(result.rejection_code, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN)

    def test_no_attachments_rejected(self):
        """Valid forwarded email from broker, but lacking statement attachments fails closed."""
        mime = create_sample_forwarded_email_mime(
            forwarder_email="alex.taylor@example.com",
            original_sender="contracts@zerodha.com",
            subject="Contract Note Confirmation",
            body_text="Your trade was executed successfully. (No attachment included)",
            attachments=[],
        )
        result = self.gate.evaluate(mime)

        self.assertFalse(result.passed)
        self.assertEqual(result.rejection_code, ERR_IDENTITY_NO_ATTACHMENTS)
        self.assertIn("No valid PDF or CSV attachments found", result.rejection_reason)

    def test_unsupported_attachment_extensions_rejected(self):
        """Email containing only unsupported attachment types (.exe, .zip, .png) fails closed."""
        mime = create_sample_forwarded_email_mime(
            forwarder_email="alex.taylor@example.com",
            original_sender="contracts@zerodha.com",
            subject="Contract Note Summary",
            body_text="Summary attached.",
            attachments=[
                ("malware.exe", "application/octet-stream", b"MZ\x90\x00"),
                ("screenshot.png", "image/png", b"\x89PNG\r\n\x1a\n"),
            ],
        )
        result = self.gate.evaluate(mime)

        self.assertFalse(result.passed)
        self.assertEqual(result.rejection_code, ERR_IDENTITY_NO_ATTACHMENTS)

    def test_pan_mismatch_rejected(self):
        """Payload specifying explicit target PAN belonging to another entity without delegation fails closed."""
        payload = InboundEmailPayload(
            raw_mime=MIME_CAMS_FORWARDED_MOTHER,
            forwarder_email="margaret.taylor@example.com",
            target_pan="ABCDE1234F",  # Robert's PAN submitted by Margaret
        )
        result = self.gate.evaluate(payload)

        self.assertFalse(result.passed)
        self.assertEqual(result.rejection_code, ERR_IDENTITY_PAN_MISMATCH)

    def test_unknown_pan_rejected(self):
        """Payload specifying non-existent or un-registered PAN fails closed."""
        payload = InboundEmailPayload(
            raw_mime=MIME_ZERODHA_FORWARDED_PRIMARY,
            forwarder_email="alex.taylor@example.com",
            target_pan="ZZZZZ9999Z",
        )
        result = self.gate.evaluate(payload)

        self.assertFalse(result.passed)
        self.assertEqual(result.rejection_code, ERR_IDENTITY_PAN_MISMATCH)
        self.assertIn("not registered to any Taylor family vault entity", result.rejection_reason)

    def test_malformed_mime_payload_rejected(self):
        """Empty or invalid raw payload fails closed with ERR_IDENTITY_MALFORMED_MIME."""
        result_empty_bytes = self.gate.evaluate(b"")
        self.assertFalse(result_empty_bytes.passed)
        self.assertEqual(result_empty_bytes.rejection_code, ERR_IDENTITY_MALFORMED_MIME)

        result_invalid_type = self.gate.evaluate(None)
        self.assertFalse(result_invalid_type.passed)
        self.assertEqual(result_invalid_type.rejection_code, ERR_IDENTITY_MALFORMED_MIME)

    def test_malformed_date_header_no_crash(self):
        """MIME with non-RFC malformed Date header does not crash and processes cleanly."""
        mime_with_bad_date = (
            b"From: alex.taylor@example.com\r\n"
            b"Date: Not_A_Valid_Date_String\r\n"
            b"To: vault@moneymoney.internal\r\n"
            b"Subject: Contract Note\r\n"
            b"Content-Type: multipart/mixed; boundary=\"BND\"\r\n\r\n"
            b"--BND\r\n"
            b"Content-Type: text/plain\r\n\r\n"
            b"---------- Forwarded message ---------\r\n"
            b"From: contracts@zerodha.com\r\n\r\n"
            b"--BND\r\n"
            b"Content-Type: application/pdf\r\n"
            b"Content-Disposition: attachment; filename=\"cn.pdf\"\r\n\r\n"
            b"%PDF-1.4 binary data\r\n"
            b"--BND--\r\n"
        )
        res = self.gate.evaluate(mime_with_bad_date)
        self.assertTrue(res.passed)
        self.assertIsNone(res.extracted_metadata.date)
        self.assertEqual(res.broker_institution, BrokerInstitution.ZERODHA)

    def test_surrogate_unicode_string_payload_no_crash(self):
        """String payload with lone surrogate Unicode characters does not crash with UnicodeEncodeError."""
        surrogate_string = "From: alex.taylor@example.com\r\nSubject: \ud961 Note\r\n\r\nBody"
        res = self.gate.evaluate(surrogate_string)
        self.assertFalse(res.passed)
        self.assertIn(
            res.rejection_code,
            [ERR_IDENTITY_MALFORMED_MIME, ERR_IDENTITY_NO_ATTACHMENTS, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN],
        )

    def test_invalid_raw_mime_type_in_dict_rejected(self):
        """Dictionary payload with non-bytes/non-string raw_mime rejects with ERR_IDENTITY_MALFORMED_MIME."""
        res_dict = self.gate.evaluate({"raw_mime": 99999})
        self.assertFalse(res_dict.passed)
        self.assertEqual(res_dict.rejection_code, ERR_IDENTITY_MALFORMED_MIME)

        # InboundEmailPayload directly instantiated with integer raw_mime
        payload_obj = InboundEmailPayload(raw_mime=12345)
        res_obj = self.gate.evaluate(payload_obj)
        self.assertFalse(res_obj.passed)
        self.assertEqual(res_obj.rejection_code, ERR_IDENTITY_MALFORMED_MIME)


if __name__ == "__main__":
    unittest.main()
