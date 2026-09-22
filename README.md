# Luma

**Only recommend what you observed.**

<p align="center">
  <img src="apps/web/public/icon.svg" alt="Luma icon" width="88" height="88" />
</p>

**Luma** is a self-hosted AI business operating system for finding local opportunities, preparing sales, winning work, and delivering it — without spray-and-pray outreach or generic “AI” pitches.

The GitHub repository remains **Jarvis** for continuity. The product name is **Luma**.

---

## Why Luma is different

| Typical AI agency tool | Luma |
|------------------------|------|
| Generic “we do AI” outreach | Opens with **observed** site signals in plain English |
| One product forced on every lead | **Service-specific** opportunities (Website, Lead Capture, Receptionist, …) |
| Auto-send sequences | **Human approval** before any external message |
| Feature dump proposals | **One-page client brief** prospects can understand |
| Black-box scoring | Transparent **heuristic factors** tied to evidence |

---

## Capabilities at a glance

### 1. Discover and ingest prospects
- Manual business create
- Prospect ingest with source metadata
- CSV import path
- Deduplication by external ID, email, domain, or name
- Research job queue with worker polling

### 2. Website research (evidence-first)
Automated analysis collects **only observable signals**:
- HTTP status, HTTPS, response time
- Mobile viewport
- Contact form, phone link, email link, clear CTA
- CMS detection (WordPress, Wix, Squarespace, Shopify, Webflow)

No invented business problems. No assumed need for automation.

### 3. Service-specific qualification
Raw signals map to your catalog — not a single “AI Website” bucket:

| Service | Typical signal drivers |
|---------|------------------------|
| **AI Website** | Site errors, no HTTPS, no mobile viewport, slow load |
| **Lead Capture System** | No form, no CTA, no email path |
| **AI Receptionist** | No phone link, weak inbound contact surface |
| **Appointment Automation** | Weak booking / CTA signals |
| **Review Automation** | Supported with industry bias |
| **Video Walkthrough** | Boosted for real estate / property niches |
| **Custom Automation** | Multi-signal residual cases |

Optional **industry bias** (dental, HVAC, contractor, restaurant, legal, …) gently boosts the services that fit that vertical.

### 4. Pipeline and sales cockpit
- Opportunities with score, evidence, service link, value range
- **Call prep** — service-specific openings, discovery questions, objection handling
- **Client brief** — shareable one-pager (what we noticed, why it matters, recommendation, investment, how we work)
- **Outreach sequence** — Day 1 / 3 / 7 drafts, low-pressure, human-approved only
- **Offers and proposals** — concrete deliverables, assumptions, exclusions per service
- Proposal status: draft → sent → accepted / rejected / expired

### 5. Delivery engine
- Accepting a proposal creates a client, project, implementation record, and delivery checklist
- Capture approved requirements per project
- Generate real delivery artifacts from service blueprints
- Validate generated artifacts against acceptance criteria
- Human approval gate before deployment
- Package a ZIP handoff the client can host or launch
- Optional static-site deployment when LUMA_DEPLOY_ROOT is configured
- Track implementation, deployment, artifacts, and handoff state in PostgreSQL
- Projects, tasks, activities and dashboard queues

### 6. Delivery reality

Luma now crosses the line from project tracking into implementation. The V1 delivery engine can generate a deployable static website package for AI Website projects and implementation/activation packages for workflow services. It does not fabricate third-party credentials, DNS ownership, calendar accounts, phone numbers, or provider access. Production deployment of a static site requires a configured `LUMA_DEPLOY_ROOT` and web-server/domain mapping on the host. Workflow services still require their provider-specific activation step.

### 7. Operating principles (product constraints)
- Start free/cheap; spend only when tied to revenue or quality
- Never commit secrets to Git
- **No auto-send** of outreach
- Evidence-first research only

---

## Stack

| Layer | Technology |
|-------|------------|
| API | FastAPI (Python) |
| Dashboard | Next.js 14 |
| Worker | Python (research queue) |
| Database | PostgreSQL |
| Runtime | Docker Compose |
| AI | Provider-neutral gateway (optional; core loop works on heuristics) |

---

## Repository layout

```
apps/api          FastAPI API, qualification, sales, website analyzer
apps/web          Next.js dashboard (+ public/icon.svg)
apps/worker       Background research job runner
database          PostgreSQL schema + service seeds
packages/leads    Lead source helpers
prompts           Versioned agent prompt templates
.github/workflows CI (compile + qualification tests)
```

---

## Quick start

```bash
cp .env.example .env
# Set strong Postgres credentials in .env

docker compose up --build
```

| Surface | URL |
|---------|-----|
| API health | `http://localhost:8000/health` |
| API root | `http://localhost:8000/` |
| Dashboard | `http://localhost:3000` |
| Deployment preview | `http://localhost:8080` |

---

## Core API map

### Prospects and research

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/businesses` | Add prospect |
| `GET` | `/businesses` | List prospects |
| `POST` | `/prospects/ingest` | Ingest / dedupe prospect |
| `POST` | `/businesses/{id}/research` | Enqueue website research |
| `GET` | `/research/jobs` | Inspect research queue |
| `POST` | `/research/jobs/{id}/run` | Run one research job |
| `POST` | `/analyze-website` | Analyze URL only |
| `POST` | `/businesses/{id}/analyze` | Analyze + create opportunities |
| `POST` | `/qualify` | Score analysis (optional `industry`) |

### Opportunities and sales

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/opportunities` | List opportunities |
| `GET` | `/opportunities/{id}` | Detail + activities |
| `POST` | `/opportunities/{id}/prepare-call` | Call prep pack |
| `POST` | `/opportunities/{id}/client-brief` | Shareable client one-pager |
| `POST` | `/opportunities/{id}/create-offer` | Scoped offer |
| `POST` | `/proposals` | Proposal draft |
| `PATCH` | `/proposals/{id}/status` | Move proposal status |

### Outreach (human-gated)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/outreach/drafts?opportunity_id=` | Day 1/3/7 **draft** emails |
| `GET` | `/outreach/drafts` | Review drafts |
| `PATCH` | `/outreach/drafts/{id}` | Edit / approve / reject |

### Delivery and ops

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/dashboard` | Counts + queues |
| `GET` | `/projects/{id}` | Project detail |
| `POST` | `/projects/{id}/start` | Start delivery |
| `POST` | `/projects/{id}/requirements` | Save approved implementation requirements |
| `POST` | `/projects/{id}/generate` | Generate implementation artifacts |
| `POST` | `/projects/{id}/validate` | Run delivery QA |
| `POST` | `/projects/{id}/approval` | Approve implementation for deployment |
| `POST` | `/projects/{id}/deploy` | Deploy an approved static site when configured |
| `POST` | `/projects/{id}/monitor` | Check the production URL after launch |
| `GET` | `/projects/{id}/artifacts` | List generated artifacts |
| `GET` | `/projects/{id}/download` | Download client delivery package |
| `POST` | `/projects/{id}/handoff` | Prepare client handoff |
| `PATCH` | `/tasks/{id}/status` | Update task |

---

## Recommended revenue workflow

1. **Ingest** a local business (with `industry` when known).
2. **Research** the website → multiple service opportunities with scores.
3. Open the top opportunity → **Client brief** → share with the owner.
4. Or **Draft outreach** → approve Day 1 only when the tone is right.
5. **Call prep** before the conversation.
6. **Create offer** with concrete deliverables → proposal → accept → project.

Nothing external is sent until a human approves it.

---

## Seeded services (catalog)

| Service | Typical setup range | Delivery days |
|---------|---------------------|---------------|
| AI Website | $750–$3,000 | 7 |
| AI Receptionist | $750–$2,500 | 7 |
| Lead Capture System | $500–$2,000 | 5 |
| Appointment Automation | $500–$2,000 | 5 |
| Review Automation | $250–$1,000 | 3 |
| Video Walkthrough | $250–$1,500 | 5 |
| Custom Automation | $750–$5,000 | 14 |

Ranges are defaults in `database/schema.sql` and can be overridden per offer.

---

## Version history (product)

| Version | Focus |
|---------|--------|
| **V1** | Discover → research → qualify → sell → deliver loop |
| **V1.1** | Website analyze + qualify primitives |
| **V1.2** | Sales + delivery cockpit |
| **V1.3** | Discovery + research queue |
| **V1.4** | Multi-service opportunity mapping |
| **V1.5** | Industry bias + service-aware call prep |
| **V1.6** | Revenue outreach sequences + offer scopes |
| **V1.7** | Client brief, warmer copy, client-friendly dashboard |
| **V1.8** | Project icon, full capabilities README, branding polish |
| **V2.0** | Delivery generation, QA, approval, deployment, monitoring, handoff |

---

## Dashboard

The web UI emphasizes:

- Headline: **Only recommend what you observed**
- Pipeline metrics
- Opportunity queue with **service badges**
- One-click **Client brief**, **Draft outreach**, **Call prep**
- Research queue, outreach drafts (approval required), projects, tasks

Icon: `apps/web/public/icon.svg` (indigo mark — light + path forward).

---

## Development and tests

```bash
# API unit tests
cd apps/api
python -m pytest test_qualification.py test_sales.py -q

# Syntax check
python -m py_compile main.py qualification.py sales.py website_analyzer.py
```

CI runs Python compile checks and qualification tests on push/PR.

---

## Security and compliance notes

- Do not store API keys, passwords, or customer secrets in Git.
- Use `.env` (see `.env.example`).
- Outreach is **draft-only** until approved — reduce spam and legal risk.
- Source adapters should only use data sources whose terms and applicable laws allow the intended use.
- Website analysis uses a polite User-Agent and short timeouts.

---

## License and naming

- Product: **Luma**
- Repository: **Jarvis** (`PcButNoBTC/Jarvis`)
- License: see repository settings / `LICENSE` if present

---

## What “done” looks like for a client

1. They receive a **short brief** about their own public site — not a feature list.
2. They understand **one recommended service** and a **price range**.
3. They approve scope before work.
4. Delivery is tracked as a project with clear tasks.

That is the product promise: **evidence, clarity, human control**.


## Client launch center

Projects now include a launch-readiness workflow. Before Luma will deploy an AI Website, the client/operator must confirm the production domain, hosting/deployment target, hosting access, DNS access, HTTPS/SSL, approved production content/assets, primary contact email, and final production URL.

The dashboard exposes these requirements in **Client Launch Center** and provides optional resource suggestions for hosting, DNS, forms, and analytics. The generated delivery package also includes `CLIENT-LAUNCH.md`.

Luma never fabricates third-party credentials or creates external accounts on the client's behalf. External providers remain explicit client-controlled dependencies.
