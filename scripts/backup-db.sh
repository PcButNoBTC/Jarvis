#!/usr/bin/env bash
# Gate 6: dump Postgres to ./backups/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
mkdir -p backups
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="backups/luma-${STAMP}.sql.gz"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

DB="${POSTGRES_DB:-jarvis}"
USER="${POSTGRES_USER:-jarvis}"
if docker compose ps db 2>/dev/null | grep -q Up; then
  docker compose exec -T db pg_dump -U "$USER" "$DB" | gzip > "$OUT"
else
  echo "DB container not up — attempting local pg_dump via DATABASE_URL"
  if [[ -n "${DATABASE_URL:-}" ]]; then
    pg_dump "$DATABASE_URL" | gzip > "$OUT"
  else
    echo "FAIL: start docker compose or set DATABASE_URL"
    exit 1
  fi
fi
echo "OK: backup written to $OUT"
ls -la "$OUT"
