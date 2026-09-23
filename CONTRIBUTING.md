# Contributing to Luma

## Principles

Luma prioritizes:

1. evidence over unsupported claims
2. deterministic control logic around probabilistic AI
3. client control
4. least-privilege provider access
5. observable outcomes
6. small, reviewable changes

## Development

Run the API tests:

    cd apps/api
    python -m pytest -q

Run compilation checks:

    python -m compileall .

Do not commit credentials or local secret-manager state.

## Provider changes

New provider integrations should include:

- registry declaration
- configuration requirements
- secret strategy
- runtime adapter
- health check
- refresh/revocation behavior
- governed capability mapping
- mocked tests
- documentation

## Governance changes

Changes that affect external actions should preserve:

- explicit approval boundaries
- role/tool scope checks
- audit logging
- action receipts where applicable
- budget enforcement
- client data boundaries

## Pull requests

Explain:

- what changed
- why it changed
- which capability it affects
- how it was tested
- what remains unverified

Never claim CI is green unless the relevant GitHub workflow has actually completed successfully.
