# Self-hosted Infisical for Luma

This directory provides an isolated Infisical stack for Luma's provider credentials.

## Setup

1. Copy `.env.example` to `.env`.
2. Generate unique `ENCRYPTION_KEY` and `AUTH_SECRET` values.
3. Set a strong Postgres password and update `DB_CONNECTION_URI` to match it.
4. Start with `docker compose up -d`.
5. Complete the initial Infisical admin setup.
6. Create a Luma project/environment and a machine identity with least-privilege access.
7. Configure Luma's `INFISICAL_URL`, `INFISICAL_CLIENT_ID`, `INFISICAL_CLIENT_SECRET`, `INFISICAL_PROJECT_ID`, environment and path.

Do not commit `.env`, encryption keys, machine-identity credentials, or OAuth tokens.

The current compose pattern follows Infisical's official self-hosted Docker Compose architecture: backend + Postgres + Redis + migration job. The example deliberately binds the backend to localhost so a reverse proxy can own public TLS.

For a production deployment, pin a tested Infisical image version and put the service behind HTTPS. Back up both the Postgres data and the Infisical encryption key.
