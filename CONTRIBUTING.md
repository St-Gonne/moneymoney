# 🤝 Contributing to MoneyMoney

Thank you for your interest in contributing to **MoneyMoney**! 

MoneyMoney is architected to be modular so anyone can add new broker statement parsers, tax regimes, or financial exporters without touching core ledger code.

---

## 🎯 High-Impact Contribution Areas

We actively welcome Pull Requests for:
1. **New Broker & Bank Parsers:** Groww, Upstox, ICICI Direct, Kotak Securities, Interactive Brokers (IBKR), Angel One.
2. **Tax & Compliance Exporters:** ClearTax / Quicko Tax P&L JSON schemas, Indian ITR-2 Schedule FA formatters.
3. **Currency & Macro Feeds:** Automated daily historical RBI / ECB exchange rate scrapers.
4. **Voice & Multimodal Latency:** Optimizing Gemini Live WebSocket audio chunking and screen context token serialization.

---

## 🛠️ Adding a New Broker Parser in 4 Steps

All parsers inherit from `BaseBrokerParser` located at [`backend/app/parsers/base.py`](backend/app/parsers/base.py).

### Step 1: Create your parser file
Create `backend/app/parsers/groww_parser.py`:

```python
from typing import Optional
from ..models.contract_note import NormalizedContractNote, NormalizedTradeItem, TradeAction
from ..models.email import ExtractedAttachment
from ..config import FamilyEntityProfile, BrokerInstitution
from .base import BaseBrokerParser

class GrowwParser(BaseBrokerParser):
    """Parser for Groww Contract Notes (PDF) and Tradebook (CSV)."""

    def can_parse(self, attachment: ExtractedAttachment, target_pan: Optional[str] = None) -> bool:
        fn = (attachment.filename or "").lower()
        data_sample = (attachment.payload_bytes or b"")[:4000]
        return "groww" in fn or b"GROWW" in data_sample

    def parse(
        self,
        attachment: ExtractedAttachment,
        entity_profile: Optional[FamilyEntityProfile] = None,
        password_used: Optional[str] = None,
    ) -> NormalizedContractNote:
        # 1. Parse text/tables from attachment.payload_bytes
        # 2. Extract trades into NormalizedTradeItem list
        # 3. Return NormalizedContractNote
        trades = []
        return NormalizedContractNote(
            contract_note_id="CN-GROWW-12345",
            broker=BrokerInstitution.GROWW,
            trade_date=date.today(),
            trades=trades,
            account_id="GROWW-DEMO",
            pan=entity_profile.pan if entity_profile else "KLMNO9012P",
        )
```

### Step 2: Register in Layout Gate
In [`backend/app/gates/layout_gate.py`](backend/app/gates/layout_gate.py), add your parser instance to `self.parsers`.

### Step 3: Add Synthetic Test Fixture
Add a sample synthetic statement in `backend/tests/fixtures/` (**NEVER include real names, real PANs, or actual account numbers**).

### Step 4: Run Tests
```bash
python3 backend/tests/run_all_tests.py
```

---

## 🧪 Local Test Suite Standards

Before opening a PR, ensure all three test suites pass cleanly:

```bash
# 1. Frontend Production Build & TypeScript Check
npm run build

# 2. UI / UX & WCAG 2.2 Invariant Tests
npm run test:ui

# 3. High-Precision XIRR Mathematical Tests
npm run test:xirr

# 4. Multi-Tier Python Ingestion Pipeline E2E Tests
python3 backend/tests/run_all_tests.py
```

---

## 🔒 PII & Data Privacy Guidelines for PRs

- **No Real PII in Code or Tests:** Never commit real names, email addresses, phone numbers, government PAN numbers, or actual portfolio figures.
- Use standard synthetic test personas (`Alex Taylor`, `Robert Taylor`, `Margaret Taylor`) and mock PANs (`KLMNO9012P`, `ABCDE1234F`).
- Any PR containing real investor PII will be rejected and purged immediately.

---

## 📄 Licensing

By contributing to MoneyMoney, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
