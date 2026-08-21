"""
Canonical Ledger Service (LedgerService)
Coordinates the complete fail-closed 4-gate ingestion pipeline:
[Raw Email/File Payload] -> Gate 1 (Identity) -> Gate 2 (Layout & Decryption) ->
Gate 3 (Math Validation) -> Gate 4 (Reconciliation & Deduplication) ->
Forex Engine (USD->INR) -> FIFO Tax Lot Engine -> Canonical Family Ledger State.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
import os
import json

try:
    from google.cloud import firestore
except ImportError:
    firestore = None


from ..config import (
    BrokerInstitution,
    FamilyEntityProfile,
    get_entity_by_email,
    get_entity_by_pan,
)
from ..gates.identity_gate import evaluate_identity_gate
from ..gates.layout_gate import evaluate_layout_gate
from ..gates.reconciliation_gate import ReconciliationGate, evaluate_reconciliation_gate
from ..gates.validation_gate import evaluate_validation_gate
from ..models.email import ExtractedAttachment, InboundEmailPayload
from ..models.ledger import (
    ActiveTaxLot,
    CanonicalTransaction,
    CapitalGainsSummary,
    PortfolioAssetBalance,
    StatementReceipt,
    TaxAssetType,
    TaxDispositionRecord,
    TransactionStatus,
)
from .fifo_tax_engine import FIFOTaxEngine
from .forex_engine import ForexEngine


class LedgerService:
    """
    Core Canonical Family Ledger Service and Ingestion Orchestrator.
    """

    def __init__(self):
        self.reconciliation_gate = ReconciliationGate()
        self.forex_engine = ForexEngine()
        self.fifo_engine = FIFOTaxEngine()
        self.canonical_transactions: List[CanonicalTransaction] = []
        self.statement_receipts: List[StatementReceipt] = []
        self.db = None
        if firestore is not None:
            try:
                self.db = firestore.Client(project=os.getenv("FIREBASE_PROJECT_ID", "family-vault-demo"))
            except Exception as e:
                self.db = None


    def reset_state(self):
        """Resets all in-memory ledger transactions, tax lots, and statement receipts."""
        self.reconciliation_gate.reset_state()
        self.fifo_engine.reset_state()
        self.canonical_transactions.clear()
        self.statement_receipts.clear()

    def ingest_inbound_email(
        self,
        raw_mime: bytes,
        forwarder_email: Optional[str] = None,
        target_pan: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes end-to-end ingestion pipeline on inbound forwarded email payload.
        """
        # Step 1: Gate 1 (Identity Gate)
        payload = InboundEmailPayload(
            raw_mime=raw_mime,
            forwarder_email=forwarder_email,
            target_pan=target_pan,
        )
        g1_res = evaluate_identity_gate(payload)
        if not g1_res.passed:
            return {
                "success": False,
                "failed_gate": "GATE_1_IDENTITY",
                "rejection_code": g1_res.rejection_code,
                "rejection_reason": g1_res.rejection_reason,
            }

        entity = get_entity_by_pan(g1_res.target_pan) if g1_res.target_pan else None
        portfolio_id = g1_res.target_entity_id or "port_primary"
        client_pan = g1_res.target_pan or "KLMNO9012P"

        attachment_results = []
        total_new_writes = 0
        total_dup_writes = 0

        for att in g1_res.extracted_attachments:
            # Step 2: Gate 2 (Layout & Decryption)
            g2_res = evaluate_layout_gate(
                attachment=att,
                entity_profile=entity,
                expected_broker=g1_res.broker_institution,
            )
            if not g2_res.passed:
                return {
                    "success": False,
                    "failed_gate": "GATE_2_LAYOUT",
                    "rejection_code": g2_res.rejection_code,
                    "rejection_reason": g2_res.rejection_reason,
                    "attachment": att.filename,
                }

            # Step 3: Gate 3 (Math Validation)
            g3_res = evaluate_validation_gate(g2_res.parsed_statement)
            if not g3_res.passed:
                return {
                    "success": False,
                    "failed_gate": "GATE_3_VALIDATION",
                    "rejection_code": g3_res.rejection_code,
                    "rejection_reason": g3_res.rejection_reason,
                    "discrepancy": g3_res.discrepancy,
                    "attachment": att.filename,
                }

            # Step 4: Gate 4 (Reconciliation & Deduplication)
            g4_res = self.reconciliation_gate.reconcile(
                statement=g2_res.parsed_statement,
                portfolio_id=portfolio_id,
                client_pan=client_pan,
                institution=g2_res.broker_institution or g1_res.broker_institution,
            )

            # Record statement receipt
            if g4_res.receipt and g4_res.receipt not in self.statement_receipts:
                self.statement_receipts.append(g4_res.receipt)

            # Step 5 & 6: Process FIFO Tax Lots for new canonical transactions
            for tx in g4_res.canonical_transactions:
                self._apply_transaction_to_tax_engine(tx)
                self.canonical_transactions.append(tx)

            total_new_writes += g4_res.new_transactions_count
            total_dup_writes += g4_res.duplicate_transactions_count

            attachment_results.append({
                "filename": att.filename,
                "layout_type": g2_res.layout_type,
                "statement_hash": g4_res.statement_hash,
                "is_duplicate_statement": g4_res.is_duplicate_statement,
                "new_transactions": g4_res.new_transactions_count,
                "duplicate_transactions": g4_res.duplicate_transactions_count,
            })

        self._flush_to_firestore(portfolio_id)
        return {
            "success": True,
            "portfolio_id": portfolio_id,
            "client_pan": client_pan,
            "broker_institution": g1_res.broker_institution,
            "attachments_processed": len(attachment_results),
            "new_transactions_committed": total_new_writes,
            "duplicate_transactions_skipped": total_dup_writes,
            "results": attachment_results,
        }

    def ingest_file_attachment(
        self,
        file_bytes: bytes,
        filename: str,
        portfolio_id: Optional[str] = None,
        target_pan: Optional[str] = None,
        password: Optional[str] = None,
        broker: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ingests a standalone PDF/CSV file (manual upload or direct webhook).
        """
        clean_pan = (target_pan or "").strip().upper()
        entity = get_entity_by_pan(clean_pan) if clean_pan else None
        resolved_portfolio = portfolio_id or (entity.entity_id if entity else "port_primary")
        resolved_pan = clean_pan or (entity.pan if entity else "KLMNO9012P")

        import hashlib
        att = ExtractedAttachment(
            filename=filename,
            content_type="application/pdf" if filename.lower().endswith(".pdf") else "text/csv",
            size_bytes=len(file_bytes),
            payload_bytes=file_bytes,
            sha256=hashlib.sha256(file_bytes).hexdigest(),
        )

        # Gate 2
        g2_res = evaluate_layout_gate(
            attachment=att,
            entity_profile=entity,
            raw_user_password=password,
            expected_broker=broker,
        )
        if not g2_res.passed:
            return {
                "success": False,
                "failed_gate": "GATE_2_LAYOUT",
                "rejection_code": g2_res.rejection_code,
                "rejection_reason": g2_res.rejection_reason,
            }

        # Gate 3
        g3_res = evaluate_validation_gate(g2_res.parsed_statement)
        if not g3_res.passed:
            return {
                "success": False,
                "failed_gate": "GATE_3_VALIDATION",
                "rejection_code": g3_res.rejection_code,
                "rejection_reason": g3_res.rejection_reason,
                "discrepancy": g3_res.discrepancy,
            }

        # Gate 4
        g4_res = self.reconciliation_gate.reconcile(
            statement=g2_res.parsed_statement,
            portfolio_id=resolved_portfolio,
            client_pan=resolved_pan,
            institution=g2_res.broker_institution or broker,
        )

        if g4_res.receipt and g4_res.receipt not in self.statement_receipts:
            self.statement_receipts.append(g4_res.receipt)

        for tx in g4_res.canonical_transactions:
            self._apply_transaction_to_tax_engine(tx)
            self.canonical_transactions.append(tx)

        self._flush_to_firestore(resolved_portfolio)
        return {
            "success": True,
            "portfolio_id": resolved_portfolio,
            "client_pan": resolved_pan,
            "statement_hash": g4_res.statement_hash,
            "is_duplicate_statement": g4_res.is_duplicate_statement,
            "new_transactions_committed": g4_res.new_transactions_count,
            "duplicate_transactions_skipped": g4_res.duplicate_transactions_count,
        }


    def _flush_to_firestore(self, portfolio_id: str):
        if not self.db:
            return
        
        try:
            doc_ref = self.db.collection('family_vaults').document(os.getenv('FIRESTORE_VAULT_DOC', 'default_family'))
            doc = doc_ref.get()
            if not doc.exists:
                return
            
            data = doc.to_dict()
            portfolios = data.get('portfolios', [])
            
            # Find the target portfolio
            target_p = None
            for p in portfolios:
                if p.get('id') == portfolio_id:
                    target_p = p
                    break
            
            if not target_p:
                return
                
            # Get updated portfolio balances from the FIFO engine
            balances = self.get_portfolio_balances(portfolio_id)
            
            # Map balances back to frontend Asset structure
            existing_assets = target_p.get('assets', [])
            
            for bal in balances:
                # Find if asset exists
                asset = next((a for a in existing_assets if a.get('symbolOrCode') == bal.symbol), None)
                if not asset:
                    asset = {
                        "id": f"ast_{bal.asset_id}",
                        "portfolioId": portfolio_id,
                        "assetType": bal.asset_type.value if hasattr(bal.asset_type, "value") else str(bal.asset_type),
                        "currency": bal.currency,
                        "name": bal.security_name,
                        "symbolOrCode": bal.symbol,
                        "institution": "Ingested Broker",
                        "quantity": 0,
                        "totalInvested": 0,
                        "currentPrice": 0,
                        "currentValue": 0,
                        "unrealizedPnl": 0,
                        "pnlPercentage": 0,
                        "lastSynced": datetime.now().isoformat()
                    }
                    existing_assets.append(asset)
                
                asset["quantity"] = float(bal.total_quantity)
                asset["totalInvested"] = float(bal.total_cost_basis_inr)
                asset["currentPrice"] = float(bal.current_price)
                asset["currentValue"] = float(bal.current_valuation_inr)
                asset["unrealizedPnl"] = float(bal.unrealized_gain_inr)
                asset["pnlPercentage"] = (float(bal.unrealized_gain_inr) / float(bal.total_cost_basis_inr) * 100) if float(bal.total_cost_basis_inr) > 0 else 0
                asset["lastSynced"] = datetime.now().isoformat()

            # Save back to Firestore
            doc_ref.update({"portfolios": portfolios, "lastUpdated": datetime.now().isoformat()})
        except Exception as e:
            print(f"Failed to flush to Firestore: {e}")

    def _apply_transaction_to_tax_engine(self, tx: CanonicalTransaction):
        """
        Dispatches canonical transaction to FIFO Tax Engine (Buy Lot vs Sell Disposition).
        """
        action = str(tx.action).upper().strip()
        asset_type = self._classify_asset_type(tx.broker, tx.symbol, tx.security_name)

        forex_rate = tx.forex_rate
        if tx.currency == "USD" and forex_rate == Decimal("1.00"):
            forex_rate = self.forex_engine.lookup_rate(tx.trade_date, mode="SPOT")
            tx.forex_rate = forex_rate
            tx.net_amount_inr = (tx.net_amount * forex_rate).quantize(Decimal("0.01"))

        if action in ("BUY", "SIP", "PURCHASE", "DIVIDEND_REINVEST", "REINVEST DIVIDEND", "BONUS"):
            if tx.quantity > Decimal("0.00"):
                self.fifo_engine.buy_lot(
                    portfolio_id=tx.portfolio_id,
                    asset_id=tx.asset_id,
                    asset_type=asset_type,
                    buy_date=tx.trade_date,
                    quantity=tx.quantity,
                    price=tx.price,
                    currency=tx.currency,
                    forex_rate=forex_rate,
                    expenses=tx.fees_and_charges,
                    client_pan=tx.client_pan,
                    symbol=tx.symbol,
                )
        elif action in ("SELL", "REDEMPTION", "SWITCH_OUT"):
            qty_to_sell = abs(tx.quantity)
            if qty_to_sell > Decimal("0.00"):
                try:
                    self.fifo_engine.sell_units(
                        portfolio_id=tx.portfolio_id,
                        asset_id=tx.asset_id,
                        asset_type=asset_type,
                        sell_date=tx.trade_date,
                        quantity=qty_to_sell,
                        sell_price=tx.price,
                        currency=tx.currency,
                        forex_rate=forex_rate,
                        expenses=tx.fees_and_charges,
                        client_pan=tx.client_pan,
                    )
                except ValueError:
                    # Oversell or unrecorded initial lot; gracefully handle or log
                    pass

    @staticmethod
    def _classify_asset_type(broker: str, symbol: str, sec_name: str) -> TaxAssetType:
        """Determines statutory tax asset type based on broker, symbol, and description."""
        b_clean = (broker or "").upper()
        s_clean = (symbol or "").upper()
        n_clean = (sec_name or "").upper()

        if "SCHWAB" in b_clean or "US_" in s_clean:
            return TaxAssetType.US_EQUITY
        if "SGB" in s_clean or "SGB" in n_clean:
            return TaxAssetType.SGB_MATURITY if "MATURITY" in n_clean else TaxAssetType.SGB
        if "DEBT" in s_clean or "DEBT" in n_clean:
            return TaxAssetType.DEBT_MUTUAL_FUND
        if "CAMS" in b_clean or "KFIN" in b_clean or "INF" in s_clean or "MUTUAL" in n_clean:
            return TaxAssetType.INDIAN_MUTUAL_FUND
        if "GOLD" in s_clean or "GOLD" in n_clean:
            return TaxAssetType.GOLD_PHYSICAL
        return TaxAssetType.INDIAN_EQUITY

    def get_transactions(
        self,
        portfolio_id: Optional[str] = None,
        broker: Optional[str] = None,
        isin_or_symbol: Optional[str] = None,
        start_date: Optional[Union[date, str]] = None,
        end_date: Optional[Union[date, str]] = None,
    ) -> List[CanonicalTransaction]:
        """Queries canonical ledger transactions with optional filters."""
        res = []
        for tx in self.canonical_transactions:
            if portfolio_id and tx.portfolio_id != portfolio_id:
                continue
            if broker and tx.broker.upper() != broker.upper():
                continue
            if isin_or_symbol and (tx.asset_id.upper() != isin_or_symbol.upper() and tx.symbol.upper() != isin_or_symbol.upper()):
                continue
            if start_date:
                sd = datetime.strptime(start_date, "%Y-%m-%d").date() if isinstance(start_date, str) else start_date
                if tx.trade_date < sd:
                    continue
            if end_date:
                ed = datetime.strptime(end_date, "%Y-%m-%d").date() if isinstance(end_date, str) else end_date
                if tx.trade_date > ed:
                    continue
            res.append(tx)
        return res

    def get_active_tax_lots(
        self,
        portfolio_id: Optional[str] = None,
        asset_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries open tax lots from FIFO engine."""
        return self.fifo_engine.get_open_lots(portfolio_id=portfolio_id, asset_id=asset_id)

    def get_tax_dispositions(
        self,
        portfolio_id: Optional[str] = None,
        financial_year: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries realized tax dispositions from FIFO engine."""
        return self.fifo_engine.get_dispositions(portfolio_id=portfolio_id, financial_year=financial_year)

    def get_capital_gains_summary(
        self,
        portfolio_id: str,
        financial_year: Optional[str] = None,
    ) -> CapitalGainsSummary:
        """Queries aggregated capital gains summary for a portfolio."""
        return self.fifo_engine.compute_capital_gains_summary(
            portfolio_id=portfolio_id,
            financial_year=financial_year,
        )

    def get_portfolio_balances(
        self,
        portfolio_id: Optional[str] = None,
    ) -> List[PortfolioAssetBalance]:
        """Calculates current portfolio asset balances based on active open tax lots."""
        open_lots = self.fifo_engine.get_open_lots(portfolio_id=portfolio_id)
        asset_map: Dict[str, Dict[str, Any]] = {}

        for lot in open_lots:
            key = f"{lot['portfolio_id']}:{lot['asset_id']}"
            if key not in asset_map:
                asset_map[key] = {
                    "portfolio_id": lot["portfolio_id"],
                    "asset_id": lot["asset_id"],
                    "symbol": lot["symbol"],
                    "asset_type": lot["asset_type"],
                    "currency": lot["currency"],
                    "total_quantity": Decimal("0.0000"),
                    "total_cost_basis_inr": Decimal("0.00"),
                }
            qty = lot["remaining_quantity"]
            cost_inr = qty * lot["cost_per_unit_inr"]
            asset_map[key]["total_quantity"] += qty
            asset_map[key]["total_cost_basis_inr"] += cost_inr

        balances: List[PortfolioAssetBalance] = []
        for b in asset_map.values():
            qty = b["total_quantity"]
            cost_tot = b["total_cost_basis_inr"].quantize(Decimal("0.01"))
            avg_cost = (cost_tot / qty).quantize(Decimal("0.01")) if qty > Decimal("0.00") else Decimal("0.00")

            bal = PortfolioAssetBalance(
                portfolio_id=b["portfolio_id"],
                asset_id=b["asset_id"],
                symbol=b["symbol"],
                security_name=b["symbol"],
                asset_type=b["asset_type"],
                total_quantity=qty,
                average_cost_inr=avg_cost,
                total_cost_basis_inr=cost_tot,
                current_price=avg_cost,
                current_valuation_inr=cost_tot,
                unrealized_gain_inr=Decimal("0.00"),
                currency=b["currency"],
            )
            balances.append(bal)

        return balances

    def get_statement_receipts(self, portfolio_id: Optional[str] = None) -> List[StatementReceipt]:
        """Returns all ingested statement boundary receipts."""
        return list(self.statement_receipts)


# Global default singleton instance
_default_ledger_service = LedgerService()


def get_ledger_service() -> LedgerService:
    """Returns the global default instance of LedgerService."""
    return _default_ledger_service
