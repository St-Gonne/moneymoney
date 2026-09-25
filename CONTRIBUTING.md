# Contributing to MoneyMoney

This repository is a public development snapshot. Start with a small,
reproducible problem in this checkout. Current private development is separate;
a feature described in the project story may not be implemented here.

Useful contributions include synthetic regression cases, corrections to setup
instructions, and specific interface or calculation defects.

## Before a larger change

For a parser, define one input format and version, the expected normalized
result, and the conditions that must be rejected. Discuss that scope before
coding. A broker name alone is not a supported-format contract.

For financial calculations, show the inputs, expected result and reasoning.
Do not treat a passing example as evidence that every tax or cash-flow case works.

## Privacy

Use invented fixtures only. Do not upload statements, account details, PANs,
credentials, email, private logs or screenshots containing financial information.
A useful bug report contains the smallest synthetic input that reproduces it.

## Verify the change

Use the relevant repository scripts and report the exact commands and results:

```sh
npm run build
npm run test:xirr
npm run test:tax
npm run test:ui
python3 backend/tests/run_all_tests.py
```

Install the required frontend/backend dependencies first. If a baseline command
fails, report the failure; do not omit it or claim a full pass. Avoid unrelated
refactors and changes to cloud resources or live data.

In a pull request, explain the problem, resulting behavior, verification and
remaining limits. Disclose AI assistance and be prepared to explain the patch.
