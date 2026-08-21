# Original User Request

## Initial Request — 2026-08-14T13:09:52Z

Build an automated, production-grade financial statement ingestion pipeline for the MoneyMoney platform (Family Wealth Vault) that expands the fail-closed statement guard architecture (inspired by https://github.com/alextaylor-ui/finance-tracker) from bank/card statements into investment contract notes and wealth assets. The system processes incoming forwarded Gmail messages, validates multi-gate evidence, decrypts password-protected PDF/CSV attachments (Zerodha, HDFC Securities, CAMS/KFintech e-CAS, Charles Schwab US), and reconciles canonical trades into the family ledger.

Working directory: /Users/Taylor_server/Documents/MoneyMoneyv1
Integrity mode: development

Reference material:
- Architecture Reference: https://github.com/alextaylor-ui/finance-tracker (finance_statement_guard fail-closed 4-gate ingestion and reconciliation model).

## Requirements

### R1. Inbound Forwarded Email Ingestion & Identity Gate
- Accept forwarded MIME / multipart email payloads from Gmail accounts (alex.taylor@example.com, robert.taylor@example.com, margaret.taylor@example.com).
- Identity Gate: Validate sender domain (@zerodha.com, @hdfcsec.com, @camsonline.com, @kfintech.com, @schwab.com) and match target account/PAN before promoting from provisional evidence to statement candidate.
- Securely extract PDF/CSV attachments into memory.

### R2. Supported-Layout & Multi-Format Decryption Engine
- Supported-Layout Gate: Identify exact broker statement layout and apply appropriate parser.
- Automatically decrypt password-protected statement PDFs using the target entity's PAN or DOB password.
- Extract structured transaction records:
  - Zerodha: Trade date, scrip name/ISIN, quantity, gross price, STT, brokerage, stamp duty, exchange turnover fee.
  - HDFC Securities: Settlement number, scrip details, transaction charges, and Demat allocation.
  - CAMS / KFintech e-CAS: Folio numbers, scheme names, AMFI codes, transaction type (PURCHASE, SIP, REDEMPTION, DIVIDEND REINVESTMENT), units, NAV, and stamp duty.
  - Charles Schwab (US): Action (Buy, Sell, Reinvest Dividend, IRS 1042-S withholding tax), ticker symbol, share quantity, USD price, and SEC transaction fees.

### R3. Fail-Closed Validation & Reconciliation Gate
- Validation Gate: Verify mathematical consistency (debit/credit sums, gross price - brokerage - taxes = net settlement amount, balance continuity).
- Reconciliation Gate: Detect overlapping dates and transaction fingerprints to prevent duplicate entries when statements are re-imported.
- Compute FIFO tax lots and apply RBI reference exchange rate conversions for US Schwab transactions into the canonical ledger.

## Acceptance Criteria

### Automated Parsing & Multi-Gate Verification
- [ ] Automated test suite runs against sample statements for Zerodha, HDFC Sec, CAMS e-CAS, and Charles Schwab, passing all 4 gates (Identity, Layout, Validation, Reconciliation).
- [ ] Malformed or unverified statement candidates fail closed without polluting canonical ledger data.

### Idempotency & Ledger Integrity
- [ ] Ingesting the same contract note or CAS statement twice results in zero duplicate transaction entries in the ledger.
- [ ] Parsed transactions produce matching portfolio valuation and tax lot summaries.
