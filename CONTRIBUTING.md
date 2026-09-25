# Contributing to MoneyMoney

The current source release is in `clarity/`. Start with its synthetic setup and
a small reproducible problem. The repository root retains the older prototype;
please say which tree your change targets.

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
cd clarity
npm ci
npm test
npm run build
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q
PYTHONPATH=backend .venv/bin/python scripts/test-private-nsdl-connected-demo.py
```

Follow [the Clarity setup](clarity/README.md) to create the Python environment first. If a baseline command
fails, report the failure; do not omit it or claim a full pass. Avoid unrelated
refactors and changes to cloud resources or live data.

In a pull request, explain the problem, resulting behavior, verification and
remaining limits. Disclose AI assistance and be prepared to explain the patch.
