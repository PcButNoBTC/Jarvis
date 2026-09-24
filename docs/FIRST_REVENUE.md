# First revenue — launch and chase profit

**Objective:** one paid local job this month, then a repeatable weekly rhythm.  
Not seven half-finished services. Not Twilio. Not regional spam.

## Offer to sell first

| Service | Price band | Why first |
|---------|------------|-----------|
| **AI Website** | $750–$3,000 | Clear deliverable, portal-friendly, no phone vendor cost |

Optional second (after one website close): Lead Capture or Appointment Automation ($500–$2,000).

Skip AI Receptionist until you choose to pay for a number.

## 14-day operator plan

### Days 1–2 — Go live (no prospects yet)

```bash
cp .env.example .env          # strong secrets
docker compose up --build -d
./scripts/preflight.sh
curl -s localhost:8000/ops/readiness   # production_ready_core true
```

- Set SMTP **or** plan to share briefs by hand / portal only at first  
- Optional: one Google or HubSpot OAuth connect  
- `./scripts/backup-db.sh` once so restore is proven  

### Days 3–5 — Pipeline (fit only)

1. Add **15–25** local businesses (website + email if public)  
2. Research each  
3. **Fit-check** — contact only if fit  
4. Generate brief → save `share_text`  

Target: **8–12** quality briefs, not 100 cold emails.

### Days 6–10 — Conversations

- Share brief (email approved send **or** LinkedIn/email you type yourself)  
- Soft CTA: 10–15 min call, easy no  
- Log outcomes honestly (including not a fit)  

Target: **3–5** calls booked.

### Days 11–14 — Close and deliver

- One scoped proposal in band ($750–$3,000)  
- Accept → project → generate **AI Website** package  
- OPERATOR-QA → portal approve  
- Collect deposit or full payment  
- Log **hours** + **paid revenue** in Luma  

**Win condition:** paid_revenue > 0 and hours logged.

## Weekly rhythm after first close

| Day | Action |
|-----|--------|
| Mon | Research + fit-check 5 new names |
| Tue–Wed | Send 3 briefs (approved); book calls |
| Thu | Discovery / proposals |
| Fri | Delivery / QA / portal; log time + money; backup |

## Unit economics (simple)

- Price: e.g. **$1,500** website  
- Hours: aim **≤ 12** logged (use package + QA, don’t rebuild from zero)  
- Effective: **≥ $125/hour** before overhead  
- If hours creep: tighten scope in the proposal, not the price first  

## What “chasing profit” is not

- Buying ads before one organic close  
- Auto-sequences without fit-check  
- Selling Receptionist without Twilio budget  
- Expanding regions before one local paid job  

## Trust = higher close rate

Promise on every brief/portal: observe-only, client approves sends, client owns logins, easy no.  
That is the advantage in an untapped market — not volume.
