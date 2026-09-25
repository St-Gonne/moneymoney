# Clarity source release

This is the current MoneyMoney interface and its connected local backend, packaged
so someone else can run it. It starts with invented accounts, holdings, prices and
cash flows. No sign-up, Firebase project, API key or model download is needed.

This is a developer alpha for synthetic use. The demo token is in the source.
It is not a safe login system for real finances, and the demo must stay on your
own computer. The production authentication and storage adapters are included
as code, but this release does not configure or certify them for self-hosting.

## Run it

Use Node 22.18 or newer and Python 3.11. The first install downloads packages;
the running demo uses local files and loopback HTTP. Commands below are for
macOS/Linux. Windows setup is an open contribution.

From the repository root:

```sh
cd clarity
npm ci
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
mkdir -m 700 .demo-data
PYTHONPATH=backend .venv/bin/python scripts/private_nsdl_connected_backend.py --data-dir "$PWD/.demo-data"
```

Leave that terminal open. In a second terminal, from `clarity/`:

```sh
npm run dev
```

Open <http://127.0.0.1:5173/?ordinary=1#overview>. The browser banner says
**Synthetic demo**. Amounts start hidden; use **Show amounts** to see the invented
values. The backend listens on `127.0.0.1:8788`, and Vite proxies `/api` there.
Both ports must be free. Don't add a public tunnel or change the listen address.

If `.demo-data` already exists, reuse it rather than rerunning `mkdir`.
The backend stores manual records in `.demo-data/connected-account-data.json`,
which is ignored by Git. Restarting it preserves changes. For a separate blank
experiment, create another private directory and pass its absolute path with
`--data-dir`. It will be seeded once with the same invented portfolio.

To inspect a production build locally, keep the backend running and use:

```sh
npm run build
npm run preview
```

Then open <http://127.0.0.1:4173/?ordinary=1#overview>. This builds static browser
files; it does not deploy the application.

## What to try

- **Overview → Holdings → holding detail:** White/Dark themes, dated values,
  account filters, currency separation and source information.
- **Accounts and Cash flows:** add invented manual records, refresh, restart the
  backend and check that they remain. New holdings without an eligible price
  stay unavailable; the demo does not invent market quotes.
- **Performance:** inspect complete and incomplete history. A higher balance is
  not automatically a return. A missing price or cash-flow history stays visible.
- **Readiness and Activity:** see what is supported by the records, what needs
  review, and which local changes have been saved.
- **Comfort:** the older simpler view and its session lifecycle code are included.
  Its account selection/totals wording needs work; some cards remain portfolio
  totals. Do not interpret all cards as selected-account results. Normal Talk
  remains unavailable. The voice tests use a mock, not a microphone or model.

The backend includes the current NSDL parser and a Schwab preview-only parser.
Use invented fixtures only. No Schwab confirm/import endpoint is implemented.
Email-import UI is present, but the demo supplies no Gmail connection service.
No brokerage, market-price or voice provider is activated by these instructions.

## Test it

From `clarity/`, after the install above:

```sh
npm test
npm run build
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
PYTHONPATH=backend .venv/bin/python scripts/test-private-nsdl-connected-demo.py
```

The frontend checks exercise scope-aware chart caching, dated chart projections,
return eligibility and mock voice cancellation/privacy behaviour. The Python
checks exercise account facts, revisions, idempotency, owner scope, dated
valuation, missing history and genuine restart persistence. The connected demo
check uses the same backend factory as the runnable app.

## Where to work

| Path | Responsibility |
| --- | --- |
| `src/components/PrivateNsdlApp.tsx` | Navigation, theme, portfolio choice and privacy controls |
| `src/components/NsdlPortfolioView.tsx` | Holdings, values, details and connected record workflows |
| `src/utils/portfolioVisuals.ts` | Chart projection and return eligibility |
| `src/utils/valuationRangeCache.ts` | Account/currency/date-aware chart cache |
| `src/components/DadModeView.tsx` | Comfort view |
| `src/services/comfortVoice/` | Mock voice contracts and session lifecycle |
| `backend/app/account_data_store.py` | Local durable facts and revisions |
| `backend/app/valuation_service.py` | Dated valuation, coverage and performance |
| `scripts/private_nsdl_connected_backend.py` | Explicit synthetic composition and fixtures |

## What this release leaves open

I want help making it easier to understand and easier to run. Useful first
changes include reducing the mobile filters, making Comfort's totals/account
scope unmistakable, measuring and splitting the initial browser bundle, and
adding reproducible platform setup checks. See the repository's issues before
starting a large change.

Turning this into a real-data self-hosted app needs a separate reviewed setup:
user-controlled authentication, access policy, private storage, backup/recovery,
per-source reconciliation and upload limits. In particular, unknown-length
uploads need a bound before spooling, and Schwab observations need ownership,
currency and overlap decisions before they can become saved holdings.

The source comes from the working app on 25 September 2026. `SOURCE_MANIFEST.json`
records source/published hashes and the packaging adaptations: local font
fallbacks, omission of two legacy package export lists and trailing whitespace
normalization. Backend financial and access control modules were copied unchanged. Family configuration values, statements,
credentials, deployment config, logs and private history are excluded. Some old
adapter field names still reflect the original two-person family design; making
that configurable is follow-up work, not a reason to include real identities.

The code follows the repository's [MIT license](../LICENSE). Installed dependencies
retain their own licenses. No third-party source or model weights are vendored.
