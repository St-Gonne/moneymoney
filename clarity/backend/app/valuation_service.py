"""Injected synthetic daily-price valuation; it never activates providers or network."""
from __future__ import annotations

import hashlib
import json
from dataclasses import fields
from datetime import date
from decimal import Decimal
from math import isfinite
from typing import Any
from types import SimpleNamespace

from .account_data_store import STORE_UNAVAILABLE
from .models.account_data import AccountDataError
from .models.valuation import SyntheticDailyPrice, ValuationError


CALCULATION_VERSION = "mvp-dated-valuation-v1"
RANGE_CALCULATION_VERSION = "mvp-dated-valuation-range-v1"
MAX_RANGE_DAYS = 3660
MAX_RANGE_POINTS = 1000


class ValuationRangeLimitError(Exception):
    """A usable client limit, distinct from malformed scope input."""


def _decimal(value: Decimal) -> str:
    return format(value, "f")


def _review_overlap_ids(snapshot: Any, manual_holdings: tuple[Any, ...]) -> set[str]:
    """Return manual facts that could duplicate a statement position.

    Different accounts can legitimately hold the same ISIN.  We therefore flag
    only a same-account, same-ISIN pair; without a shared stable holding id or
    an explicit owner reconciliation decision, the manual fact remains visible
    but is omitted from aggregate valuation and return calculations.
    """
    statement_pairs = {
        (getattr(item, "account_scope_id", None), getattr(item, "isin", None))
        for item in getattr(snapshot, "holdings", ())
        if isinstance(getattr(item, "account_scope_id", None), str) and isinstance(getattr(item, "isin", None), str) and getattr(item, "isin").strip()
    }
    return {
        item.fact_id for item in manual_holdings
        if isinstance(getattr(item, "isin", None), str) and item.isin.strip() and (item.account_id, item.isin) in statement_pairs
    }


class SyntheticDailyPriceSource:
    """A bounded test/local fixture source; construction is the only admission path."""

    def __init__(self, records: tuple[SyntheticDailyPrice, ...]) -> None:
        if len(records) > 256 or len({(r.owner_scope_id, r.portfolio_id, r.holding_id, r.price_date) for r in records}) != len(records):
            raise ValuationError("ERR_VALUATION_INVALID")
        self._records = records

    def records(self, owner: str, portfolio: str, as_of: date) -> tuple[SyntheticDailyPrice, ...]:
        return tuple(r for r in self._records if r.owner_scope_id == owner and r.portfolio_id == portfolio and r.price_date == as_of)

    def observation_dates(self, owner: str, portfolio: str, holding_ids: set[str] | None = None, currency: str | None = None) -> tuple[date, ...]:
        """Return persisted fixture dates only; this source never fills gaps."""
        return tuple(sorted({r.price_date for r in self._records if r.owner_scope_id == owner and r.portfolio_id == portfolio and (holding_ids is None or r.holding_id in holding_ids) and (currency is None or r.currency == currency)}))


class LocalValuationService:
    def __init__(self, source: SyntheticDailyPriceSource) -> None:
        self._source = source

    def _digest(self, facts: dict[str, Any], prices: tuple[SyntheticDailyPrice, ...], as_of: date, snapshot: Any, account_id: str | None, currency: str | None = None) -> str:
        payload = {
            "version": CALCULATION_VERSION,
            "asOf": as_of.isoformat(),
            "accountId": account_id,
            "currency": currency,
            "facts": _wire_facts(facts),
            "prices": sorted((p.holding_id, _decimal(p.price), p.currency, p.price_date.isoformat(), p.source, p.status, p.source_revision) for p in prices),
            "snapshotRevision": getattr(snapshot, "revision_id", None),
            "snapshotDate": getattr(snapshot, "as_of_date", None).isoformat() if getattr(snapshot, "as_of_date", None) else None,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()

    def _valuation(self, store: Any, owner: str, portfolio: str, as_of: date, snapshot: Any = None, account_id: str | None = None, currency: str | None = None, *, persist: bool) -> dict[str, Any]:
        facts = _facts_as_of(store, owner, portfolio, as_of, account_id, currency)
        snapshot = _eligible_snapshot(snapshot, as_of, account_id, currency)
        statement_ids = {holding_id for holding_id in (getattr(holding, "holding_id", None) for holding in getattr(snapshot, "holdings", ())) if isinstance(holding_id, str) and holding_id} if snapshot is not None else set()
        # A manual fact is ordinarily distinct from an imported statement row.
        # The only safe automatic reconciliation key in this MVP is the opaque,
        # stable holding id itself.  Display names, ISINs and account labels are
        # evidence for review, not a license to merge two positions.
        manual_holdings = tuple(holding for holding in facts["opening_holdings"] if holding.fact_id not in statement_ids)
        review_overlap_ids = _review_overlap_ids(snapshot, manual_holdings)
        selected_holding_ids = {holding.fact_id for holding in manual_holdings}
        prices = tuple(price for price in self._source.records(owner, portfolio, as_of) if price.holding_id in selected_holding_ids)
        digest = self._digest(facts, prices, as_of, snapshot, account_id, currency)
        by_id = {p.holding_id: p for p in prices}
        rows = []
        for holding in sorted(manual_holdings, key=lambda item: item.fact_id):
            price = by_id.get(holding.fact_id)
            if price is None:
                rows.append({"holdingId": holding.fact_id, "accountScopeId": holding.account_id, "holdingSource": "MANUAL", "reconciliationStatus": "REVIEW_REQUIRED" if holding.fact_id in review_overlap_ids else "CLEAR", "status": "INSUFFICIENT_DATA", "reason": "MISSING_PRICE"})
            elif price.currency != holding.currency:
                rows.append({"holdingId": holding.fact_id, "accountScopeId": holding.account_id, "holdingSource": "MANUAL", "reconciliationStatus": "REVIEW_REQUIRED" if holding.fact_id in review_overlap_ids else "CLEAR", "status": "INSUFFICIENT_DATA", "reason": "MIXED_CURRENCY"})
            else:
                rows.append({"holdingId": holding.fact_id, "accountScopeId": holding.account_id, "holdingSource": "MANUAL", "reconciliationStatus": "REVIEW_REQUIRED" if holding.fact_id in review_overlap_ids else "CLEAR", "status": "CALCULATED", "quantity": _decimal(holding.quantity), "price": _decimal(price.price), "currency": price.currency, "priceDate": price.price_date.isoformat(), "source": price.source, "priceStatus": price.status, "currentValue": _decimal(holding.quantity * price.price)})
        if snapshot is not None:
            statement_holdings = tuple(
                holding for holding in getattr(snapshot, "holdings", ())
                if all(hasattr(holding, field) for field in ("holding_id", "account_scope_id", "quantity", "currency", "statement_price", "statement_value"))
            )
            for holding in sorted(statement_holdings, key=lambda item: item.holding_id):
                rows.append({
                    "holdingId": holding.holding_id,
                    "holdingSource": "STATEMENT",
                    "status": "STATEMENT_VALUE",
                    "accountScopeId": holding.account_scope_id,
                    "quantity": holding.quantity,
                    "currency": holding.currency,
                    "statementPrice": holding.statement_price,
                    "statementValue": holding.statement_value,
                    "statementDate": snapshot.as_of_date.isoformat(),
                })
        totals: dict[str, dict[str, Decimal | int]] = {}
        for row in rows:
            currency = row.get("currency")
            raw_value = row.get("currentValue") if row.get("status") == "CALCULATED" else row.get("statementValue")
            if not isinstance(currency, str) or raw_value is None:
                continue
            try:
                value = Decimal(str(raw_value))
            except Exception:
                continue
            if not value.is_finite() or value < 0:
                continue
            bucket = totals.setdefault(currency, {"calculated": Decimal("0"), "statement": Decimal("0"), "excluded": 0})
            if row.get("reconciliationStatus") == "REVIEW_REQUIRED":
                bucket["excluded"] += 1
                continue
            bucket["calculated" if row.get("status") == "CALCULATED" else "statement"] += value
        summary = [
            {"currency": currency, "calculatedValue": _decimal(parts["calculated"]), "statementValue": _decimal(parts["statement"]), "totalIncludedValue": _decimal(parts["calculated"] + parts["statement"]), "calculatedAsOf": as_of.isoformat() if parts["calculated"] else None, "statementAsOf": snapshot.as_of_date.isoformat() if parts["statement"] and snapshot is not None else None, "excludedForReconciliationCount": parts["excluded"]}
            for currency, parts in sorted(totals.items())
        ]
        result = {"calculationVersion": CALCULATION_VERSION, "inputDigest": digest, "asOf": as_of.isoformat(), "holdings": rows, "summaryByCurrency": summary}
        if persist:
            store.cache_derived(owner, portfolio, "valuation", as_of.isoformat(), digest, result)
        return result

    def valuation(self, store: Any, owner: str, portfolio: str, as_of: date, snapshot: Any = None, account_id: str | None = None, currency: str | None = None) -> dict[str, Any]:
        return self._valuation(store, owner, portfolio, as_of, snapshot, account_id, currency, persist=True)

    def _eligible_observations(self, store: Any, owner: str, portfolio: str, snapshot: Any, account_id: str | None, currency: str, source_dates: tuple[date, ...]) -> tuple[dict[str, Any], ...]:
        """Project exact eligible observations without filling a durable holding cache.

        The ordinary point endpoint retains its existing cache behavior.  Range
        work must not write a potentially large full-holding response per date;
        this request-local path performs the identical calculation and keeps only
        the compact response that the range caller needs.
        """
        eligible: list[dict[str, Any]] = []
        for observed_at in source_dates:
            facts = _facts_as_of(store, owner, portfolio, observed_at, account_id, currency)
            expected = {item.fact_id for item in facts["opening_holdings"]}
            if not expected:
                continue
            result = self._valuation(store, owner, portfolio, observed_at, snapshot, account_id, currency, persist=False)
            actual = {
                row["holdingId"] for row in result["holdings"]
                if row.get("holdingSource") == "MANUAL"
                and row.get("reconciliationStatus") == "CLEAR"
                and row.get("status") == "CALCULATED"
                and row.get("currency") == currency
            }
            if actual == expected:
                summaries = [summary for summary in result["summaryByCurrency"] if summary.get("currency") == currency]
                if len(summaries) != 1:
                    raise AccountDataError("ERR_ACCOUNT_REQUEST_INVALID")
                summary = summaries[0]
                # Do not retain one full holding-array result per date.  The
                # service only needs this compact evidence after eligibility is
                # established; the local result is released on the next loop.
                eligible.append({
                    "observedAt": observed_at,
                    "inputDigest": result["inputDigest"],
                    "point": {
                        "asOf": observed_at.isoformat(),
                        "calculatedValue": summary["calculatedValue"],
                        "statementValue": summary["statementValue"],
                        "totalIncludedValue": summary["totalIncludedValue"],
                    },
                })
        return tuple(eligible)

    def observation_dates(self, store: Any, owner: str, portfolio: str, snapshot: Any = None, account_id: str | None = None, currency: str | None = None) -> tuple[date, ...]:
        """Return only genuine dates fully valuing the exact requested scope.

        This is deliberately derived from the injected/persisted price source
        and the same valuation path as the ordinary private application.  It
        never invents dates, interpolates values, or lets a partial/mixed scope
        become a chart series.
        """
        if not currency:
            return ()
        source_dates = getattr(self._source, "observation_dates", None)
        if not callable(source_dates):
            return ()
        candidates = tuple(sorted(set(source_dates(owner, portfolio))))
        if len(candidates) > MAX_RANGE_DAYS + 1:
            return ()
        return tuple(item["observedAt"] for item in self._eligible_observations(store, owner, portfolio, snapshot, account_id, currency, candidates))

    def valuation_range(self, store: Any, owner: str, portfolio: str, snapshot: Any, account_id: str | None, currency: str, start: date | None, end: date | None, granularity: str) -> dict[str, Any]:
        """Return a bounded, scope-isolated compact history series.

        Only persisted source dates that fully value the exact manual scope are
        represented.  A monthly request selects the latest genuine observation
        in each month; it never manufactures a month-end price.
        """
        if granularity not in {"daily", "monthly"} or (start is None) != (end is None) or (start is not None and (end is None or end < start or (end - start).days > MAX_RANGE_DAYS)):
            raise AccountDataError("ERR_ACCOUNT_REQUEST_INVALID")
        source_dates = getattr(self._source, "observation_dates", None)
        if not callable(source_dates):
            available_dates: tuple[date, ...] = ()
        else:
            scope_facts = store.list_scope(owner, portfolio)
            scope_ids = {item.fact_id for item in scope_facts["opening_holdings"] if not getattr(item, "voided", False) and (account_id is None or item.account_id == account_id) and item.currency == currency}
            try:
                available_dates = tuple(sorted(set(source_dates(owner, portfolio, scope_ids, currency))))
            except TypeError:
                available_dates = tuple(sorted(set(source_dates(owner, portfolio))))
        source_candidates = tuple(item for item in available_dates if (start is None or item >= start) and (end is None or item <= end))
        if len(source_candidates) > MAX_RANGE_DAYS + 1 or (granularity == "daily" and len(source_candidates) > MAX_RANGE_POINTS):
            raise ValuationRangeLimitError()
        eligible = self._eligible_observations(store, owner, portfolio, snapshot, account_id, currency, source_candidates)
        selected = tuple(item for item in eligible if (start is None or item["observedAt"] >= start) and (end is None or item["observedAt"] <= end))
        endpoint_items = selected
        if granularity == "monthly":
            by_month: dict[tuple[int, int], dict[str, Any]] = {}
            for item in selected:
                observed_at = item["observedAt"]
                by_month[(observed_at.year, observed_at.month)] = item
            selected = tuple(by_month[key] for key in sorted(by_month))
        if len(selected) > MAX_RANGE_POINTS:
            raise ValuationRangeLimitError()
        points = [item["point"] for item in selected]
        payload = {
            "calculationVersion": RANGE_CALCULATION_VERSION,
            "scope": {"accountId": account_id, "currency": currency},
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "granularity": granularity,
            "availableStart": available_dates[0].isoformat() if available_dates else None,
            "availableEnd": available_dates[-1].isoformat() if available_dates else None,
            "pointDigests": [item["inputDigest"] for item in endpoint_items],
            "points": points,
        }
        revision = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        partial = bool(start is not None and (not endpoint_items or endpoint_items[0]["observedAt"] != start or endpoint_items[-1]["observedAt"] != end))
        return {
            "calculationVersion": RANGE_CALCULATION_VERSION,
            "inputDigest": revision,
            "scope": {"accountId": account_id, "currency": currency},
            "range": {"start": payload["start"], "end": payload["end"], "granularity": granularity},
            "coverage": {"availableStart": payload["availableStart"], "availableEnd": payload["availableEnd"], "observedCount": len(available_dates), "selectedObservedCount": len(endpoint_items), "returnedCount": len(points), "partial": partial},
            "points": points,
            "first": endpoint_items[0]["point"] if endpoint_items else None,
            "last": endpoint_items[-1]["point"] if endpoint_items else None,
        }

    def performance(self, store: Any, owner: str, portfolio: str, as_of: date, snapshot: Any = None, account_id: str | None = None) -> dict[str, Any]:
        valuation = self.valuation(store, owner, portfolio, as_of, snapshot, account_id)
        facts = _facts_as_of(store, owner, portfolio, as_of, account_id)
        snapshot = _eligible_snapshot(snapshot, as_of, account_id)
        statement_ids = {holding_id for holding_id in (getattr(holding, "holding_id", None) for holding in getattr(snapshot, "holdings", ())) if isinstance(holding_id, str) and holding_id} if snapshot is not None else set()
        manual_holdings = tuple(holding for holding in facts["opening_holdings"] if holding.fact_id not in statement_ids)
        review_overlap_ids = _review_overlap_ids(snapshot, manual_holdings)
        calculated_manual_holdings = tuple(holding for holding in manual_holdings if holding.fact_id not in review_overlap_ids)
        selected_holding_ids = {holding.fact_id for holding in manual_holdings}
        prices = tuple(price for price in self._source.records(owner, portfolio, as_of) if price.holding_id in selected_holding_ids)
        digest = self._digest(facts, prices, as_of, snapshot, account_id)
        accounts = facts["accounts"]
        flows = facts["cash_flows"]
        reasons: list[str] = []
        if review_overlap_ids:
            reasons.append("RECONCILIATION_REQUIRED")
        if not accounts or not all(a.manual_history_complete for a in accounts) or not flows:
            reasons.append("MISSING_HISTORY")
        currencies = {item.currency for item in accounts} | {item.currency for item in facts["opening_holdings"]} | {item.currency for item in flows}
        calculated = [row for row in valuation["holdings"] if row["status"] == "CALCULATED" and row.get("reconciliationStatus") != "REVIEW_REQUIRED"]
        currencies |= {row["currency"] for row in calculated} | {price.currency for price in prices}
        if len(currencies) != 1:
            reasons.append("MIXED_CURRENCY")
        if len(calculated) != len(calculated_manual_holdings) and not review_overlap_ids:
            reasons.append("MISSING_PRICE")
        terminal = sum((Decimal(row["currentValue"]) for row in calculated), Decimal("0"))
        if terminal <= 0 and not review_overlap_ids:
            reasons.append("NON_POSITIVE_TERMINAL_VALUE")
        base = {"calculationVersion": CALCULATION_VERSION, "inputDigest": digest, "asOf": as_of.isoformat(), "coverage": {"historyComplete": not reasons, "cashflowCount": len(flows), "reasons": list(dict.fromkeys(reasons)), "scope": "manual_complete_history_only"}}
        if reasons:
            result = {**base, "gain": {"status": "INSUFFICIENT_DATA", "reason": reasons[0]}, "xirr": {"status": "UNAVAILABLE", "reason": reasons[0]}}
        else:
            gain = sum((flow.amount for flow in flows), terminal)
            xirr, unavailable_reason = _xirr(tuple((flow.effective_date, flow.amount) for flow in sorted(flows, key=lambda item: (item.effective_date, item.fact_id))) + ((as_of, terminal),))
            if xirr is None:
                result = {**base, "gain": {"status": "INSUFFICIENT_DATA", "reason": unavailable_reason}, "xirr": {"status": "UNAVAILABLE", "reason": unavailable_reason}}
            else:
                result = {**base, "gain": {"status": "CALCULATED", "value": _decimal(gain), "currency": next(iter(currencies))}, "xirr": {"status": "CALCULATED", "valuePct": _decimal(xirr * Decimal("100"))}}
        store.cache_derived(owner, portfolio, "performance", as_of.isoformat(), digest, result)
        return result


def _wire_facts(facts: dict[str, Any]) -> dict[str, Any]:
    def semantic_value(value: Any) -> Any:
        if isinstance(value, (date, Decimal)):
            return value.isoformat() if isinstance(value, date) else _decimal(value)
        if hasattr(value, "__dataclass_fields__"):
            return {field.name: semantic_value(getattr(value, field.name)) for field in fields(value) if field.name != "recorded_at"}
        return value
    return {name: sorted((semantic_value(item) for item in values), key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=True)) for name, values in sorted(facts.items())}


def _facts_as_of(store: Any, owner: str, portfolio: str, as_of: date, account_id: str | None, currency: str | None = None) -> dict[str, Any]:
    facts = store.list_scope(owner, portfolio)
    accounts = facts["accounts"]
    if account_id is not None:
        accounts = tuple(account for account in accounts if account.account_id == account_id)
        if len(accounts) != 1:
            raise AccountDataError("ERR_ACCOUNT_NOT_FOUND")
        facts = {
            "accounts": accounts,
            "opening_holdings": tuple(item for item in facts["opening_holdings"] if item.account_id == account_id),
            "cash_flows": tuple(item for item in facts["cash_flows"] if item.account_id == account_id),
        }
    if currency is not None:
        accounts = tuple(account for account in facts["accounts"] if account.currency == currency)
        account_ids = {account.account_id for account in accounts}
        facts = {
            "accounts": accounts,
            "opening_holdings": tuple(item for item in facts["opening_holdings"] if item.account_id in account_ids and item.currency == currency),
            "cash_flows": tuple(item for item in facts["cash_flows"] if item.account_id in account_ids and item.currency == currency),
        }
    return {
        "accounts": tuple(sorted(facts["accounts"], key=lambda item: item.account_id)),
        "opening_holdings": tuple(sorted((item for item in facts["opening_holdings"] if item.as_of <= as_of and not getattr(item, "voided", False)), key=lambda item: item.fact_id)),
        "cash_flows": tuple(sorted((item for item in facts["cash_flows"] if item.effective_date <= as_of and not getattr(item, "voided", False)), key=lambda item: (item.effective_date, item.fact_id))),
    }


def _eligible_snapshot(snapshot: Any, as_of: date, account_id: str | None, currency: str | None = None) -> Any:
    snapshot_date = getattr(snapshot, "as_of_date", None)
    if not isinstance(snapshot_date, date) or snapshot_date > as_of:
        return None
    if account_id is None and currency is None:
        return snapshot
    # An account-level result must still see its own statement evidence.  It is
    # narrowed before reconciliation so other accounts cannot affect this scope.
    return SimpleNamespace(
        revision_id=getattr(snapshot, "revision_id", None),
        as_of_date=snapshot_date,
        holdings=tuple(
            item for item in getattr(snapshot, "holdings", ())
            if (account_id is None or getattr(item, "account_scope_id", None) == account_id)
            and (currency is None or getattr(item, "currency", None) == currency)
        ),
    )


def _xirr(flows: tuple[tuple[date, Decimal], ...]) -> tuple[Decimal | None, str | None]:
    if len({day for day, _amount in flows}) < 2:
        return None, "SAME_DAY_ONLY"
    if len(flows) < 2 or not any(amount < 0 for _, amount in flows) or not any(amount > 0 for _, amount in flows):
        return None, "INVALID_CASHFLOW"
    origin = min(day for day, _ in flows)
    def npv(rate: float) -> float:
        return sum(float(amount) / (1.0 + rate) ** ((day - origin).days / 365.0) for day, amount in flows)
    low, high = -0.9999, 10.0
    try:
        left, right = npv(low), npv(high)
    except (OverflowError, ZeroDivisionError):
        return None, "SOLVER_FAILURE"
    if not isfinite(left) or not isfinite(right) or left * right > 0:
        return None, "SOLVER_FAILURE"
    for _ in range(160):
        middle = (low + high) / 2
        value = npv(middle)
        if not isfinite(value):
            return None, "SOLVER_FAILURE"
        if abs(value) < 1e-9:
            return Decimal(str(round(middle, 12))), None
        if left * value <= 0:
            high, right = middle, value
        else:
            low, left = middle, value
    return Decimal(str(round((low + high) / 2, 12))), None
