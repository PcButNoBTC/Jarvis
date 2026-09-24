# Luma operations

## Local startup

```
cp .env.example .env
docker compose up --build
```

## Production basics

Before exposing Luma publicly:

- use HTTPS
- configure strong authentication secrets
- configure a real secret backend
- use strong PostgreSQL credentials
- restrict database network access
- configure reverse-proxy limits
- configure application rate limits
- enable GitHub secret scanning/push protection where appropriate
- back up PostgreSQL
- back up the Infisical encryption key and database
- configure monitoring
- exercise provider health checks
- verify outbound provider permissions
- keep provider scopes narrow

## Infisical

See infrastructure/infisical/README.md.

The bundled self-hosted stack is intended as an operational starting point. Pin a tested image version for production rather than relying on a floating image tag.

## Deployment

Static website deployment is bounded by LUMA_DEPLOY_ROOT.

Deployment requires:

- approved implementation
- launch readiness
- appropriate production configuration
- human approval

External DNS, domain and provider configuration remains explicit.

## Rate limiting

Luma uses PostgreSQL-backed fixed-window buckets so application replicas can share state.

This should be combined with:

- reverse-proxy throttling
- WAF/edge controls
- provider-side quotas
- connection limits
- alerting

## Backups

At minimum back up:

- PostgreSQL database
- Infisical PostgreSQL database
- Infisical encryption key
- deployment artifacts
- client handoff artifacts as required by contract

Test restoration rather than assuming backups work.

## Incident handling

If a provider credential is suspected compromised:

1. revoke/rotate it at the provider
2. mark the integration error/revoked
3. rotate the secret reference
4. review audit/security events
5. inspect recent action receipts
6. reauthorize with minimum required scopes
7. verify provider health
8. document the incident

