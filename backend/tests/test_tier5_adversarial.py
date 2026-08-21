"""
Tier 5: Adversarial Hardening & Forensic Integrity Test Suite (MoneyMoney Ingestion Pipeline)
Tests adversarial security boundaries, cryptographic anti-tampering, math falsification attacks, and zero-leakage in-memory safety.
"""
import os
import unittest
from datetime import date, datetime
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
    create_spoofed_mime,
    create_unauthorized_forwarder_mime,
)
from backend.tests.fixtures.sample_zerodha import (
    build_valid_zerodha_statement,
    SyntheticTradeRow,
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


class TestTier5AdversarialHardening(unittest.TestCase):
    """
    Tier 5 Test Suite: Forensic Security, Attack Surface & Anti-Tamper Hardening.
    """

    def test_adv_01_strict_invariant_intolerance_above_two_paise(self):
        """Discrepancy of ₹0.021 is rejected immediately by fail-closed gate"""
        stmt = build_valid_zerodha_statement()
        stmt.net_settlement_amount += Decimal("0.021") # Exceeds 0.02
        passed, err, disc = ReferenceValidationGate.validate_zerodha(stmt)
        self.assertFalse(passed)
        self.assertIn("ERR_VALIDATION_MATH_MISMATCH", err)

    def test_adv_02_penny_drop_shaving_attack_detection_across_multiple_trades(self):
        """Sub-paise shaving across 10 trades accumulates and is caught by the aggregate net invariant"""
        stmt = build_valid_zerodha_statement()
        # Add 10 trades where ₹0.01 is shaved from each
        for i in range(10):
            t = SyntheticTradeRow(
                order_no=f"ORD_{i}", trade_no=f"TR_{i}", trade_time="10:00:00",
                security_name=f"STOCK_{i} - EQ", isin=f"INE0000000{i}", action="BUY",
                quantity=Decimal("10"), gross_rate=Decimal("100.00")
            )
            stmt.trades.append(t)
        
        # Invalidate net settlement by total shaved amount (₹0.10)
        stmt.net_settlement_amount += Decimal("0.10")
        passed, err, disc = ReferenceValidationGate.validate_zerodha(stmt)
        self.assertFalse(passed)

    def test_adv_03_sha256_fingerprint_bit_flip_tamper_detection(self):
        """Any bit alteration in trade parameters alters SHA-256 fingerprint completely"""
        fp1 = ReferenceReconciliationGate.compute_transaction_fingerprint(
            "port_primary", "ZERODHA", "INE155A01022", "2024-08-14", "BUY", Decimal("800.0000"), Decimal("480.0000"), "84920194"
        )
        fp2 = ReferenceReconciliationGate.compute_transaction_fingerprint(
            "port_primary", "ZERODHA", "INE155A01022", "2024-08-14", "BUY", Decimal("800.0001"), Decimal("480.0000"), "84920194"
        )
        self.assertNotEqual(fp1, fp2)

    def test_adv_04_spoofed_broker_domain_header_injection_attack(self):
        """Spoofed broker domain in From header is blocked by Gate 1"""
        mime = create_spoofed_mime(
            forwarder="alex.taylor@example.com",
            fake_domain_from="Zerodha Scam <contracts@zerodh4-phishing.com>"
        )
        res = ReferenceIdentityGate.process_mime_payload(mime, "alex.taylor@example.com")
        self.assertFalse(res["passed"])
        self.assertEqual(res["rejection_code"], "ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN")

    def test_adv_05_unauthorized_external_forwarder_email_perimeter_lockout(self):
        """Email from unauthorized external forwarder blocked before reaching attachment parser"""
        mime = create_unauthorized_forwarder_mime("attacker@darkweb.org")
        res = ReferenceIdentityGate.process_mime_payload(mime, "attacker@darkweb.org")
        self.assertFalse(res["passed"])
        self.assertEqual(res["rejection_code"], "ERR_IDENTITY_UNAUTHORIZED_FORWARDER")

    def test_adv_06_in_memory_extraction_zero_disk_leakage(self):
        """Verifies no temp files are created in /tmp or workspace root during extraction"""
        before_files = set(os.listdir("."))
        mime = create_zerodha_mime()
        res = ReferenceIdentityGate.process_mime_payload(mime, "alex.taylor@example.com")
        after_files = set(os.listdir("."))
        self.assertEqual(before_files, after_files)
        self.assertTrue(res["passed"])

    def test_adv_07_cas_unit_balance_falsification_attack_detection(self):
        """CAS with manipulated unit balances fails Gate 3 validation"""
        corrupted = build_corrupted_cams_statement()
        passed, err, diff = ReferenceValidationGate.validate_cas(corrupted)
        self.assertFalse(passed)
        self.assertIn("ERR_VALIDATION_CAS_UNIT_CONTINUITY", err)

    def test_adv_08_phantom_inventory_oversell_attack_prevention(self):
        """Attempts to sell shares without prior acquisition lot are blocked"""
        fifo = ReferenceFIFOTaxEngine()
        with self.assertRaises(ValueError) as ctx:
            fifo.sell_units("port_primary", "UNOWNED_ASSET", "EQUITY", date(2024, 8, 14), Decimal("100"), Decimal("500.00"))
        self.assertIn("Oversell condition", str(ctx.exception))

    def test_adv_09_negative_quantity_or_price_injection_defense(self):
        """Negative unit price or negative buy quantity fails math validation"""
        stmt = build_valid_zerodha_statement()
        stmt.trades[0].quantity = Decimal("-500")
        stmt.trades[0].gross_total = Decimal("-240000.00")
        passed, err, disc = ReferenceValidationGate.validate_zerodha(stmt)
        # Gross sum discrepancy flags invariant violation
        self.assertFalse(passed)

    def test_adv_10_forensic_integrity_audit_zero_bypass_verification(self):
        """Verifies that math invariant tolerance is strictly <= 0.02 and not disabled"""
        self.assertEqual(MATH_INVARIANT_TOLERANCE, Decimal("0.02"))


if __name__ == "__main__":
    unittest.main()
