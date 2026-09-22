# Luma

Self-hosted AI business operating system for finding opportunities, preparing sales, winning work, and helping deliver it.

## V1

Luma V1 is built around a simple loop:

**Discover → Research → Qualify → Sell → Deliver → Follow up → Measure revenue**

### Stack
- PostgreSQL
- FastAPI
- Next.js
- Python worker
- Provider-neutral AI gateway
- Docker Compose

### Repository layout

```
apps/api        FastAPI API
apps/web        Next.js dashboard
apps/worker     scheduled/background jobs
database        PostgreSQL schema and seeds
packages        shared domain/AI modules
prompts         versioned agent prompts
infrastructure  deployment helpers
tests            automated tests
```

## Quick start

1. Copy `.env.example` to `.env`.
2. Set strong database credentials.
3. Start services:

```bash
docker compose up --build
```

4. API health: `/health`
5. Dashboard: `http://localhost:3000`

## Operating principle

Start free/cheap. Spend more only when an expense can be tied to revenue, delivery quality, or a measurable reduction in manual work.

Never put API keys, passwords, private keys, or customer secrets in Git.


## V1.1 API

The first money-making primitives now include:

- `POST /businesses` — add a prospect.
- `GET /businesses` — list prospects.
- `POST /analyze-website` — collect conservative, observable website signals.
- `POST /qualify` — score an analysis with transparent evidence-based heuristics.
- `GET /dashboard` — pipeline counts.

Website analysis is intentionally evidence-first. It does not invent business problems or assume that automation is needed. Outbound actions remain human-approved.

CI runs Python compilation checks and qualification tests on pushes and pull requests.


## V1.2 Sales + delivery cockpit

Sales workflow endpoints:

- `GET /opportunities` — review qualified opportunities.
- `GET /opportunities/{id}` — inspect evidence and activity.
- `POST /opportunities/{id}/prepare-call` — create evidence-based call prep.
- `POST /opportunities/{id}/create-offer` — turn an opportunity into a scoped offer.
- `POST /proposals` — create a proposal draft.
- `PATCH /proposals/{id}/status` — move a proposal through draft/sent/accepted/rejected/expired.

Delivery workflow:

- Accepting a proposal automatically creates or activates the client, creates a project, creates an initial delivery checklist, and marks the opportunity won.
- `GET /projects/{id}` — inspect the project and tasks.
- `POST /projects/{id}/start` — start delivery and optionally set dates.

The proposal and call-prep generators are deterministic templates for now. This keeps the core business loop usable without requiring a paid AI provider; stronger model-based generation can be added behind the provider-neutral AI layer later.

Outbound communication is still not automatically sent. Human approval remains the gate before external communication.

## Naming

The AI operator is named **Luma**. The GitHub repository remains **Jarvis** for continuity with the existing project infrastructure.


## V1.3 Discovery + research queue

Luma now has a controlled discovery foundation:

- `POST /prospects/ingest` — ingest or update a prospect with source metadata.
- `POST /businesses/{id}/research` — enqueue website research.
- `GET /research/jobs` — inspect the research queue.
- `POST /research/jobs/{id}/run` — execute one research job.
- The worker polls the queue and asks the API to run research.
- `POST /outreach/drafts` — create an evidence-based outbound draft.
- `GET /outreach/drafts` — review drafts awaiting human approval.

Deduplication prefers a source external ID, then email, then normalized website domain, then business name. The system does not auto-send outbound messages. Source adapters should only use data sources whose automation terms and applicable laws permit the intended use.


## V1.4 Service-specific opportunities

Raw website signals are no longer collapsed into a single “AI Website” opportunity.

`map_to_service_opportunities()` maps observed factors to the existing service catalog:

| Signal family              | Primary services                          |
|----------------------------|-------------------------------------------|
| Site errors / HTTPS / mobile / slow load | AI Website, Custom Automation    |
| Missing contact form / CTA / email     | Lead Capture System, Appointment Automation |
| Missing phone link                   | AI Receptionist, Appointment Automation   |
| Multi-signal residual                | Custom Automation                       |

Research jobs and `POST /businesses/{id}/analyze` now create **one opportunity per qualifying service**, each with its own score, evidence factors, title, and linked `service_id`.

`POST /qualify` without `service_name` returns the full list of service-specific opportunities plus an aggregate score. With `service_name` it remains a single weighted score for backward compatibility.

Prompt version for automated research is now `website-analysis-v2`.


## V1.5 Industry bias + service-aware sales

- Optional `industry` on a business boosts relevant services (e.g. dental → Appointment Automation + AI Receptionist; contractor → Lead Capture; restaurant → Review Automation).
- Research and analyze paths pass `business.industry` into the mapper.
- `POST /qualify` accepts `industry` when returning the full opportunity list.
- Call-prep generators use service-specific openings and discovery questions.
- Dashboard opportunity queue shows a clear service badge per opportunity.


## V1.6 Revenue outreach + offer scope

Upgrades aimed only at booking meetings and closing offers:

- `POST /outreach/drafts` builds a **Day 1 / 3 / 7** email sequence from opportunity evidence (plain-English observations, service outcome, industry hook). All messages stay **draft** until human approval.
- Service-specific default offer deliverables, assumptions, and exclusions so proposals are concrete and easier to accept.
- No auto-send. Human gate remains the control point before any external message.
