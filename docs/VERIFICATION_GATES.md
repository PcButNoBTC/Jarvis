# Verification gates — live environment

Architecture in the repository is not the same as a production business system.  
These gates must be exercised in a **real environment** before claiming production-ready operations.

## Required for honest “live” claims

| Gate | What “done” means |
|------|-------------------|
| PostgreSQL production | Managed or hardened instance + **backup and restore tested** |
| Public HTTPS | Dashboard and API on real TLS certificates |
| Public WSS (if voice/realtime) | Secure websocket path tested end-to-end |
| DNS | Stable hostnames for app, API, and webhooks |
| Twilio (if receptionist/voice) | Real account, number, Media Streams test call |
| OpenAI / model provider (if used) | Real credentials, budget caps, logged spend |
| OAuth providers | Real Google / Microsoft / Calendly / HubSpot apps + one CONNECTED flow |
| SMTP | Real send of one **approved** outreach draft |
| CRM / calendar | One real contact or event created via approved path |
| Monitoring | Basic uptime + error visibility |
| Client workflow | Research → brief → proposal → package → portal approve → hours + revenue logged |

## Explicitly not proven by a git commit

- That Twilio audio formats work on a live call  
- That OAuth refresh survives days in production  
- That backups restore cleanly  
- That a local business will pay  

## Status language

- **Repo hardened** — safe to say  
- **Production architecture aligned** — safe to say when docs and code match  
- **Production-ready business** — only after gates above are green  

`GET /ops/readiness` covers config basics only. It does **not** replace these gates.
