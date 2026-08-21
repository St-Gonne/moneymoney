"""
Normalized Contract Note and Trade Execution Models
Defines canonical data structures for broker contract notes, trades, and statutory levy breakdowns.
"""

from datetime import date, time, datetime
from decimal import Decimal
from enum import Enum
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
                elif isinstance(v, Enum):
                    res[k] = v.value
                elif isinstance(v, Decimal):
                    res[k] = float(v)
                elif isinstance(v, (date, time, datetime)):
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


class BrokerInstitution(str, Enum):
    ZERODHA = "ZERODHA"
    HDFC_SECURITIES = "HDFC_SECURITIES"
    CAMS_KFINTECH = "CAMS_KFINTECH"
    CHARLES_SCHWAB = "CHARLES_SCHWAB"


class TradedSegment(str, Enum):
    EQUITY_DELIVERY = "EQUITY_DELIVERY"
    EQUITY_INTRADAY = "EQUITY_INTRADAY"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"
    MUTUAL_FUND = "MUTUAL_FUND"
    US_EQUITY = "US_EQUITY"
    SGB = "SGB"
    OTHER = "OTHER"


class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    SIP = "SIP"
    DIVIDEND_REINVEST = "DIVIDEND_REINVEST"
    CASH_DIVIDEND = "CASH_DIVIDEND"
    TAX_WITHHOLDING_1042S = "TAX_WITHHOLDING_1042S"
    BONUS = "BONUS"
    SPLIT = "SPLIT"
    REDEMPTION = "REDEMPTION"
    STAMP_DUTY = "STAMP_DUTY"
    SWITCH_IN = "SWITCH_IN"
    SWITCH_OUT = "SWITCH_OUT"


class BrokerLevyBreakdown(BaseModel):
    """
    Itemized breakdown of broker commissions, exchange levies, statutory taxes, and GST.
    """
    brokerage: Decimal = Field(default=Decimal("0.00"))
    stt: Decimal = Field(default=Decimal("0.00"))
    exchange_turnover_fee: Decimal = Field(default=Decimal("0.00"))
    sebi_turnover_fee: Decimal = Field(default=Decimal("0.00"))
    stamp_duty: Decimal = Field(default=Decimal("0.00"))
    cgst: Decimal = Field(default=Decimal("0.00"))
    sgst: Decimal = Field(default=Decimal("0.00"))
    igst: Decimal = Field(default=Decimal("0.00"))
    demat_charges: Decimal = Field(default=Decimal("0.00"))
    sec_fee_usd: Decimal = Field(default=Decimal("0.00"))
    total_charges_inr: Decimal = Field(default=Decimal("0.00"))

    def compute_total_inr(self) -> Decimal:
        """Calculates sum of all INR levies."""
        total = (
            self.brokerage
            + self.stt
            + self.exchange_turnover_fee
            + self.sebi_turnover_fee
            + self.stamp_duty
            + self.cgst
            + self.sgst
            + self.igst
            + self.demat_charges
        )
        self.total_charges_inr = total.quantize(Decimal("0.01"))
        return self.total_charges_inr


class NormalizedTradeItem(BaseModel):
    """
    Individual execution line item from contract notes or trade activity.
    """
    trade_id: str
    order_id: Optional[str] = None
    trade_time: Optional[Union[time, str]] = None
    symbol: str
    security_name: str
    isin: Optional[str] = None
    action: Union[TradeAction, str]
    segment: Union[TradedSegment, str] = TradedSegment.EQUITY_DELIVERY
    quantity: Decimal
    gross_price: Decimal
    net_price: Decimal
    gross_total: Decimal
    net_total: Decimal
    brokerage: Decimal = Field(default=Decimal("0.00"))
    exchange: Optional[str] = None
    currency: str = "INR"


class NormalizedContractNote(BaseModel):
    """
    Normalized AST representation of an Electronic Contract Note (ECN) cum Tax Invoice.
    """
    statement_id: str
    institution: Union[BrokerInstitution, str]
    contract_note_number: str
    trade_date: date
    settlement_date: Optional[date] = None
    settlement_number: Optional[str] = None
    account_number: str
    client_pan: str
    client_name: str
    trades: List[NormalizedTradeItem] = Field(default_factory=list)
    levies: BrokerLevyBreakdown = Field(default_factory=BrokerLevyBreakdown)
    net_settlement_amount: Decimal = Field(default=Decimal("0.00"))
    currency: str = "INR"
    forex_rate_to_inr: Decimal = Field(default=Decimal("1.00"))
    math_validation_passed: bool = False
    validation_discrepancy: Decimal = Field(default=Decimal("0.00"))
