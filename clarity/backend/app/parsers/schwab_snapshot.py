"""Local, read-only Schwab month-end position evidence for the observed layout.

No ledger posting, FX conversion, account linking, or private-data persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
import re

import pdfplumber
import pypdfium2


class SnapshotError(ValueError):
    pass


@dataclass(frozen=True)
class Position:
    section: str
    symbol: str
    quantity: Decimal
    printed_price: Decimal
    market_value: Decimal
    cost_basis: Decimal
    unrealized_gain: Decimal


@dataclass(frozen=True)
class Snapshot:
    account_number: str
    as_of: date
    printed_currency_glyph: str
    iso_currency: None  # The observed source prints $, but no ISO code.
    cash_value: Decimal
    equity_value: Decimal
    fund_value: Decimal
    total_value: Decimal
    positions: tuple[Position, ...]


@dataclass(frozen=True)
class MonthComparison:
    matched_positions: int
    added_positions: int
    removed_positions: int
    quantity_changed: int


_BANDS = ((285, 330), (330, 400), (400, 480), (480, 560),
          (560, 625), (625, 680), (680, 740), (740, 790))


def _number(text: str) -> Decimal:
    value = text.strip().replace("$", "").replace(",", "").replace("%", "")
    negative = value.startswith("(") and value.endswith(")")
    if negative:
        value = value[1:-1]
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise SnapshotError("Unrecognized printed number") from None
    if not result.is_finite():
        raise SnapshotError("Unrecognized printed number")
    return -result if negative else result


def _at(words: list[dict], y: float, x_low: float, x_high: float,
        *, tolerance: float = 3.0) -> dict:
    found = [word for word in words if abs(word["top"] - y) <= tolerance
             and x_low <= word["x0"] < x_high]
    if len(found) != 1:
        raise SnapshotError("Missing or ambiguous printed cell")
    return found[0]


def _header_y(words: list[dict], *, lower: float, upper: float) -> float:
    found = [w for w in words if w["text"] == "Quantity"
             and 285 <= w["x0"] < 320 and lower <= w["top"] <= upper]
    if len(found) != 1:
        raise SnapshotError("Missing or ambiguous position table")
    return found[0]["top"]


def _position(words: list[dict], y: float, section: str) -> Position:
    cells = [_at(words, y, low, high) for low, high in _BANDS]
    values = [_number(cell["text"]) for cell in cells]
    qty, price, market, cost, gain = values[:5]
    if qty <= 0 or price <= 0 or market < 0 or cost < 0:
        raise SnapshotError("Invalid position amounts")
    if abs(qty * price - market) > Decimal("0.02"):
        raise SnapshotError("Position price and value disagree")
    if abs(market - cost - gain) > Decimal("0.02"):
        raise SnapshotError("Position cost and gain disagree")
    symbol = _at(words, y, 10, 55)["text"]
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,11}", symbol):
        raise SnapshotError("Missing position symbol")
    return Position(section, symbol, qty, price, market, cost, gain)


def _security_total(words: list[dict], y: float, positions: tuple[Position, ...]) -> None:
    printed_market = _number(_at(words, y, 400, 480)["text"])
    printed_cost = _number(_at(words, y, 480, 560)["text"])
    printed_gain = _number(_at(words, y, 560, 625)["text"])
    if printed_market != sum((p.market_value for p in positions), Decimal(0)):
        raise SnapshotError("Position section value mismatch")
    if printed_cost != sum((p.cost_basis for p in positions), Decimal(0)):
        raise SnapshotError("Position section cost mismatch")
    if printed_gain != sum((p.unrealized_gain for p in positions), Decimal(0)):
        raise SnapshotError("Position section gain mismatch")


def _row_count(words: list[dict], start_y: float, end_y: float) -> int:
    quantity_cells = []
    for word in words:
        if not (start_y + 6 < word["top"] < end_y - 4 and 285 <= word["x0"] < 330):
            continue
        try:
            _number(word["text"])
        except SnapshotError:
            continue
        quantity_cells.append(round(word["top"]))
    return len(set(quantity_cells))


def _category(words: list[dict], y: float, label: str) -> None:
    text = "".join(w["text"] for w in sorted(words, key=lambda w: w["x0"])
                   if abs(w["top"] - y) <= 2 and 100 <= w["x0"] < 280)
    if text != label:
        raise SnapshotError("Unsupported allocation categories")


def _period_end(text: str) -> date:
    match = re.search(r"\b([A-Z][a-z]+)\s+(\d{1,2})-(\d{1,2}),\s*(\d{4})\b", text)
    if match is None:
        raise SnapshotError("Missing statement period")
    try:
        month = datetime.strptime(match.group(1), "%B").month
        start = date(int(match.group(4)), month, int(match.group(2)))
        end = date(int(match.group(4)), month, int(match.group(3)))
    except ValueError:
        raise SnapshotError("Invalid statement period") from None
    if start > end or end.day != monthrange(end.year, end.month)[1]:
        raise SnapshotError("Unsupported statement period")
    return end


def _header(pdf_bytes: bytes) -> tuple[str, date]:
    try:
        document = pypdfium2.PdfDocument(pdf_bytes)
        if len(document) != 6:
            raise SnapshotError("Unsupported statement length")
        lines = document[0].get_textpage().get_text_range().splitlines()
    except SnapshotError:
        raise
    except Exception:
        raise SnapshotError("Could not read statement header") from None
    if len(lines) < 6 or lines[1].strip() != "Statement Period" or lines[3].strip() != "Account Number":
        raise SnapshotError("Unsupported statement header")
    if "Schwab One International" not in lines[5]:
        raise SnapshotError("Unsupported statement issuer")
    account = lines[4].strip()
    if not re.fullmatch(r"\d{4}-\d{4}", account):
        raise SnapshotError("Missing account number")
    return account, _period_end(lines[2])


def parse_pdf_bytes(pdf_bytes: bytes) -> Snapshot:
    if not pdf_bytes.startswith(b"%PDF") or len(pdf_bytes) > 12_000_000:
        raise SnapshotError("Unsupported PDF")
    account, as_of = _header(pdf_bytes)
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            pages = [pdf.pages[i].extract_words() for i in (0, 1, 2, 3)]
    except Exception:
        raise SnapshotError("Could not read statement positions") from None
    summary, cash_equity, funds = pages[1], pages[2], pages[3]

    allocation: list[Decimal] = []
    for y, label in ((145, "CashandCashInvestments"),
                     (161, "Equities"), (177, "ExchangeTradedFunds")):
        _category(summary, y, label)
        allocation.append(_number(_at(summary, y, 280, 345)["text"]))
    cash, equity, fund = allocation
    total = _number(_at(summary, 199, 280, 345)["text"])
    if min(allocation) < 0 or total != sum(allocation):
        raise SnapshotError("Account allocation mismatch")
    page_one_total = _number(_at(pages[0], 462, 610, 700)["text"])
    if page_one_total != total:
        raise SnapshotError("Account summary mismatch")

    cash_y = _header_y(cash_equity, lower=310, upper=345)
    equity_y = _header_y(cash_equity, lower=390, upper=440)
    fund_y = _header_y(funds, lower=120, upper=145)
    if not all(any(w["text"] == "Price($)" and abs(w["top"] - y) <= 2
                   for w in words) for words, y in ((cash_equity, equity_y), (funds, fund_y))):
        raise SnapshotError("Missing printed currency evidence")
    if _row_count(cash_equity, equity_y, equity_y + 34) != 1:
        raise SnapshotError("Unexpected equity position count")
    if _row_count(funds, fund_y, fund_y + 53) != 2:
        raise SnapshotError("Unexpected fund position count")
    # Cash columns are beginning, ending, and change in period.  The ending
    # column, not the beginning column, is the current cash allocation.
    beginning = _number(_at(cash_equity, cash_y + 16, 400, 480)["text"])
    ending = _number(_at(cash_equity, cash_y + 16, 480, 560)["text"])
    change = _number(_at(cash_equity, cash_y + 16, 560, 625)["text"])
    if beginning + change != ending or ending != cash:
        raise SnapshotError("Cash comparison mismatch")
    if _number(_at(cash_equity, cash_y + 35, 480, 560)["text"]) != ending:
        raise SnapshotError("Cash section total mismatch")

    equity_positions = (_position(cash_equity, equity_y + 16, "EQUITY"),)
    fund_positions = (_position(funds, fund_y + 17, "ETF"),
                      _position(funds, fund_y + 35, "ETF"))
    _security_total(cash_equity, equity_y + 34, equity_positions)
    _security_total(funds, fund_y + 53, fund_positions)
    if sum((p.market_value for p in equity_positions), Decimal(0)) != equity:
        raise SnapshotError("Equity allocation mismatch")
    if sum((p.market_value for p in fund_positions), Decimal(0)) != fund:
        raise SnapshotError("Fund allocation mismatch")
    positions = equity_positions + fund_positions
    if len({p.symbol for p in positions}) != len(positions):
        raise SnapshotError("Repeated position symbol")
    return Snapshot(account, as_of, "$", None, cash, equity, fund, total, positions)


def compare_months(first: Snapshot, second: Snapshot) -> MonthComparison:
    if first.account_number != second.account_number:
        raise SnapshotError("Different statement accounts")
    if first.as_of >= second.as_of:
        raise SnapshotError("Statements out of order")
    old = {p.symbol: p for p in first.positions}
    new = {p.symbol: p for p in second.positions}
    shared = old.keys() & new.keys()
    for symbol in shared:
        if old[symbol].section != new[symbol].section:
            raise SnapshotError("Position category changed")
    return MonthComparison(len(shared), len(new.keys() - old.keys()),
                           len(old.keys() - new.keys()),
                           sum(old[s].quantity != new[s].quantity for s in shared))
