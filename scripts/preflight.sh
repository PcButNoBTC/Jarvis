#!/usr/bin/env bash
# Gate 1–2: local/shared host preflight before first client
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "FAIL: .env missing — cp .env.example .env and set secrets"
  exit 1
fi

# shellcheck disable=SC1091
set -a
source .env
set +a

fail=0
warn() { echo "WARN: $*"; }
die() { echo "FAIL: $*"; fail=1; }
ok() { echo "OK: $*"; }

if [[ -z "${LUMA_AUTH_SECRET:-}" || ${#LUMA_AUTH_SECRET} -lt 16 ]]; then
  die "LUMA_AUTH_SECRET must be 16+ characters"
else
  ok "LUMA_AUTH_SECRET length ${#LUMA_AUTH_SECRET}"
fi

for weak in change-me password postgres jarvis secret; do
  if [[ "${POSTGRES_PASSWORD:-}" == "$weak" || "${POSTGRES_PASSWORD:-}" == *"change-me"* ]]; then
    die "POSTGRES_PASSWORD looks weak/default — set a strong password"
  fi
done
ok "POSTGRES_PASSWORD is set and not a known default pattern (spot-check)"

if [[ -z "${SMTP_HOST:-}" ]]; then
  warn "SMTP_HOST unset — required before gate 4 (approved send)"
else
  ok "SMTP_HOST=${SMTP_HOST}"
fi

API="${NEXT_PUBLIC_API_URL:-http://localhost:8000}"
if curl -sf "${API}/health" >/dev/null 2>&1; then
  ok "API health at ${API}/health"
  echo "--- /ops/readiness ---"
  curl -sf "${API}/ops/readiness" | python3 -m json.tool 2>/dev/null || curl -sf "${API}/ops/readiness"
else
  warn "API not reachable at ${API} — start with: docker compose up --build"
fi

if [[ $fail -ne 0 ]]; then
  echo "Preflight FAILED — fix FAIL lines before launch"
  exit 1
fi
echo "Preflight passed core checks. Complete gates 3–7 via docs/LAUNCH_CHECKLIST.md"
