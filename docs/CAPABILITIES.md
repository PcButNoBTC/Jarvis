# Luma capabilities

This document is the detailed capability inventory. The route implementation, database schema and tests remain the technical source of truth.

## Business operating system

Luma connects:

Discover → Research → Qualify → Sell → Configure → Build → QA → Launch/Handoff → Measure → Learn.

## Discovery

- business and contact records
- prospect ingestion
- source metadata
- deduplication
- research queue
- retry/backoff
- scheduled automation

## Research

- website HTTP/HTTPS observations
- response-time observation
- mobile viewport observation
- CTA/contact-surface observation
- phone/email/form observation
- CMS/technology hints
- research reports
- evidence items
- evidence claims
- evidence-strength scoring
- alternatives and uncertainty

Luma is designed to avoid turning an observation into an unsupported claim.

## Qualification

Current services:

1. AI Website
2. AI Receptionist
3. Lead Capture System
4. Appointment Automation
5. Review Automation
6. Video Walkthrough
7. Custom Automation

Qualification supports:

- service-specific factors
- numeric confidence
- fit score/disposition
- rationale
- why this
- why not
- alternatives
- estimated value
- next action
- lifecycle state

## Sales

- call preparation
- discovery questions
- objection handling
- client briefs
- offers
- proposal versions
- proposal lifecycle
- follow-up queue
- outreach drafts
- outreach suppression
- communication preferences

External outreach remains human-approved.

## Project control plane

- project configuration
- requirements compilation
- service adapters
- tasks
- milestones
- dependencies
- approval history
- revision requests
- implementation records
- artifact records
- deployment records
- handoff records

## Delivery

- service-specific build plans
- implementation artifact generation
- deterministic requirements
- acceptance criteria
- QA contracts
- launch readiness
- static deployment to configured deployment root
- production URL monitoring
- ZIP handoff packages

## Client portal

- scoped access tokens
- project status
- milestones
- configuration/requirements
- client approval
- revision requests
- deliverable downloads
- AI disclosure preference
- communication preference
- data-ownership messaging

## Integrations

Current runtime providers:

### Google Calendar
- OAuth
- calendar listing
- availability
- event creation
- token refresh
- health checks

### Microsoft Outlook
- OAuth
- calendar listing
- schedule/availability
- event creation
- token refresh
- health checks

### Calendly
- OAuth foundation
- PKCE authorization
- event-type listing
- booking-link support
- refresh-token rotation handling
- health checks

### HubSpot
- OAuth foundation
- contact creation/listing
- deal creation
- health checks

### SMTP
- health checks
- email sending

### Twilio
- health checks
- SMS sending

Stripe, hosting, forms, analytics and other providers have registry/adapter foundations but should not be described as universally production-complete.

## Agent platform

Agents are specialized by job:

- research
- sales
- project
- build
- QA
- launch

Controls include:

- agent policy
- allowed tools
- approval requirement
- budget
- maximum tool calls
- token limits
- risk policy
- evaluation
- trajectory events
- budget ledger

## Runtime governance

Provider and agent actions are intended to pass through:

1. identity
2. rate limit
3. scope
4. risk
5. approval
6. secret retrieval
7. provider adapter
8. audit
9. action receipt
10. outcome

Action receipts can form a hash-linked history.

## Workflow engine

- durable workflow runs
- deterministic step transitions
- approval steps
- checkpoints
- retry/backoff
- five-field cron parser
- atomic schedule claims
- research worker
- scheduled workflow worker

Current governed workflows include research, proposal follow-up, project delivery and blueprint optimization.

## Revenue and economics

- billing records
- payment reconciliation
- revenue transactions
- recurring revenue
- operating cost records
- model/agent cost estimates
- contribution
- revenue-per-operating-dollar
- service performance

## Outcome intelligence

- client outcome records
- baseline/current values
- client confirmation
- metric snapshots
- automated optimization candidate scanning
- optimization proposals
- human approval
- versioned service blueprints

The optimizer proposes changes; it does not silently change an active client implementation.

## Security

- signed bearer authentication
- roles: owner/admin/operator/client
- optional API key
- scoped portal tokens
- secret references
- OAuth state signing
- single-use OAuth state nonces
- token expiry
- refresh-token rotation persistence
- audit log
- security event model
- distributed PostgreSQL-backed rate limits
- self-hosted Infisical deployment bundle

## Growth

Regional playbooks store:

- region
- status
- proven offers
- industry patterns
- outreach metrics
- client-success metrics

Expansion is intentionally tied to demonstrated client value.

## Explicit non-capabilities

Luma does not automatically:

- create arbitrary third-party accounts
- invent credentials
- claim DNS/domain ownership
- bypass provider authorization
- silently send outreach
- silently deploy unapproved work
- silently change active client projects because of optimizer output
- guarantee provider API compatibility forever
- replace legal/compliance review for outreach or data use

