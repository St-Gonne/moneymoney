"""
Synthetic HDFC Securities Contract Note Fixtures
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List

@dataclass
class SyntheticHDFCTradeRow:
    exchange: str # NSE / BSE
    scrip_name: str
    isin: str
    action: str # BUY / SELL
    quantity: Decimal
    gross_rate: Decimal
    brokerage: Decimal
    gross_total: Decimal = field(init=False)
    net_total: Decimal = field(init=False)

    def __post_init__(self):
        self.gross_total = (self.quantity * self.gross_rate).quantize(Decimal("0.01"))
        if self.action.upper() == "BUY":
            self.net_total = self.gross_total + self.brokerage
        else:
            self.net_total = self.gross_total - self.brokerage

@dataclass
class SyntheticHDFCStatement:
    contract_note_no: str
    trade_date: date
    settlement_no: str
    trading_acc_no: str
    demat_client_id: str
    client_pan: str
    client_name: str
    trades: List[SyntheticHDFCTradeRow]
    # Charges
    total_brokerage: Decimal
    stt: Decimal
    exchange_turnover: Decimal
    sebi_fee: Decimal
    stamp_duty: Decimal
    service_tax_gst: Decimal
    demat_charges: Decimal # Demat allocation e.g. 15.93 (13.50 + GST)
    net_amount: Decimal
    currency: str = "INR"

    def to_raw_text(self) -> str:
        out = []
        out.append("================================================================================")
        out.append("                         HDFC SECURITIES LIMITED                                ")
        out.append("               SEBI Reg. No: INZ000186937 / Member Code: 07714                  ")
        out.append("                       Contract Note Cum Tax Invoice                            ")
        out.append("================================================================================")
        out.append(f"Contract Note No: {self.contract_note_no}       Trade Date: {self.trade_date.strftime('%d/%m/%Y')}")
        out.append(f"Settlement No:    {self.settlement_no}                 PAN:        {self.client_pan}")
        out.append(f"Trading A/c:      {self.trading_acc_no}             Demat ID:   {self.demat_client_id}")
        out.append(f"Client Name:      {self.client_name}")
        out.append("--------------------------------------------------------------------------------")
        out.append("Exch Scrip Description             ISIN         B/S  Qty   Gross Rate  Brokerage  Net Amount")
        out.append("--------------------------------------------------------------------------------")
        for t in self.trades:
            bs = "BUY" if t.action.upper() == "BUY" else "SELL"
            out.append(f"{t.exchange:<4} {t.scrip_name:<28} {t.isin:<12} {bs:<4} {t.quantity:>5} {t.gross_rate:>10.2f} {t.brokerage:>10.2f} {t.net_total:>11.2f}")
        out.append("--------------------------------------------------------------------------------")
        out.append("CHARGES & STATUTORY LEVIES SUMMARY:")
        out.append(f"Total Brokerage                     : {self.total_brokerage:.2f}")
        out.append(f"Securities Transaction Tax (STT)    : {self.stt:.2f}")
        out.append(f"Exchange Turnover Charges           : {self.exchange_turnover:.2f}")
        out.append(f"SEBI Turnover Charges               : {self.sebi_fee:.2f}")
        out.append(f"Stamp Duty                          : {self.stamp_duty:.2f}")
        out.append(f"GST on Brokerage & Charges (18%)    : {self.service_tax_gst:.2f}")
        out.append(f"Demat Allocation Charges (inc GST)  : {self.demat_charges:.2f}")
        out.append("--------------------------------------------------------------------------------")
        out.append(f"Net Amount Payable by Client        : {self.net_amount:.2f}")
        out.append("================================================================================")
        return "\n".join(out)


def build_valid_hdfc_statement(
    trade_date: date = date(2024, 8, 14),
    pan: str = "ABCDE1234F",
    client_name: str = "Robert Taylor",
    trading_acc_no: str = "1092847101",
) -> SyntheticHDFCStatement:
    """
    Constructs a mathematically consistent HDFC Securities Contract Note.
    Trade 1: BUY 600 HDFC BANK LTD @ 1,350.00 = 8,10,000.00
    Brokerage (0.02%) = 162.00
    STT (0.1% on buy) = 810.00
    Exchange Turnover Fee (NSE 0.00297%) = 24.06
    SEBI Fee (0.0001%) = 0.81
    Stamp Duty (0.015%) = 121.50
    Taxable broker services = Brokerage (162.00) + Exch (24.06) + SEBI (0.81) = 186.87
    GST (18% of 186.87) = 33.64
    Demat Allocation Fee = 15.93 (13.50 + 18% GST of 2.43)
    Total Levies = 162.00 + 810.00 + 24.06 + 0.81 + 121.50 + 33.64 + 15.93 = 1167.94
    Net Amount (Payable) = - (810000.00 + 1167.94) = -811167.94
    """
    t1 = SyntheticHDFCTradeRow(
        exchange="NSE",
        scrip_name="HDFC BANK LIMITED",
        isin="INE040A01034",
        action="BUY",
        quantity=Decimal("600"),
        gross_rate=Decimal("1350.00"),
        brokerage=Decimal("162.00"),
    )
    return SyntheticHDFCStatement(
        contract_note_no="HDFC/2024/08/14/009182",
        trade_date=trade_date,
        settlement_no="2024115",
        trading_acc_no=trading_acc_no,
        demat_client_id="1208670000123456",
        client_pan=pan,
        client_name=client_name,
        trades=[t1],
        total_brokerage=Decimal("162.00"),
        stt=Decimal("810.00"),
        exchange_turnover=Decimal("24.06"),
        sebi_fee=Decimal("0.81"),
        stamp_duty=Decimal("121.50"),
        service_tax_gst=Decimal("33.64"),
        demat_charges=Decimal("15.93"),
        net_amount=Decimal("-811167.94"),
    )
