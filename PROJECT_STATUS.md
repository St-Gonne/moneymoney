# MoneyMoney — Family Wealth Vault Project Status

> **Current Status**: Production-Hardened • Open-Source Showcase • 355+ Automated Tests Passing (100%)  
> **Demo URL**: [https://family-vault.example.com](https://family-vault.example.com)  
> **Repository**: [https://github.com/St-Gonne/moneymoney](https://github.com/St-Gonne/moneymoney)


---

## 1. Quick Start for Developers

1. **Frontend Architecture**: React 19 + TypeScript + Vite with custom 16.6 kB Vanilla CSS layout engine in `src/index.css`.
2. **Backend & Ingestion**: Python 3.11+ FastAPI backend with 4-stage fail-closed statement guard (`backend/app/gates/`), typed parsers (`backend/app/parsers/`), and server-side Gemini AI Gateway (`backend/app/api/ai.py`).
3. **Database & Sync**: Google Cloud Firestore (`family_vaults/default_family`) with real-time `onSnapshot` subscriptions in `src/services/firebase.ts` and fallback offline synthetic data in `src/data/mockFamilyData.ts`.
4. **Security & Whitelist**: Configurable OAuth whitelist via `ALLOWED_FAMILY_EMAILS` environment variable.
5. **AI Copilot & Voice Architecture**:
   - Master Gemini key hosted securely server-side or configured locally via `VITE_GEMINI_API_KEY`.
   - Fact-constrained screen context grounding in `src/services/geminiLive/screenContext.ts`.
   - Real-time bidirectional voice assistant via Gemini Live WebSocket API (`@google/genai`).
6. **Local Dev Commands**:
   - Frontend: `npm run dev` (Port 5173).
   - Backend: `uvicorn backend.app.main:app --reload --port 8000`.
   - Docker: `docker compose up --build`.
7. **Test Suites**:
   - `npm run test:ui` (75 UI & accessibility tests)
   - `npm run test:xirr` (35 mathematical stress tests)
   - `python3 backend/tests/run_all_tests.py` (245 Python E2E tests)

---

## 2. Demonstration Persona Models (100% Synthetic Data Baseline)

### Alex Taylor (`port_primary` • PAN: `KLMNO9012P`):
- **Role**: Family Administrator (Full Vault Access).
- **Holdings**: Reliance Industries, TCS, HDFC Bank, Nifty 50 Direct Index Fund, Parag Parikh Flexi Cap Fund, SGB 2.50% Sep 2031, US Tech RSUs (Alphabet `GOOG`), US Total Market ETF (`VTI`), Fixed Deposits, PPF.

### Robert Taylor (`port_father` • PAN: `ABCDE1234F`):
- **Role**: Senior Citizen Member ("Dad's Mode").
- **Holdings**: High-yield Senior Fixed Deposits, Sovereign Gold Bonds, Liquid Emergency Fund, conservative hybrid mutual funds.
- **UI Mode**: High-contrast 32px touch-first OLED interface with Gemini Live voice assistance.

### Margaret Taylor (`port_mother` • PAN: `FGHIJ5678K`):
- **Role**: Family Member.
- **Holdings**: Direct Mutual Funds, Gold ETF (Gold BeES), Bluechip equities.

### Taylor Family Trust (`port_trust` • PAN: `PQRST3456Q`):
- **Role**: Family Entity / Trust.
- **Holdings**: Real estate allocation, diversified index funds.

---

## 3. Verified System Capabilities

| Component | Status | Description |
| :--- | :---: | :--- |
| **AuthGate & Security** | ✅ Live | Strict Google OAuth + Whitelist resolution for family personas. |
| **Fail-Closed 4-Gate Ingestion** | ✅ Live | 4 verification gates (Identity, Decrypt, Invariants, Recon) for Zerodha, HDFC Sec, CAMS/KFintech e-CAS, Charles Schwab. |
| **Finance Act 2024 Tax Matrix** | ✅ Live | Section 112A ₹1.25L exemption headroom, 12.5% LTCG, 20% STCG, SGB Section 47 exemption, Schedule FA tracking. |
| **3-Tier XIRR & Analytics Engine** | ✅ Live | Hybrid Newton-Raphson + Bisection annualized return engine with Monte Carlo verified stability. |
| **Senior Citizen Voice Portal** | ✅ Live | 32px touch-first interface with bidirectional Gemini Live voice assistance and 1-click SOS screen concierge. |
| **Zero-Trust Privacy Shield** | ✅ Live | 1-click Privacy Camouflage blur (👁️) for masking asset numbers when viewing in public. |
| **100% Test Coverage** | ✅ Live | 355+ automated tests passing across frontend UI, mathematical benchmarks, and backend ingestion pipelines. |
