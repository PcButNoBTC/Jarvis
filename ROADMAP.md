# Luma Strong MVP Roadmap

The Strong MVP is complete only when the operating loop is connected end-to-end.

## Phase 1 — Delivery control plane
- [x] Service-specific project configuration
- [x] Configuration validation
- [x] Configuration → compiled requirements
- [x] Requirements persisted on project and implementation
- [x] Service adapter build-plan layer
- [x] Provider-specific artifact generators
- [x] Configuration-aware QA contract endpoint

## Phase 2 — Opportunity and sales intelligence
- [x] Evidence-first client-respect fit assessment
- [x] Why-this / why-not / alternatives fields
- [x] No-pressure outreach preference and suppression controls
- [x] Client outcome tracking before expansion
- [x] Service-specific opportunity mapping
- [x] Numeric confidence
- [x] Evidence ledger
- [x] Opportunity lifecycle endpoint
- [x] Human-approved outreach drafts
- [x] Duplicate active-opportunity guard
- [x] Follow-up queue and proposal versioning

## Phase 3 — Project operations
- [x] Delivery task checklist
- [x] Project milestones
- [x] Milestone status updates
- [x] Dependencies
- [x] Approval history
- [x] Client review/revision loop

## Phase 4 — Build, QA, launch, handoff
- [x] Artifact generation
- [x] Automated validation
- [x] Approval gate
- [x] Static deployment target
- [x] Launch readiness
- [x] Monitoring
- [x] Handoff package
- [ ] Provider-specific deployment adapters (live external execution)
- [ ] Service-specific production generators

## Phase 5 — Revenue / economics
- [x] Revenue transactions
- [x] Cost records
- [x] Contribution calculation
- [x] Revenue-per-cost metric
- [x] Service performance
- [x] Billing records
- [x] Payment reconciliation
- [x] Recurring revenue lifecycle
- [ ] Margin by project/client
- [ ] Model-token cost attribution

## Phase 6 — Automation
- [x] Workflow definitions
- [x] Workflow run persistence
- [x] Deterministic step advancement
- [x] Human approval boundary for consequential actions
- [x] Scheduled triggers with five-field cron parsing and atomic worker claims
- [x] Research retry/backoff policy
- [ ] Event-driven orchestration

## Phase 7 — Integrations
- [x] Provider registry
- [x] Connection records
- [x] Email adapter (SMTP runtime)
- [x] Calendar adapters (Google, Outlook, Calendly runtime/connect foundation)
- [x] CRM adapter (HubSpot OAuth/connect foundation + runtime adapter)
- [ ] Forms adapter
- [x] Phone/voice adapter (Twilio runtime + realtime bridge foundation)
- [ ] Analytics adapter
- [ ] Payment provider adapter
- [ ] Hosting adapters

## Phase 8 — Security
- [x] Optional self-hosted API key
- [x] Scoped client portal tokens
- [x] Audit-log data model
- [x] User authentication
- [x] Roles/permissions
- [x] Secret-reference abstraction
- [~] Infisical secret backend (runtime integration implemented; deployment bootstrap still required)
- [x] Security event logging
- [x] PostgreSQL-backed distributed application rate limiting

## Phase 9 — Client portal
- [x] Client AI-disclosure and communication preferences
- [x] Client data-ownership messaging
- [x] Scoped project read view
- [x] Milestone visibility
- [x] Requirements submission via project configuration API
- [x] Client approval
- [x] Revision requests
- [x] Deliverable downloads
- [ ] Client messaging

## Phase 10 — Agent layer
- [x] Trust-first operating policy available to agents
- [x] Expansion gated on demonstrated client value
- [x] Agent-run persistence
- [x] Tool/control-plane foundations
- [x] Research agent registry/governance
- [x] Sales agent registry/governance
- [x] Project agent registry/governance
- [x] Build agent registry/governance
- [x] QA agent registry/governance
- [x] Launch agent registry/governance
- [x] Per-agent budgets and tool/approval policy records
- [x] Agent evaluation

## Phase 11 — Regional growth
- [x] Regional playbook data model
- [x] Regional playbook API
- [x] Trust-first dashboard surface
- [ ] Pilot metrics and referral tracking
- [ ] Region-specific outreach rate limits
- [ ] Automated client-success reporting

## Definition of Strong MVP

Every module must have:
1. A clear job.
2. Persistent state.
3. Validation.
4. An observable outcome.
5. A safe handoff to the next module.
6. Human approval before consequential external actions.
7. Enough telemetry to measure whether it contributes to revenue.


## Remaining production dependencies

Core control-plane and selected live provider runtime paths are implemented. Remaining production work is deliberately bounded: provider-specific deployment/hosting, forms, analytics, broader payment execution, event-driven orchestration, enterprise authentication hardening, edge rate limiting, client messaging, and broader provider provisioning. Live credentials and provider-account testing remain required before declaring an integration production-ready.


## Phase 12 — Control & Intelligence Core (revamp)
- [x] Evidence/claim provenance model
- [x] Evidence-strength separate from model confidence
- [x] Reusable service blueprints
- [x] Runtime action policy decisions
- [x] Agent budget ledger and hard charge enforcement
- [x] Scoped agent tool gateway
- [x] Tamper-evident action receipts
- [x] Durable workflow checkpoints
- [x] Retry/backoff primitives
- [x] Client metric snapshots
- [x] Agent trajectory events
- [x] Unit economics endpoint
- [x] Security event schema
- [x] DB-backed distributed rate limiting
- [x] Provider actions wrapped by gateway/policy middleware
- [x] Automated outcome-to-blueprint optimization with human publication gate

- [x] Governed provider execution gateway
- [x] OAuth access-token expiry persistence
- [x] OAuth refresh and refresh-token rotation persistence
- [x] Provider health lifecycle
- [x] Outcome-driven optimization proposal generation
- [x] Human-gated blueprint approval/publishing
- [x] Automated metric scanning for optimization candidates
- [x] Distributed PostgreSQL-backed rate limiting for API/auth/OAuth
- [x] Self-hosted Infisical deployment bundle


## Capability status language

- **Ready:** implemented control-plane capability.
- **Runtime adapter:** provider action code exists and is reachable through governed execution.
- **Foundation:** contracts/data model exist but production execution is incomplete.
- **Supported:** bounded execution exists with explicit configuration requirements.
- **Production-ready:** reserved for paths that have been exercised against real provider accounts and deployment infrastructure.

Do not equate a checked item with universal third-party provisioning.

## Production release gate

- [x] Production readiness runbook and explicit release verification gate
- [x] Liveness/readiness separation and baseline security response headers

## Phase 13 — Optional Voice

The client must never need to join a call. Email and the client portal remain the default communication path; voice is an optional interface into the same client/project context.

- [x] Voice session control-plane model
- [x] Conversation turn persistence
- [x] AI disclosure requirement
- [x] Voice modes and escalation states
- [x] Twilio inbound webhook/TwiML compatibility path
- [x] Real-time media-stream contract
- [x] Realtime speech/model bridge foundation with interruption handling
- [x] Realtime GA WebSocket session/audio event contract aligned
- [x] Production webhook signature validation
- [x] Operator-approved custom-number test-call endpoint
- [x] E.164 destination validation and call lifecycle persistence
- [x] Do-not-call / preferred-channel policy primitives
- [ ] Real provider-account test and realtime contract validation
- [ ] Natural-voice quality evaluation against target latency/turn-taking
- [ ] Conversation intelligence connected to governed tools
- [ ] Automatic post-call email summary
- [ ] Human escalation/transfer

### Voice quality bar

Luma Voice is not considered production-ready merely because speech-to-text and text-to-speech work. The production bar is natural turn-taking, interruption handling, low latency, context-aware answers, explicit AI disclosure, no fabricated commitments, governed actions, reliable escalation, and an email follow-up path.
