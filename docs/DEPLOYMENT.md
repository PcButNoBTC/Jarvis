# Deployment — toward production

## Local (operator laptop)

```bash
cp .env.example .env
# Set POSTGRES_PASSWORD and LUMA_AUTH_SECRET (16+ chars)
docker compose up --build
curl -s http://localhost:8000/ops/readiness
```

## Shared / public host (minimum)

1. Strong `POSTGRES_PASSWORD` and `LUMA_AUTH_SECRET`
2. `LUMA_API_KEY` for machine access
3. TLS reverse proxy for API + web
4. Set `NEXT_PUBLIC_API_URL` to the public API URL
5. OAuth redirect URIs must match public API base
6. SMTP before any approved outreach send
7. Automated Postgres backups + restore drill

## After deploy

| Check | Action |
|-------|--------|
| Health | `GET /health` |
| Readiness | `GET /ops/readiness` |
| One OAuth connect | Integration Center → verify → CONNECTED |
| One fit-check + brief | Real or sample business |
| Portal token | Create access, open as client |
| Backup | Dump DB and restore to a scratch instance |

## Do not claim

“Production-ready for all clients” until verification gates in `docs/VERIFICATION_GATES.md` are green.
