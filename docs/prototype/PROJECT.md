# Project: MoneyMoney Financial Statement Ingestion Pipeline (Family Wealth Vault)

## Architecture
The MoneyMoney ingestion pipeline extends the fail-closed 4-gate architecture to investment contract notes and wealth assets across all Taylor family entities (Alex, Robert, Margaret, and Taylor Family Trust).

```
[Raw Forwarded MIME / Attachment Stream / Manual Upload]
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ GATE 1: IDENTITY GATE (Sender & PAN Whitelist)          │
│ • Forwarder Email in Authorized Whitelist               │
│ • Original Sender Domain in Broker Whitelist            │
│ • Target PAN / Account matched to Vault Entity          │
└──────────────────────────┬──────────────────────────────┘
                           │ PASS (Candidate Promoted)
                           ▼
┌─────────────────────────────────────────────────────────┐
│ GATE 2: SUPPORTED-LAYOUT GATE (Signature & Decryption)  │
│ • Magic Bytes & Document Tokens Matched                 │
│ • Deterministic Decryption (PAN / DOB schemes)          │
│ • Dispatched to Typed Parser:                           │
│   - ZerodhaContractNoteParser                           │
│   - HDFCSecContractNoteParser                           │
│   - CamsKfintechCasParser                               │
│   - CharlesSchwabParser                                 │
└──────────────────────────┬──────────────────────────────┘
                           │ PASS (Structured AST Generated)
                           ▼
┌─────────────────────────────────────────────────────────┐
│ GATE 3: VALIDATION GATE (Fail-Closed Mathematical Guard)│
│ • Gross - Brokerage - Taxes == Net Settlement           │
│ • Line Item Charges == Aggregated Invoices              │
│ • CAS Unit Balance Continuity (Opening + Net == Closing)│
│ • Absolute Invariant Tolerance <= 0.02                  │
└──────────────────────────┬──────────────────────────────┘
                           │ PASS (Verified Intermediate Records)
                           ▼
┌─────────────────────────────────────────────────────────┐
│ GATE 4: RECONCILIATION GATE (Deduplication & Forex)     │
│ • Statement Boundary Hash (Idempotency Receipt)         │
│ • Transaction Fingerprint Hash (SHA-256 Deduplication)  │
│ • RBI Reference Forex Conversion (Historical USD->INR)  │
│ • Chronological FIFO Tax Lot Accounting Engine          │
└──────────────────────────┬──────────────────────────────┘
                           │ PASS (Canonical Ingestion)
                           ▼
┌─────────────────────────────────────────────────────────┐
│ CANONICAL TAYLOR FAMILY VAULT LEDGER                  │
│ • canonical_transactions                                │
│ • active_tax_lots (STCG / LTCG / 112A Exemption)        │
│ • tax_lot_dispositions (Schedule FA & Form 67 FTC)     │
│ • portfolio_asset_balances                              │
└─────────────────────────────────────────────────────────┘
```

---

## Feature Inventory

Every feature requested in `ORIGINAL_REQUEST.md` is cataloged below with its designated milestone.

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Inbound Forwarded Email Parsing | Parse RFC 822 / MIME multipart emails from authorized family accounts (`alex.taylor@example.com`, `robert.taylor@example.com`, `margaret.taylor@example.com`). | M1 | ORIGINAL_REQUEST §R1 |
| 2 | Identity Gate & Domain Verification | Validate broker domain whitelist (`@zerodha.com`, `@hdfcsec.com`, `@camsonline.com`, `@kfintech.com`, `@schwab.com`) and match target entity PAN/Account. | M1 | ORIGINAL_REQUEST §R1 |
| 3 | Secure In-Memory Attachment Extraction | Extract PDF/CSV attachments into memory streams without disk writes. | M1 | ORIGINAL_REQUEST §R1 |
| 4 | Supported-Layout Identification | Signature & token sniffing to classify document format and broker layout. | M2 | ORIGINAL_REQUEST §R2 |
| 5 | Multi-Candidate PDF Decryption | In-memory `pikepdf` decryption cascade with entity PAN, DOB, name+DOB permutations. | M2 | ORIGINAL_REQUEST §R2 |
| 6 | Zerodha Contract Note Parser | Extract trade executions, ISINs, brokerage, STT, turnover fees, stamp duty, CGST/SGST/IGST, net settlement. | M2 | ORIGINAL_REQUEST §R2 |
| 7 | HDFC Securities Parser | Extract settlement number, scrip details, charges, Demat allocation fees, net amount. | M2 | ORIGINAL_REQUEST §R2 |
| 8 | CAMS / KFintech e-CAS Parser | Extract folios, schemes, AMFI codes, transaction types (PURCHASE, SIP, REDEMPTION, DIVIDEND REINVESTMENT, STAMP DUTY), units, NAV. | M2 | ORIGINAL_REQUEST §R2 |
| 9 | Charles Schwab (US) Parser | Extract trades (Buy/Sell), reinvested/cash dividends, SEC fees, and IRS 1042-S 25% withholding tax. | M2 | ORIGINAL_REQUEST §R2 |
| 10 | Fail-Closed Mathematical Validation Gate | Zero-tolerance invariant checks ($Gross - Brokerage - Levies == Net$, GST exactness, unit continuity). | M3 | ORIGINAL_REQUEST §R3 |
| 11 | Transaction Fingerprinting & Idempotency | Deterministic SHA-256 fingerprinting and statement boundary hashing (0 duplicate ledger writes on re-ingestion). | M3 | ORIGINAL_REQUEST §R3 |
| 12 | RBI Reference Forex Rate Engine | Historical USD/INR conversion for Schwab US transactions & Rule 115 / Schedule FA compliance. | M3 | ORIGINAL_REQUEST §R3 |
| 13 | FIFO Tax Lot Accounting Engine | Full Finance Act 2024 / Budget 2024 compliance (12.5% LTCG, 20% STCG, ₹1.25L Sec 112A exemption, 24m foreign threshold, Section 50AA, SGB Sec 47). | M3 | ORIGINAL_REQUEST §R3 |
| 14 | Canonical Ledger Integration & API Endpoints | Ingestion API endpoints (`/api/statements/inbound-email`, `/api/statements/process-file`, `/api/ledger/*`) and frontend integration. | M3 | ORIGINAL_REQUEST §R3 |
| 15 | Multi-Tier Automated E2E Test Suite | Comprehensive opaque-box test suite (Tiers 1-4: >=5 per feature, boundaries, pairwise, real-world multi-broker workloads). | Track E2E | ORIGINAL_REQUEST §Acceptance |
| 16 | Adversarial Hardening & Forensic Verification | Tier 5 adversarial stress testing + Forensic integrity verification. | M4 | ORIGINAL_REQUEST §Acceptance |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| **Track E2E** | E2E Testing Suite (Tiers 1-4) | Comprehensive opaque-box test framework, synthetic/sample statements, test runner, `TEST_INFRA.md`, `TEST_READY.md`. | none | DONE |
| **M1** | Inbound Email & Identity Gate | MIME parsing, sender/forwarder whitelist, target entity PAN/account matching, memory attachment extractor. | none | DONE |
| **M2** | Decryption Engine & Multi-Broker Parsers | Layout classifier, `pikepdf` password cascade, Zerodha ECN, HDFC Sec, CAMS/KFintech e-CAS, Charles Schwab parsers. | M1 | DONE |
| **M3** | Validation, Reconciliation, Forex & FIFO Ledger | Math validation gate ($\epsilon \le 0.02$), SHA-256 fingerprinting & boundary hashing, RBI forex engine, FIFO tax lots, API endpoints. | M2 | DONE |
| **M4** | 100% E2E Test Pass & Adversarial Hardening | Pass 100% E2E test suite (Tiers 1-4), Tier 5 adversarial stress testing, Forensic Integrity Audit, final verification. | M3, Track E2E | DONE |

---

## Code Layout

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app & routing
│   ├── config.py                        # Whitelists, constants, settings
│   ├── models/
│   │   ├── __init__.py
│   │   ├── email.py                     # MIME & email models
│   │   ├── contract_note.py             # Broker contract note & trade models
│   │   ├── cas.py                       # CAMS/KFintech CAS models
│   │   ├── schwab.py                    # Charles Schwab US models
│   │   └── ledger.py                    # Canonical ledger & tax lot models
│   ├── gates/
│   │   ├── __init__.py
│   │   ├── identity_gate.py             # Gate 1: Email, domain & PAN whitelist
│   │   ├── layout_gate.py               # Gate 2: Sniffer & pikepdf decryption cascade
│   │   ├── validation_gate.py           # Gate 3: Mathematical invariant checker
│   │   └── reconciliation_gate.py       # Gate 4: Fingerprint deduplication & boundary hash
│   ├── parsers/
│   │   ├── __init__.py
│   │   ├── base.py                      # Abstract parser interface
│   │   ├── zerodha_parser.py            # Zerodha ECN PDF & Tradebook CSV parser
│   │   ├── hdfc_parser.py               # HDFC Securities contract note parser
│   │   ├── cas_parser.py                # CAMS & KFintech mutual fund CAS parser
│   │   └── schwab_parser.py             # Charles Schwab US CSV/PDF parser
│   ├── engines/
│   │   ├── __init__.py
│   │   ├── forex_engine.py              # RBI / FBIL USD/INR Reference Rate engine
│   │   ├── fifo_tax_engine.py           # Finance Act 2024 FIFO tax lot & capital gains engine
│   │   └── ledger_service.py            # Canonical ledger synchronization & persistence
│   └── fixtures/
│       ├── __init__.py
│       └── sample_statements.py         # Deterministic sample statements & email MIME payloads
├── tests/
│   ├── __init__.py
│   ├── conftest.py                      # Pytest fixtures & mock environment
│   ├── test_tier1_feature_coverage.py   # Tier 1: >=5 test cases per feature
│   ├── test_tier2_boundary_corner.py    # Tier 2: Boundaries, edge cases, malformed payloads
│   ├── test_tier3_cross_feature.py      # Tier 3: Pairwise combinations & state transitions
│   ├── test_tier4_workloads.py          # Tier 4: Real-world multi-broker full pipeline scenarios
│   └── test_tier5_adversarial.py        # Tier 5: Adversarial attack cases & stress tests
```

---

## Forensic Integrity Guard
- No hardcoded test fixtures in production logic.
- No dummy/mock bypasses in validation or reconciliation gates.
- Strict math verification tolerance $\epsilon \le 0.02$.
- Binary veto on any Forensic Auditor integrity violation.
