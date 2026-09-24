# First-client loop (operator run sheet)

Print or keep open while serving the first client.

1. **Preflight** — `./scripts/preflight.sh` and `curl -s $API/ops/readiness | jq .launch_ready`
2. **Ingest** — create business (name, website, email, industry)
3. **Research** — queue research; wait for completion
4. **Fit-check** — `POST /opportunities/{id}/fit-check` — stop if not fit
5. **Brief** — `POST /opportunities/{id}/client-brief` — send only `share_text`
6. **Discovery** — 10–15 min call; soft CTA; easy no
7. **Proposal** — scoped offer; accept → project
8. **Configure** — project options for the service
9. **Generate** — delivery package; complete OPERATOR-QA.md
10. **Portal** — create access; client approves
11. **Activate / handoff** — only after acceptance
12. **Measure** — `POST /time-entries`; record paid revenue
13. **Backup** — `./scripts/backup-db.sh` after the job is closed

Tone: evidence only, no pressure, client owns logins.
