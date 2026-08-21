"""
Normalized Charles Schwab (US) Statement Models
Defines data structures for foreign equity trading activity, dividends, and IRS 1042-S tax withholding.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

try:
    from pydantic import BaseModel, Field
except ImportError:
    class BaseModel:
        def __init__(self, **kwargs):
            # Instantiate fresh copies of default attributes
            for k, v in self.__class__.__dict__.items():
                if not k.startswith("__") and not callable(v):
                    if isinstance(v, list):
                        setattr(self, k, [])
                    elif isinstance(v, dict):
                        setattr(self, k, {})
                    else:
                        setattr(self, k, v)
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


class SchwabRSULot(BaseModel):
    """
    Sub-lot breakdown for RSU / Equity Award sales.
    """
    grant_id: str = ""
    vest_date: Optional[date] = None
    shares: Decimal = Field(default=Decimal("0.0000"))
    vest_fmv_usd: Decimal = Field(default=Decimal("0.00"))
    sale_price_usd: Decimal = Field(default=Decimal("0.00"))
    total_cost_basis_usd: Decimal = Field(default=Decimal("0.00"))
    realized_gain_loss_usd: Decimal = Field(default=Decimal("0.00"))
    holding_period: str = "LONG TERM"  # LONG TERM / SHORT TERM


class NormalizedSchwabRecord(BaseModel):
    """
    Individual transaction line from Charles Schwab CSV Activity or Monthly PDF.
    """
    trade_date: date
    action_raw: str
    canonical_action: str  # BUY, SELL, DIVIDEND_REINVEST, CASH_DIVIDEND, TAX_WITHHOLDING_1042S, TAX_REVERSAL, JOURNAL_TRANSFER, WIRE_TRANSFER, INTEREST, OTHER
    symbol: Optional[str] = None
    description: str = ""
    quantity: Optional[Decimal] = None
    price_usd: Optional[Decimal] = None
    fees_usd: Decimal = Field(default=Decimal("0.00"))
    net_amount_usd: Decimal = Field(default=Decimal("0.00"))
    gross_dividend_usd: Optional[Decimal] = None
    tax_withheld_usd: Optional[Decimal] = None
    target_account: Optional[str] = None  # e.g., "...955" for inter-account journals
    rsu_lots: List[SchwabRSULot] = Field(default_factory=list)


class NormalizedSchwabHolding(BaseModel):
    """
    Position snapshot from Schwab Monthly PDF / Position summary.
    """
    symbol: str
    description: str = ""
    asset_type: str = "EQUITY"  # EQUITY, ETF, CASH
    quantity: Decimal = Field(default=Decimal("0.0000"))
    price_usd: Decimal = Field(default=Decimal("0.00"))
    market_value_usd: Decimal = Field(default=Decimal("0.00"))
    cost_basis_usd: Decimal = Field(default=Decimal("0.00"))
    unrealized_gain_usd: Decimal = Field(default=Decimal("0.00"))


class NormalizedSchwabStatement(BaseModel):
    """
    Normalized AST representation of a Charles Schwab US Account Activity Statement.
    """
    statement_id: str
    account_number: str
    account_holder: str
    statement_period: str
    records: List[NormalizedSchwabRecord] = Field(default_factory=list)
    holdings: List[NormalizedSchwabHolding] = Field(default_factory=list)
    cash_balance_usd: Decimal = Field(default=Decimal("0.00"))
    total_account_value_usd: Decimal = Field(default=Decimal("0.00"))
    total_buy_usd: Decimal = Field(default=Decimal("0.00"))
    total_sell_usd: Decimal = Field(default=Decimal("0.00"))
    total_dividend_usd: Decimal = Field(default=Decimal("0.00"))
    total_tax_withheld_usd: Decimal = Field(default=Decimal("0.00"))
    total_sec_fees_usd: Decimal = Field(default=Decimal("0.00"))

