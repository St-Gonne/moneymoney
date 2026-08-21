"""
Synthetic Zerodha Contract Note (ECN) & Tradebook CSV Fixtures
"""
from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal
from typing import List, Dict, Any, Optional

@dataclass
class SyntheticTradeRow:
    order_no: str
    trade_no: str
    trade_time: str
    security_name: str
    isin: str
    action: str # BUY / SELL
    quantity: Decimal
    gross_rate: Decimal
    brokerage_per_unit: Decimal = Decimal("0.00")
    net_rate: Decimal = field(init=False)
    gross_total: Decimal = field(init=False)
    net_total: Decimal = field(init=False)

    def __post_init__(self):
        self.net_rate = self.gross_rate
        self.gross_total = (self.quantity * self.gross_rate).quantize(Decimal("0.01"))
        self.net_total = self.gross_total

@dataclass
class SyntheticZerodhaStatement:
    contract_note_no: str
    trade_date: date
    settlement_date: date
    settlement_no: str
    client_code: str
    client_pan: str
    client_name: str
    trades: List[SyntheticTradeRow]
    # Charges
    brokerage: Decimal
    stt: Decimal
    exchange_turnover_fee: Decimal
    sebi_turnover_fee: Decimal
    stamp_duty: Decimal
    cgst: Decimal
    sgst: Decimal
    igst: Decimal
    net_settlement_amount: Decimal
    currency: str = "INR"

    def to_csv_string(self) -> str:
        """Export as Zerodha Console / Tradebook CSV export"""
        lines = ["symbol,isin,trade_date,exchange,segment,series,trade_type,quantity,price,order_id,trade_id"]
        for t in self.trades:
            sym = t.security_name.split()[0]
            ttype = "buy" if t.action.upper() == "BUY" else "sell"
            lines.append(f"{sym},{t.isin},{self.trade_date.isoformat()},NSE,EQ,EQ,{ttype},{t.quantity},{t.gross_rate},{t.order_no},{t.trade_no}")
        return "\n".join(lines)

    def to_raw_text(self) -> str:
        """Synthetic text representation resembling pdfplumber extracted text"""
        out = []
        out.append("================================================================================")
        out.append("                              ZERODHA BROKING LTD                               ")
        out.append("                  SEBI Registration No. INZ000031633 / NSE / BSE                 ")
        out.append("                         CONTRACT NOTE CUM TAX INVOICE                          ")
        out.append("================================================================================")
        out.append(f"Contract Note No : {self.contract_note_no}       Trade Date      : {self.trade_date.strftime('%d-%m-%Y')}")
        out.append(f"Settlement No    : {self.settlement_no}              Settlement Date : {self.settlement_date.strftime('%d-%m-%Y')}")
        out.append(f"Client Code      : {self.client_code}                   Client PAN      : {self.client_pan}")
        out.append(f"Client Name      : {self.client_name}")
        out.append("--------------------------------------------------------------------------------")
        out.append("Order No         Trade No   Time     Security / ISIN              B/S  Qty   Gross Rate  Net Total")
        out.append("--------------------------------------------------------------------------------")
        for t in self.trades:
            bs = "B" if t.action.upper() == "BUY" else "S"
            out.append(f"{t.order_no:<16} {t.trade_no:<10} {t.trade_time:<8} {t.security_name:<28} {bs:<4} {t.quantity:>5} {t.gross_rate:>10.2f} {t.gross_total:>11.2f}")
            out.append(f"                 ISIN: {t.isin}")
        out.append("--------------------------------------------------------------------------------")
        out.append("CHARGES BREAKDOWN:")
        out.append(f"Pay in / Pay out Obligation (Gross): {sum(t.gross_total if t.action == 'SELL' else -t.gross_total for t in self.trades):.2f}")
        out.append(f"Brokerage                          : {self.brokerage:.2f}")
        out.append(f"Securities Transaction Tax (STT)   : {self.stt:.2f}")
        out.append(f"Exchange Turnover Charges          : {self.exchange_turnover_fee:.2f}")
        out.append(f"SEBI Turnover Fees                 : {self.sebi_turnover_fee:.2f}")
        out.append(f"Stamp Duty                         : {self.stamp_duty:.2f}")
        out.append(f"CGST (9%)                          : {self.cgst:.2f}")
        out.append(f"SGST (9%)                          : {self.sgst:.2f}")
        out.append(f"IGST (18%)                         : {self.igst:.2f}")
        out.append("--------------------------------------------------------------------------------")
        out.append(f"Net Amount Receivable / (Payable)  : {self.net_settlement_amount:.2f}")
        out.append("================================================================================")
        return "\n".join(out)


def build_valid_zerodha_statement(
    trade_date: date = date(2024, 8, 14),
    pan: str = "KLMNO9012P",
    client_name: str = "Alex Taylor",
    client_code: str = "ZR1102",
) -> SyntheticZerodhaStatement:
    """
    Constructs a mathematically consistent Zerodha Delivery Contract Note.
    Trade 1: BUY 800 TATA MOTORS @ 480.00 = 3,84,000.00
    Trade 2: BUY 100 INFY @ 1,500.00 = 1,50,000.00
    Total Gross Outflow = 5,34,000.00
    Brokerage = 0.00 (Zero brokerage on delivery)
    STT (0.1% on delivery buy) = 534.00
    Exchange Turnover Fee (NSE 0.00297%) = 15.86
    SEBI Turnover Fee (₹10/crore = 0.0001%) = 0.53
    Stamp Duty (0.015% on buy) = 80.10
    Taxable Charges = 0.00 + 15.86 + 0.53 = 16.39
    CGST (9% of 16.39) = 1.48
    SGST (9% of 16.39) = 1.48
    Total Charges = 0.00 + 534.00 + 15.86 + 0.53 + 80.10 + 1.48 + 1.48 = 633.45
    Net Settlement Amount (Payable) = - (534000.00 + 633.45) = -534633.45
    """
    t1 = SyntheticTradeRow(
        order_no="1100000028471920",
        trade_no="84920194",
        trade_time="10:14:32",
        security_name="TATA MOTORS LTD - EQ",
        isin="INE155A01022",
        action="BUY",
        quantity=Decimal("800"),
        gross_rate=Decimal("480.00"),
    )
    t2 = SyntheticTradeRow(
        order_no="1100000028471921",
        trade_no="84920195",
        trade_time="11:20:15",
        security_name="INFOSYS LTD - EQ",
        isin="INE009A01021",
        action="BUY",
        quantity=Decimal("100"),
        gross_rate=Decimal("1500.00"),
    )
    return SyntheticZerodhaStatement(
        contract_note_no="CN20240814-ZR1102",
        trade_date=trade_date,
        settlement_date=date(2024, 8, 16),
        settlement_no="2024154",
        client_code=client_code,
        client_pan=pan,
        client_name=client_name,
        trades=[t1, t2],
        brokerage=Decimal("0.00"),
        stt=Decimal("534.00"),
        exchange_turnover_fee=Decimal("15.86"),
        sebi_turnover_fee=Decimal("0.53"),
        stamp_duty=Decimal("80.10"),
        cgst=Decimal("1.48"),
        sgst=Decimal("1.48"),
        igst=Decimal("0.00"),
        net_settlement_amount=Decimal("-534633.45"),
    )


def build_corrupted_math_zerodha_statement() -> SyntheticZerodhaStatement:
    """Statement with intentional ₹50.00 math discrepancy to test Gate 3 fail-closed rejection"""
    stmt = build_valid_zerodha_statement()
    # Inject discrepancy into net settlement
    stmt.net_settlement_amount = Decimal("-534583.45") # 50 rupee missing error
    return stmt
