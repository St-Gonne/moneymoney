"""
Pytest configuration, shared fixtures, reference models and test harness for MoneyMoney Ingestion Pipeline.
"""
import hashlib
import io
import re
import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any, Literal

try:
    import pytest
except ImportError:
    pytest = None

# Reference Invariant Tolerance
MATH_INVARIANT_TOLERANCE = Decimal("0.02")

from backend.tests.fixtures.sample_family_vault import (
    AUTHORIZED_FORWARDERS,
    AUTHORIZED_BROKER_DOMAINS,
    FAMILY_VAULT_PROFILES,
    PAN_TO_PROFILE,
    EMAIL_TO_PROFILE,
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
    create_spoofed_mime,
    create_unauthorized_forwarder_mime,
)
from backend.tests.fixtures.sample_zerodha import (
    build_valid_zerodha_statement,
    build_corrupted_math_zerodha_statement,
    SyntheticZerodhaStatement,
)
from backend.tests.fixtures.sample_hdfc import (
    build_valid_hdfc_statement,
    SyntheticHDFCStatement,
)
from backend.tests.fixtures.sample_cas import (
    build_valid_cams_statement,
    build_corrupted_cams_statement,
    SyntheticCasStatement,
)
from backend.tests.fixtures.sample_schwab import (
    build_valid_schwab_statement,
    build_corrupted_schwab_statement,
    SyntheticSchwabStatement,
)

# ==============================================================================
# REFERENCE IMPLEMENTATION CONTRACTS & PIPELINE SIMULATION (OPAQUE BOX ORACLE)
# ==============================================================================

class ReferenceIdentityGate:
    """
    Authoritative reference implementation of Gate 1: Identity Gate.
    Verifies forwarder email, parses RFC 822 MIME headers, matches broker domain,
    extracts attachments in-memory, and resolves target family profile.
    """
    @staticmethod
    def process_mime_payload(raw_mime: bytes, forwarder_email: str) -> Dict[str, Any]:
        # 1. Forwarder Whitelist Check
        if forwarder_email not in AUTHORIZED_FORWARDERS:
            return {
                "passed": False,
                "rejection_code": "ERR_IDENTITY_UNAUTHORIZED_FORWARDER",
                "rejection_reason": f"Forwarder {forwarder_email} is not in authorized family whitelist",
                "target_entity_id": None,
                "target_pan": None,
                "broker_institution": None,
                "extracted_attachments": []
            }

        # 2. Parse RFC 822 MIME email
        import email
        from email.policy import default as default_policy
        try:
            msg = email.message_from_bytes(raw_mime, policy=default_policy)
        except Exception as e:
            return {
                "passed": False,
                "rejection_code": "ERR_IDENTITY_MIME_CORRUPT",
                "rejection_reason": f"Failed to parse MIME payload: {str(e)}",
                "target_entity_id": None,
                "target_pan": None,
                "broker_institution": None,
                "extracted_attachments": []
            }

        # 3. Extract original sender from headers or forwarded message block
        body_text = ""
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    body_text += part.get_content()
                except Exception:
                    pass

        # Look for From: in headers or forwarded block
        original_sender = msg.get("From", "")
        broker_domain = None
        
        # Regex search for all forwarded sender lines
        fwd_matches = re.findall(r"From:\s*([^\n\r]+)", body_text, re.IGNORECASE)
        candidate_senders = list(fwd_matches)
        if original_sender:
            candidate_senders.append(original_sender)

        matched_broker = None
        for sender_str in candidate_senders:
            clean_s = sender_str.lower()
            for domain in AUTHORIZED_BROKER_DOMAINS:
                d_suffix = domain.lstrip("@").lower()
                if d_suffix in clean_s:
                    broker_domain = domain
                    if "zerodha" in d_suffix:
                        matched_broker = "ZERODHA"
                    elif "hdfc" in d_suffix:
                        matched_broker = "HDFC_SECURITIES"
                    elif "cams" in d_suffix:
                        matched_broker = "CAMS_KFINTECH"
                    elif "kfin" in d_suffix:
                        matched_broker = "CAMS_KFINTECH"
                    elif "schwab" in d_suffix:
                        matched_broker = "CHARLES_SCHWAB"
                    break
            if matched_broker:
                break

        if not matched_broker:
            return {
                "passed": False,
                "rejection_code": "ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN",
                "rejection_reason": "Original sender domain not recognized in broker whitelist",
                "target_entity_id": None,
                "target_pan": None,
                "broker_institution": None,
                "extracted_attachments": []
            }

        # 4. Extract attachments in memory
        extracted_attachments = []
        for part in msg.walk():
            content_disposition = part.get("Content-Disposition", "")
            if "attachment" in content_disposition or part.get_filename():
                filename = part.get_filename() or "attachment.bin"
                payload_bytes = part.get_payload(decode=True)
                if payload_bytes:
                    extracted_attachments.append({
                        "filename": filename,
                        "content_bytes": payload_bytes,
                        "size_bytes": len(payload_bytes),
                        "content_type": part.get_content_type()
                    })

        if not extracted_attachments:
            return {
                "passed": False,
                "rejection_code": "ERR_IDENTITY_NO_ATTACHMENTS",
                "rejection_reason": "No attachments found in email payload",
                "target_entity_id": None,
                "target_pan": None,
                "broker_institution": matched_broker,
                "extracted_attachments": []
            }

        # 5. Resolve target family profile
        profile = EMAIL_TO_PROFILE.get(forwarder_email)
        target_entity_id = profile.portfolio_id if profile else "port_primary"
        target_pan = profile.pan if profile else "KLMNO9012P"

        return {
            "passed": True,
            "rejection_code": None,
            "rejection_reason": None,
            "target_entity_id": target_entity_id,
            "target_pan": target_pan,
            "broker_institution": matched_broker,
            "extracted_attachments": extracted_attachments
        }


class ReferenceDecryptionEngine:
    """
    Authoritative reference implementation of Gate 2: Decryption & Layout Gate.
    Attempts candidate password cascade (PAN upper, PAN lower, DOB DDMMYYYY, name+DOB)
    and classifies statement format.
    """
    @staticmethod
    def generate_password_candidates(pan: str, dob: Optional[date] = None, first_name: Optional[str] = None) -> List[str]:
        candidates = []
        if pan:
            candidates.append(pan.upper().strip())
            candidates.append(pan.lower().strip())
        if dob:
            dd = f"{dob.day:02d}"
            mm = f"{dob.month:02d}"
            yyyy = f"{dob.year:04d}"
            yy = f"{dob.year % 100:02d}"
            candidates.append(f"{dd}{mm}{yyyy}")
            candidates.append(f"{dd}-{mm}-{yyyy}")
            candidates.append(f"{dd}/{mm}/{yyyy}")
            candidates.append(f"{dd}{mm}{yy}")
            candidates.append(f"{dd}{mm}")
            if first_name:
                candidates.append(f"{first_name.upper()[:4]}{dd}{mm}")
            if pan and len(pan) >= 4:
                candidates.append(f"{pan.upper()[:4]}{dd}{mm}")
        candidates.append("") # Unencrypted fallback
        seen = set()
        return [c for c in candidates if not (c in seen or seen.add(c))]

    @staticmethod
    def classify_and_decrypt(
        attachment_bytes: bytes,
        filename: str,
        target_pan: str,
        target_dob: Optional[date] = None,
        target_first_name: Optional[str] = None,
        actual_pdf_password: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Sniff layout
        layout_type = None
        lower_fn = filename.lower()
        if lower_fn.endswith(".csv"):
            if "schwab" in lower_fn or b"Action" in attachment_bytes:
                layout_type = "SCHWAB_CSV"
            elif "tradebook" in lower_fn or b"trade_type" in attachment_bytes:
                layout_type = "ZERODHA_CSV"
            else:
                layout_type = "GENERIC_CSV"
        elif lower_fn.endswith(".pdf") or attachment_bytes.startswith(b"%PDF"):
            if b"HDFC" in attachment_bytes or "hdfc" in lower_fn:
                layout_type = "HDFC_PDF"
            elif b"ZERODHA" in attachment_bytes or "zerodha" in lower_fn or lower_fn.startswith("cn_"):
                layout_type = "ZERODHA_PDF"
            elif b"CAMS" in attachment_bytes or "cams" in lower_fn:
                layout_type = "CAMS_CAS_PDF"
            elif b"KFintech" in attachment_bytes or "kfin" in lower_fn:
                layout_type = "KFINTECH_CAS_PDF"
            else:
                layout_type = "GENERIC_PDF"
        else:
            return {
                "passed": False,
                "rejection_code": "ERR_LAYOUT_UNSUPPORTED_FORMAT",
                "rejection_reason": f"Unsupported attachment format: {filename}",
                "layout_type": None,
                "decrypted_bytes": None
            }

        # Decrypt if password required
        passwords = ReferenceDecryptionEngine.generate_password_candidates(
            target_pan, target_dob, target_first_name
        )

        if actual_pdf_password and actual_pdf_password not in passwords:
            return {
                "passed": False,
                "rejection_code": "ERR_LAYOUT_DECRYPTION_FAILED",
                "rejection_reason": "All password cascade attempts failed to decrypt statement PDF",
                "layout_type": layout_type,
                "decrypted_bytes": None
            }

        return {
            "passed": True,
            "rejection_code": None,
            "rejection_reason": None,
            "layout_type": layout_type,
            "decrypted_bytes": attachment_bytes
        }


class ReferenceValidationGate:
    """
    Authoritative reference implementation of Gate 3: Fail-Closed Mathematical Validation Gate.
    Verifies trade totals, tax deductions, GST exactness, and unit balance continuity.
    """
    @staticmethod
    def validate_zerodha(stmt: SyntheticZerodhaStatement) -> Tuple[bool, Optional[str], Decimal]:
        gross_sum = sum(t.gross_total for t in stmt.trades)
        total_charges = (
            stmt.brokerage +
            stmt.stt +
            stmt.exchange_turnover_fee +
            stmt.sebi_turnover_fee +
            stmt.stamp_duty +
            stmt.cgst +
            stmt.sgst +
            stmt.igst
        )

        expected_net = -(gross_sum + total_charges) # For BUY
        discrepancy = abs(expected_net - stmt.net_settlement_amount)

        if discrepancy > MATH_INVARIANT_TOLERANCE:
            return False, f"ERR_VALIDATION_MATH_MISMATCH: Discrepancy {discrepancy} exceeds tolerance {MATH_INVARIANT_TOLERANCE}", discrepancy

        taxable = stmt.brokerage + stmt.exchange_turnover_fee + stmt.sebi_turnover_fee
        expected_gst = (taxable * Decimal("0.18")).quantize(Decimal("0.01"))
        actual_gst = stmt.cgst + stmt.sgst + stmt.igst
        gst_discrepancy = abs(expected_gst - actual_gst)
        if gst_discrepancy > Decimal("0.05"):
            return False, f"ERR_VALIDATION_GST_MISMATCH: GST discrepancy {gst_discrepancy}", gst_discrepancy

        return True, None, Decimal("0.00")

    @staticmethod
    def validate_hdfc(stmt: SyntheticHDFCStatement) -> Tuple[bool, Optional[str], Decimal]:
        gross_sum = sum(t.gross_total for t in stmt.trades)
        total_charges = (
            stmt.total_brokerage +
            stmt.stt +
            stmt.exchange_turnover +
            stmt.sebi_fee +
            stmt.stamp_duty +
            stmt.service_tax_gst +
            stmt.demat_charges
        )
        expected_net = -(gross_sum + total_charges)
        discrepancy = abs(expected_net - stmt.net_amount)
        if discrepancy > MATH_INVARIANT_TOLERANCE:
            return False, f"ERR_VALIDATION_MATH_MISMATCH: Discrepancy {discrepancy}", discrepancy
        return True, None, Decimal("0.00")

    @staticmethod
    def validate_cas(stmt: SyntheticCasStatement) -> Tuple[bool, Optional[str], Decimal]:
        for scheme in stmt.schemes:
            running_balance = scheme.opening_unit_balance
            for tx in scheme.transactions:
                running_balance += tx.units
                balance_diff = abs(running_balance - tx.unit_balance)
                if balance_diff > Decimal("0.001"):
                    return False, f"ERR_VALIDATION_CAS_UNIT_CONTINUITY: Folio {scheme.folio_number} unit continuity mismatch {balance_diff}", balance_diff
            
            close_diff = abs(running_balance - scheme.closing_unit_balance)
            if close_diff > Decimal("0.001"):
                return False, f"ERR_VALIDATION_CAS_CLOSING_BALANCE: Closing balance mismatch {close_diff}", close_diff
        return True, None, Decimal("0.00")

    @staticmethod
    def validate_schwab(stmt: SyntheticSchwabStatement) -> Tuple[bool, Optional[str], Decimal]:
        for r in stmt.rows:
            if r.action.lower() in ("buy", "bought"):
                expected = -((r.quantity * r.price) + r.fees_and_comm)
                diff = abs(expected - r.amount)
                if diff > Decimal("0.02"):
                    return False, f"ERR_VALIDATION_SCHWAB_MATH: Buy math discrepancy {diff}", diff
            elif r.action.lower() in ("sell", "sold"):
                expected = (r.quantity * r.price) - r.fees_and_comm
                diff = abs(expected - r.amount)
                if diff > Decimal("0.02"):
                    return False, f"ERR_VALIDATION_SCHWAB_MATH: Sell math discrepancy {diff}", diff
        return True, None, Decimal("0.00")


class ReferenceReconciliationGate:
    """
    Authoritative reference implementation of Gate 4: Reconciliation & Ledger Gate.
    """
    @staticmethod
    def compute_statement_hash(
        institution: str,
        account_or_folio: str,
        start_date: str,
        end_date: str,
        trades_count: int,
        net_amount: Decimal,
    ) -> str:
        key = f"{institution}:{account_or_folio}:{start_date}:{end_date}:{trades_count}:{net_amount:.2f}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    @staticmethod
    def compute_transaction_fingerprint(
        portfolio_id: str,
        institution: str,
        isin_or_symbol: str,
        trade_date: str,
        action: str,
        quantity: Decimal,
        unit_price: Decimal,
        order_or_trade_id: str,
    ) -> str:
        key = f"{portfolio_id}:{institution}:{isin_or_symbol}:{trade_date}:{action}:{quantity:.4f}:{unit_price:.4f}:{order_or_trade_id}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()


class ReferenceFIFOTaxEngine:
    """
    Authoritative reference implementation of Finance Act 2024 / Budget 2024
    FIFO Tax Lot and Capital Gains Engine.
    """
    def __init__(self):
        self.active_lots: Dict[str, List[Dict[str, Any]]] = {}

    def buy_lot(
        self,
        portfolio_id: str,
        asset_id: str,
        asset_type: str,
        buy_date: date,
        quantity: Decimal,
        price: Decimal,
        currency: str = "INR",
        forex_rate: Decimal = Decimal("1.00"),
        expenses: Decimal = Decimal("0.00"),
    ) -> Dict[str, Any]:
        key = f"{portfolio_id}:{asset_id}"
        if key not in self.active_lots:
            self.active_lots[key] = []
        
        lot = {
            "lot_id": f"lot_{key}_{len(self.active_lots[key])+1}",
            "portfolio_id": portfolio_id,
            "asset_id": asset_id,
            "asset_type": asset_type,
            "purchase_date": buy_date,
            "initial_quantity": quantity,
            "remaining_quantity": quantity,
            "cost_per_unit": price,
            "cost_per_unit_inr": (price * forex_rate).quantize(Decimal("0.01")),
            "expenses_per_unit": (expenses / quantity) if quantity > 0 else Decimal("0.00"),
            "currency": currency,
            "status": "ACTIVE",
        }
        self.active_lots[key].append(lot)
        return lot

    def sell_units(
        self,
        portfolio_id: str,
        asset_id: str,
        asset_type: str,
        sell_date: date,
        quantity: Decimal,
        sell_price: Decimal,
        currency: str = "INR",
        forex_rate: Decimal = Decimal("1.00"),
        expenses: Decimal = Decimal("0.00"),
    ) -> List[Dict[str, Any]]:
        key = f"{portfolio_id}:{asset_id}"
        lots = self.active_lots.get(key, [])
        remaining_to_sell = quantity
        dispositions = []

        lots.sort(key=lambda x: x["purchase_date"])

        for lot in lots:
            if remaining_to_sell <= Decimal("0.00"):
                break
            if lot["remaining_quantity"] <= Decimal("0.00"):
                continue

            matched_qty = min(remaining_to_sell, lot["remaining_quantity"])
            holding_days = (sell_date - lot["purchase_date"]).days

            if asset_type == "DEBT_MUTUAL_FUND":
                is_long_term = False
                tax_rate_pct = Decimal("30.00")
            elif asset_type == "SGB_MATURITY":
                is_long_term = True
                tax_rate_pct = Decimal("0.00")
            elif asset_type == "US_EQUITY":
                is_long_term = holding_days > 730
                tax_rate_pct = Decimal("12.50") if is_long_term else Decimal("30.00")
            else:
                is_long_term = holding_days > 365
                tax_rate_pct = Decimal("12.50") if is_long_term else Decimal("20.00")

            cost_basis_inr = (matched_qty * lot["cost_per_unit_inr"]).quantize(Decimal("0.01"))
            sale_proceeds_inr = (matched_qty * sell_price * forex_rate).quantize(Decimal("0.01"))
            realized_gain_inr = sale_proceeds_inr - cost_basis_inr

            disp = {
                "lot_id": lot["lot_id"],
                "portfolio_id": portfolio_id,
                "asset_id": asset_id,
                "matched_quantity": matched_qty,
                "acquisition_date": lot["purchase_date"],
                "sale_date": sell_date,
                "holding_days": holding_days,
                "is_long_term": is_long_term,
                "cost_basis_inr": cost_basis_inr,
                "sale_proceeds_inr": sale_proceeds_inr,
                "realized_gain_inr": realized_gain_inr,
                "tax_rate_pct": tax_rate_pct,
                "estimated_tax_inr": max(Decimal("0.00"), realized_gain_inr * (tax_rate_pct / Decimal("100.00"))).quantize(Decimal("0.01")),
            }
            dispositions.append(disp)

            lot["remaining_quantity"] -= matched_qty
            if lot["remaining_quantity"] == Decimal("0.00"):
                lot["status"] = "EXHAUSTED"
            remaining_to_sell -= matched_qty

        if remaining_to_sell > Decimal("0.00"):
            raise ValueError(f"Oversell condition: Sold {quantity} units but only {quantity - remaining_to_sell} units available in active lots")

        return dispositions
