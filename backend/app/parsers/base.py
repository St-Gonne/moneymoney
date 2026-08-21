"""
Base Broker Statement Parser Interface
Defines the abstract interface and common utility methods for all broker-specific statement parsers.
"""

from abc import ABC, abstractmethod
import io
import re
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Union

from ..config import FamilyEntityProfile
from ..models.email import ExtractedAttachment
from ..models.contract_note import NormalizedContractNote
from ..models.cas import NormalizedCasStatement
from ..models.schwab import NormalizedSchwabStatement

StatementOutput = Union[NormalizedContractNote, NormalizedCasStatement, NormalizedSchwabStatement]


class BaseBrokerParser(ABC):
    """
    Abstract base class for broker-specific contract note, CAS, and trading statement parsers.
    """

    @abstractmethod
    def can_parse(self, attachment: ExtractedAttachment, target_pan: Optional[str] = None) -> bool:
        """
        Determines whether this parser can process the given attachment based on signature tokens and format.
        """
        pass

    @abstractmethod
    def parse(
        self,
        stream: io.BytesIO,
        entity_profile: Optional[FamilyEntityProfile] = None,
        password: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> StatementOutput:
        """
        Parses the binary stream into a normalized statement AST.
        """
        pass

    # --------------------------------------------------------------------------
    # Shared Data Cleaning & Transformation Helpers
    # --------------------------------------------------------------------------

    @staticmethod
    def clean_decimal(val: Any, default: Decimal = Decimal("0.00")) -> Decimal:
        """Safely parses numbers, strings with currency symbols and commas to Decimal."""
        if val is None:
            return default
        if isinstance(val, Decimal):
            return val
        if isinstance(val, (int, float)):
            return Decimal(str(val))

        s = str(val).strip()
        if not s:
            return default

        # Remove currency symbols, commas, and whitespace
        s_clean = s.replace("₹", "").replace("$", "").replace(",", "").replace(" ", "").strip()
        # Handle parenthesized negative numbers e.g. (1,234.50) -> -1234.50
        if s_clean.startswith("(") and s_clean.endswith(")"):
            s_clean = "-" + s_clean[1:-1]
        # Handle trailing minus e.g. 1234.50- -> -1234.50
        elif s_clean.endswith("-"):
            s_clean = "-" + s_clean[:-1]
        # Handle leading plus
        elif s_clean.startswith("+"):
            s_clean = s_clean[1:]

        try:
            return Decimal(s_clean)
        except (InvalidOperation, ValueError):
            return default

    @staticmethod
    def parse_date(date_val: Any) -> Optional[date]:
        """Parses various date string formats into standard datetime.date."""
        if date_val is None:
            return None
        if isinstance(date_val, date) and not isinstance(date_val, datetime):
            return date_val
        if isinstance(date_val, datetime):
            return date_val.date()

        s = str(date_val).strip()
        if not s:
            return None

        # Common date patterns
        formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%b-%Y",
            "%d %b %Y",
            "%d-%B-%Y",
            "%d %B %Y",
            "%Y/%m/%d",
            "%d%m%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue

        # Regex fallback for embedded dates
        match = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})", s)
        if match:
            d, m, y = match.groups()
            if len(y) == 2:
                y = "20" + y
            try:
                return date(int(y), int(m), int(d))
            except ValueError:
                pass

        return None

    @staticmethod
    def parse_time(time_val: Any) -> Optional[time]:
        """Parses time string formats (e.g. HH:MM:SS, HH:MM)."""
        if time_val is None:
            return None
        if isinstance(time_val, time):
            return time_val

        s = str(time_val).strip()
        if not s:
            return None

        formats = ["%H:%M:%S", "%I:%M:%S %p", "%H:%M", "%I:%M %p"]
        for fmt in formats:
            try:
                return datetime.strptime(s, fmt).time()
            except ValueError:
                continue
        return None

    @staticmethod
    def clean_str(val: Any) -> str:
        """Strips and normalizes strings."""
        if val is None:
            return ""
        return str(val).strip()

    @staticmethod
    def extract_regex(pattern: Union[str, re.Pattern], text: str, group: int = 1, default: Optional[str] = None) -> Optional[str]:
        """Extracts first capture group matching pattern in text."""
        if not text:
            return default
        match = re.search(pattern, text, re.IGNORECASE) if isinstance(pattern, str) else pattern.search(text)
        if match:
            try:
                return match.group(group).strip()
            except IndexError:
                return match.group(0).strip()
        return default
