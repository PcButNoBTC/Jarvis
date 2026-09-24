# Production Readiness Runbook

Luma is production-ready only when the application code, database, deployment edge, provider accounts, and operational checks have all been exercised together. A green unit-test run is necessary but not sufficient.

## Required infrastructure

- PostgreSQL with automated backups and a tested restore.
- Public HTTPS for the API.
- Public WSS for Twilio Media Streams when voice is enabled.
- Persistent deployment root configured with `LUMA_DEPLOY_ROOT`.
- Secrets stored in Infisical or an equivalent managed secret backend.
- TLS termination and firewall rules allowing only required traffic.
- Process supervision for API and worker with automatic restart.
- Centralized logs and alerting for API, worker, provider, and database failures.

## Release gate

1. Apply the schema to staging.
2. Start API and worker with production-like configuration.
3. Run the API tests and compilation checks.
4. Verify `/health` and `/ready`.
5. Exercise login, roles, portal, proposal acceptance, requirements, QA, approval, deployment, monitoring, and handoff.
6. Exercise every enabled provider against a real sandbox/test account.
7. Verify secrets are loaded through the secret backend and never persisted as raw credentials.
8. Verify rate limiting and security headers at the public edge.
9. Verify backups and perform a restore drill.
10. Review audit records for consequential actions.

## Voice release gate

Voice is optional; email and the client portal remain the default client path.

- Twilio webhooks validate `X-Twilio-Signature`.
- Outbound destinations are E.164 and explicitly operator-approved.
- Do-not-call and communication preferences are checked before initiating calls.
- The assistant discloses that it is AI.
- Twilio Media Streams use secure WSS on port 443.
- The Realtime bridge uses the current GA session shape and PCMU/8000 telephony audio.
- Verify bidirectional audio, interruption/barge-in, transcripts, timeout handling, terminal call status, and error recovery with a real provider account.
- Perform an operator-approved custom-number test call before enabling outbound calling.

The current Realtime GA contract uses `session.type=realtime`, `session.audio.input/output.format`, and `response.output_audio.delta`; the bridge must not rely on the retired beta header or older event names.

## Consequential-action policy

AI agents must not bypass the control plane. Provider actions remain behind policy evaluation, scoped tools, approvals, and receipts. External actions such as outbound messages, calendar changes, deployments, and calls require explicit authorization according to policy.

## Business safety

- Research retains evidence and source URLs.
- Outreach respects suppression and opt-out signals.
- Recommendations explain the observed problem, evidence, proposed solution, and alternatives.
- Luma recommends the smallest useful intervention rather than maximizing contract value.
- Client data ownership and AI disclosure remain visible where appropriate.
- Expansion follows demonstrated client value.

## Operating metrics

Track revenue, operating cost, revenue per operating dollar, project contribution/margin, model tokens and cost, provider failure rate, workflow retry rate, research-to-qualified conversion, proposal-to-won conversion, delivery cycle time, and service-specific client outcomes.

## What source control cannot prove

A repository cannot prove that a third-party account, DNS record, phone number, payment account, SMTP relay, OAuth consent, or deployment host works. Those require environment-specific verification. Luma therefore treats provider-account testing and deployment validation as release gates rather than fake completion checkboxes.
