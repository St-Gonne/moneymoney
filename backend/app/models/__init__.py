"""
Data Models for MoneyMoney Ingestion Pipeline
"""

from .email import (
    ExtractedAttachment,
    ExtractedEmailMetadata,
    IdentityGateResult,
    InboundEmailPayload,
)
from .contract_note import (
    BrokerInstitution,
    TradedSegment,
    TradeAction,
    BrokerLevyBreakdown,
    NormalizedTradeItem,
    NormalizedContractNote,
)
from .cas import (
    CasTransactionRecord,
    NormalizedCasScheme,
    NormalizedCasFolio,
    NormalizedCasStatement,
)
from .schwab import (
    NormalizedSchwabRecord,
    NormalizedSchwabStatement,
)
from .ledger import (
    TransactionStatus,
    TaxAssetType,
    TaxHoldingType,
    TaxLotStatus,
    CanonicalTransaction,
    ActiveTaxLot,
    TaxDispositionRecord,
    PortfolioAssetBalance,
    CapitalGainsSummary,
    StatementReceipt,
)

__all__ = [
    "ExtractedAttachment",
    "ExtractedEmailMetadata",
    "IdentityGateResult",
    "InboundEmailPayload",
    "BrokerInstitution",
    "TradedSegment",
    "TradeAction",
    "BrokerLevyBreakdown",
    "NormalizedTradeItem",
    "NormalizedContractNote",
    "CasTransactionRecord",
    "NormalizedCasScheme",
    "NormalizedCasFolio",
    "NormalizedCasStatement",
    "NormalizedSchwabRecord",
    "NormalizedSchwabStatement",
    "TransactionStatus",
    "TaxAssetType",
    "TaxHoldingType",
    "TaxLotStatus",
    "CanonicalTransaction",
    "ActiveTaxLot",
    "TaxDispositionRecord",
    "PortfolioAssetBalance",
    "CapitalGainsSummary",
    "StatementReceipt",
]

