"""
Reconciliation Gate & Transaction Fingerprinting Engine (Gate 4)
Enforces idempotency and deduplication across multiple statement imports:
1. Deterministic SHA-256 Transaction Fingerprinting:
   Prevents duplicate transaction writes across overlapping statement periods or re-ingestions.
2. Statement Boundary Hashing:
   Computes unique SHA-256 hash representing the entire statement (broker, account_id, period, net amount, count).
   Returns idempotent success receipt on exact statement re-ingestion with 0 duplicate ledger mutations.
3. Multi-Broker Ingestion Reconciliation:
   Maintains in-memory and canonical deduplication registry.
"""

import hashlib
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple, Union

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
                elif isinstance(v, Decimal):
                    res[k] = float(v)
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

from ..config import (
    ERR_RECONCILIATION_DUPLICATE_STATEMENT,
    ERR_RECONCILIATION_DUPLICATE_TRANSACTION,
    BrokerInstitution,
)
from ..models.cas import NormalizedCasStatement
from ..models.contract_note import NormalizedContractNote
from ..models.ledger import CanonicalTransaction, StatementReceipt, TransactionStatus
from ..models.schwab import NormalizedSchwabStatement


class ReconciliationGateResult(BaseModel):
    """
    Result returned by Gate 4 (Reconciliation Gate).
    """
    passed: bool = True
    is_duplicate_statement: bool = False
    idempotent_noop: bool = False
    rejection_code: Optional[str] = None
    rejection_reason: Optional[str] = None
    statement_hash: str = ""
    total_transactions: int = 0
    new_transactions_count: int = 0
    duplicate_transactions_count: int = 0
    canonical_transactions: List[CanonicalTransaction] = Field(default_factory=list)
    receipt: Optional[StatementReceipt] = None


class ReconciliationGate:
    """
    Gate 4: Deterministic Transaction Fingerprinting, Boundary Hashing, and Idempotency Guard.
    """

    def __init__(self):
        self._ingested_statement_hashes: Dict[str, StatementReceipt] = {}
        self._seen_transaction_fingerprints: Set[str] = set()
        self._canonical_ledger: List[CanonicalTransaction] = []

    def reset_state(self):
        """Clears in-memory reconciliation registry (useful for isolated unit testing)."""
        self._ingested_statement_hashes.clear()
        self._seen_transaction_fingerprints.clear()
        self._canonical_ledger.clear()

    @staticmethod
    def compute_statement_hash(
        institution: str,
        account_or_folio: str,
        start_date: Union[str, date, datetime],
        end_date: Union[str, date, datetime],
        trades_count: int,
        net_amount: Union[Decimal, float, int, str],
    ) -> str:
        """
        Computes deterministic SHA-256 boundary hash for a statement.
        Key format: {institution}:{account_or_folio}:{start_date}:{end_date}:{trades_count}:{net_amount:.2f}
        """
        s_date = start_date.isoformat() if isinstance(start_date, (date, datetime)) else str(start_date)
        e_date = end_date.isoformat() if isinstance(end_date, (date, datetime)) else str(end_date)
        net_dec = Decimal(str(net_amount)).quantize(Decimal("0.01"))
        
        key = f"{institution}:{account_or_folio}:{s_date}:{e_date}:{trades_count}:{net_dec:.2f}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    @staticmethod
    def compute_transaction_fingerprint(
        portfolio_id: str,
        institution: str,
        isin_or_symbol: str,
        trade_date: Union[str, date, datetime],
        action: str,
        quantity: Union[Decimal, float, int, str],
        unit_price: Union[Decimal, float, int, str],
        order_or_trade_id: str,
    ) -> str:
        """
        Computes deterministic SHA-256 fingerprint for an individual trade/transaction.
        Key format: {portfolio_id}:{institution}:{isin_or_symbol}:{trade_date}:{action}:{quantity:.4f}:{unit_price:.4f}:{order_or_trade_id}
        """
        t_date = trade_date.isoformat() if isinstance(trade_date, (date, datetime)) else str(trade_date)
        qty_dec = Decimal(str(quantity)).quantize(Decimal("0.0001"))
        price_dec = Decimal(str(unit_price)).quantize(Decimal("0.0001"))
        clean_action = str(action).upper().strip()
        clean_symbol = str(isin_or_symbol or "UNKNOWN").strip().upper()

        key = f"{portfolio_id}:{institution}:{clean_symbol}:{t_date}:{clean_action}:{qty_dec:.4f}:{price_dec:.4f}:{order_or_trade_id}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def is_statement_ingested(self, statement_hash: str) -> bool:
        """Checks whether statement hash is already recorded in the canonical registry."""
        return statement_hash in self._ingested_statement_hashes

    def is_transaction_seen(self, fingerprint: str) -> bool:
        """Checks whether transaction fingerprint is already recorded in the canonical registry."""
        return fingerprint in self._seen_transaction_fingerprints

    def reconcile(
        self,
        statement: Any,
        portfolio_id: str,
        client_pan: str,
        institution: Optional[str] = None,
        forex_rate: Decimal = Decimal("1.00"),
    ) -> ReconciliationGateResult:
        """
        Reconciles a validated statement AST against canonical ledger state.
        Computes boundary hash and extracts deduplicated CanonicalTransaction records.
        """
        if isinstance(statement, NormalizedContractNote) or hasattr(statement, "contract_note_number") or hasattr(statement, "contract_note_no") or hasattr(statement, "trades"):
            return self._reconcile_contract_note(statement, portfolio_id, client_pan, institution, forex_rate)
        elif isinstance(statement, NormalizedCasStatement) or hasattr(statement, "folios") or hasattr(statement, "schemes"):
            return self._reconcile_cas_statement(statement, portfolio_id, client_pan, institution, forex_rate)
        elif isinstance(statement, NormalizedSchwabStatement) or hasattr(statement, "records") or hasattr(statement, "rows"):
            return self._reconcile_schwab_statement(statement, portfolio_id, client_pan, institution, forex_rate)

        else:
            # Generic fallback
            return self._reconcile_generic(statement, portfolio_id, client_pan, institution, forex_rate)

    def _reconcile_contract_note(
        self,
        stmt: Any,
        portfolio_id: str,
        client_pan: str,
        institution_override: Optional[str],
        forex_rate: Decimal,
    ) -> ReconciliationGateResult:
        inst_val = getattr(stmt, "institution", institution_override or BrokerInstitution.ZERODHA)
        inst_str = inst_val.value if hasattr(inst_val, "value") else str(inst_val)
        
        acc_no = getattr(stmt, "account_number", getattr(stmt, "trading_acc_no", "ACC_UNKNOWN"))
        trade_date = getattr(stmt, "trade_date", date.today())
        trades = getattr(stmt, "trades", [])
        net_settlement = getattr(stmt, "net_settlement_amount", getattr(stmt, "net_amount", Decimal("0.00")))

        stmt_hash = self.compute_statement_hash(
            institution=inst_str,
            account_or_folio=acc_no,
            start_date=trade_date,
            end_date=trade_date,
            trades_count=len(trades),
            net_amount=net_settlement,
        )

        # Idempotency Check on Statement Boundary Hash
        if self.is_statement_ingested(stmt_hash):
            existing_receipt = self._ingested_statement_hashes[stmt_hash]
            return ReconciliationGateResult(
                passed=True,
                is_duplicate_statement=True,
                idempotent_noop=True,
                statement_hash=stmt_hash,
                total_transactions=len(trades),
                new_transactions_count=0,
                duplicate_transactions_count=len(trades),
                canonical_transactions=[],
                receipt=existing_receipt,
            )

        new_canonical_txs: List[CanonicalTransaction] = []
        dup_count = 0

        for idx, t in enumerate(trades):
            action_val = getattr(t, "action", "BUY")
            action_str = action_val.value if hasattr(action_val, "value") else str(action_val).upper()
            
            isin_or_sym = getattr(t, "isin", None) or getattr(t, "symbol", getattr(t, "scrip_name", f"SEC_{idx+1}"))
            trade_id = getattr(t, "trade_id", getattr(t, "order_id", getattr(t, "trade_no", getattr(t, "order_no", f"TRD_{idx+1}"))))
            qty = getattr(t, "quantity", Decimal("0.00"))
            rate = getattr(t, "gross_price", getattr(t, "gross_rate", getattr(t, "price", Decimal("0.00"))))
            gross_tot = getattr(t, "gross_total", (qty * rate).quantize(Decimal("0.01")))
            net_tot = getattr(t, "net_total", gross_tot)
            sec_name = getattr(t, "security_name", getattr(t, "scrip_name", getattr(t, "symbol", isin_or_sym)))

            fp = self.compute_transaction_fingerprint(
                portfolio_id=portfolio_id,
                institution=inst_str,
                isin_or_symbol=isin_or_sym,
                trade_date=trade_date,
                action=action_str,
                quantity=qty,
                unit_price=rate,
                order_or_trade_id=trade_id,
            )

            if self.is_transaction_seen(fp):
                dup_count += 1
                continue

            tx = CanonicalTransaction(
                transaction_id=fp,
                statement_id=getattr(stmt, "statement_id", getattr(stmt, "contract_note_number", None)),
                statement_hash=stmt_hash,
                portfolio_id=portfolio_id,
                client_pan=client_pan,
                broker=inst_str,
                account_number=acc_no,
                trade_date=trade_date,
                settlement_date=getattr(stmt, "settlement_date", None),
                asset_id=isin_or_sym,
                symbol=getattr(t, "symbol", isin_or_sym),
                security_name=sec_name,
                action=action_str,
                quantity=qty,
                price=rate,
                gross_amount=gross_tot,
                fees_and_charges=getattr(t, "brokerage", Decimal("0.00")),
                net_amount=net_tot,
                currency="INR",
                forex_rate=forex_rate,
                net_amount_inr=(net_tot * forex_rate).quantize(Decimal("0.01")),
                fingerprint=fp,
                status=TransactionStatus.PROCESSED,
                created_at=datetime.now(),
            )
            new_canonical_txs.append(tx)

        # Register statement receipt and transaction fingerprints
        receipt = StatementReceipt(
            statement_hash=stmt_hash,
            institution=inst_str,
            account_number=acc_no,
            statement_period_start=trade_date,
            statement_period_end=trade_date,
            net_amount=net_settlement,
            trades_count=len(trades),
            status="COMPLETED",
        )
        self._ingested_statement_hashes[stmt_hash] = receipt

        for tx in new_canonical_txs:
            self._seen_transaction_fingerprints.add(tx.fingerprint)
            self._canonical_ledger.append(tx)

        return ReconciliationGateResult(
            passed=True,
            is_duplicate_statement=False,
            idempotent_noop=False,
            statement_hash=stmt_hash,
            total_transactions=len(trades),
            new_transactions_count=len(new_canonical_txs),
            duplicate_transactions_count=dup_count,
            canonical_transactions=new_canonical_txs,
            receipt=receipt,
        )

    def _reconcile_cas_statement(
        self,
        stmt: Any,
        portfolio_id: str,
        client_pan: str,
        institution_override: Optional[str],
        forex_rate: Decimal,
    ) -> ReconciliationGateResult:
        inst_str = BrokerInstitution.CAMS_KFINTECH
        schemes = getattr(stmt, "schemes", [])
        if not schemes and hasattr(stmt, "folios"):
            for folio in getattr(stmt, "folios", []):
                schemes.extend(getattr(folio, "schemes", []))

        total_txs = sum(len(getattr(s, "transactions", [])) for s in schemes)
        first_folio = schemes[0].folio_number if schemes else "FOLIO_UNKNOWN"
        stmt_period = getattr(stmt, "statement_period", "PERIOD_CAS")

        stmt_hash = self.compute_statement_hash(
            institution=inst_str,
            account_or_folio=first_folio,
            start_date=stmt_period,
            end_date=stmt_period,
            trades_count=total_txs,
            net_amount=Decimal("0.00"),
        )

        if self.is_statement_ingested(stmt_hash):
            existing_receipt = self._ingested_statement_hashes[stmt_hash]
            return ReconciliationGateResult(
                passed=True,
                is_duplicate_statement=True,
                idempotent_noop=True,
                statement_hash=stmt_hash,
                total_transactions=total_txs,
                new_transactions_count=0,
                duplicate_transactions_count=total_txs,
                canonical_transactions=[],
                receipt=existing_receipt,
            )

        new_canonical_txs: List[CanonicalTransaction] = []
        dup_count = 0

        for scheme in schemes:
            folio_no = getattr(scheme, "folio_number", "FOLIO")
            isin_or_amfi = getattr(scheme, "isin", None) or getattr(scheme, "amfi_code", "MUTUAL_FUND")
            scheme_name = getattr(scheme, "scheme_name", "Mutual Fund Scheme")

            for tx_idx, tx in enumerate(getattr(scheme, "transactions", [])):
                tx_date = getattr(tx, "date", getattr(tx, "tx_date", date.today()))
                tx_type = getattr(tx, "transaction_type", getattr(tx, "tx_type", "PURCHASE")).upper()
                units = getattr(tx, "units", Decimal("0.000"))
                nav = getattr(tx, "nav", Decimal("0.00"))
                gross = getattr(tx, "gross_amount", getattr(tx, "amount", (units * nav).quantize(Decimal("0.01"))))
                stamp = getattr(tx, "stamp_duty", Decimal("0.00"))

                fp = self.compute_transaction_fingerprint(
                    portfolio_id=portfolio_id,
                    institution=inst_str,
                    isin_or_symbol=isin_or_amfi,
                    trade_date=tx_date,
                    action=tx_type,
                    quantity=units,
                    unit_price=nav,
                    order_or_trade_id=f"{folio_no}_{tx_idx}",
                )

                if self.is_transaction_seen(fp):
                    dup_count += 1
                    continue

                canonical_tx = CanonicalTransaction(
                    transaction_id=fp,
                    statement_id=getattr(stmt, "statement_id", None),
                    statement_hash=stmt_hash,
                    portfolio_id=portfolio_id,
                    client_pan=client_pan,
                    broker=inst_str,
                    account_number=folio_no,
                    trade_date=tx_date,
                    asset_id=isin_or_amfi,
                    symbol=isin_or_amfi,
                    security_name=scheme_name,
                    action=tx_type,
                    quantity=units,
                    price=nav,
                    gross_amount=gross,
                    fees_and_charges=stamp,
                    net_amount=gross,
                    currency="INR",
                    forex_rate=forex_rate,
                    net_amount_inr=(gross * forex_rate).quantize(Decimal("0.01")),
                    fingerprint=fp,
                    status=TransactionStatus.PROCESSED,
                    created_at=datetime.now(),
                )
                new_canonical_txs.append(canonical_tx)

        receipt = StatementReceipt(
            statement_hash=stmt_hash,
            institution=inst_str,
            account_number=first_folio,
            net_amount=Decimal("0.00"),
            trades_count=total_txs,
            status="COMPLETED",
        )
        self._ingested_statement_hashes[stmt_hash] = receipt

        for tx in new_canonical_txs:
            self._seen_transaction_fingerprints.add(tx.fingerprint)
            self._canonical_ledger.append(tx)

        return ReconciliationGateResult(
            passed=True,
            is_duplicate_statement=False,
            idempotent_noop=False,
            statement_hash=stmt_hash,
            total_transactions=total_txs,
            new_transactions_count=len(new_canonical_txs),
            duplicate_transactions_count=dup_count,
            canonical_transactions=new_canonical_txs,
            receipt=receipt,
        )

    def _reconcile_schwab_statement(
        self,
        stmt: Any,
        portfolio_id: str,
        client_pan: str,
        institution_override: Optional[str],
        forex_rate: Decimal,
    ) -> ReconciliationGateResult:
        inst_str = BrokerInstitution.CHARLES_SCHWAB
        acc_no = getattr(stmt, "account_number", "84920194")
        period = getattr(stmt, "statement_period", "PERIOD_SCHWAB")
        records = getattr(stmt, "records", getattr(stmt, "rows", []))

        total_net_usd = sum(getattr(r, "net_amount_usd", getattr(r, "amount", Decimal("0.00"))) for r in records)

        stmt_hash = self.compute_statement_hash(
            institution=inst_str,
            account_or_folio=acc_no,
            start_date=period,
            end_date=period,
            trades_count=len(records),
            net_amount=total_net_usd,
        )

        if self.is_statement_ingested(stmt_hash):
            existing_receipt = self._ingested_statement_hashes[stmt_hash]
            return ReconciliationGateResult(
                passed=True,
                is_duplicate_statement=True,
                idempotent_noop=True,
                statement_hash=stmt_hash,
                total_transactions=len(records),
                new_transactions_count=0,
                duplicate_transactions_count=len(records),
                canonical_transactions=[],
                receipt=existing_receipt,
            )

        new_canonical_txs: List[CanonicalTransaction] = []
        dup_count = 0

        for idx, r in enumerate(records):
            action_raw = getattr(r, "canonical_action", getattr(r, "action", "BUY")).upper()
            symbol = getattr(r, "symbol", "US_EQUITY") or "CASH"
            t_date = getattr(r, "trade_date", getattr(r, "tx_date", date.today()))
            qty = getattr(r, "quantity", Decimal("0.00")) or Decimal("0.00")
            price = getattr(r, "price_usd", getattr(r, "price", Decimal("0.00"))) or Decimal("0.00")
            fees = getattr(r, "fees_usd", getattr(r, "fees_and_comm", Decimal("0.00")))
            net_amt = getattr(r, "net_amount_usd", getattr(r, "amount", Decimal("0.00")))

            fp = self.compute_transaction_fingerprint(
                portfolio_id=portfolio_id,
                institution=inst_str,
                isin_or_symbol=symbol,
                trade_date=t_date,
                action=action_raw,
                quantity=qty,
                unit_price=price,
                order_or_trade_id=f"{acc_no}_{idx}",
            )

            if self.is_transaction_seen(fp):
                dup_count += 1
                continue

            tx = CanonicalTransaction(
                transaction_id=fp,
                statement_id=getattr(stmt, "statement_id", None),
                statement_hash=stmt_hash,
                portfolio_id=portfolio_id,
                client_pan=client_pan,
                broker=inst_str,
                account_number=acc_no,
                trade_date=t_date,
                asset_id=symbol,
                symbol=symbol,
                security_name=getattr(r, "description", symbol),
                action=action_raw,
                quantity=qty,
                price=price,
                gross_amount=(qty * price).quantize(Decimal("0.01")),
                fees_and_charges=fees,
                net_amount=net_amt,
                currency="USD",
                forex_rate=forex_rate,
                net_amount_inr=(net_amt * forex_rate).quantize(Decimal("0.01")),
                fingerprint=fp,
                status=TransactionStatus.PROCESSED,
                created_at=datetime.now(),
            )
            new_canonical_txs.append(tx)

        receipt = StatementReceipt(
            statement_hash=stmt_hash,
            institution=inst_str,
            account_number=acc_no,
            net_amount=total_net_usd,
            trades_count=len(records),
            status="COMPLETED",
        )
        self._ingested_statement_hashes[stmt_hash] = receipt

        for tx in new_canonical_txs:
            self._seen_transaction_fingerprints.add(tx.fingerprint)
            self._canonical_ledger.append(tx)

        return ReconciliationGateResult(
            passed=True,
            is_duplicate_statement=False,
            idempotent_noop=False,
            statement_hash=stmt_hash,
            total_transactions=len(records),
            new_transactions_count=len(new_canonical_txs),
            duplicate_transactions_count=dup_count,
            canonical_transactions=new_canonical_txs,
            receipt=receipt,
        )

    def _reconcile_generic(
        self,
        stmt: Any,
        portfolio_id: str,
        client_pan: str,
        institution_override: Optional[str],
        forex_rate: Decimal,
    ) -> ReconciliationGateResult:
        stmt_hash = hashlib.sha256(str(stmt).encode("utf-8")).hexdigest()
        return ReconciliationGateResult(
            passed=True,
            statement_hash=stmt_hash,
            total_transactions=0,
            new_transactions_count=0,
            duplicate_transactions_count=0,
            canonical_transactions=[],
        )


# Global default instance & convenience helpers
_default_reconciliation_gate = ReconciliationGate()


def evaluate_reconciliation_gate(
    statement: Any,
    portfolio_id: str,
    client_pan: str,
    institution: Optional[str] = None,
    forex_rate: Decimal = Decimal("1.00"),
) -> ReconciliationGateResult:
    """Convenience functional interface for evaluating a statement through Gate 4."""
    return _default_reconciliation_gate.reconcile(
        statement=statement,
        portfolio_id=portfolio_id,
        client_pan=client_pan,
        institution=institution,
        forex_rate=forex_rate,
    )
