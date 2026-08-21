"""
Empirical Challenger Milestone 1 Iteration 2 Deep Stress & Fuzzing Suite
Target: backend/app/gates/identity_gate.py
Validates:
1. 3 Remediated Defect Vectors (Corrupt Date, Lone Surrogates, Non-bytes raw_mime) across deep permutations
2. Extreme Edge Case Fuzzing (2,500+ iterations: random bytes, malformed MIME, type variations, nested structures)
3. 100% Fail-Closed Perimeter Assurance & Zero Unhandled Exceptions
"""

import email
import email.message
import email.policy
import os
import random
import string
import sys
import unittest
from typing import Any, List, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.config import (
    ERR_IDENTITY_MALFORMED_MIME,
    ERR_IDENTITY_NO_ATTACHMENTS,
    ERR_IDENTITY_PAN_MISMATCH,
    ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN,
    ERR_IDENTITY_UNAUTHORIZED_FORWARDER,
    ERR_IDENTITY_UNRESOLVED_ENTITY,
    BrokerInstitution,
)
from backend.app.gates.identity_gate import IdentityGate, evaluate_identity_gate
from backend.app.models.email import (
    ExtractedAttachment,
    ExtractedEmailMetadata,
    IdentityGateResult,
    InboundEmailPayload,
)


def create_raw_mime_with_custom_header(
    from_addr: str = "alex.taylor@example.com",
    broker_addr: str = "contracts@zerodha.com",
    subject: str = "Contract Note for 14-Aug-2026",
    date_header_line: str = "Date: Fri, 14 Aug 2026 12:00:00 +0530",
    attachment_filename: str = "CN_AUG2026.pdf",
    attachment_content: bytes = b"%PDF-1.4 sample contract note binary content",
) -> bytes:
    boundary = "================_BOUNDARY_12345_=="
    raw = (
        f"From: {from_addr}\r\n"
        f"To: vault-ingest@moneymoney.internal\r\n"
        f"Subject: {subject}\r\n"
        f"{date_header_line}\r\n"
        f"Message-ID: <msg-iter2-test@moneymoney.internal>\r\n"
        f"Content-Type: multipart/mixed; boundary=\"{boundary}\"\r\n\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: text/plain; charset=\"utf-8\"\r\n\r\n"
        f"---------- Forwarded message ---------\r\n"
        f"From: Zerodha <{broker_addr}>\r\n"
        f"Subject: Contract Note\r\n\r\n"
        f"Attached.\r\n\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: application/pdf; name=\"{attachment_filename}\"\r\n"
        f"Content-Disposition: attachment; filename=\"{attachment_filename}\"\r\n\r\n"
    ).encode("utf-8") + attachment_content + f"\r\n--{boundary}--\r\n".encode("utf-8")
    return raw


class TestEmpiricalDefectPermutations(unittest.TestCase):
    """Deep empirical testing of the 3 remediated defect vectors."""

    def setUp(self):
        self.gate = IdentityGate()

    def test_defect_1_deep_corrupt_date_header_permutations(self):
        """Test numerous corrupt/non-RFC Date headers to confirm zero TypeErrors and graceful handling."""
        unparseable_date_lines = [
            "Date: Invalid_Date_12345",
            "Date: None",
            "Date: -1",
            "Date: 999999999999999999999999",
            "Date: Fri, 32 Aug 2026 25:61:99 +9999",
            "Date: Yesterday at 5pm",
            "Date: 14-08-2026 12:00:00",
            "Date: Wed, 29 Feb 2025 12:00:00 +0530",  # Non-leap year invalid Feb 29
            "Date: 0",
            "Date: ",
            "Date: !!@#$%^&*()",
            "Date: \x00\x01\x02",
            "Date: Inception",
            "Date: Mon, 00 Jan 2000 00:00:00 GMT",
        ]
        for date_line in unparseable_date_lines:
            raw = create_raw_mime_with_custom_header(date_header_line=date_line)
            res = self.gate.evaluate(raw)
            self.assertIsInstance(res, IdentityGateResult, f"Failed on date line: {date_line}")
            self.assertTrue(res.passed, f"Valid email with corrupt date should pass Gate 1, failed on '{date_line}': {res.rejection_reason}")
            self.assertEqual(res.broker_institution, BrokerInstitution.ZERODHA)
            self.assertIsNone(res.extracted_metadata.date, f"Date should be None for unparseable date '{date_line}'")

    def test_defect_2_deep_surrogate_unicode_string_permutations(self):
        """Test strings containing various high/low/paired surrogate unicode characters."""
        surrogate_samples = [
            "From: alex.taylor@example.com\r\nSubject: \ud961 test\r\n\r\nBody",
            "From: alex.taylor@example.com\r\nSubject: \ud800\udfff test\r\n\r\nBody",
            "From: alex.taylor@example.com\r\nSubject: \udc00 test\r\n\r\nBody",
            "From: alex.taylor@example.com\r\nSubject: " + "".join(chr(c) for c in range(0xD800, 0xD850)) + "\r\n\r\nBody",
            {"raw_mime": "From: alex.taylor@example.com\r\nSubject: \ud961 in dict\r\n\r\nBody"},
            {"raw_mime": "From: alex.taylor@example.com\r\nSubject: \ud83d\ude00\ud961 mix\r\n\r\nBody"},
        ]
        for sample in surrogate_samples:
            res = self.gate.evaluate(sample)
            self.assertIsInstance(res, IdentityGateResult)
            # Evaluates fail-closed without crashing
            self.assertFalse(res.passed)
            self.assertIn(
                res.rejection_code,
                [ERR_IDENTITY_MALFORMED_MIME, ERR_IDENTITY_NO_ATTACHMENTS, ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN],
            )

    def test_defect_3_deep_non_bytes_payload_types(self):
        """Test various invalid and non-bytes payload types in dict, object, and direct arguments."""
        invalid_types: List[Any] = [
            {"raw_mime": 12345},
            {"raw_mime": 12.345},
            {"raw_mime": True},
            {"raw_mime": False},
            {"raw_mime": [b"list", b"of", b"bytes"]},
            {"raw_mime": {"nested": "dict"}},
            {"raw_mime": object()},
            {"raw_mime": lambda x: x},
            12345,
            12.345,
            True,
            False,
            [b"some_bytes"],
            (b"tuple_bytes",),
            set([1, 2, 3]),
            object(),
            lambda: None,
            None,
            InboundEmailPayload(raw_mime=12345),  # type: ignore
            InboundEmailPayload(raw_mime=None),   # type: ignore
            InboundEmailPayload(raw_mime={"bad": "type"}),  # type: ignore
        ]
        for invalid_input in invalid_types:
            res = self.gate.evaluate(invalid_input)
            self.assertIsInstance(res, IdentityGateResult, f"Failed on type {type(invalid_input)}")
            self.assertFalse(res.passed, f"Invalid type {type(invalid_input)} must fail closed")
            self.assertEqual(res.rejection_code, ERR_IDENTITY_MALFORMED_MIME)


class TestEmpiricalDeepFuzzer(unittest.TestCase):
    """Category 2: 2,500+ Iteration Deep Fuzzer."""

    def setUp(self):
        self.gate = IdentityGate()

    def test_2500_deep_fuzzing_iterations(self):
        """Runs 2,500 fuzzed payloads across 12 mutation strategies."""
        random.seed(1337)
        base_sample = create_raw_mime_with_custom_header()

        strategies = [
            "raw_random_bytes",
            "bit_flip",
            "byte_shuffle",
            "boundary_mangle",
            "header_mangle",
            "unicode_noise",
            "surrogate_noise",
            "null_byte_injection",
            "crlf_flood",
            "truncated_prefixes",
            "dict_mutation",
            "object_mutation",
        ]

        total_iterations = 2500
        for i in range(total_iterations):
            strat = random.choice(strategies)

            if strat == "raw_random_bytes":
                payload = os.urandom(random.randint(0, 8192))
            elif strat == "bit_flip":
                ba = bytearray(base_sample)
                for _ in range(random.randint(1, 10)):
                    idx = random.randint(0, len(ba) - 1)
                    ba[idx] ^= random.randint(1, 255)
                payload = bytes(ba)
            elif strat == "byte_shuffle":
                ba = bytearray(base_sample)
                start = random.randint(0, len(ba) - 20)
                sub = ba[start : start + 20]
                random.shuffle(sub)
                ba[start : start + 20] = sub
                payload = bytes(ba)
            elif strat == "boundary_mangle":
                payload = base_sample.replace(b"--", os.urandom(2))
            elif strat == "header_mangle":
                headers = [b"From: ", b"To: ", b"Subject: ", b"Date: ", b"Content-Type: "]
                target = random.choice(headers)
                payload = base_sample.replace(target, os.urandom(len(target)))
            elif strat == "unicode_noise":
                chars = (
                    string.ascii_letters
                    + string.digits
                    + " \t\r\n"
                    + "₹€$¥£"
                    + "αβγδεζηθικλμνξοπρστυφχψω"
                    + "абвгдежзийклмнопрстуфхцчшщъыьэюя"
                    + "💥🔥🚀🎉✨💰📈📊"
                )
                payload = "".join(random.choice(chars) for _ in range(random.randint(1, 200)))
            elif strat == "surrogate_noise":
                surrogates = "".join(chr(random.randint(0xD800, 0xDFFF)) for _ in range(20))
                payload = f"From: alex.taylor@example.com\r\nSubject: {surrogates}\r\n\r\nBody"
            elif strat == "null_byte_injection":
                ba = bytearray(base_sample)
                for _ in range(random.randint(1, 20)):
                    idx = random.randint(0, len(ba) - 1)
                    ba[idx] = 0
                payload = bytes(ba)
            elif strat == "crlf_flood":
                payload = b"\r\n" * random.randint(1, 500) + base_sample
            elif strat == "truncated_prefixes":
                length = random.randint(0, len(base_sample))
                payload = base_sample[:length]
            elif strat == "dict_mutation":
                dict_payload = {}
                if random.random() > 0.3:
                    dict_payload["raw_mime"] = random.choice([
                        os.urandom(100),
                        "some string",
                        12345,
                        None,
                        [],
                        {},
                        base_sample,
                    ])
                if random.random() > 0.5:
                    dict_payload["forwarder_email"] = random.choice([
                        "alex.taylor@example.com",
                        "attacker@evil.com",
                        123,
                        None,
                    ])
                if random.random() > 0.5:
                    dict_payload["target_pan"] = random.choice(["KLMNO9012P", "BADPAN123", None, 999])
                payload = dict_payload
            elif strat == "object_mutation":
                payload = InboundEmailPayload(
                    raw_mime=random.choice([base_sample, os.urandom(50), b"", None, 1234]),  # type: ignore
                    forwarder_email=random.choice(["alex.taylor@example.com", None, "bad@evil.com"]),
                    target_pan=random.choice(["KLMNO9012P", None, "INVALID"]),
                )

            # Evaluate through Identity Gate
            res = self.gate.evaluate(payload)
            self.assertIsInstance(
                res,
                IdentityGateResult,
                f"Fuzz iteration {i} (strategy={strat}) failed to return IdentityGateResult",
            )
            # If passed is False, verify valid rejection code and reason
            if not res.passed:
                self.assertIsNotNone(res.rejection_code, f"Failed result must have rejection_code on iter {i}")
                self.assertIsNotNone(res.rejection_reason, f"Failed result must have rejection_reason on iter {i}")


if __name__ == "__main__":
    unittest.main()
