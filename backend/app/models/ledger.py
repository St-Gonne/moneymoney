"""
Canonical Ledger, Tax Lot, and Portfolio Valuation Models
Defines data structures for canonical ledger transactions, active tax lots,
tax dispositions, capital gains summaries, and portfolio valuation.
"""

from datetime import date, datetime
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


class TransactionStatus(str, Enum):
    PROCESSED = "PROCESSED"
    DUPLICATE_SKIPPED = "DUPLICATE_SKIPPED"
    RECONCILED = "RECONCILED"
    FAILED = "FAILED"


class TaxAssetType(str, Enum):
    EQUITY = "EQUITY"
    INDIAN_EQUITY = "INDIAN_EQUITY"
    MUTUAL_FUND = "MUTUAL_FUND"
    INDIAN_MUTUAL_FUND = "INDIAN_MUTUAL_FUND"
    US_EQUITY = "US_EQUITY"
    DEBT_MUTUAL_FUND = "DEBT_MUTUAL_FUND"
    SGB = "SGB"
    SGB_MATURITY = "SGB_MATURITY"
    GOLD_PHYSICAL = "GOLD_PHYSICAL"
    OTHER = "OTHER"


class TaxHoldingType(str, Enum):
    SHORT_TERM = "SHORT_TERM"
    LONG_TERM = "LONG_TERM"
    EXEMPT = "EXEMPT"


class TaxLotStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PARTIALLY_DEPLETED = "PARTIALLY_DEPLETED"
    EXHAUSTED = "EXHAUSTED"


class CanonicalTransaction(BaseModel):
    """
    Normalized, deduplicated transaction record in canonical family vault ledger.
    """
    transaction_id: str
    statement_id: Optional[str] = None
    statement_hash: Optional[str] = None
    portfolio_id: str
    client_pan: str
    broker: str
    account_number: str
    trade_date: date
    settlement_date: Optional[date] = None
    asset_id: str  # ISIN or Ticker Symbol
    symbol: str
    security_name: str
    action: str  # BUY, SELL, SIP, DIVIDEND, etc.
    quantity: Decimal = Field(default=Decimal("0.0000"))
    price: Decimal = Field(default=Decimal("0.00"))
    gross_amount: Decimal = Field(default=Decimal("0.00"))
    fees_and_charges: Decimal = Field(default=Decimal("0.00"))
    net_amount: Decimal = Field(default=Decimal("0.00"))
    currency: str = "INR"
    forex_rate: Decimal = Field(default=Decimal("1.00"))
    net_amount_inr: Decimal = Field(default=Decimal("0.00"))
    fingerprint: str = ""
    status: Union[TransactionStatus, str] = TransactionStatus.PROCESSED
    created_at: Optional[datetime] = None


class ActiveTaxLot(BaseModel):
    """
    Open tax lot representing unliquidated asset quantities held in a portfolio.
    """
    lot_id: str
    portfolio_id: str
    client_pan: str
    asset_id: str
    symbol: str
    asset_type: Union[TaxAssetType, str] = TaxAssetType.INDIAN_EQUITY
    purchase_date: date
    acquisition_date: Optional[date] = None
    initial_quantity: Decimal
    remaining_quantity: Decimal
    cost_per_unit: Decimal
    currency: str = "INR"
    forex_rate: Decimal = Field(default=Decimal("1.00"))
    cost_per_unit_inr: Decimal = Field(default=Decimal("0.00"))
    expenses_per_unit: Decimal = Field(default=Decimal("0.00"))
    status: Union[TaxLotStatus, str] = TaxLotStatus.ACTIVE

    def __post_init__(self):
        if not self.acquisition_date:
            self.acquisition_date = self.purchase_date


class TaxDispositionRecord(BaseModel):
    """
    Closed or realized tax disposition record when a lot is depleted by a sale or redemption.
    """
    disposition_id: str
    lot_id: str
    portfolio_id: str
    client_pan: str
    asset_id: str
    symbol: str
    asset_type: Union[TaxAssetType, str] = TaxAssetType.INDIAN_EQUITY
    matched_quantity: Decimal
    acquisition_date: date
    sale_date: date
    holding_days: int
    is_long_term: bool
    cost_basis_inr: Decimal
    sale_proceeds_inr: Decimal
    realized_gain_inr: Decimal
    tax_rate_pct: Decimal
    estimated_tax_inr: Decimal
    foreign_tax_withheld_usd: Decimal = Field(default=Decimal("0.00"))
    foreign_tax_withheld_inr: Decimal = Field(default=Decimal("0.00"))
    foreign_tax_credit_eligible: bool = False
    section: Optional[str] = None  # e.g., 112A, 111A, 50AA, 47, SCHEDULE_FA


class PortfolioAssetBalance(BaseModel):
    """
    Aggregated current balance and valuation for an asset in a portfolio.
    """
    portfolio_id: str
    asset_id: str
    symbol: str
    security_name: str
    asset_type: Union[TaxAssetType, str] = TaxAssetType.INDIAN_EQUITY
    total_quantity: Decimal = Field(default=Decimal("0.0000"))
    average_cost_inr: Decimal = Field(default=Decimal("0.00"))
    total_cost_basis_inr: Decimal = Field(default=Decimal("0.00"))
    current_price: Optional[Decimal] = None
    current_valuation_inr: Optional[Decimal] = None
    unrealized_gain_inr: Optional[Decimal] = None
    currency: str = "INR"


class CapitalGainsSummary(BaseModel):
    """
    Financial Year Capital Gains Tax Computation Summary (Budget / Finance Act 2024).
    """
    portfolio_id: str
    financial_year: str
    total_stcg_inr: Decimal = Field(default=Decimal("0.00"))
    total_ltcg_inr: Decimal = Field(default=Decimal("0.00"))
    section_112a_exemption_inr: Decimal = Field(default=Decimal("0.00"))
    taxable_ltcg_inr: Decimal = Field(default=Decimal("0.00"))
    total_tax_inr: Decimal = Field(default=Decimal("0.00"))
    total_foreign_tax_credit_inr: Decimal = Field(default=Decimal("0.00"))
    dispositions: List[TaxDispositionRecord] = Field(default_factory=list)


class StatementReceipt(BaseModel):
    """
    Receipt record for an ingested statement to enforce idempotency.
    """
    statement_hash: str
    institution: str
    account_number: str
    statement_period_start: Optional[date] = None
    statement_period_end: Optional[date] = None
    net_amount: Decimal = Field(default=Decimal("0.00"))
    trades_count: int = 0
    ingested_at: datetime = Field(default_factory=datetime.now)
    status: str = "COMPLETED"
