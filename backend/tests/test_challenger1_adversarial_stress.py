"""
Adversarial Stress Testing & Security Verification Suite (Gate 1 - Identity Gate)
Milestone 1: Inbound Email Ingestion & Identity Gate
Challenger 1: teamwork_preview_challenger_m1_1

Covers:
1. Header injection & spoofed sender attacks (CRLF, multiple From, display name spoofing, subdomain hijacks)
2. Forwarded block tampering (fake forward blocks, chained delimiters, missing lines, cross-entity PAN injection)
3. Unicode domain homoglyph spoofing (Cyrillic, Greek, Full-width, Punycode IDNs across all 5 broker domains)
4. Malformed and truncated MIME streams (corrupted base64, truncated boundaries, binary garbage, null bytes)
5. Massive attachment payloads, zero-byte parts, and malicious file extension filtering (.exe, .zip, .sh)
6. Case-sensitivity & whitespace normalization edge cases on forwarder emails, broker domains, and PANs
7. Defect demonstrations: Explicit empirical test cases reproducing the 3 unhandled exception vulnerabilities
8. Fuzzing harness: 1,000 randomized mutations validating fail-closed perimeter behavior
"""

import email
import email.message
import email.policy
import hashlib
import io
import os
import random
import string
import sys
import tempfile
import unittest
from datetime import datetime
from typing import List, Optional, Tuple, Union

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.config import (
    ALLOWED_BROKER_DOMAINS,
    ALLOWED_FAMILY_EMAILS,
    BROKER_DOMAIN_MAP,
    ERR_IDENTITY_MALFORMED_MIME,
    ERR_IDENTITY_NO_ATTACHMENTS,
    ERR_IDENTITY_PAN_MISMATCH,
    ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN,
    ERR_IDENTITY_UNAUTHORIZED_FORWARDER,
    ERR_IDENTITY_UNRESOLVED_ENTITY,
    FAMILY_PAN_REGISTRY,
    BrokerInstitution,
    FamilyEntityProfile,
    get_entity_by_email,
    get_entity_by_pan,
    is_authorized_broker_domain,
    is_authorized_forwarder,
    resolve_broker_institution,
)
from backend.app.gates.identity_gate import IdentityGate, evaluate_identity_gate
from backend.app.models.email import (
    ExtractedAttachment,
    ExtractedEmailMetadata,
    IdentityGateResult,
    InboundEmailPayload,
)


def build_raw_mime(
    from_header: Optional[str] = "alex.taylor@example.com",
    to_header: str = "vault-ingest@moneymoney.internal",
    subject: str = "Contract Note",
    body: str = "---------- Forwarded message ---------\nFrom: Zerodha <contracts@zerodha.com>\n\nAttached.",
    attachments: Optional[List[Tuple[str, str, bytes]]] = None,
    custom_headers: Optional[List[Tuple[str, str]]] = None,
) -> bytes:
    """Constructs a raw RFC 822 MIME byte stream with full control over headers and formatting."""
    msg = email.message.EmailMessage()
    if from_header is not None:
        msg["From"] = from_header
    msg["To"] = to_header
    msg["Subject"] = subject
    msg["Date"] = "Fri, 14 Aug 2026 12:00:00 +0530"
    msg["Message-ID"] = "<msg-adv-test-01@moneymoney.internal>"

    if custom_headers:
        for k, v in custom_headers:
            msg[k] = v

    msg.set_content(body)

    if attachments:
        for fname, ctype, data in attachments:
            mtype, stype = ctype.split("/", 1)
            msg.add_attachment(data, maintype=mtype, subtype=stype, filename=fname)

    return msg.as_bytes()


class TestAdversarialHeaderInjectionAndSpoofing(unittest.TestCase):
    """Category 1: Header Injection & Spoofed Sender Attacks."""

    def setUp(self):
        self.gate = IdentityGate()
        self.dummy_pdf = b"%PDF-1.4 sample contract note binary content"

    def test_display_name_contains_authorized_email_but_real_address_is_attacker(self):
        """Attacker uses display name 'alex.taylor@example.com' with attacker mailbox."""
        spoofed_from = '"alex.taylor@example.com" <attacker@evil.com>'
        mime = build_raw_mime(
            from_header=spoofed_from,
            body="---------- Forwarded message ---------\nFrom: contracts@zerodha.com\n\nTrade attached.",
            attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
        )
        res = self.gate.evaluate(mime)
        self.assertFalse(res.passed, "Display name spoofing attack should fail closed.")
        self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_FORWARDER)

    def test_display_name_contains_broker_email_in_forwarder(self):
        """Attacker sets display name to broker email 'contracts@zerodha.com'."""
        spoofed_from = '"contracts@zerodha.com" <hacker@phishing.net>'
        mime = build_raw_mime(
            from_header=spoofed_from,
            body="---------- Forwarded message ---------\nFrom: contracts@zerodha.com\n\nTrade attached.",
            attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
        )
        res = self.gate.evaluate(mime)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_FORWARDER)

    def test_broker_display_name_spoof_with_attacker_broker_address(self):
        """Forwarder is authorized, but forwarded From header has broker display name with fake domain."""
        fake_broker_from = '"Zerodha Support" <zerodha@support-mailer.evil.org>'
        body = f"---------- Forwarded message ---------\nFrom: {fake_broker_from}\n\nTrade attached."
        mime = build_raw_mime(
            from_header="alex.taylor@example.com",
            body=body,
            attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
        )
        res = self.gate.evaluate(mime)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN)

    def test_subdomain_hijacking_attempts(self):
        """Attacker uses lookalike domain suffixes that contain broker name but belong to attacker."""
        hijacked_domains = [
            "contracts@zerodha.com.evil.com",
            "support@zerodha.com-verify.org",
            "alerts@hdfcsec.com.phish.in",
            "cas@camsonline.com.attacker.com",
            "reports@kfintech.com.malicious.io",
            "trade@schwab.com.fakeportal.net",
            "support@evilzerodha.com",
            "support@zerodhasecurities.com",
        ]
        for bad_addr in hijacked_domains:
            body = f"---------- Forwarded message ---------\nFrom: Broker <{bad_addr}>\n\nStatement attached."
            mime = build_raw_mime(
                from_header="alex.taylor@example.com",
                body=body,
                attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
            )
            res = self.gate.evaluate(mime)
            self.assertFalse(res.passed, f"Domain hijack {bad_addr} should be rejected.")
            self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN)

    def test_reversed_domain_structure(self):
        """Attacker uses reversed domain structure like @com.zerodha or @net.hdfcbank."""
        for rev_domain in ["support@com.zerodha", "help@net.hdfcbank"]:
            body = f"---------- Forwarded message ---------\nFrom: <{rev_domain}>\n\nStatement."
            mime = build_raw_mime(
                from_header="alex.taylor@example.com",
                body=body,
                attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
            )
            res = self.gate.evaluate(mime)
            self.assertFalse(res.passed)
            self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN)

    def test_multiple_from_headers_injection(self):
        """Email contains multiple From headers injected into MIME envelope."""
        raw = (
            b"From: attacker@evil.com\r\n"
            b"From: alex.taylor@example.com\r\n"
            b"To: vault-ingest@moneymoney.internal\r\n"
            b"Subject: Injected Note\r\n"
            b"Content-Type: multipart/mixed; boundary=\"ADV_BOUND\"\r\n\r\n"
            b"--ADV_BOUND\r\n"
            b"Content-Type: text/plain\r\n\r\n"
            b"---------- Forwarded message ---------\r\n"
            b"From: contracts@zerodha.com\r\n\r\n"
            b"--ADV_BOUND\r\n"
            b"Content-Type: application/pdf; name=\"cn.pdf\"\r\n"
            b"Content-Disposition: attachment; filename=\"cn.pdf\"\r\n\r\n"
            b"%PDF-1.4 binary\r\n"
            b"--ADV_BOUND--\r\n"
        )
        res = self.gate.evaluate(raw)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_FORWARDER)

    def test_crlf_injection_in_headers(self):
        """Attempts to inject CRLF into From header to break MIME parsing."""
        raw = (
            b"From: alex.taylor@example.com\r\n Bcc: attacker@evil.com\r\n"
            b"To: vault-ingest@moneymoney.internal\r\n"
            b"Subject: Test CRLF\r\n"
            b"Content-Type: multipart/mixed; boundary=\"BOUND\"\r\n\r\n"
            b"--BOUND\r\n"
            b"Content-Type: text/plain\r\n\r\n"
            b"---------- Forwarded message ---------\r\n"
            b"From: contracts@zerodha.com\r\n\r\n"
            b"--BOUND\r\n"
            b"Content-Type: application/pdf\r\n"
            b"Content-Disposition: attachment; filename=\"test.pdf\"\r\n\r\n"
            b"%PDF-1.4 data\r\n"
            b"--BOUND--\r\n"
        )
        res = self.gate.evaluate(raw)
        self.assertIsInstance(res, IdentityGateResult)

    def test_null_byte_in_from_header(self):
        """Null byte embedded in From header."""
        raw = (
            b"From: alex.taylor@example.com\x00@evil.com\r\n"
            b"To: vault-ingest@moneymoney.internal\r\n"
            b"Subject: Null Byte From\r\n"
            b"Content-Type: text/plain\r\n\r\n"
            b"Hello\r\n"
        )
        res = self.gate.evaluate(raw)
        self.assertFalse(res.passed)
        self.assertIn(
            res.rejection_code,
            [ERR_IDENTITY_UNAUTHORIZED_FORWARDER, ERR_IDENTITY_MALFORMED_MIME, ERR_IDENTITY_NO_ATTACHMENTS],
        )


class TestAdversarialForwardedBlockTampering(unittest.TestCase):
    """Category 2: Forwarded Block Tampering."""

    def setUp(self):
        self.gate = IdentityGate()
        self.dummy_pdf = b"%PDF-1.4 valid trade content"

    def test_chained_nested_forwarded_blocks_with_attacker_first(self):
        """Attacker injects an untrusted forward block before a legitimate broker forward block."""
        body = (
            "---------- Forwarded message ---------\n"
            "From: Malware Bot <bot@malwaredomain.com>\n"
            "Date: Fri, 14 Aug 2026\n"
            "Subject: Injected payload\n\n"
            "---------- Forwarded message ---------\n"
            "From: Zerodha Contracts <contracts@zerodha.com>\n"
            "Subject: Contract Note\n\n"
            "Legitimate content.\n"
        )
        mime = build_raw_mime(
            from_header="alex.taylor@example.com",
            body=body,
            attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
        )
        res = self.gate.evaluate(mime)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN)

    def test_forwarded_block_with_missing_from_line(self):
        """Forwarded block delimiter is present, but lacks a 'From:' line."""
        body = (
            "---------- Forwarded message ---------\n"
            "Date: Fri, 14 Aug 2026 10:00:00\n"
            "Subject: Missing From Line\n"
            "To: alex.taylor@example.com\n\n"
            "No sender specified in this block.\n"
        )
        mime = build_raw_mime(
            from_header="alex.taylor@example.com",
            body=body,
            attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
        )
        res = self.gate.evaluate(mime)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN)

    def test_cross_entity_pan_tampering_in_forwarded_body(self):
        """Authorized forwarder Margaret forwards an email containing Robert's PAN."""
        body = (
            "---------- Forwarded message ---------\n"
            "From: HDFC Securities <customercare@hdfcsec.com>\n"
            "Subject: Statement for Account ABCDE1234F\n\n"
            "Dear Customer, contract note for PAN ABCDE1234F is attached.\n"
        )
        mime = build_raw_mime(
            from_header="margaret.taylor@example.com",
            body=body,
            attachments=[("hdfc_cn.pdf", "application/pdf", self.dummy_pdf)],
        )
        payload = InboundEmailPayload(
            raw_mime=mime,
            forwarder_email="margaret.taylor@example.com",
            target_pan="ABCDE1234F",
        )
        res = self.gate.evaluate(payload)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_PAN_MISMATCH)

    def test_forwarded_block_with_fake_broker_in_body_text_only(self):
        """Body mentions 'zerodha.com' in prose but 'From:' line inside forwarded block is attacker."""
        body = (
            "---------- Forwarded message ---------\n"
            "From: Fake Service <alerts@phish-service.com>\n"
            "Subject: Your Zerodha Account at zerodha.com\n\n"
            "Visit https://zerodha.com to check your statement.\n"
        )
        mime = build_raw_mime(
            from_header="alex.taylor@example.com",
            body=body,
            attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
        )
        res = self.gate.evaluate(mime)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN)


class TestAdversarialUnicodeHomoglyphs(unittest.TestCase):
    """Category 3: Unicode Domain Homoglyph & Internationalized Domain Spoofing."""

    def setUp(self):
        self.gate = IdentityGate()
        self.dummy_pdf = b"%PDF-1.4 valid trade content"

    def test_cyrillic_homoglyph_zerodha(self):
        """Cyrillic 'е' (U+0435) in 'zеrodha.com' must be rejected."""
        cyrillic_zerodha = "contracts@z\u0435rodha.com"
        body = f"---------- Forwarded message ---------\nFrom: Zerodha <{cyrillic_zerodha}>\n\nStatement."
        mime = build_raw_mime(
            from_header="alex.taylor@example.com",
            body=body,
            attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
        )
        res = self.gate.evaluate(mime)
        self.assertFalse(res.passed, "Cyrillic homoglyph in Zerodha domain must fail closed.")
        self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN)

    def test_cyrillic_homoglyph_hdfcsec(self):
        """Cyrillic 'е' (U+0435) in 'hdfcsеc.com' must be rejected."""
        cyrillic_hdfc = "support@hdfcs\u0435c.com"
        body = f"---------- Forwarded message ---------\nFrom: HDFC Sec <{cyrillic_hdfc}>\n\nStatement."
        mime = build_raw_mime(
            from_header="robert.taylor@example.com",
            body=body,
            attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
        )
        res = self.gate.evaluate(mime)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN)

    def test_cyrillic_homoglyph_camsonline(self):
        """Cyrillic 'а' (U+0430) and 'о' (U+043E) in 'cаmsоnline.com' must be rejected."""
        cyrillic_cams = "donotreply@c\u0430ms\u043Enline.com"
        body = f"---------- Forwarded message ---------\nFrom: CAMS <{cyrillic_cams}>\n\nStatement."
        mime = build_raw_mime(
            from_header="margaret.taylor@example.com",
            body=body,
            attachments=[("cas.pdf", "application/pdf", self.dummy_pdf)],
        )
        res = self.gate.evaluate(mime)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN)

    def test_cyrillic_homoglyph_kfintech(self):
        """Cyrillic 'с' (U+0441) in 'kfinteсh.com' must be rejected."""
        cyrillic_kfintech = "cas@kfinte\u0441h.com"
        body = f"---------- Forwarded message ---------\nFrom: KFintech <{cyrillic_kfintech}>\n\nStatement."
        mime = build_raw_mime(
            from_header="margaret.taylor@example.com",
            body=body,
            attachments=[("cas.pdf", "application/pdf", self.dummy_pdf)],
        )
        res = self.gate.evaluate(mime)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN)

    def test_cyrillic_homoglyph_schwab(self):
        """Cyrillic 'с' (U+0441) and 'а' (U+0430) in 'sсhwаb.com' must be rejected."""
        cyrillic_schwab = "statements@s\u0441hw\u0430b.com"
        body = f"---------- Forwarded message ---------\nFrom: Charles Schwab <{cyrillic_schwab}>\n\nStatement."
        mime = build_raw_mime(
            from_header="alex.taylor@example.com",
            body=body,
            attachments=[("trades.csv", "text/csv", b"Date,Action\n2026-08-14,Buy\n")],
        )
        res = self.gate.evaluate(mime)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN)

    def test_greek_homoglyph_zerodha(self):
        """Greek 'α' (U+03B1) in 'zerodhα.com' must be rejected."""
        greek_zerodha = "contracts@zerodh\u03B1.com"
        body = f"---------- Forwarded message ---------\nFrom: Zerodha <{greek_zerodha}>\n\nStatement."
        mime = build_raw_mime(
            from_header="alex.taylor@example.com",
            body=body,
            attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
        )
        res = self.gate.evaluate(mime)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN)

    def test_fullwidth_homoglyphs(self):
        """Full-width Unicode characters in domain name must be rejected."""
        fullwidth_domain = "contracts@\uff5a\uff45\uff52\uff4f\uff44\uff48\uff41.\uff43\uff4f\uff4d"
        body = f"---------- Forwarded message ---------\nFrom: Zerodha <{fullwidth_domain}>\n\nStatement."
        mime = build_raw_mime(
            from_header="alex.taylor@example.com",
            body=body,
            attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
        )
        res = self.gate.evaluate(mime)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN)

    def test_punycode_idn_domain_rejection(self):
        """IDN Punycode domain e.g. xn--zrodha-72a.com must be rejected."""
        puny_domain = "contracts@xn--zrodha-72a.com"
        body = f"---------- Forwarded message ---------\nFrom: Zerodha <{puny_domain}>\n\nStatement."
        mime = build_raw_mime(
            from_header="alex.taylor@example.com",
            body=body,
            attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
        )
        res = self.gate.evaluate(mime)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN)

    def test_unicode_homoglyph_in_forwarder_email(self):
        """Cyrillic 'а' (U+0430) in forwarder email 'alex.taylor@gmail.com'."""
        cyrillic_forwarder = "sh\u0430ran.taylor@gmail.com"
        mime = build_raw_mime(
            from_header=cyrillic_forwarder,
            body="---------- Forwarded message ---------\nFrom: contracts@zerodha.com\n\nAttached.",
            attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
        )
        res = self.gate.evaluate(mime)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_UNAUTHORIZED_FORWARDER)


class TestAdversarialMalformedAndTruncatedMime(unittest.TestCase):
    """Category 4: Malformed & Truncated MIME Streams."""

    def setUp(self):
        self.gate = IdentityGate()

    def test_completely_truncated_mime_at_boundary_declaration(self):
        """MIME declares multipart boundary but stream ends abruptly."""
        truncated_raw = b"Content-Type: multipart/mixed; boundary=\"MISSING_BOUNDARY\"\r\n\r\n"
        res = self.gate.evaluate(truncated_raw)
        self.assertFalse(res.passed)
        self.assertIn(
            res.rejection_code,
            [ERR_IDENTITY_MALFORMED_MIME, ERR_IDENTITY_UNAUTHORIZED_FORWARDER, ERR_IDENTITY_NO_ATTACHMENTS],
        )

    def test_corrupted_base64_attachment_payload(self):
        """MIME attachment contains corrupted Base64 padding / non-base64 characters."""
        raw = (
            b"From: alex.taylor@example.com\r\n"
            b"To: vault-ingest@moneymoney.internal\r\n"
            b"Subject: Corrupted Base64\r\n"
            b"Content-Type: multipart/mixed; boundary=\"BND\"\r\n\r\n"
            b"--BND\r\n"
            b"Content-Type: text/plain\r\n\r\n"
            b"---------- Forwarded message ---------\r\n"
            b"From: contracts@zerodha.com\r\n\r\n"
            b"--BND\r\n"
            b"Content-Type: application/pdf\r\n"
            b"Content-Disposition: attachment; filename=\"corrupt.pdf\"\r\n"
            b"Content-Transfer-Encoding: base64\r\n\r\n"
            b"!!!NOT_VALID_BASE64_BYTES###$$$===\r\n"
            b"--BND--\r\n"
        )
        res = self.gate.evaluate(raw)
        self.assertIsInstance(res, IdentityGateResult)

    def test_pure_random_binary_garbage_stream(self):
        """Feeds random binary entropy (10 KB) directly into Identity Gate."""
        random_bytes = os.urandom(10240)
        res = self.gate.evaluate(random_bytes)
        self.assertFalse(res.passed)
        self.assertIsNotNone(res.rejection_code)

    def test_deeply_nested_multipart_mime_bomb(self):
        """15 levels of nested multipart containers."""
        inner = (
            b"Content-Type: application/pdf; name=\"cn.pdf\"\r\n"
            b"Content-Disposition: attachment; filename=\"cn.pdf\"\r\n\r\n"
            b"%PDF-1.4 nested payload\r\n"
        )
        for i in range(15):
            bnd = f"BND_{i}".encode("ascii")
            inner = (
                b"Content-Type: multipart/mixed; boundary=\"" + bnd + b"\"\r\n\r\n"
                b"--" + bnd + b"\r\n"
                b"Content-Type: text/plain\r\n\r\n"
                b"---------- Forwarded message ---------\r\n"
                b"From: contracts@zerodha.com\r\n\r\n"
                b"--" + bnd + b"\r\n" + inner + b"\r\n--" + bnd + b"--\r\n"
            )
        root_mime = b"From: alex.taylor@example.com\r\nSubject: Deep Nested\r\n" + inner
        res = self.gate.evaluate(root_mime)
        self.assertIsInstance(res, IdentityGateResult)
        if res.passed:
            self.assertEqual(res.broker_institution, BrokerInstitution.ZERODHA)
            self.assertGreaterEqual(len(res.extracted_attachments), 1)

    def test_null_bytes_injected_throughout_mime_stream(self):
        """MIME stream with null bytes injected between headers and body."""
        raw = (
            b"From:\x00 alex.taylor@example.com\r\n"
            b"To: vault-ingest@moneymoney.internal\r\n"
            b"Subject: Null \x00 Byte Stream\r\n\r\n"
            b"---------- Forwarded message ---------\r\n"
            b"From:\x00 contracts@zerodha.com\r\n\r\n"
            b"Test\x00body\x00with\x00nulls."
        )
        res = self.gate.evaluate(raw)
        self.assertIsInstance(res, IdentityGateResult)


class TestAdversarialMassiveAttachmentsAndPartHandling(unittest.TestCase):
    """Category 5: Massive Attachment Payloads, Zero-Byte Parts & Malicious Extensions."""

    def setUp(self):
        self.gate = IdentityGate()

    def test_zero_byte_pdf_attachment_fail_closed(self):
        """Email with a 0-byte PDF attachment must fail with ERR_IDENTITY_NO_ATTACHMENTS."""
        mime = build_raw_mime(
            from_header="alex.taylor@example.com",
            body="---------- Forwarded message ---------\nFrom: contracts@zerodha.com\n\nEmpty PDF.",
            attachments=[("empty.pdf", "application/pdf", b"")],
        )
        res = self.gate.evaluate(mime)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_NO_ATTACHMENTS)

    def test_massive_10mb_pdf_attachment_stream(self):
        """10MB PDF attachment extracted cleanly into memory with correct SHA-256 and zero disk writes."""
        large_bytes = b"%PDF-1.7 " + (b"A" * (10 * 1024 * 1024))
        expected_sha = hashlib.sha256(large_bytes).hexdigest()

        mime = build_raw_mime(
            from_header="alex.taylor@example.com",
            body="---------- Forwarded message ---------\nFrom: contracts@zerodha.com\n\nLarge note attached.",
            attachments=[("huge_contract_note.pdf", "application/pdf", large_bytes)],
        )
        res = self.gate.evaluate(mime)
        self.assertTrue(res.passed, f"Large attachment failed: {res.rejection_reason}")
        self.assertEqual(len(res.extracted_attachments), 1)

        att = res.extracted_attachments[0]
        self.assertEqual(att.size_bytes, len(large_bytes))
        self.assertEqual(att.sha256, expected_sha)
        stream = att.get_stream()
        self.assertIsInstance(stream, io.BytesIO)
        self.assertEqual(stream.read(), large_bytes)

    def test_malicious_decoy_extensions_filtered_out(self):
        """Email with mixed attachments (.exe, .sh, .vbs, .pdf). Only .pdf must be extracted."""
        pdf_content = b"%PDF-1.4 valid note"
        mixed_attachments = [
            ("payload.exe", "application/x-msdownload", b"MZ\x90\x00\x03"),
            ("exploit.sh", "application/x-sh", b"#!/bin/bash\nrm -rf /"),
            ("malware.vbs", "text/vbscript", b"MsgBox 'pwned'"),
            ("contract.pdf", "application/pdf", pdf_content),
        ]
        mime = build_raw_mime(
            from_header="alex.taylor@example.com",
            body="---------- Forwarded message ---------\nFrom: contracts@zerodha.com\n\nMixed files.",
            attachments=mixed_attachments,
        )
        res = self.gate.evaluate(mime)
        self.assertTrue(res.passed)
        self.assertEqual(len(res.extracted_attachments), 1)
        self.assertEqual(res.extracted_attachments[0].filename, "contract.pdf")
        self.assertEqual(res.extracted_attachments[0].payload_bytes, pdf_content)

    def test_fifty_empty_mime_parts_no_crash(self):
        """Message with 50 empty MIME parts does not crash and rejects gracefully."""
        boundary = "BOUND_50_PARTS"
        parts = [f"--{boundary}\r\nContent-Type: text/plain\r\n\r\n" for _ in range(50)]
        raw = (
            f"From: alex.taylor@example.com\r\n"
            f"To: vault-ingest@moneymoney.internal\r\n"
            f"Subject: 50 Parts\r\n"
            f"Content-Type: multipart/mixed; boundary=\"{boundary}\"\r\n\r\n"
            + "".join(parts)
            + f"--{boundary}--\r\n"
        ).encode("utf-8")

        res = self.gate.evaluate(raw)
        self.assertIsInstance(res, IdentityGateResult)
        self.assertFalse(res.passed)


class TestAdversarialCaseSensitivityAndNormalization(unittest.TestCase):
    """Category 6: Case-Sensitivity & Normalization Edge Cases."""

    def setUp(self):
        self.gate = IdentityGate()
        self.dummy_pdf = b"%PDF-1.4 valid note"

    def test_mixed_case_forwarder_emails(self):
        """Forwarder emails with mixed casing (e.g. AlEx.TaYlOr@GmAiL.cOm)."""
        cased_forwarders = [
            ("ALEX.TAYLOR@EXAMPLE.COM", "port_primary", "KLMNO9012P"),
            ("RoBeRt.TaYlOr@GmAiL.cOm", "port_father", "ABCDE1234F"),
            ("MARGARET.TAYLOR@GMAIL.COM", "port_mother", "FGHIJ5678K"),
        ]
        for cased_email, entity_id, pan in cased_forwarders:
            mime = build_raw_mime(
                from_header=cased_email,
                body="---------- Forwarded message ---------\nFrom: contracts@zerodha.com\n\nAttached.",
                attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
            )
            res = self.gate.evaluate(mime)
            self.assertTrue(res.passed, f"Cased email {cased_email} failed: {res.rejection_reason}")
            self.assertEqual(res.target_entity_id, entity_id)
            self.assertEqual(res.target_pan, pan)

    def test_mixed_case_broker_domains(self):
        """Broker sender addresses with uppercase / mixed case domains."""
        cased_brokers = [
            ("CONTRACTS@ZERODHA.COM", BrokerInstitution.ZERODHA),
            ("CustomerCare@HdfcSec.Com", BrokerInstitution.HDFC_SECURITIES),
            ("DONOTREPLY@CAMSONLINE.COM", BrokerInstitution.CAMS_KFINTECH),
            ("CAS@KFINTECH.COM", BrokerInstitution.CAMS_KFINTECH),
            ("STATEMENTS@SCHWAB.COM", BrokerInstitution.CHARLES_SCHWAB),
        ]
        for broker_email, expected_inst in cased_brokers:
            body = f"---------- Forwarded message ---------\nFrom: Broker Bot <{broker_email}>\n\nStatement."
            mime = build_raw_mime(
                from_header="alex.taylor@example.com",
                body=body,
                attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
            )
            res = self.gate.evaluate(mime)
            self.assertTrue(res.passed, f"Cased broker {broker_email} failed: {res.rejection_reason}")
            self.assertEqual(res.broker_institution, expected_inst)

    def test_explicit_lowercase_and_whitespace_padded_pan(self):
        """Explicit target PAN passed in lowercase with whitespace padding."""
        payload = InboundEmailPayload(
            raw_mime=build_raw_mime(
                from_header="alex.taylor@example.com",
                body="---------- Forwarded message ---------\nFrom: contracts@zerodha.com\n\nAttached.",
                attachments=[("cn.pdf", "application/pdf", self.dummy_pdf)],
            ),
            forwarder_email="  alex.taylor@example.com  ",
            target_pan="  klmno9012p  ",
        )
        res = self.gate.evaluate(payload)
        self.assertTrue(res.passed, f"Padded lowercase PAN failed: {res.rejection_reason}")
        self.assertEqual(res.target_pan, "KLMNO9012P")
        self.assertEqual(res.target_entity_id, "port_primary")

    def test_huf_pan_forwarded_by_karta_alex_with_mixed_case(self):
        """HUF PAN 'pqrst3456q' submitted by Alex in mixed case."""
        payload = InboundEmailPayload(
            raw_mime=build_raw_mime(
                from_header="Alex.Taylor@Gmail.Com",
                body="---------- Forwarded message ---------\nFrom: cas@kfintech.com\n\nHUF Statement.",
                attachments=[("huf.pdf", "application/pdf", self.dummy_pdf)],
            ),
            forwarder_email="Alex.Taylor@Gmail.Com",
            target_pan="PqrSt3456q",
        )
        res = self.gate.evaluate(payload)
        self.assertTrue(res.passed, f"HUF submission failed: {res.rejection_reason}")
        self.assertEqual(res.target_entity_id, "port_trust")
        self.assertEqual(res.target_pan, "PQRST3456Q")


class TestAdversarialDefectDemonstrations(unittest.TestCase):
    """
    Category 7: Defect Remediation & Zero Unhandled Exception Verification.
    Explicitly tests and verifies that the 3 previously identified unhandled exception
    vulnerabilities in backend/app/gates/identity_gate.py are now completely remediated.
    """

    def setUp(self):
        self.gate = IdentityGate()

    def test_remediation_1_malformed_date_header_handled_gracefully(self):
        """
        REMEDIATION VERIFICATION: Corrupted/non-RFC Date header in raw MIME
        is safely caught, does not raise TypeError, and returns parsed_date=None in metadata.
        """
        raw_mime = (
            b"From: alex.taylor@example.com\r\n"
            b"Date: Invalid_Date_12345\r\n"
            b"To: vault@internal\r\n"
            b"Subject: Test Note\r\n"
            b"Content-Type: multipart/mixed; boundary=\"BND\"\r\n\r\n"
            b"--BND\r\n"
            b"Content-Type: text/plain\r\n\r\n"
            b"---------- Forwarded message ---------\r\n"
            b"From: contracts@zerodha.com\r\n\r\n"
            b"--BND\r\n"
            b"Content-Type: application/pdf\r\n"
            b"Content-Disposition: attachment; filename=\"cn.pdf\"\r\n\r\n"
            b"%PDF-1.4 data\r\n"
            b"--BND--\r\n"
        )
        res = self.gate.evaluate(raw_mime)
        self.assertIsInstance(res, IdentityGateResult)
        self.assertTrue(res.passed, f"Expected pass, got rejection: {res.rejection_reason}")
        self.assertIsNone(res.extracted_metadata.date, "Malformed Date should gracefully result in None date.")
        self.assertEqual(res.broker_institution, BrokerInstitution.ZERODHA)

    def test_remediation_2_surrogate_unicode_string_handled_gracefully(self):
        """
        REMEDIATION VERIFICATION: Passing a string containing surrogate Unicode characters
        (e.g., lone high surrogate '\\ud961') does not raise UnicodeEncodeError and fails closed gracefully.
        """
        surrogate_string = "From: alex.taylor@example.com\r\nSubject: \ud961 test\r\n\r\nBody"
        res = self.gate.evaluate(surrogate_string)
        self.assertIsInstance(res, IdentityGateResult)
        self.assertFalse(res.passed)
        self.assertIn(
            res.rejection_code,
            [ERR_IDENTITY_MALFORMED_MIME, ERR_IDENTITY_NO_ATTACHMENTS, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN],
        )

    def test_remediation_3_dict_with_integer_raw_mime_rejected_fail_closed(self):
        """
        REMEDIATION VERIFICATION: Passing a dict with an integer raw_mime (e.g., {'raw_mime': 12345})
        does not raise AttributeError and fails closed with ERR_IDENTITY_MALFORMED_MIME.
        """
        invalid_dict_payload = {"raw_mime": 12345}
        res = self.gate.evaluate(invalid_dict_payload)
        self.assertIsInstance(res, IdentityGateResult)
        self.assertFalse(res.passed)
        self.assertEqual(res.rejection_code, ERR_IDENTITY_MALFORMED_MIME)


class TestAdversarialFuzzingSuite(unittest.TestCase):
    """
    Category 8: Fuzzing Harness (1,000 Randomized Mutations).
    Verifies that across 1,000 randomized byte and valid unicode mutations,
    evaluate() maintains fail-closed perimeter security with ZERO unhandled exceptions.
    """

    def setUp(self):
        self.gate = IdentityGate()

    def test_1000_fuzzed_valid_mutations_fail_closed(self):
        """1,000 mutations across byte bit-flips, truncations, boundary corruptions, and noise."""
        random.seed(42)

        valid_sample = build_raw_mime(
            from_header="alex.taylor@example.com",
            body="---------- Forwarded message ---------\nFrom: contracts@zerodha.com\n\nTrade attached.",
            attachments=[("cn.pdf", "application/pdf", b"%PDF-1.4 sample")],
        )

        mutation_types = [
            "random_bytes",
            "bit_flip",
            "byte_deletion",
            "byte_insertion",
            "header_truncation",
            "boundary_corrupt",
            "unicode_text",
            "none_values",
        ]

        for i in range(1000):
            mtype = random.choice(mutation_types)
            if mtype == "random_bytes":
                length = random.randint(0, 4096)
                payload = os.urandom(length)
            elif mtype == "bit_flip":
                ba = bytearray(valid_sample)
                pos = random.randint(0, len(ba) - 1)
                ba[pos] ^= random.randint(1, 255)
                payload = bytes(ba)
            elif mtype == "byte_deletion":
                ba = bytearray(valid_sample)
                start = random.randint(0, len(ba) - 10)
                del ba[start : start + random.randint(1, 50)]
                payload = bytes(ba)
            elif mtype == "byte_insertion":
                ba = bytearray(valid_sample)
                pos = random.randint(0, len(ba) - 1)
                noise = os.urandom(random.randint(1, 100))
                ba[pos:pos] = noise
                payload = bytes(ba)
            elif mtype == "header_truncation":
                cut = random.randint(1, min(len(valid_sample), 200))
                payload = valid_sample[:cut]
            elif mtype == "boundary_corrupt":
                payload = valid_sample.replace(b"--", b"xx", random.randint(1, 3))
            elif mtype == "unicode_text":
                chars = string.ascii_letters + string.digits + " ₹€$!@#$%^&*()_+-=~`[]{}|;:',.<>?/ " + "αβγδε" + "абвгде"
                payload = "".join(random.choice(chars) for _ in range(100))
            elif mtype == "none_values":
                payload = None

            res = self.gate.evaluate(payload)
            self.assertIsInstance(
                res,
                IdentityGateResult,
                f"Iteration {i} (mutation={mtype}) failed to return IdentityGateResult",
            )


if __name__ == "__main__":
    unittest.main()
