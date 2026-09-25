# MoneyMoney

A family portfolio prototype for Indian and US assets, with a simpler interface
for an older parent. I started it because the information was spread across
brokers, statements and accounts, and a single balance hid too much uncertainty.

**Public status: development snapshot.** This repository is not a verified
production wealth platform. More recent work lives in a separately controlled
private version. A capability described in that work is not necessarily available
in this checkout.

The name stuck before I noticed the connection: my dad's favourite song is
ABBA's “Money, Money, Money.”

## What is in this repository

- A React and TypeScript interface for viewing portfolio information.
- Python ingestion and ledger components, with synthetic test fixtures.
- XIRR and tax-calculation code with test scripts.
- Experiments with a simpler parent-facing view and Gemini voice assistance.

These are components to inspect and test. Their presence does not establish
complete broker coverage, tax-filing suitability, secure multi-user deployment,
accessibility conformance or correctness for every cash-flow pattern.

## Progress in the private version

As of September 2026, the separate private work includes statement review,
account-scoped portfolio views and clearer source-coverage labels. Recent local
interface work connects overview, holdings and holding detail. The important
boundary is what each source actually proves:

- A parsed statement covers a particular account and date; it does not prove a
  complete family portfolio.
- The local Schwab path is a review-only preview. It does not save imported
  holdings, and currency and ownership still need explicit resolution.
- The local Zerodha cash reader has no portfolio-import bridge.
- Insufficient price or cash-flow history must remain visible instead of being
  filled with invented charts or return figures.

This is a progress summary, not a release of those private features. Private
statements, account mappings, credentials and runtime data are not published.

## Inspect the public frontend

From a clone of this repository, with a Node version supported by the pinned
Vite dependency:

```sh
npm ci
npm run dev
```

Inspect with synthetic data. Connecting a provider or deploying the application
requires separate configuration and review. The current publication update is
documentation-only; it does not certify this checkout's deployment or setup path.

## Check individual components

The repository includes these commands:

```sh
npm run test:xirr
npm run test:tax
npm run test:ui
python3 backend/tests/run_all_tests.py
```

Read the scripts and install their dependencies before running them. Test counts
are not coverage percentages. Passing a synthetic suite does not establish real
statement support, legal tax correctness or live account isolation.

Earlier README claims of “production-grade,” “100% test coverage” and guaranteed
XIRR convergence were too broad and have been removed. The project should earn
those claims through inspectable evidence, not wording.

## Contributing

Start with a reproducible defect in the public checkout: a synthetic calculation
case, a documented setup failure, or a specific interface problem. See
[CONTRIBUTING.md](CONTRIBUTING.md). Discuss parser or financial-model changes
before implementing them so the supported input and expected result are clear.

## Who did what

I define the product, constraints and acceptance criteria. AI coding tools write
the implementation under my direction. The reason for building it is practical:
help my family understand what we own, where a number came from, and what is still
missing.

## License

[MIT](LICENSE).
