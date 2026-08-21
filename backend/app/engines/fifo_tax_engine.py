"""
FIFO Tax Lot Accounting & Capital Gains Engine (Finance Act 2024 / Budget 2024)
Maintains strict chronological FIFO queues per asset (ISIN/ticker) and entity (portfolio/PAN).

Statutory Capital Gains Rules:
1. Listed Indian Equities & Equity Mutual Funds:
   - Holding period > 12 months (365 days): LTCG taxed at 12.5% (unindexed).
   - Section 112A annual aggregate exemption: ₹1,25,000 across total Indian equity LTCG per financial year.
   - Holding period <= 12 months (365 days): STCG taxed at 20.0% (Section 111A).
2. Foreign Equities (Charles Schwab US / Schedule FA):
   - Holding period > 24 months (730 days): LTCG taxed at 12.5% (unindexed).
   - Holding period <= 24 months (730 days): STCG taxed at applicable income tax slab rate (30.0%).
   - Foreign Tax Credit (FTC) tracking for IRS 1042-S 25% tax withheld (Form 67).
3. Specified Debt Mutual Funds (Section 50AA, acquired on or after 1 April 2023):
   - Deemed Short-Term Capital Gains taxed at slab rate (30.0%) regardless of holding period.
4. Sovereign Gold Bonds (SGB, Section 47):
   - Redemption at maturity: 100% tax exempt (0% tax rate).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from ..models.ledger import (
    ActiveTaxLot,
    CapitalGainsSummary,
    TaxAssetType,
    TaxDispositionRecord,
    TaxLotStatus,
)


class FIFOTaxEngine:
    """
    Chronological FIFO Tax Lot and Capital Gains Accounting Engine.
    """

    def __init__(self):
        # Key: "{portfolio_id}:{asset_id}" -> List of ActiveTaxLot
        self.active_lots: Dict[str, List[Dict[str, Any]]] = {}
        # Historical dispositions log
        self.dispositions_log: List[Dict[str, Any]] = []

    def reset_state(self):
        """Clears in-memory tax lots and dispositions."""
        self.active_lots.clear()
        self.dispositions_log.clear()

    @staticmethod
    def get_financial_year(d: date) -> str:
        """Determines Indian financial year for a given date (e.g. 2024-08-14 -> 'FY2024-25')."""
        if d.month >= 4:
            return f"FY{d.year}-{str(d.year + 1)[-2:]}"
        else:
            return f"FY{d.year - 1}-{str(d.year)[-2:]}"

    def buy_lot(
        self,
        portfolio_id: str,
        asset_id: str,
        asset_type: Union[TaxAssetType, str],
        buy_date: Union[date, datetime, str],
        quantity: Union[Decimal, float, int, str],
        price: Union[Decimal, float, int, str],
        currency: str = "INR",
        forex_rate: Union[Decimal, float, int, str] = Decimal("1.00"),
        expenses: Union[Decimal, float, int, str] = Decimal("0.00"),
        client_pan: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates and registers an open tax lot in the portfolio's asset queue.
        """
        # Parse date
        if isinstance(buy_date, str):
            b_date = datetime.strptime(buy_date[:10], "%Y-%m-%d").date()
        elif isinstance(buy_date, datetime):
            b_date = buy_date.date()
        else:
            b_date = buy_date

        qty_dec = Decimal(str(quantity))
        price_dec = Decimal(str(price))
        forex_dec = Decimal(str(forex_rate))
        expenses_dec = Decimal(str(expenses))
        type_str = asset_type.value if hasattr(asset_type, "value") else str(asset_type).upper()

        key = f"{portfolio_id}:{asset_id}"
        if key not in self.active_lots:
            self.active_lots[key] = []

        cost_per_unit_inr = (price_dec * forex_dec).quantize(Decimal("0.01"))
        expenses_per_unit = (expenses_dec / qty_dec).quantize(Decimal("0.01")) if qty_dec > Decimal("0.00") else Decimal("0.00")

        lot_id = f"lot_{key}_{len(self.active_lots[key]) + 1}_{int(datetime.now().timestamp() * 1000)}"

        lot = {
            "lot_id": lot_id,
            "portfolio_id": portfolio_id,
            "client_pan": client_pan or "",
            "asset_id": asset_id,
            "symbol": symbol or asset_id,
            "asset_type": type_str,
            "purchase_date": b_date,
            "acquisition_date": b_date,
            "initial_quantity": qty_dec,
            "remaining_quantity": qty_dec,
            "cost_per_unit": price_dec,
            "cost_per_unit_inr": cost_per_unit_inr,
            "expenses_per_unit": expenses_per_unit,
            "currency": currency,
            "forex_rate": forex_dec,
            "status": "ACTIVE",
        }

        self.active_lots[key].append(lot)
        return lot

    def sell_units(
        self,
        portfolio_id: str,
        asset_id: str,
        asset_type: Union[TaxAssetType, str],
        sell_date: Union[date, datetime, str],
        quantity: Union[Decimal, float, int, str],
        sell_price: Union[Decimal, float, int, str],
        currency: str = "INR",
        forex_rate: Union[Decimal, float, int, str] = Decimal("1.00"),
        expenses: Union[Decimal, float, int, str] = Decimal("0.00"),
        client_pan: Optional[str] = None,
        foreign_tax_withheld_usd: Union[Decimal, float, int, str] = Decimal("0.00"),
    ) -> List[Dict[str, Any]]:
        """
        Depletes active lots chronologically (FIFO) and computes realized gains,
        holding period, and statutory tax liabilities under Finance Act 2024.
        """
        if isinstance(sell_date, str):
            s_date = datetime.strptime(sell_date[:10], "%Y-%m-%d").date()
        elif isinstance(sell_date, datetime):
            s_date = sell_date.date()
        else:
            s_date = sell_date

        qty_to_sell = Decimal(str(quantity))
        price_dec = Decimal(str(sell_price))
        forex_dec = Decimal(str(forex_rate))
        tax_withheld_usd_dec = Decimal(str(foreign_tax_withheld_usd))
        type_str = asset_type.value if hasattr(asset_type, "value") else str(asset_type).upper()

        key = f"{portfolio_id}:{asset_id}"
        lots = self.active_lots.get(key, [])

        # Sort lots strictly by purchase date (FIFO)
        lots.sort(key=lambda x: x["purchase_date"])

        remaining_to_sell = qty_to_sell
        dispositions: List[Dict[str, Any]] = []

        for lot in lots:
            if remaining_to_sell <= Decimal("0.00"):
                break
            if lot["remaining_quantity"] <= Decimal("0.00"):
                continue

            matched_qty = min(remaining_to_sell, lot["remaining_quantity"])
            holding_days = (s_date - lot["purchase_date"]).days

            # Statutory Classification under Finance Act 2024:
            # 1. Specified Debt Mutual Funds (Section 50AA)
            if type_str in ("DEBT_MUTUAL_FUND", "DEBT_MF"):
                is_long_term = False
                tax_rate_pct = Decimal("30.00")
                section = "50AA"
            # 2. Sovereign Gold Bonds held to maturity (Section 47)
            elif type_str in ("SGB_MATURITY", "SGB_REDEMPTION"):
                is_long_term = True
                tax_rate_pct = Decimal("0.00")
                section = "47"
            # 3. Foreign Equities (Charles Schwab US / Schedule FA) -> 24 Month threshold
            elif type_str in ("US_EQUITY", "FOREIGN_EQUITY", "US_STOCKS"):
                is_long_term = holding_days > 730  # > 24 months
                tax_rate_pct = Decimal("12.50") if is_long_term else Decimal("30.00")
                section = "SCHEDULE_FA"
            # 4. Listed Indian Equities & Equity Mutual Funds -> 12 Month threshold
            else:
                is_long_term = holding_days > 365  # > 12 months
                tax_rate_pct = Decimal("12.50") if is_long_term else Decimal("20.00")
                section = "112A" if is_long_term else "111A"

            cost_basis_inr = (matched_qty * lot["cost_per_unit_inr"]).quantize(Decimal("0.01"))
            sale_proceeds_inr = (matched_qty * price_dec * forex_dec).quantize(Decimal("0.01"))
            realized_gain_inr = sale_proceeds_inr - cost_basis_inr

            # Calculate estimated tax before annual aggregate exemption
            if realized_gain_inr > Decimal("0.00"):
                estimated_tax_inr = (realized_gain_inr * (tax_rate_pct / Decimal("100.00"))).quantize(Decimal("0.01"))
            else:
                estimated_tax_inr = Decimal("0.00")

            foreign_tax_withheld_inr = (tax_withheld_usd_dec * forex_dec).quantize(Decimal("0.01"))

            disp = {
                "disposition_id": f"disp_{lot['lot_id']}_{len(dispositions) + 1}",
                "lot_id": lot["lot_id"],
                "portfolio_id": portfolio_id,
                "client_pan": client_pan or lot.get("client_pan", ""),
                "asset_id": asset_id,
                "symbol": lot.get("symbol", asset_id),
                "asset_type": type_str,
                "matched_quantity": matched_qty,
                "acquisition_date": lot["purchase_date"],
                "sale_date": s_date,
                "holding_days": holding_days,
                "is_long_term": is_long_term,
                "cost_basis_inr": cost_basis_inr,
                "sale_proceeds_inr": sale_proceeds_inr,
                "realized_gain_inr": realized_gain_inr,
                "tax_rate_pct": tax_rate_pct,
                "estimated_tax_inr": estimated_tax_inr,
                "foreign_tax_withheld_usd": tax_withheld_usd_dec,
                "foreign_tax_withheld_inr": foreign_tax_withheld_inr,
                "foreign_tax_credit_eligible": foreign_tax_withheld_inr > Decimal("0.00"),
                "section": section,
                "financial_year": self.get_financial_year(s_date),
            }
            dispositions.append(disp)
            self.dispositions_log.append(disp)

            lot["remaining_quantity"] -= matched_qty
            if lot["remaining_quantity"] <= Decimal("0.00001"):
                lot["remaining_quantity"] = Decimal("0.00")
                lot["status"] = "EXHAUSTED"
            else:
                lot["status"] = "PARTIALLY_DEPLETED"

            remaining_to_sell -= matched_qty

        # Oversell validation guard
        if remaining_to_sell > Decimal("0.00001"):
            available_total = qty_to_sell - remaining_to_sell
            raise ValueError(
                f"Oversell condition: Sold {qty_to_sell} units of '{asset_id}' in portfolio '{portfolio_id}', "
                f"but only {available_total} units available in active lots."
            )

        return dispositions

    def get_open_lots(
        self,
        portfolio_id: Optional[str] = None,
        asset_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Returns active open tax lots with remaining quantity > 0."""
        res: List[Dict[str, Any]] = []
        for key, lot_list in self.active_lots.items():
            port, a_id = key.split(":", 1)
            if portfolio_id and port != portfolio_id:
                continue
            if asset_id and a_id != asset_id:
                continue
            for lot in lot_list:
                if lot["remaining_quantity"] > Decimal("0.00"):
                    res.append(lot)
        return res

    def get_dispositions(
        self,
        portfolio_id: Optional[str] = None,
        financial_year: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Returns tax dispositions filtered by portfolio and financial year."""
        res = []
        for d in self.dispositions_log:
            if portfolio_id and d["portfolio_id"] != portfolio_id:
                continue
            if financial_year and d.get("financial_year") != financial_year:
                continue
            res.append(d)
        return res

    def compute_capital_gains_summary(
        self,
        portfolio_id: str,
        financial_year: Optional[str] = None,
    ) -> CapitalGainsSummary:
        """
        Computes aggregate capital gains tax summary including Section 112A ₹1,25,000 exemption.
        """
        disps = self.get_dispositions(portfolio_id=portfolio_id, financial_year=financial_year)
        
        total_stcg = Decimal("0.00")
        total_ltcg_112a = Decimal("0.00")
        total_ltcg_other = Decimal("0.00")
        total_ftc = Decimal("0.00")
        disposition_records: List[TaxDispositionRecord] = []

        for d in disps:
            gain = d["realized_gain_inr"]
            if d["is_long_term"]:
                if d.get("section") == "112A":
                    total_ltcg_112a += gain
                elif d.get("section") != "47":  # Exclude tax-exempt SGB
                    total_ltcg_other += gain
            else:
                total_stcg += gain

            total_ftc += d.get("foreign_tax_withheld_inr", Decimal("0.00"))

            disp_record = TaxDispositionRecord(
                disposition_id=d["disposition_id"],
                lot_id=d["lot_id"],
                portfolio_id=d["portfolio_id"],
                client_pan=d["client_pan"],
                asset_id=d["asset_id"],
                symbol=d["symbol"],
                asset_type=d["asset_type"],
                matched_quantity=d["matched_quantity"],
                acquisition_date=d["acquisition_date"],
                sale_date=d["sale_date"],
                holding_days=d["holding_days"],
                is_long_term=d["is_long_term"],
                cost_basis_inr=d["cost_basis_inr"],
                sale_proceeds_inr=d["sale_proceeds_inr"],
                realized_gain_inr=d["realized_gain_inr"],
                tax_rate_pct=d["tax_rate_pct"],
                estimated_tax_inr=d["estimated_tax_inr"],
                foreign_tax_withheld_usd=d.get("foreign_tax_withheld_usd", Decimal("0.00")),
                foreign_tax_withheld_inr=d.get("foreign_tax_withheld_inr", Decimal("0.00")),
                foreign_tax_credit_eligible=d.get("foreign_tax_credit_eligible", False),
                section=d.get("section"),
            )
            disposition_records.append(disp_record)

        # Section 112A LTCG Exemption: ₹1,25,000 across total Indian equity LTCG
        section_112a_exemption = min(max(Decimal("0.00"), total_ltcg_112a), Decimal("125000.00"))
        taxable_ltcg_112a = max(Decimal("0.00"), total_ltcg_112a - section_112a_exemption)

        # Tax calculations under Finance Act 2024
        tax_112a = (taxable_ltcg_112a * Decimal("0.125")).quantize(Decimal("0.01"))
        tax_ltcg_other = (max(Decimal("0.00"), total_ltcg_other) * Decimal("0.125")).quantize(Decimal("0.01"))
        
        # Domestic STCG 20% + Foreign/Debt STCG 30%
        # For simplicity, calculate from individual itemized dispositions
        tax_stcg = Decimal("0.00")
        for d in disps:
            if not d["is_long_term"] and d["realized_gain_inr"] > Decimal("0.00"):
                tax_stcg += (d["realized_gain_inr"] * (d["tax_rate_pct"] / Decimal("100.00"))).quantize(Decimal("0.01"))

        total_tax = tax_112a + tax_ltcg_other + tax_stcg
        total_ltcg = total_ltcg_112a + total_ltcg_other

        return CapitalGainsSummary(
            portfolio_id=portfolio_id,
            financial_year=financial_year or "ALL",
            total_stcg_inr=total_stcg,
            total_ltcg_inr=total_ltcg,
            section_112a_exemption_inr=section_112a_exemption,
            taxable_ltcg_inr=taxable_ltcg_112a + max(Decimal("0.00"), total_ltcg_other),
            total_tax_inr=total_tax,
            total_foreign_tax_credit_inr=total_ftc,
            dispositions=disposition_records,
        )


# Global default instance
_default_fifo_engine = FIFOTaxEngine()
