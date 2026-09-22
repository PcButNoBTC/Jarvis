# Jarvis

Self-hosted AI business operating system for finding opportunities, preparing sales, winning work, and helping deliver it.

## V1

Jarvis V1 is built around a simple loop:

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
