# Launch checklist — first client

Complete these seven gates before treating Luma as live for paying work.

## Gate 1 — Strong secrets

```bash
cp .env.example .env
# Set POSTGRES_PASSWORD to a long random string (not change-me)
# Set LUMA_AUTH_SECRET to 16+ random characters
# On shared hosts also set LUMA_API_KEY
./scripts/preflight.sh
```

## Gate 2 — Readiness green

```bash
docker compose up --build -d
curl -s http://localhost:8000/ops/readiness | python3 -m json.tool
```

Require `"production_ready_core": true`. Aim for `"launch_ready": true` before outreach.

Machine list: `GET /ops/launch-checklist`

## Gate 3 — One live OAuth

1. Create OAuth app (Google Calendar **or** HubSpot) with redirect  
   `https://<your-api>/integrations/oauth/<provider>/callback`
2. Set `GOOGLE_CLIENT_ID/SECRET` or `HUBSPOT_CLIENT_ID/SECRET` in `.env`
3. Integration Center → Connect → complete OAuth
4. Health check → **human verify** → status **CONNECTED**

See `docs/OPS_OAUTH_CHECKLIST.md`.

## Gate 4 — SMTP test

```bash
# In .env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
curl -s -X POST http://localhost:8000/ops/smtp-test \
  -H 'Content-Type: application/json' \
  -d '{"approved":true,"to":"you@example.com"}'
```

Confirm the message arrives. Outreach send uses the same dual gate (`status=approved` + `approved=true`).

## Gate 5 — Full loop (friendly or real business)

Follow `scripts/first-client-loop.md`:

Research → **fit-check** → client brief (`share_text`) → proposal → generate package → portal approve → log **hours** + **paid revenue**.

Do not skip fit-check. Do not auto-send.

## Gate 6 — Backup / restore

```bash
./scripts/backup-db.sh
# On a scratch project or after hours:
./scripts/restore-db.sh backups/luma-XXXX.sql.gz
```

Type `RESTORE` only when you intend to overwrite the target DB.

## Gate 7 — Public HTTPS (non-localhost)

1. Reverse proxy (Caddy example in `docs/DEPLOYMENT.md`) terminating TLS
2. `NEXT_PUBLIC_API_URL=https://api.yourdomain.com`
3. OAuth redirect URIs updated to the same public API base
4. Re-test one OAuth connect on the public URL

## First-client ready definition

| Must be true | Source |
|--------------|--------|
| Secrets strong, DB up | `/ops/readiness` |
| You can restore a backup | Gate 6 script |
| One path to contact a client ethically | Fit-check + brief |
| One path to deliver | AI Website (or chosen service) package + portal |
| One path to get paid and measure | Revenue + time entries |

**Regional expansion** only after one paid local job with hours logged.
