# Local source release checks — 25 September 2026

Candidate: `clarity/`, `0.1.0-alpha.1`. Checked on macOS arm64 with Node 26.0.0
and Python 3.11.15. GitHub CI uses Node 22.18 and Python 3.11 on Linux; that is a
separate check, not part of these local results.

- Fresh `npm install` from the bounded package manifest: passed; 67 packages,
  npm reported zero known vulnerabilities at install time.
- Fresh Python virtual environment installed the declared dependencies. The
  resolved environment is captured in `requirements.lock.txt`.
- `npm run build`: passed type-check and production bundle.
- `npm test`: all three suites passed: Clarity cache, portfolio visuals and
  mock Comfort voice session lifecycle.
- `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q`: **38 passed**.
- `PYTHONPATH=backend .venv/bin/python scripts/test-private-nsdl-connected-demo.py`:
  **V3_SYNTHETIC_PORTFOLIO_COVERAGE_DEMO=PASS**. This covers the actual local
  composition, dated/currency-separated fixture values and restart persistence.
- The public candidate was started on loopback and opened in Chrome. Its
  synthetic data banner, values and current navigation were checked. The README
  public-demo screenshot is from that running candidate.

Known non-failing findings: the minified initial JavaScript bundle is 689.62 kB
(200.59 kB gzip), above Vite's 500 kB warning threshold. Starlette emitted a
TestClient/httpx deprecation warning. Neither is silently suppressed.

No real statement, private identity, Firebase credential, market-data provider,
Gmail session, microphone or model was used. No cloud or production service was
changed. The frontend excludes the remote-font import. Existing source adapters
for optional services are present but unconfigured by the synthetic entrypoint.

The manifest records 70 copied source/fixture/config files. Five have packaging
changes: font loading, two legacy `__init__` export lists and trailing whitespace
normalization in two TypeScript files. It records SHA-256 before and after;
financial and authentication logic is unchanged.
No private source history, output folders, logs, environment files, account store,
node_modules, virtual environment or deployment configuration is part of the diff.

These checks establish a reproducible synthetic development starting point.
They do not establish correctness for all financial situations, acceptance of
real statements, accessibility, secure public hosting or live voice readiness.
