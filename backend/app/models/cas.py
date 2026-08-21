"""
Normalized CAMS / KFintech Consolidated Account Statement (CAS) Models
Defines data structures for mutual fund folios, schemes, and transaction histories.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

try:
    from pydantic import BaseModel, Field
except ImportError:
    class BaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def dict(self) -> dict:
            return self.model_dump()

        def model_dump(self) -> dict:
            res = {}
            for k, v in self.__dict__.items():
                if isinstance(v, BaseModel):
                    res[k] = v.model_dump()
                elif isinstance(v, list):
                    res[k] = [i.model_dump() if isinstance(i, BaseModel) else i for i in v]
                elif isinstance(v, Decimal):
                    res[k] = float(v)
                elif isinstance(v, (date, datetime)):
                    res[k] = v.isoformat()
                else:
                    res[k] = v
            return res

        def __repr__(self):
            fields = ", ".join(f"{k}={v!r}" for k, v in self.__dict__.items())
            return f"{self.__class__.__name__}({fields})"

        def __eq__(self, other):
            if isinstance(other, self.__class__):
                return self.__dict__ == other.__dict__
            return False

    def Field(default=None, default_factory=None, **kwargs):
        if default_factory is not None:
            return default_factory()
        return default


class CasTransactionRecord(BaseModel):
    """
    Individual mutual fund transaction line within a scheme folio.
    """
    date: date
    transaction_type: str  # PURCHASE, SIP, REDEMPTION, DIVIDEND_REINVESTMENT, STAMP_DUTY, SWITCH_IN, SWITCH_OUT
    gross_amount: Decimal = Field(default=Decimal("0.00"))
    stamp_duty: Decimal = Field(default=Decimal("0.00"))
    net_amount: Decimal = Field(default=Decimal("0.00"))
    nav: Decimal = Field(default=Decimal("0.00"))
    units: Decimal = Field(default=Decimal("0.000"))
    unit_balance: Decimal = Field(default=Decimal("0.000"))
    description: Optional[str] = None


class NormalizedCasScheme(BaseModel):
    """
    Individual Mutual Fund Scheme belonging to a Folio in CAS.
    """
    folio_number: str
    amc_name: str
    scheme_name: str
    amfi_code: Optional[str] = None
    isin: Optional[str] = None
    advisor: str = "DIRECT"
    opening_unit_balance: Decimal = Field(default=Decimal("0.000"))
    transactions: List[CasTransactionRecord] = Field(default_factory=list)
    closing_unit_balance: Decimal = Field(default=Decimal("0.000"))
    valuation_nav: Decimal = Field(default=Decimal("0.00"))
    closing_market_value_inr: Decimal = Field(default=Decimal("0.00"))


class NormalizedCasFolio(BaseModel):
    """
    Folio grouping under an AMC.
    """
    folio_number: str
    amc_name: str
    pan: str
    schemes: List[NormalizedCasScheme] = Field(default_factory=list)


class NormalizedCasStatement(BaseModel):
    """
    Normalized Consolidated Account Statement representing entire mutual fund holdings across AMCs.
    """
    statement_id: str
    statement_period: str
    investor_name: str
    investor_pan: str
    investor_email: Optional[str] = None
    folios: List[NormalizedCasFolio] = Field(default_factory=list)
    schemes: List[NormalizedCasScheme] = Field(default_factory=list)
