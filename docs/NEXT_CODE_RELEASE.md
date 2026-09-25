# Release scope and remaining work

Updated 25 September 2026: the bounded developer release below is now included
in [`clarity/`](../clarity/README.md). It contains current source, a persistent
synthetic backend, setup instructions, tests and a captured public-demo screen.
The original assessment is retained below to explain the release boundary.
It remains unsuitable for a whole-workspace push or real-data demo deployment.

## Why this needs a deliberate release

The newer source changes 25 existing frontend files and adds 39; its application
backend changes 8 files and adds 34 compared with this public snapshot. That is
not a small README update or a patch we can certify by copying a few components.
These counts cover src and backend/app source files, not tests or dependencies.

The working version mixes publicizable application code with household-specific
configuration, private release machinery and incomplete integrations. The next
release needs its own clean checkout and synthetic setup. Private financial data,
account mappings, credentials and historical Git objects are not release inputs.

## Recommended first scope

- Clarity overview, holdings and holding detail, with synthetic accounts.
- Dated values, source labels, privacy masking and honest insufficient-history states.
- A small local test backend and explicit replaceable configuration.
- Existing Comfort UI clearly marked as unfinished.
- Voice off by default, with the synthetic lifecycle harness available to developers.
- Exact dependency installation, a short walkthrough and focused tests.

Do not require contributors to connect the owner's Firebase/Render resources,
provide real statements or turn on a paid voice provider to make a first contribution.

## Evidence required before publishing that source

1. A reviewed file manifest, secret/private-content scan and dependency/license inventory.
2. No fixed household membership or account identifiers in sample configuration.
3. A clean clone can start the synthetic app using only documented instructions.
4. Auth/scope isolation, persistence, duplicate handling and numerical regression
   checks pass in that candidate. Tests cannot silently reach live resources.
5. Desktop and phone screenshots match the code in the release.
6. Known limits and the contribution targets refer to that exact checkout.

The local Schwab path needs a durable statement-observation, ownership, currency
and overlap/idempotency contract before it can save holdings. Request-size handling
for uploads without Content-Length also needs closure before hosted exposure.
These are not reasons to hold a bounded synthetic demo, but they must not be
silently promoted as ready import features.

## Comfort and voice queue

Comfort needs simpler navigation/copy, verified account-to-total semantics and a
trial with its intended user. Its current helper retains whole-portfolio metrics
when an account filter changes; the intended whole-portfolio versus selected-account
meaning must be resolved and labelled before presenting it as an account-specific
summary. The Clarity redesign did not address that older Comfort behavior.

The current private Talk surface remains unavailable. The proposed next direction
still needs protected canonical context, provider choice and explicit consent,
real audio lifecycle verification, grounded answers, and user acceptance. The
available local voice receipt is marked review_required; the offline integration
successor is prepared-only. A later receipt may supersede that state, so recheck
current controls before implementation.

## What this publication includes

The current Clarity source graph is published under the repository's MIT license,
with unchanged financial/access-control modules. Its explicit synthetic
composition uses local files and a public test identity. The source manifest,
local test receipt and setup instructions are in `clarity/`. The first README
screenshot was captured from this public candidate; older detail/mobile images
are labelled with their 23 September date.

Real-data authentication, storage deployment, provider choice and the outstanding
Comfort/import issues remain follow-up work. No family data, credentials,
production configuration, git history or private release machinery is included.
