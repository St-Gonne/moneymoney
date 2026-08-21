"""
RBI Reference Forex Rate Engine (ForexEngine)
Provides historical USD/INR exchange rate conversions based on official RBI / FBIL reference rates:
1. SPOT conversion: Historical reference rate for trade date (with prior business day fallback for weekends/holidays).
2. Rule 115 conversion: Indian Income Tax Rule 115 for foreign income/dividends (rate on last day of month preceding transaction).
3. IRS 1042-S 25% foreign withholding tax conversion for Schedule FA and Form 67 Foreign Tax Credit (FTC).
"""

import calendar
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, Optional, Tuple, Union

from ..config import (
    DEFAULT_USD_INR_RATE,
    HISTORICAL_RBI_FOREX_RATES,
)


class ForexEngine:
    """
    Historical RBI Reference Rate Conversion Engine.
    """

    def __init__(
        self,
        rates_table: Optional[Dict[date, Decimal]] = None,
        default_rate: Decimal = DEFAULT_USD_INR_RATE,
    ):
        self.rates_table: Dict[date, Decimal] = (
            dict(rates_table) if rates_table is not None else dict(HISTORICAL_RBI_FOREX_RATES)
        )
        self.default_rate: Decimal = default_rate

    def get_preceding_month_end(self, tx_date: date) -> date:
        """
        Computes the last calendar day of the month preceding tx_date (Income Tax Rule 115).
        For January transactions (e.g. 2024-01-15), returns 2023-12-31.
        For May transactions (e.g. 2023-05-18), returns 2023-04-30.
        """
        if tx_date.month == 1:
            return date(tx_date.year - 1, 12, 31)
        
        prev_month = tx_date.month - 1
        year = tx_date.year
        _, last_day = calendar.monthrange(year, prev_month)
        return date(year, prev_month, last_day)

    def lookup_rate(
        self,
        tx_date: Union[date, datetime, str],
        mode: str = "SPOT",
    ) -> Decimal:
        """
        Look up RBI reference forex rate with deterministic fallback:
        - mode="SPOT": Uses tx_date directly (or closest prior business day).
        - mode="RULE_115": Uses the last calendar day of the month preceding tx_date.
        """
        # Parse date if necessary
        if isinstance(tx_date, str):
            try:
                d = datetime.strptime(tx_date[:10], "%Y-%m-%d").date()
            except ValueError:
                d = date.today()
        elif isinstance(tx_date, datetime):
            d = tx_date.date()
        else:
            d = tx_date

        if mode.upper() in ("RULE_115", "RULE115"):
            lookup_d = self.get_preceding_month_end(d)
        else:
            lookup_d = d

        # Direct hit
        if lookup_d in self.rates_table:
            return self.rates_table[lookup_d]

        # Find closest preceding date in historical rates table
        available_dates = sorted(self.rates_table.keys())
        closest: Optional[date] = None
        for cand_date in available_dates:
            if cand_date <= lookup_d:
                closest = cand_date
            else:
                break

        if closest is not None:
            return self.rates_table[closest]

        # If target date is before all available dates, find earliest available or default
        if available_dates:
            return self.rates_table[available_dates[0]]

        return self.default_rate

    def convert_usd_to_inr(
        self,
        usd_amount: Union[Decimal, float, int, str],
        tx_date: Union[date, datetime, str],
        mode: str = "SPOT",
    ) -> Decimal:
        """Converts USD monetary amount into INR at the applicable RBI reference rate."""
        amt_dec = Decimal(str(usd_amount))
        rate = self.lookup_rate(tx_date, mode=mode)
        return (amt_dec * rate).quantize(Decimal("0.01"))

    def convert_dividend_and_withholding(
        self,
        gross_dividend_usd: Union[Decimal, float, int, str],
        tax_withheld_usd: Union[Decimal, float, int, str],
        tx_date: Union[date, datetime, str],
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Converts foreign dividend and IRS 1042-S tax withholding into INR under Rule 115.
        Returns (gross_dividend_inr, tax_withheld_inr, rule_115_rate).
        """
        rate = self.lookup_rate(tx_date, mode="RULE_115")
        gross_usd = Decimal(str(gross_dividend_usd))
        tax_usd = Decimal(str(tax_withheld_usd))

        gross_inr = (gross_usd * rate).quantize(Decimal("0.01"))
        tax_inr = (tax_usd * rate).quantize(Decimal("0.01"))
        return gross_inr, tax_inr, rate


# Global default instance
_default_forex_engine = ForexEngine()


def lookup_rbi_rate(
    tx_date: Union[date, datetime, str],
    mode: str = "SPOT",
) -> Decimal:
    """Convenience helper to lookup RBI reference rate."""
    return _default_forex_engine.lookup_rate(tx_date, mode=mode)


def convert_usd_to_inr(
    usd_amount: Union[Decimal, float, int, str],
    tx_date: Union[date, datetime, str],
    mode: str = "SPOT",
) -> Decimal:
    """Convenience helper to convert USD to INR."""
    return _default_forex_engine.convert_usd_to_inr(usd_amount, tx_date, mode=mode)
