"""
Synthetic Charles Schwab US Statement & CSV Activity Fixtures
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import List, Optional

@dataclass
class SyntheticSchwabRow:
    tx_date: date
    action: str # Buy, Sell, Reinvest Dividend, Qual Dividend, Tax Withholding
    symbol: str
    description: str
    quantity: Optional[Decimal]
    price: Optional[Decimal]
    fees_and_comm: Decimal
    amount: Decimal # Net cash flow in USD

@dataclass
class SyntheticSchwabStatement:
    account_number: str
    account_holder: str
    statement_period: str
    rows: List[SyntheticSchwabRow]

    def to_csv_string(self) -> str:
        lines = [
            f'"Transactions  for account {self.account_number} as of 08/14/2026"',
            '"Date","Action","Symbol","Description","Quantity","Price","Fees & Comm","Amount"'
        ]
        for r in self.rows:
            d_str = r.tx_date.strftime("%m/%d/%Y")
            qty_str = f"{r.quantity}" if r.quantity is not None else ""
            price_str = f"${r.price:.2f}" if r.price is not None else ""
            fee_str = f"${r.fees_and_comm:.2f}" if r.fees_and_comm > 0 else ""
            amt_str = f"${r.amount:.2f}" if r.amount >= 0 else f"-${abs(r.amount):.2f}"
            lines.append(f'"{d_str}","{r.action}","{r.symbol}","{r.description}","{qty_str}","{price_str}","{fee_str}","{amt_str}"')
        return "\n".join(lines)


def build_valid_schwab_statement(
    account_number: str = "84920194",
    account_holder: str = "Alex Taylor",
) -> SyntheticSchwabStatement:
    """
    Constructs realistic Charles Schwab US Activity records for Alex Taylor:
    1. 2023-05-18: Buy 150 NVDA @ $62.40 = -$9,360.00
    2. 2023-11-15: Qual Dividend NVDA = +$24.00 (Gross Dividend)
    3. 2023-11-15: Tax Withholding (IRS 1042-S 25% NRA withholding) = -$6.00
    4. 2024-02-20: Reinvest Dividend 0.05 VOO @ $450.00 = -$22.50
    5. 2024-08-10: Sell 50 NVDA @ $125.00 = Gross $6,250.00, SEC Fee $0.17 -> Net +$6,249.83
    """
    rows = [
        SyntheticSchwabRow(
            tx_date=date(2023, 5, 18),
            action="Buy",
            symbol="NVDA",
            description="NVIDIA CORPORATION",
            quantity=Decimal("150.000"),
            price=Decimal("62.40"),
            fees_and_comm=Decimal("0.00"),
            amount=Decimal("-9360.00"),
        ),
        SyntheticSchwabRow(
            tx_date=date(2023, 11, 15),
            action="Qual Dividend",
            symbol="NVDA",
            description="NVIDIA CORPORATION CASH DIVIDEND",
            quantity=None,
            price=None,
            fees_and_comm=Decimal("0.00"),
            amount=Decimal("24.00"),
        ),
        SyntheticSchwabRow(
            tx_date=date(2023, 11, 15),
            action="Tax Withholding",
            symbol="NVDA",
            description="IRS 1042-S 25% NRA TAX WITHHELD",
            quantity=None,
            price=None,
            fees_and_comm=Decimal("0.00"),
            amount=Decimal("-6.00"),
        ),
        SyntheticSchwabRow(
            tx_date=date(2024, 2, 20),
            action="Reinvest Dividend",
            symbol="VOO",
            description="VANGUARD S&P 500 ETF REINVESTMENT",
            quantity=Decimal("0.050"),
            price=Decimal("450.00"),
            fees_and_comm=Decimal("0.00"),
            amount=Decimal("-22.50"),
        ),
        SyntheticSchwabRow(
            tx_date=date(2024, 8, 10),
            action="Sell",
            symbol="NVDA",
            description="NVIDIA CORPORATION",
            quantity=Decimal("50.000"),
            price=Decimal("125.00"),
            fees_and_comm=Decimal("0.17"),
            amount=Decimal("6249.83"),
        ),
    ]
    return SyntheticSchwabStatement(
        account_number=account_number,
        account_holder=account_holder,
        statement_period="01/01/2023 to 08/14/2024",
        rows=rows,
    )


def build_corrupted_schwab_statement() -> SyntheticSchwabStatement:
    """Schwab statement with broken math (withholding mismatch)"""
    stmt = build_valid_schwab_statement()
    # Gross dividend $24, but withholding $15 (62.5% instead of 25%)
    stmt.rows[2].amount = Decimal("-15.00")
    return stmt
