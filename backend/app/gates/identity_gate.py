"""
Identity Gate (Gate 1): Inbound Email Ingestion & Perimeter Identity Security
Enforces strict fail-closed verification on inbound forwarded MIME payloads:
1. Parses RFC 822 / MIME multipart messages using standard library email.
2. Validates forwarder email against authorized family whitelist.
3. Extracts original broker sender from forwarded headers and validates broker domain whitelist.
4. Resolves target family entity, portfolio ID, and PAN.
5. In-memory extraction of PDF and CSV attachments (zero disk writes).
"""

import email
import email.policy
import email.utils
import hashlib
import io
import re
from datetime import datetime
from email.header import decode_header
from typing import Dict, List, Optional, Tuple, Union

from ..config import (
    ERR_IDENTITY_MALFORMED_MIME,
    ERR_IDENTITY_NO_ATTACHMENTS,
    ERR_IDENTITY_PAN_MISMATCH,
    ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN,
    ERR_IDENTITY_UNAUTHORIZED_FORWARDER,
    ERR_IDENTITY_UNRESOLVED_ENTITY,
    FAMILY_PAN_REGISTRY,
    FamilyEntityProfile,
    get_entity_by_email,
    get_entity_by_pan,
    is_authorized_broker_domain,
    is_authorized_forwarder,
    resolve_broker_institution,
)
from ..models.email import (
    ExtractedAttachment,
    ExtractedEmailMetadata,
    IdentityGateResult,
    InboundEmailPayload,
)

# Email address extraction regex
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")

# PAN format regex (5 letters, 4 digits, 1 letter)
PAN_REGEX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")

# Forwarded header pattern delimiters
FORWARDED_BLOCK_PATTERNS = [
    re.compile(r"-+\s*Forwarded message\s*-+", re.IGNORECASE),
    re.compile(r"-+\s*Original Message\s*-+", re.IGNORECASE),
]

# Forwarded 'From' line pattern within body
FORWARDED_FROM_REGEX = re.compile(
    r"(?:From|Sender):\s*([^\r\n]+)", re.IGNORECASE
)


def _decode_header_str(header_val: Optional[str]) -> str:
    """Safely decodes an RFC 2047 encoded email header to a Python unicode string."""
    if not header_val:
        return ""
    try:
        decoded_fragments = decode_header(header_val)
        result = []
        for fragment, encoding in decoded_fragments:
            if isinstance(fragment, bytes):
                if encoding:
                    try:
                        result.append(fragment.decode(encoding, errors="replace"))
                    except (LookupError, UnicodeDecodeError):
                        result.append(fragment.decode("utf-8", errors="replace"))
                else:
                    result.append(fragment.decode("utf-8", errors="replace"))
            else:
                result.append(str(fragment))
        return "".join(result).strip()
    except Exception:
        return str(header_val).strip()


def _extract_email_address(raw_str: str) -> Optional[str]:
    """Extracts a clean email address from a string (e.g. 'Name <user@domain.com>' -> 'user@domain.com')."""
    if not raw_str:
        return None
    _, addr = email.utils.parseaddr(raw_str)
    if addr and "@" in addr:
        return addr.strip().lower()
    
    # Fallback to regex search
    match = EMAIL_REGEX.search(raw_str)
    if match:
        return match.group(0).strip().lower()
    return None


class IdentityGate:
    """
    Gate 1: Perimeter Identity Gate for Inbound Email Ingestion.
    All incoming statements must pass through this gate before parsing.
    """

    def __init__(self):
        pass

    def evaluate(self, payload: Union[InboundEmailPayload, bytes, str, dict]) -> IdentityGateResult:
        """
        Evaluates an inbound email payload through the Identity Gate.
        
        Parameters:
            payload: InboundEmailPayload, raw bytes, str, or dict representing the payload.
            
        Returns:
            IdentityGateResult with passed=True or fail-closed rejection details.
        """
        # Step 1: Normalize input to InboundEmailPayload
        try:
            if isinstance(payload, InboundEmailPayload):
                inbound = payload
            elif isinstance(payload, bytes):
                inbound = InboundEmailPayload(raw_mime=payload)
            elif isinstance(payload, (bytearray, memoryview)):
                inbound = InboundEmailPayload(raw_mime=bytes(payload))
            elif isinstance(payload, str):
                inbound = InboundEmailPayload(raw_mime=payload.encode("utf-8", errors="replace"))
            elif isinstance(payload, dict):
                raw_mime = payload.get("raw_mime")
                if isinstance(raw_mime, str):
                    raw_mime = raw_mime.encode("utf-8", errors="replace")
                elif isinstance(raw_mime, (bytearray, memoryview)):
                    raw_mime = bytes(raw_mime)
                elif raw_mime is not None and not isinstance(raw_mime, (bytes, bytearray)):
                    return IdentityGateResult(
                        passed=False,
                        rejection_code=ERR_IDENTITY_MALFORMED_MIME,
                        rejection_reason="Invalid raw_mime type in dictionary payload (expected bytes, bytearray, or str).",
                    )
                inbound = InboundEmailPayload(
                    raw_mime=raw_mime or b"",
                    forwarder_email=payload.get("forwarder_email"),
                    received_timestamp=payload.get("received_timestamp"),
                    target_pan=payload.get("target_pan"),
                )
            else:
                return IdentityGateResult(
                    passed=False,
                    rejection_code=ERR_IDENTITY_MALFORMED_MIME,
                    rejection_reason="Invalid payload type provided to IdentityGate.",
                )

            # Type check inbound.raw_mime
            if not isinstance(inbound.raw_mime, (bytes, bytearray)):
                return IdentityGateResult(
                    passed=False,
                    rejection_code=ERR_IDENTITY_MALFORMED_MIME,
                    rejection_reason="Invalid raw MIME data type provided to IdentityGate (expected bytes or bytearray).",
                )

            if len(inbound.raw_mime.strip()) == 0:
                return IdentityGateResult(
                    passed=False,
                    rejection_code=ERR_IDENTITY_MALFORMED_MIME,
                    rejection_reason="Empty or null raw MIME content.",
                )

            # Step 2: Parse RFC 822 / MIME Multipart Message
            try:
                msg = email.message_from_bytes(bytes(inbound.raw_mime), policy=email.policy.default)
            except Exception as e:
                return IdentityGateResult(
                    passed=False,
                    rejection_code=ERR_IDENTITY_MALFORMED_MIME,
                    rejection_reason=f"Failed to parse RFC 822 MIME structure: {str(e)}",
                )

            if msg is None:
                return IdentityGateResult(
                    passed=False,
                    rejection_code=ERR_IDENTITY_MALFORMED_MIME,
                    rejection_reason="RFC 822 MIME parser returned empty message.",
                )

            # Step 3: Extract & Verify Forwarder Email
            forwarder_email = inbound.forwarder_email
            if not forwarder_email:
                # Check envelope headers (From, Sender, X-Forwarded-From, Return-Path)
                for header_name in ["From", "Sender", "X-Forwarded-From", "Return-Path"]:
                    try:
                        header_val = msg.get(header_name)
                        if header_val:
                            candidate = _extract_email_address(_decode_header_str(str(header_val)))
                            if candidate:
                                forwarder_email = candidate
                                break
                    except Exception:
                        continue

            if not forwarder_email:
                return IdentityGateResult(
                    passed=False,
                    rejection_code=ERR_IDENTITY_UNAUTHORIZED_FORWARDER,
                    rejection_reason="Could not extract forwarder email address from headers or payload.",
                )

            forwarder_email = forwarder_email.strip().lower()
            if not is_authorized_forwarder(forwarder_email):
                return IdentityGateResult(
                    passed=False,
                    rejection_code=ERR_IDENTITY_UNAUTHORIZED_FORWARDER,
                    rejection_reason=f"Forwarder email '{forwarder_email}' is not in authorized family whitelist.",
                )

            # Step 4: Extract Body & Find Original Broker Sender
            plain_body_text, html_body_text = self._extract_bodies(msg)
            combined_body = plain_body_text + "\n" + html_body_text

            original_sender, forwarded_header_block = self._extract_original_sender(msg, combined_body)

            # Validate Broker Domain
            if not original_sender:
                return IdentityGateResult(
                    passed=False,
                    rejection_code=ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN,
                    rejection_reason="No original broker sender could be identified in forwarded headers or envelope.",
                )

            sender_domain = original_sender.split("@")[-1].lower()
            broker_institution = resolve_broker_institution(sender_domain)

            if not broker_institution:
                return IdentityGateResult(
                    passed=False,
                    rejection_code=ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN,
                    rejection_reason=f"Original sender domain '@{sender_domain}' ({original_sender}) is not in authorized broker whitelist.",
                )

            # Step 5: Resolve Target Family Member & Validate PAN
            subj_header = ""
            try:
                raw_subj = msg.get("Subject", "")
                if raw_subj:
                    subj_header = _decode_header_str(str(raw_subj))
            except Exception:
                subj_header = ""

            target_entity, pan_error = self._resolve_target_entity(
                forwarder_email=forwarder_email,
                explicit_pan=inbound.target_pan,
                subject=subj_header,
                body_text=combined_body,
            )

            if pan_error:
                return IdentityGateResult(
                    passed=False,
                    rejection_code=pan_error[0],
                    rejection_reason=pan_error[1],
                )

            if not target_entity:
                return IdentityGateResult(
                    passed=False,
                    rejection_code=ERR_IDENTITY_UNRESOLVED_ENTITY,
                    rejection_reason=f"Unable to resolve authorized family vault entity for forwarder '{forwarder_email}'.",
                )

            # Step 6: Extract Attachments (PDF and CSV) In-Memory
            attachments = self._extract_attachments(msg)
            if not attachments:
                return IdentityGateResult(
                    passed=False,
                    rejection_code=ERR_IDENTITY_NO_ATTACHMENTS,
                    rejection_reason="No valid PDF or CSV attachments found in email payload.",
                )

            # Step 7: Build Metadata and Success Result
            parsed_date = None
            try:
                date_val = msg.get("Date")
                if date_val:
                    try:
                        parsed_date = email.utils.parsedate_to_datetime(str(date_val))
                    except Exception:
                        parsed_date = None
            except Exception:
                parsed_date = None

            headers_dict = {}
            try:
                for k, v in msg.items():
                    try:
                        headers_dict[str(k)] = _decode_header_str(str(v))
                    except Exception:
                        headers_dict[str(k)] = str(v)
            except Exception:
                pass

            subject_meta = ""
            try:
                sub_val = msg.get("Subject")
                if sub_val is not None:
                    subject_meta = _decode_header_str(str(sub_val))
            except Exception:
                subject_meta = ""

            msg_id_meta = None
            try:
                mid_val = msg.get("Message-ID")
                if mid_val is not None:
                    msg_id_meta = str(mid_val)
            except Exception:
                msg_id_meta = None

            extracted_meta = ExtractedEmailMetadata(
                forwarder_email=forwarder_email,
                original_sender=original_sender,
                original_sender_domain=sender_domain,
                subject=subject_meta,
                date=parsed_date,
                message_id=msg_id_meta,
                headers=headers_dict,
                forwarded_body_header=forwarded_header_block,
            )

            return IdentityGateResult(
                passed=True,
                target_entity_id=target_entity.entity_id,
                target_pan=target_entity.pan,
                broker_institution=broker_institution,
                extracted_metadata=extracted_meta,
                extracted_attachments=attachments,
            )
        except Exception as e:
            return IdentityGateResult(
                passed=False,
                rejection_code=ERR_IDENTITY_MALFORMED_MIME,
                rejection_reason=f"Unhandled exception during Gate 1 identity evaluation: {str(e)}",
            )

    def _extract_bodies(self, msg: email.message.EmailMessage) -> Tuple[str, str]:
        """Extracts plain text and html body strings from the MIME tree."""
        plain_parts = []
        html_parts = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                # Skip actual attachments
                if "attachment" in content_disposition.lower():
                    continue

                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            plain_parts.append(payload.decode(charset, errors="replace"))
                    except Exception:
                        pass
                elif content_type == "text/html":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            html_parts.append(payload.decode(charset, errors="replace"))
                    except Exception:
                        pass
        else:
            content_type = msg.get_content_type()
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    text = payload.decode(charset, errors="replace")
                    if content_type == "text/html":
                        html_parts.append(text)
                    else:
                        plain_parts.append(text)
            except Exception:
                pass

        return "\n".join(plain_parts), "\n".join(html_parts)

    def _extract_original_sender(
        self, msg: email.message.EmailMessage, body_text: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Locates the original sender address from forwarded header blocks or auxiliary headers.
        Returns (sender_email, matched_header_snippet).
        """
        # 1. Search body text for forwarded header blocks
        for delimiter_regex in FORWARDED_BLOCK_PATTERNS:
            match = delimiter_regex.search(body_text)
            if match:
                # Look in the text immediately following the delimiter (up to 1000 characters)
                start_idx = match.start()
                block_window = body_text[start_idx : start_idx + 1000]
                from_match = FORWARDED_FROM_REGEX.search(block_window)
                if from_match:
                    from_line = from_match.group(1).strip()
                    extracted_addr = _extract_email_address(from_line)
                    if extracted_addr:
                        return extracted_addr, block_window[:200].strip()

        # 2. Search body text directly for 'From: ...' lines matching broker domains
        for line in body_text.splitlines():
            line_clean = line.strip()
            if line_clean.lower().startswith("from:"):
                addr = _extract_email_address(line_clean)
                if addr and is_authorized_broker_domain(addr):
                    return addr, line_clean

        # 3. Check MIME headers for forwarded sender or direct broker sender
        auxiliary_headers = [
            "X-Original-Sender",
            "X-Forwarded-From",
            "Reply-To",
            "Sender",
            "From",
        ]
        for h in auxiliary_headers:
            val = msg.get(h)
            if val:
                decoded_val = _decode_header_str(str(val))
                addr = _extract_email_address(decoded_val)
                if addr and is_authorized_broker_domain(addr):
                    return addr, f"{h}: {decoded_val}"

        # 4. If top-level From header exists, extract it even if not a broker, to report in rejection
        from_val = msg.get("From")
        if from_val:
            addr = _extract_email_address(_decode_header_str(str(from_val)))
            if addr:
                return addr, f"From: {from_val}"

        return None, None

    def _resolve_target_entity(
        self,
        forwarder_email: str,
        explicit_pan: Optional[str] = None,
        subject: str = "",
        body_text: str = "",
    ) -> Tuple[Optional[FamilyEntityProfile], Optional[Tuple[str, str]]]:
        """
        Resolves the family vault entity and validates PAN consistency.
        Returns (FamilyEntityProfile, None) on success or (None, (error_code, reason)) on error.
        """
        # 1. If explicit PAN is specified
        if explicit_pan:
            clean_pan = explicit_pan.strip().upper()
            profile = get_entity_by_pan(clean_pan)
            if not profile:
                return None, (
                    ERR_IDENTITY_PAN_MISMATCH,
                    f"Specified target PAN '{clean_pan}' is not registered to any family vault entity.",
                )
            
            # Verify forwarder is authorized to submit for this PAN
            # Alex is authorized for Alex portfolio and HUF portfolio
            # Robert is authorized for Robert portfolio and HUF portfolio
            # Margaret is authorized for Margaret portfolio
            if profile.entity_id == "port_trust":
                if forwarder_email not in ("alex.taylor@example.com", "robert.taylor@example.com"):
                    return None, (
                        ERR_IDENTITY_PAN_MISMATCH,
                        f"Forwarder '{forwarder_email}' is not authorized to submit for HUF PAN '{clean_pan}'.",
                    )
            elif profile.email.lower() != forwarder_email.lower():
                return None, (
                    ERR_IDENTITY_PAN_MISMATCH,
                    f"Forwarder '{forwarder_email}' is not authorized for target PAN '{clean_pan}' (owned by {profile.name}).",
                )
            return profile, None

        # 2. Check if a PAN is explicitly referenced in the subject line or forwarded body
        combined_text = subject + " " + body_text
        found_pans = PAN_REGEX.findall(combined_text)
        for pan in found_pans:
            if pan in FAMILY_PAN_REGISTRY:
                profile = FAMILY_PAN_REGISTRY[pan]
                # If HUF PAN found, allow if forwarded by Alex or Robert
                if profile.entity_id == "port_trust" and forwarder_email in (
                    "alex.taylor@example.com",
                    "robert.taylor@example.com",
                    "alex.taylor@example.com",
                    "robert.taylor@example.com",
                ):
                    return profile, None
                if profile.email.lower() == forwarder_email.lower():
                    return profile, None

        # 3. Default resolution by forwarder email
        default_entity = get_entity_by_email(forwarder_email)
        if default_entity:
            return default_entity, None

        return None, (
            ERR_IDENTITY_UNRESOLVED_ENTITY,
            f"No family vault entity found matching forwarder '{forwarder_email}'.",
        )

    def _extract_attachments(self, msg: email.message.EmailMessage) -> List[ExtractedAttachment]:
        """
        Extracts PDF and CSV attachments into memory streams without writing to disk.
        """
        attachments: List[ExtractedAttachment] = []

        for part in msg.walk():
            # Check for attachment disposition or content type
            content_type = part.get_content_type().lower()
            content_disposition = str(part.get("Content-Disposition", "")).lower()

            raw_filename = part.get_filename()
            filename = _decode_header_str(raw_filename) if raw_filename else None

            # Determine if this part is a statement attachment
            is_pdf = content_type == "application/pdf" or (filename and filename.lower().endswith(".pdf"))
            is_csv = (
                content_type in ("text/csv", "text/comma-separated-values", "application/vnd.ms-excel")
                or (filename and filename.lower().endswith(".csv"))
            )

            # Accept if explicit attachment disposition OR matching MIME type with filename
            if is_pdf or is_csv:
                payload = part.get_payload(decode=True)
                if not payload:
                    continue

                if not filename:
                    ext = ".pdf" if is_pdf else ".csv"
                    filename = f"statement_attachment_{len(attachments) + 1}{ext}"

                sha256_hash = hashlib.sha256(payload).hexdigest()
                norm_content_type = "application/pdf" if is_pdf else "text/csv"

                attachments.append(
                    ExtractedAttachment(
                        filename=filename,
                        content_type=norm_content_type,
                        size_bytes=len(payload),
                        payload_bytes=payload,
                        sha256=sha256_hash,
                    )
                )

        return attachments


# Global default instance & helper function
_default_identity_gate = IdentityGate()


def evaluate_identity_gate(payload: Union[InboundEmailPayload, bytes, str, dict]) -> IdentityGateResult:
    """Convenience functional interface for evaluating an inbound payload through Gate 1."""
    return _default_identity_gate.evaluate(payload)
