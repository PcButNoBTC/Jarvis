# Luma Production Release Gate

This document defines what production ready means for the self-hosted Luma control plane.

## 1. Application
- [ ] Deploy the exact release commit; do not deploy an unpinned working tree.
- [ ] Configure PostgreSQL with automated backups and tested restore.
- [ ] Set LUMA_AUTH_SECRET to a high-entropy secret and rotate it through the configured secret manager.
- [ ] Configure an owner account using LUMA_ADMIN_EMAIL and a scrypt password hash.
- [ ] Set LUMA_DEPLOY_ROOT to a dedicated directory that is not writable by unrelated services.
- [ ] Expose /health for liveness and /ready for readiness.
- [ ] Put the API behind HTTPS and a reverse proxy that supports WebSockets on /voice/stream.
- [ ] Keep /docs and /openapi.json disabled or access-controlled in a public deployment unless intentionally exposed.

## 2. Secrets and providers
Use the Infisical backend for production OAuth/provider secrets. Environment variables are a local-development fallback.

Before enabling a provider for clients:
1. Connect the provider account.
2. Run its health check.
3. Verify the granted scopes.
4. Exercise one read operation.
5. Exercise one write operation with human approval.
6. Record the result in the integration connection and audit trail.

Luma must report a provider as configured only after these checks. A saved configuration choice is not proof that the provider is connected.

## 3. Voice
Voice is optional; email and the client portal remain the default communication path.

For Twilio:
- Use a verified E.164 caller ID/number.
- Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_NUMBER.
- Configure signed HTTPS webhooks for incoming calls and status callbacks.
- Configure a public wss:// Media Streams endpoint on TCP 443.
- Validate X-Twilio-Signature on every webhook/stream handshake.
- Set LUMA_REALTIME_MODEL to gpt-realtime-2.1 unless a separately validated model is selected.
- Test the Realtime WebSocket session and PCMU 8 kHz audio path against a real account.
- Require explicit operator approval for custom-number outbound test calls.
- Enforce E.164 destination validation, do-not-call/preferred-channel policy, and a bounded call TimeLimit.
- Verify lifecycle callbacks for initiated, ringing, answered, completed, failed, busy, and no-answer outcomes.
- Verify AI disclosure before substantive conversation.
- Do not enable autonomous consequential actions until their tools are separately governed and tested.

Twilio Media Streams require secure WebSockets and signature validation. OpenAI's server-side Realtime WebSocket flow uses a server-owned connection with the API key kept on the trusted backend. Consult the current provider documentation before changing the transport contract.

## 4. Sales and outreach
- Research must contain source evidence before an opportunity is eligible for outreach.
- Outreach remains human-approved by default.
- Respect suppression, do-not-contact, and channel preferences.
- Keep a durable record of drafts, approvals, sends, and failures.
- Do not use scraped contact data in ways prohibited by applicable law or provider terms.
- Start with small, measured batches; expand only after demonstrated client value.

## 5. Delivery
Every project must pass:
configuration -> requirements -> implementation -> validation -> client approval -> deployment -> monitoring -> handoff

No deployment should occur without an approved implementation and launch-readiness checks.

## 6. Economics
Track revenue transactions, provider/model cost, infrastructure cost, project cost, recurring revenue, contribution/margin, and client outcome metrics.
Do not declare an opportunity or service successful from lead volume alone.

## 7. Release verification
Run CI on the exact release commit and verify all required checks are successful.

Then perform a staging smoke test:
- authenticate
- create/read a business
- enqueue and run research
- inspect evidence and opportunity state
- create and approve an outreach draft without sending
- create a project
- configure it
- compile requirements
- generate artifacts
- validate
- approve
- deploy to a staging target
- monitor the deployed URL
- generate the handoff package
- record a revenue/cost event
- verify analytics

For every enabled external provider, run one real provider-account test. Do not label an integration production-ready from static code inspection alone.

## 8. Rollback
Keep the previous application image/commit available. Roll back the application before changing database schema backwards. Database migrations must be forward-compatible whenever possible.

For a failed provider rollout:
1. disable the provider integration,
2. preserve the audit trail,
3. switch to client-managed/email fallback,
4. investigate,
5. re-test before re-enabling.

## 9. Definition
Luma is production-ready when the self-hosted core has passed the release verification above and each enabled external integration has passed a real-account test. Capabilities that have code but have not passed that gate must remain labeled foundation, runtime adapter, or supported rather than production-ready.