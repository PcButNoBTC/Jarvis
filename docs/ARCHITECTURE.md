# Luma architecture

## System view

Luma is a self-hosted control plane around probabilistic AI and deterministic business workflows.

```
Next.js dashboard
       |
       v
FastAPI control plane
       |
       +---- PostgreSQL
       |
       +---- workflow/agent governance
       |
       +---- secret backend
       |          |
       |          v
       |     provider adapters
       |
       +---- worker
```

## Control-plane layers

### 1. Experience

apps/web provides the operator dashboard and client-facing workflow surfaces.

### 2. API/control plane

apps/api owns:

- authentication
- authorization
- opportunities
- sales
- projects
- delivery
- automation
- integrations
- revenue
- governance
- analytics

### 3. System of record

PostgreSQL stores durable business state:

- businesses
- contacts
- research
- opportunities
- offers
- proposals
- clients
- projects
- tasks
- activities
- messages
- agent runs
- workflows
- integrations
- billing
- approvals
- revisions
- outcomes
- metrics
- policies
- receipts
- checkpoints
- optimization proposals

### 4. Worker

apps/worker handles queued/scheduled work without moving provider credentials into worker business logic.

### 5. Secret boundary

PostgreSQL stores secret references. Provider credentials are retrieved through the secret backend.

Production topology:

Luma API/Worker → Infisical → provider API

### 6. Provider boundary

Adapters receive credentials and provider-specific payloads. They do not receive database access or direct control-plane state.

## Governed action path

```
request
  ↓
authenticated principal
  ↓
distributed rate limit
  ↓
tool/action mapping
  ↓
policy evaluation
  ↓
approval check
  ↓
credential retrieval/refresh
  ↓
provider adapter
  ↓
health/error lifecycle
  ↓
audit event
  ↓
tamper-evident receipt
  ↓
outcome
```

The key architectural rule is that agents do not directly call provider SDKs or databases.

## Project lifecycle

```
opportunity
   ↓
offer
   ↓
proposal
   ↓
client acceptance
   ↓
project
   ↓
configuration
   ↓
compiled requirements
   ↓
implementation
   ↓
generation
   ↓
QA
   ↓
client review
   ↓
approval
   ↓
deployment/activation
   ↓
monitoring
   ↓
handoff
```

## Learning lifecycle

```
delivery
  ↓
client outcome
  ↓
metric snapshot
  ↓
pattern detection
  ↓
optimization proposal
  ↓
human approval
  ↓
service blueprint version
  ↓
future delivery
```

## Design rules

1. AI proposes; deterministic control logic enforces.
2. Evidence is separate from interpretation.
3. Consequential external actions have approval boundaries.
4. Provider credentials remain outside normal application state.
5. Client-specific configuration becomes explicit requirements.
6. Outcomes are measured separately from activity.
7. Reusable blueprints are versioned.
8. Production claims require real provider execution/testing.

