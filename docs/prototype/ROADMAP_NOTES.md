# MoneyMoney Project Roadmap & User Notes

This document captures prioritized feature requests, architectural designs, and reminders for upcoming development threads.

---

## 📌 1. Role-Based Access Level Architecture (Priority: High)
* **Objective:** Not all family users should see the entire Consolidated Family Vault by default; visibility must be determined by user role/access tier.
* **Access Tiers to Implement:**
  1. **Vault Administrator / Head of Family (e.g., Alex):** Full visibility across all family member portfolios (Zerodha, HDFC, Direct MFs, Charles Schwab), statement ingestion, and administrative settings.
  2. **Individual Family Member (e.g., Robert / Father, Margaret):** Restricted by default to their own personal portfolio, with simplified summaries and Dad's Voice Portal.
  3. **Read-Only / Advisor Access:** Restricted view for Chartered Accountants or family financial planners (e.g., Tax Matrix & Schedule FA only).
* **Current Foundation:** Top-level view defaults to the user's individual portfolio (`port_primary`, `port_father`, `port_mother`) rather than forcing consolidated view.

---

## 📌 2. Red "Need Help?" Action Workflow (Priority: Medium-High)
* **Objective:** Define the custom backend / frontend handler for the red "Need Help" button located in the footer.
* **Candidate Workflows:**
  - **Option A (Family Concierge Alert):** Sends an instant email/WhatsApp notification to Alex with the active screen context and question.
  - **Option B (AI Diagnostic Audit):** Triggers a Gemini one-click diagnostic check of any parsing mismatches, tax deadlines, or urgent broker actions.
  - **Option C (Visual Guided Walkthrough):** Opens an interactive step-by-step assistant for statement uploads and ledger navigation.

---

## 📌 3. Advanced Profile Edit & Customization Menu (Priority: Medium)
* **Objective:** Expand the Profile Edit modal (`ProfileEditModal.tsx`).
* **Features to Include:**
  - Custom profile photo / avatar graphic upload (with Cloud Storage synchronization).
  - Core PAN and account nickname modifications.
  - Default landing screen selection (e.g., Dad always lands on Voice Portal, Alex on Portfolio Overview).
  - Currency display preference (INR Lakhs/Crores vs Millions/Billions).

---

## 💡 4. Quality-of-Life & Compliance Enhancements

1. **✅ Privacy Shield / Camouflage Mode (👁️) [COMPLETED]:**
   - 1-click top-header eye toggle masks all monetary numbers with a blur filter (`blur(6px)`) with smooth hover-to-reveal for public browsing.
2. **✅ One-Click CA / Tax Accountant Bundle Export [COMPLETED]:**
   - Single-click generation of consolidated CSV/Excel + printable CA Tax Dossier bundling Section 112A LTCG/STCG, 1042-S foreign tax credits, Form 67 FTC, and Schedule FA peak values under Finance Act (No. 2) 2024.
3. **✅ Inline Dual Currency Flip for US Stocks [COMPLETED]:**
   - 1-click row-level flip badge (`$ USD ⇄ ₹ INR`) on Charles Schwab US holdings with dual-currency subtitle visibility.
4. **✅ 3-Tier XIRR & Performance Analytics Engine [COMPLETED]:**
   - Asset-level, Category-level, and Portfolio-level blended XIRR with Cashflow Waterfall ledger.
5. **✅ Member Profile & Preferences Suite [COMPLETED]:**
   - PAN, DOB cascade for zero-friction statement decryption, entity type, default landing, and number format (Lakhs/Crores vs Millions/Billions).
6. **Milestone & Goal Tracking [UPCOMING]:**
   - Visual progress bars for family milestones (e.g., emergency fund target, retirement target, SGB Sep 2031 redemption dates).

---

## 📌 5. Phased Architecture Hardening & Ingestion Integration Plan

This section documents the architectural strategy and rationale for the phased evolution of the MoneyMoney platform:

### **Phase 1: Gemini Live Voice Security & Semantic Context Hardening**
* **Rationale**: Raw API keys in browser `localStorage` pose a security vulnerability for family vault data. The Cloud Run backend (`backend/app/api/ai.py`) provisions ephemeral session tokens via `/api/ai/live-token` for `gemini-3.1-flash-live-preview`.
* **Latency Optimization**: Deprecate DOM canvas rasterization (`html2canvas`) in favor of deterministic token-optimized text context (`buildSemanticContext`), eliminating main-thread jank during screen transitions.

### **Phase 2: Ingestion UI & 4-Gate Backend Integration**
* **Rationale**: The Python backend contains a fail-closed 4-Gate ingestion engine (Identity, Supported-Layout, Math Validation $\epsilon \le 0.02$, and SHA-256 Deduplication).
* **Execution**: Wire `StatementImportModal.tsx` directly to `/api/statements/process-file` and `/api/statements/inbound-email`, displaying exact discrepancy breakdowns on failure and committing verified transactions directly to the canonical ledger and Firestore.

### **Phase 3: Frontend Modularization & Math Verification Test Harness**
* **Rationale**: `App.tsx` handles multiple orthogonal concerns (voice manager, theme mutations, privacy masking, command palette, Firestore subscriptions).
* **Execution**: Decompose `App.tsx` into custom hooks (`useGeminiAssistant`, `useThemeManager`, `useVaultSync`). Add `vitest` unit tests for `taxEngine.ts` (Finance Act 2024 compliance) and `xirr.ts` (Newton-Raphson cashflows).
