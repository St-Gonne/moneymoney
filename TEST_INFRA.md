# MoneyMoney Ingestion Pipeline: Test Infrastructure & Philosophy (`TEST_INFRA.md`)

## 1. Testing Philosophy & Core Principles

The MoneyMoney automated financial statement ingestion pipeline manages personal wealth ledgers and tax liabilities for all members of the Family Wealth Vault (Alex, Robert, Margaret, and Taylor Family Trust). Ingestion defects can lead to corrupted portfolio valuations, erroneous tax computations, and regulatory non-compliance under Indian Income Tax (ITR-2 / ITR-3 Schedule FA & Section 112A).

To ensure ledger integrity, the test infrastructure adheres to four fundamental principles:

1. **Opaque-Box Requirement-Driven Design**:
   Tests are authored strictly against official specifications, regulatory rules (Finance Act 2024, Rule 115, SEBI Circulars, GST 18%, IRS 1042-S 25%), and interface contracts in `PROJECT.md`, without coupling to transient implementation internals.

2. **Fail-Closed Perimeter & Math Guard**:
   Every statement payload is treated as untrusted provisional evidence until it clears all 4 perimeter gates (Identity, Supported-Layout & Decryption, Mathematical Invariant, and Reconciliation Deduplication). Any discrepancy exceeding $\epsilon = 0.02$ causes immediate rejection with zero ledger mutation.

3. **Multi-Tier Hierarchy with Forensic Integrity**:
   Coverage is organized into 5 systematic tiers, ranging from unit feature verification to multi-broker annual family workloads and adversarial stress testing.

4. **Zero-Flake Determinism & In-Memory Safety**:
   All test fixtures, historical forex lookup tables, and MIME payloads are fully deterministic and execute completely in memory without disk leakage or external network dependencies.

---

## 2. Test Tier Architecture & Count Breakdown

| Tier | Purpose | Scope | Test Count |
|---|---|---|---|
| **Tier 1: Feature Coverage** | Happy-path & canonical inputs for all 16 features | Minimum 5 test cases per feature covering Zerodha, HDFC, CAMS, Schwab, MIME emails, RBI forex, and FIFO engine | **80 tests** |
| **Tier 2: Boundary & Corner Cases** | Extreme values, fail-closed negative tests, edge conditions | Empty payloads, micro-trades, ₹100 Cr extremes, leap years, sub-paise GST rounding, corrupted MIME boundaries, password exhaustion | **80 tests** |
| **Tier 3: Cross-Feature Interactions** | Pairwise multi-gate state transitions | Identity Pass + Layout Fail, Valid Decryption + Math Failure, Multi-broker mixed portfolio ingestion, overlapping date deduplication | **15 tests** |
| **Tier 4: Real-World Workloads** | Complete family vault annual workloads | Alex (US Schwab + Zerodha + CAMS), Robert (HDFC + SGB + CAS), Margaret (Gold + CAS), HUF (Index Fund + FD), Section 112A exemption, Schedule FA audit | **7 tests** |
| **Tier 5: Adversarial Hardening** | Forensic integrity & attack surface testing | Shaving attacks, SHA-256 fingerprint bit-flip tampering, spoofed domain headers, path traversal defense, zero disk leakage audit | **10 tests** |
| **TOTAL** | **Comprehensive Full Suite Coverage** | **All 16 Features + 4 Gates + 4 Family Portfolios** | **192 tests** |

---

## 3. Feature Matrix Mapping (PROJECT.md ↔ Test Suite)

| Feature # | Feature Name | Tier 1 Coverage | Tier 2 Coverage | Tiers 3-5 Verification |
|---|---|---|---|---|
| **F1** | Inbound Forwarded Email Parsing | `test_f01_tc01..tc05` (5 tests) | `test_f01_b01..b05` (5 tests) | `test_pair_01`, `test_pair_12`, `test_adv_05` |
| **F2** | Identity Gate & Domain Verification | `test_f02_tc01..tc05` (5 tests) | `test_f02_b01..b05` (5 tests) | `test_pair_01`, `test_adv_04`, `test_adv_05` |
| **F3** | Secure In-Memory Attachment Extraction | `test_f03_tc01..tc05` (5 tests) | `test_f03_b01..b05` (5 tests) | `test_adv_06` |
| **F4** | Supported-Layout Identification | `test_f04_tc01..tc05` (5 tests) | `test_f04_b01..b05` (5 tests) | `test_pair_01` |
| **F5** | Multi-Candidate PDF Decryption | `test_f05_tc01..tc05` (5 tests) | `test_f05_b01..b05` (5 tests) | `test_pair_02` |
| **F6** | Zerodha Contract Note Parser | `test_f06_tc01..tc05` (5 tests) | `test_f06_b01..b05` (5 tests) | `test_pair_04`, `test_scenario_01` |
| **F7** | HDFC Securities Parser | `test_f07_tc01..tc05` (5 tests) | `test_f07_b01..b05` (5 tests) | `test_pair_04`, `test_scenario_02` |
| **F8** | CAMS / KFintech e-CAS Parser | `test_f08_tc01..tc05` (5 tests) | `test_f08_b01..b05` (5 tests) | `test_pair_08`, `test_scenario_01..04` |
| **F9** | Charles Schwab (US) Parser | `test_f09_tc01..tc05` (5 tests) | `test_f09_b01..b05` (5 tests) | `test_pair_07`, `test_scenario_01` |
| **F10** | Fail-Closed Validation Gate ($\epsilon \le 0.02$) | `test_f10_tc01..tc05` (5 tests) | `test_f10_b01..b05` (5 tests) | `test_pair_02`, `test_adv_01`, `test_adv_02` |
| **F11** | Transaction Fingerprinting & Idempotency | `test_f11_tc01..tc05` (5 tests) | `test_f11_b01..b05` (5 tests) | `test_pair_03`, `test_pair_06`, `test_scenario_07` |
| **F12** | RBI Reference Forex Rate Engine | `test_f12_tc01..tc05` (5 tests) | `test_f12_b01..b05` (5 tests) | `test_pair_07`, `test_scenario_01`, `test_scenario_06` |
| **F13** | FIFO Tax Lot Accounting Engine | `test_f13_tc01..tc05` (5 tests) | `test_f13_b01..b05` (5 tests) | `test_pair_05`, `test_pair_08`, `test_pair_11`, `test_scenario_06` |
| **F14** | Canonical Ledger Integration & APIs | `test_f14_tc01..tc05` (5 tests) | `test_f14_b01..b05` (5 tests) | `test_pair_10`, `test_scenario_05` |
| **F15** | Multi-Tier Automated E2E Test Suite | `test_f15_tc01..tc05` (5 tests) | `test_f15_b01..b05` (5 tests) | `run_all_tests.py` |
| **F16** | Adversarial Hardening & Forensics | `test_f16_tc01..tc05` (5 tests) | `test_f16_b01..b05` (5 tests) | `test_adv_01..10` (10 tests) |

---

## 4. Test Fixtures & Synthetic Statement Generators

The test harness provides high-fidelity synthetic fixture generators in `backend/tests/fixtures/`:

1. **`sample_family_vault.py`**:
   - Authorized family emails (`alex.taylor@example.com`, `robert.taylor@example.com`, `margaret.taylor@example.com`).
   - PAN & DOB registry for Alex (`KLMNO9012P`), Robert (`ABCDE1234F`), Margaret (`FGHIJ5678K`), and HUF (`PQRST3456Q`).
   - Curated historical RBI Reference Rate table (2022–2026).
2. **`sample_emails.py`**:
   - RFC 822 MIME generators with Gmail forwarded headers, broker attachments, spoofed domains, and unauthorized forwarders.
3. **`sample_zerodha.py`**:
   - Zerodha ECN PDF text and Tradebook CSV generators with exact SEBI charges (Brokerage, STT, Turnover, Stamp duty, 18% GST) and Net Settlement.
4. **`sample_hdfc.py`**:
   - HDFC Securities contract note generators with Demat Allocation Charges (₹13.50 + 18% GST = ₹15.93).
5. **`sample_cas.py`**:
   - CAMS & KFintech mutual fund CAS statements with unit balance continuity and 0.005% stamp duty on inflows.
6. **`sample_schwab.py`**:
   - Charles Schwab US activity CSV generators with Buy/Sell, Reinvest Dividend, Cash Dividend, IRS 1042-S 25% withholding, and SEC fees.

---

## 5. How to Run the Tests

### Option A: Using the Master Test Runner (Recommended)
```bash
python3 backend/tests/run_all_tests.py
```

### Option B: Using Pytest
```bash
pytest backend/tests/ -v
```

### Option C: Using Python Standard unittest Discovery
```bash
python3 -m unittest discover -s backend/tests -p "test_*.py" -v
```

### Option D: Running Individual Tiers
```bash
python3 -m unittest backend.tests.test_tier1_feature_coverage -v
python3 -m unittest backend.tests.test_tier2_boundary_corner -v
python3 -m unittest backend.tests.test_tier3_cross_feature -v
python3 -m unittest backend.tests.test_tier4_workloads -v
python3 -m unittest backend.tests.test_tier5_adversarial -v
```

---

## 6. Authoritative Expected Output Derivations

All test expectations are derived from statutory requirements and formal mathematical definitions:
1. **Gross Equity**: $\text{Gross} = \text{Quantity} \times \text{Gross Rate}$
2. **Net Settlement (Buy)**: $-\left(\text{Gross} + \text{Brokerage} + \text{STT} + \text{Turnover} + \text{Stamp Duty} + \text{GST} + \text{Demat}\right)$
3. **GST Exactness**: $\text{GST} = \left(\text{Brokerage} + \text{Turnover Fee} + \text{SEBI Fee} + \text{Demat Allocation Fee}\right) \times 18\%$
4. **CAS Unit Continuity**: $\text{Balance}_k = \text{Balance}_{k-1} + \Delta\text{Units}_k \quad (\pm 0.001)$
5. **US Dividend Withholding**: $\text{Tax Withheld} = \text{Gross Dividend} \times 25\%$ (IRS Section 1441 / 1042-S)
6. **Finance Act 2024 LTCG Exemption**: $\text{Taxable LTCG} = \max\left(0, \sum \text{LTCG} - \text{₹}1,25,000\right) \times 12.5\%$
7. **Foreign Asset Holding Period**: Domestic listed equity LTCG $> 12$ months; Foreign unlisted equity LTCG $> 24$ months.
