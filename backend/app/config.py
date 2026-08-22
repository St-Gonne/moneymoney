"""
MoneyMoney Pipeline Configuration & Security Whitelists
Defines perimeter security boundaries, authorized family entities, and broker registries.
"""

import os
from typing import Dict, List, Set, Optional, NamedTuple
from dataclasses import dataclass


# ----------------------------------------------------------------------
# 1. Error Codes (Perimeter & Identity Guard, Layout & Decryption)
# ----------------------------------------------------------------------
ERR_IDENTITY_UNAUTHORIZED_FORWARDER = "ERR_IDENTITY_UNAUTHORIZED_FORWARDER"
ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN = "ERR_IDENTITY_UNAUTHORIZED_BROKER_DOMAIN"
ERR_IDENTITY_NO_ATTACHMENTS = "ERR_IDENTITY_NO_ATTACHMENTS"
ERR_IDENTITY_PAN_MISMATCH = "ERR_IDENTITY_PAN_MISMATCH"
ERR_IDENTITY_MALFORMED_MIME = "ERR_IDENTITY_MALFORMED_MIME"
ERR_IDENTITY_UNRESOLVED_ENTITY = "ERR_IDENTITY_UNRESOLVED_ENTITY"

# Gate 2 Error Codes
ERR_LAYOUT_UNSUPPORTED_FORMAT = "ERR_LAYOUT_UNSUPPORTED_FORMAT"
ERR_LAYOUT_DECRYPTION_FAILED = "ERR_LAYOUT_DECRYPTION_FAILED"
ERR_LAYOUT_PARSING_FAILED = "ERR_LAYOUT_PARSING_FAILED"

# Gate 3 Error Codes (Mathematical Validation Gate)
ERR_VALIDATION_MATH_MISMATCH = "ERR_VALIDATION_MATH_MISMATCH"
ERR_VALIDATION_GST_MISMATCH = "ERR_VALIDATION_GST_MISMATCH"
ERR_VALIDATION_CAS_UNIT_CONTINUITY = "ERR_VALIDATION_CAS_UNIT_CONTINUITY"
ERR_VALIDATION_CAS_CLOSING_BALANCE = "ERR_VALIDATION_CAS_CLOSING_BALANCE"
ERR_VALIDATION_SCHWAB_MATH = "ERR_VALIDATION_SCHWAB_MATH"
ERR_VALIDATION_EMPTY_STATEMENT = "ERR_VALIDATION_EMPTY_STATEMENT"
ERR_VALIDATION_UNSUPPORTED_STATEMENT = "ERR_VALIDATION_UNSUPPORTED_STATEMENT"

# Gate 4 Error Codes (Reconciliation & Deduplication Gate)
ERR_RECONCILIATION_DUPLICATE_STATEMENT = "ERR_RECONCILIATION_DUPLICATE_STATEMENT"
ERR_RECONCILIATION_DUPLICATE_TRANSACTION = "ERR_RECONCILIATION_DUPLICATE_TRANSACTION"
ERR_RECONCILIATION_OVERSELL = "ERR_RECONCILIATION_OVERSELL"

# Invariant Tolerances
from decimal import Decimal
from datetime import date
MATH_INVARIANT_TOLERANCE = Decimal("0.02")
CAS_UNIT_CONTINUITY_TOLERANCE = Decimal("0.001")
GST_VALIDATION_TOLERANCE = Decimal("0.05")


# ----------------------------------------------------------------------
# 2. Broker Institutions & Domain Whitelist
# ----------------------------------------------------------------------
class BrokerInstitution:
    ZERODHA = "ZERODHA"
    HDFC_SECURITIES = "HDFC_SECURITIES"
    CAMS_KFINTECH = "CAMS_KFINTECH"
    CHARLES_SCHWAB = "CHARLES_SCHWAB"


# Domain to Broker Institution Mapping
BROKER_DOMAIN_MAP: Dict[str, str] = {
    "zerodha.com": BrokerInstitution.ZERODHA,
    "hdfcsec.com": BrokerInstitution.HDFC_SECURITIES,
    "hdfcbank.net": BrokerInstitution.HDFC_SECURITIES,
    "camsonline.com": BrokerInstitution.CAMS_KFINTECH,
    "kfintech.com": BrokerInstitution.CAMS_KFINTECH,
    "schwab.com": BrokerInstitution.CHARLES_SCHWAB,
}

# Set of allowed broker domains (with leading @ for matching checks)
ALLOWED_BROKER_DOMAINS: Set[str] = {
    "@zerodha.com",
    "@hdfcsec.com",
    "@hdfcbank.net",
    "@camsonline.com",
    "@kfintech.com",
    "@schwab.com",
}

# Plain domain strings
ALLOWED_BROKER_DOMAIN_SUFFIXES: List[str] = [
    "zerodha.com",
    "hdfcsec.com",
    "hdfcbank.net",
    "camsonline.com",
    "kfintech.com",
    "schwab.com",
]

# ----------------------------------------------------------------------
# 3. Authorized Family Forwarders Whitelist
# ----------------------------------------------------------------------
_env_emails = os.getenv("ALLOWED_FAMILY_EMAILS")
if _env_emails:
    ALLOWED_FAMILY_EMAILS: Set[str] = {e.strip().lower() for e in _env_emails.split(",") if e.strip()}
else:
    ALLOWED_FAMILY_EMAILS: Set[str] = {
        "alex.taylor@example.com",
        "robert.taylor@example.com",
        "margaret.taylor@example.com",
        "chiragsuchde@gmail.com",
        "chirag.suchde@gmail.com",
        "aanchaltulsiani@gmail.com",
        "sahiltulsiani@gmail.com",
        "sahil.tulsiani@gmail.com",
        "sharan.tulsiani@gmail.com",
    }

# ----------------------------------------------------------------------
# 4. Family Vault Entity Profiles & PAN Mapping
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class FamilyEntityProfile:
    entity_id: str
    pan: str
    name: str
    email: str
    entity_type: str  # INDIVIDUAL, SENIOR_CITIZEN, HUF
    dob: Optional[str] = None  # YYYY-MM-DD format if available


# Mapping from PAN to Family Entity Profile
FAMILY_PAN_REGISTRY: Dict[str, FamilyEntityProfile] = {
    "KLMNO9012P": FamilyEntityProfile(
        entity_id="port_primary",
        pan="KLMNO9012P",
        name="Alex Taylor",
        email="alex.taylor@example.com",
        entity_type="INDIVIDUAL",
        dob="1990-08-15",
    ),
    "ABCDE1234F": FamilyEntityProfile(
        entity_id="port_father",
        pan="ABCDE1234F",
        name="Robert Taylor",
        email="robert.taylor@example.com",
        entity_type="SENIOR_CITIZEN",
        dob="1955-03-20",
    ),
    "FGHIJ5678K": FamilyEntityProfile(
        entity_id="port_mother",
        pan="FGHIJ5678K",
        name="Margaret Taylor",
        email="margaret.taylor@example.com",
        entity_type="INDIVIDUAL",
        dob="1992-11-10",
    ),
    "PQRST3456Q": FamilyEntityProfile(
        entity_id="port_trust",
        pan="PQRST3456Q",
        name="Taylor Family Trust",
        email="alex.taylor@example.com",
        entity_type="HUF",
        dob=None,
    ),
}

# Primary email to Default Entity ID
EMAIL_TO_ENTITY_MAP: Dict[str, str] = {
    "alex.taylor@example.com": "port_primary",
    "robert.taylor@example.com": "port_father",
    "margaret.taylor@example.com": "port_mother",
}

# Entity ID to Profile Map
ENTITY_ID_REGISTRY: Dict[str, FamilyEntityProfile] = {
    profile.entity_id: profile for profile in FAMILY_PAN_REGISTRY.values()
}


def is_authorized_forwarder(email_address: str) -> bool:
    """Verifies whether the given email address is in the authorized family whitelist."""
    if not email_address:
        return False
    normalized = email_address.strip().lower()
    return normalized in ALLOWED_FAMILY_EMAILS


def resolve_broker_institution(domain_or_email: str) -> Optional[str]:
    """
    Resolves broker institution from domain or email address.
    Supports subdomains, e.g. 'mailer.zerodha.com' -> 'ZERODHA'.
    """
    if not domain_or_email:
        return None
    
    clean = domain_or_email.strip().lower()
    if "@" in clean:
        clean = clean.split("@")[-1]
        
    for suffix, institution in BROKER_DOMAIN_MAP.items():
        if clean == suffix or clean.endswith("." + suffix):
            return institution
            
    return None


def is_authorized_broker_domain(domain_or_email: str) -> bool:
    """Checks if the given domain or email matches any authorized broker."""
    return resolve_broker_institution(domain_or_email) is not None


def get_entity_by_pan(pan: str) -> Optional[FamilyEntityProfile]:
    """Retrieves family entity profile by 10-character uppercase PAN."""
    if not pan:
        return None
    return FAMILY_PAN_REGISTRY.get(pan.strip().upper())


def get_entity_by_email(email_address: str) -> Optional[FamilyEntityProfile]:
    """Retrieves default family entity profile for an authorized family forwarder email."""
    if not email_address:
        return None
    entity_id = EMAIL_TO_ENTITY_MAP.get(email_address.strip().lower())
    if entity_id:
        return ENTITY_ID_REGISTRY.get(entity_id)
    return None


# ----------------------------------------------------------------------
# 5. Historical RBI / FBIL USD/INR Reference Rates Table
# ----------------------------------------------------------------------
HISTORICAL_RBI_FOREX_RATES: Dict[date, Decimal] = {
    date(2022, 1, 31): Decimal("74.50"),
    date(2022, 6, 30): Decimal("78.95"),
    date(2022, 12, 30): Decimal("82.78"),
    date(2023, 1, 31): Decimal("81.74"),
    date(2023, 3, 31): Decimal("82.22"),
    date(2023, 4, 28): Decimal("81.80"),
    date(2023, 5, 18): Decimal("82.35"),
    date(2023, 5, 31): Decimal("82.68"),
    date(2023, 6, 30): Decimal("82.04"),
    date(2023, 8, 31): Decimal("82.75"),
    date(2023, 11, 15): Decimal("83.25"),
    date(2023, 11, 30): Decimal("83.35"),
    date(2023, 12, 29): Decimal("83.12"),
    date(2024, 1, 31): Decimal("83.05"),
    date(2024, 2, 29): Decimal("82.90"),
    date(2024, 3, 28): Decimal("83.37"),
    date(2024, 4, 30): Decimal("83.45"),
    date(2024, 5, 31): Decimal("83.42"),
    date(2024, 6, 28): Decimal("83.56"),
    date(2024, 7, 31): Decimal("83.72"),
    date(2024, 8, 14): Decimal("83.95"),
    date(2024, 12, 31): Decimal("84.25"),
    date(2025, 3, 31): Decimal("84.50"),
    date(2025, 6, 30): Decimal("84.85"),
    date(2025, 12, 31): Decimal("85.10"),
    date(2026, 1, 30): Decimal("85.20"),
    date(2026, 8, 14): Decimal("84.50"),
}

DEFAULT_USD_INR_RATE: Decimal = Decimal("84.50")

