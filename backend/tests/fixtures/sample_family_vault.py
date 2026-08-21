"""
Family Vault Entity Registry, Historical Forex Rates, and Test Constants
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

# Authorized Family Email Whitelist
AUTHORIZED_FORWARDERS = [
    "alex.taylor@example.com",
    "robert.taylor@example.com",
    "margaret.taylor@example.com",
]

# Authorized Broker Sender Domains
AUTHORIZED_BROKER_DOMAINS = [
    "@zerodha.com",
    "@hdfcsec.com",
    "@hdfcbank.net",
    "@camsonline.com",
    "@kfintech.com",
    "@schwab.com",
]

@dataclass
class FamilyMemberProfile:
    portfolio_id: str
    name: str
    first_name: str
    email: str
    pan: str
    dob: date
    entity_type: str # INDIVIDUAL, SENIOR_CITIZEN, HUF
    accounts: Dict[str, str] = field(default_factory=dict) # e.g. {"ZERODHA": "ZR1102", "SCHWAB": "XX8901"}

FAMILY_VAULT_PROFILES: Dict[str, FamilyMemberProfile] = {
    "port_primary": FamilyMemberProfile(
        portfolio_id="port_primary",
        name="Alex Taylor",
        first_name="Alex",
        email="alex.taylor@example.com",
        pan="KLMNO9012P",
        dob=date(1990, 8, 15),
        entity_type="INDIVIDUAL",
        accounts={
            "ZERODHA": "ZR1102",
            "SCHWAB": "84920194",
            "CAMS": "4481023/1",
        }
    ),
    "port_father": FamilyMemberProfile(
        portfolio_id="port_father",
        name="Robert Taylor",
        first_name="Robert",
        email="robert.taylor@example.com",
        pan="ABCDE1234F",
        dob=date(1955, 5, 20),
        entity_type="SENIOR_CITIZEN",
        accounts={
            "HDFC_SECURITIES": "1092847101",
            "CAMS": "9082341/88",
        }
    ),
    "port_mother": FamilyMemberProfile(
        portfolio_id="port_mother",
        name="Margaret Taylor",
        first_name="Margaret",
        email="margaret.taylor@example.com",
        pan="FGHIJ5678K",
        dob=date(1958, 11, 12),
        entity_type="SENIOR_CITIZEN",
        accounts={
            "CAMS": "1098234/0",
        }
    ),
    "port_trust": FamilyMemberProfile(
        portfolio_id="port_trust",
        name="Taylor Family Trust",
        first_name="Taylor",
        email="alex.taylor@example.com",
        pan="PQRST3456Q",
        dob=date(2015, 4, 1),
        entity_type="HUF",
        accounts={
            "CAMS": "HUF-990812",
        }
    ),
}

# Mapping of PAN to Profile
PAN_TO_PROFILE: Dict[str, FamilyMemberProfile] = {
    p.pan: p for p in FAMILY_VAULT_PROFILES.values()
}

# Mapping of Email to Profile
EMAIL_TO_PROFILE: Dict[str, FamilyMemberProfile] = {
    "alex.taylor@example.com": FAMILY_VAULT_PROFILES["port_primary"],
    "robert.taylor@example.com": FAMILY_VAULT_PROFILES["port_father"],
    "margaret.taylor@example.com": FAMILY_VAULT_PROFILES["port_mother"],
}

# Curated Historical RBI / FBIL USD/INR Reference Rate Table
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

DEFAULT_USD_INR_RATE = Decimal("84.50")

def lookup_rbi_rate(tx_date: date, mode: str = "SPOT") -> Decimal:
    """
    Look up RBI reference forex rate with fallback to nearest available date.
    """
    if mode == "RULE_115":
        # Last day of month preceding the transaction month
        first_of_month = date(tx_date.year, tx_date.month, 1)
        # previous day
        if tx_date.month == 1:
            lookup_d = date(tx_date.year - 1, 12, 31)
        else:
            from calendar import monthrange
            prev_month = tx_date.month - 1
            _, last_day = monthrange(tx_date.year, prev_month)
            lookup_d = date(tx_date.year, prev_month, last_day)
    else:
        lookup_d = tx_date

    if lookup_d in HISTORICAL_RBI_FOREX_RATES:
        return HISTORICAL_RBI_FOREX_RATES[lookup_d]

    # Find closest preceding date
    available_dates = sorted(HISTORICAL_RBI_FOREX_RATES.keys())
    closest = None
    for d in available_dates:
        if d <= lookup_d:
            closest = d
        else:
            break
    if closest:
        return HISTORICAL_RBI_FOREX_RATES[closest]
    return DEFAULT_USD_INR_RATE
