# Luma integrations

## Provider model

An integration has:

- project/client association
- provider
- category
- status
- capabilities
- secret reference
- scopes
- provider account ID
- expiry
- health-check timestamp
- metadata

The database stores a reference to credentials, not the raw OAuth token.

## OAuth providers

### Google Calendar
Authorization code OAuth is supported. The runtime can refresh access tokens and call calendar APIs.

### Microsoft Outlook
Authorization code OAuth is supported for delegated calendar access. The runtime can refresh access tokens and call Microsoft Graph calendar APIs.

### Calendly
OAuth authorization includes PKCE support. Refresh-token rotation is accounted for by persisting a returned replacement refresh token.

### HubSpot
OAuth connection foundation and runtime contact/deal actions are present.

## Credential lifecycle

```
OAuth callback
   ↓
token exchange
   ↓
secret backend
   ↓
secret reference in PostgreSQL
   ↓
runtime retrieves token
   ↓
expiry check
   ↓
refresh if needed
   ↓
persist rotated credentials
   ↓
provider call
```

A provider that returns persistent authentication failure is surfaced through integration health/error state.

## Messaging

SMTP provides email sending.

Twilio provides SMS sending.

The generic governed messaging action maps to a provider-specific capability at the runtime boundary.

## Provider status terminology

- **Registry**: provider is declared and selectable.
- **Foundation**: configuration/contracts exist.
- **Runtime adapter**: provider action code exists.
- **Connected**: credentials are stored through the configured secret path.
- **Verified**: health check has succeeded.
- **Error**: the latest runtime action/health check failed.
- **Production-ready**: requires real provider-account testing, deployment configuration, monitoring and security review; it is not inferred merely from having an adapter.

## Adding a provider

A new provider should implement:

1. provider declaration
2. capabilities
3. configuration requirements
4. credential strategy
5. adapter
6. health check
7. refresh/revocation handling if applicable
8. governed capability mapping
9. tests with mocked provider responses
10. integration documentation

Do not place provider credentials in source code or database JSON fields.

