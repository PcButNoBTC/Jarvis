# Security policy

## Scope

This repository contains a self-hosted business operating system. Security includes application authentication, authorization, provider credentials, client data, outbound communication and deployment actions.

## Current controls

- signed bearer authentication
- owner/admin/operator/client roles
- optional API key protection
- scoped client portal tokens
- secret-reference abstraction
- OAuth state signing
- single-use OAuth state nonces
- provider token expiry/refresh handling
- PostgreSQL-backed distributed rate limiting
- audit log
- security event schema
- governed action decisions
- tamper-evident action receipts
- approval history
- deployment approval gates
- client revision/approval controls

## Credential handling

Do not commit:

- passwords
- API keys
- OAuth access tokens
- OAuth refresh tokens
- machine-identity credentials
- Infisical encryption keys
- provider secrets

PostgreSQL should contain secret references, not raw provider OAuth credentials.

## Authorization model

Roles currently include:

- owner
- admin
- operator
- client

Agents use policy/tool scopes in addition to human roles.

Consequential actions such as sending messages, creating events, charging payment and deploying require explicit policy/approval handling.

## Production hardening still required

The application is not presented as enterprise-complete. Depending on deployment, additional controls may include:

- MFA
- session revocation
- password reset/recovery
- edge/WAF rate limiting
- centralized security alerting
- fine-grained project/client authorization
- stronger audit retention
- provider-specific least-privilege review
- dependency/SBOM scanning
- regular restore tests
- penetration testing

## Reporting

For a private security report, contact the repository maintainer through the GitHub repository's current contact/security channel. Do not publish credentials or exploit details in a public issue.

## Repository security

For a public GitHub repository, enable appropriate GitHub security features such as secret scanning, push protection, Dependabot alerts and code scanning. GitHub recommends these controls as baseline repository security practices.
