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
