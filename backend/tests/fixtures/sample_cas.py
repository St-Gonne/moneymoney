"""
Synthetic CAMS / KFintech Mutual Fund Consolidated Account Statement (CAS) Fixtures
"""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import List, Dict, Any, Optional

@dataclass
class SyntheticCasTx:
    tx_date: date
    tx_type: str # PURCHASE, SIP, REDEMPTION, DIVIDEND_REINVESTMENT, STAMP_DUTY
    gross_amount: Decimal
    stamp_duty: Decimal # 0.005% post July 1, 2020
    net_amount: Decimal
    nav: Decimal
    units: Decimal
    unit_balance: Decimal

@dataclass
class SyntheticCasScheme:
    folio_number: str
    amc_name: str
    scheme_name: str
    amfi_code: str
    isin: str
    advisor: str = "DIRECT"
    opening_unit_balance: Decimal = Decimal("0.000")
    transactions: List[SyntheticCasTx] = field(default_factory=list)
    closing_unit_balance: Decimal = Decimal("0.000")
    valuation_nav: Decimal = Decimal("0.000")
    closing_market_value: Decimal = Decimal("0.00")

@dataclass
class SyntheticCasStatement:
    statement_period: str
    investor_name: str
    investor_pan: str
    investor_email: str
    schemes: List[SyntheticCasScheme]

    def to_cas_dict(self) -> Dict[str, Any]:
        """Returns structured dictionary resembling casparser parsed output"""
        folios_out = []
        for s in self.schemes:
            tx_list = []
            for t in s.transactions:
                tx_list.append({
                    "date": t.tx_date.isoformat(),
                    "description": t.tx_type,
                    "amount": float(t.gross_amount),
                    "units": float(t.units),
                    "nav": float(t.nav),
                    "balance": float(t.unit_balance),
                    "type": t.tx_type,
                    "stamp_duty": float(t.stamp_duty),
                })
            folios_out.append({
                "folio": s.folio_number,
                "amc": s.amc_name,
                "PAN": self.investor_pan,
                "schemes": [{
                    "scheme": s.scheme_name,
                    "amfi": s.amfi_code,
                    "isin": s.isin,
                    "advisor": s.advisor,
                    "open": float(s.opening_unit_balance),
                    "close": float(s.closing_unit_balance),
                    "valuation": {
                        "date": "2024-08-14",
                        "nav": float(s.valuation_nav),
                        "value": float(s.closing_market_value),
                    },
                    "transactions": tx_list
                }]
            })
        return {
            "statement_period": {"from": "2023-01-01", "to": "2024-08-14"},
            "investor_info": {
                "name": self.investor_name,
                "email": self.investor_email,
                "pan": self.investor_pan,
            },
            "folios": folios_out
        }


def build_valid_cams_statement(
    pan: str = "KLMNO9012P",
    name: str = "Alex Taylor",
    email: str = "alex.taylor@example.com",
) -> SyntheticCasStatement:
    """
    Constructs a verified CAMS statement with Quant Active Fund transactions and continuous unit balance.
    Tx 1 (2023-05-18): Initial Purchase ₹10,00,000. Stamp Duty ₹50.00 (0.005%). Net ₹9,99,950. NAV 465.10. Units = 2149.968. Balance = 2149.968
    Tx 2 (2023-06-10): SIP ₹50,000. Stamp Duty ₹2.50. Net ₹49,997.50. NAV 480.00. Units = 104.161. Balance = 2254.129
    Tx 3 (2024-08-10): Redemption 500 units @ NAV 620.00 = Gross ₹3,10,000. Units = -500.000. Balance = 1754.129
    Closing Balance = 1754.129 units.
    Valuation NAV = 625.00 -> Market Value = 1754.129 * 625.00 = ₹10,96,330.63
    """
    s1 = SyntheticCasScheme(
        folio_number="4481023/1",
        amc_name="Quant Mutual Fund",
        scheme_name="Quant Active Fund - Direct Plan - Growth",
        amfi_code="100085",
        isin="INF966L01AA3",
        advisor="DIRECT",
        opening_unit_balance=Decimal("0.000"),
        transactions=[
            SyntheticCasTx(
                tx_date=date(2023, 5, 18),
                tx_type="PURCHASE",
                gross_amount=Decimal("1000000.00"),
                stamp_duty=Decimal("50.00"),
                net_amount=Decimal("999950.00"),
                nav=Decimal("465.10"),
                units=Decimal("2149.968"),
                unit_balance=Decimal("2149.968"),
            ),
            SyntheticCasTx(
                tx_date=date(2023, 6, 10),
                tx_type="SIP",
                gross_amount=Decimal("50000.00"),
                stamp_duty=Decimal("2.50"),
                net_amount=Decimal("49997.50"),
                nav=Decimal("480.00"),
                units=Decimal("104.161"),
                unit_balance=Decimal("2254.129"),
            ),
            SyntheticCasTx(
                tx_date=date(2024, 8, 10),
                tx_type="REDEMPTION",
                gross_amount=Decimal("310000.00"),
                stamp_duty=Decimal("0.00"),
                net_amount=Decimal("310000.00"),
                nav=Decimal("620.00"),
                units=Decimal("-500.000"),
                unit_balance=Decimal("1754.129"),
            ),
        ],
        closing_unit_balance=Decimal("1754.129"),
        valuation_nav=Decimal("625.00"),
        closing_market_value=Decimal("1096330.63"),
    )
    return SyntheticCasStatement(
        statement_period="01-Jan-2023 to 14-Aug-2024",
        investor_name=name,
        investor_pan=pan,
        investor_email=email,
        schemes=[s1],
    )


def build_corrupted_cams_statement() -> SyntheticCasStatement:
    """CAMS statement with broken unit continuity for fail-closed validation test"""
    stmt = build_valid_cams_statement()
    # Mutate unit balance in Tx 2 to introduce a break in balance continuity
    stmt.schemes[0].transactions[1].unit_balance = Decimal("2999.000") # False leap
    return stmt
