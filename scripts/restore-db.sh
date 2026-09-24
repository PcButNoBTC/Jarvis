#!/usr/bin/env bash
# Gate 6: restore a gzipped dump into the running db (DESTRUCTIVE to current data)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
DUMP="${1:-}"
if [[ -z "$DUMP" || ! -f "$DUMP" ]]; then
  echo "Usage: $0 backups/luma-YYYYMMDD.sql.gz"
  exit 1
fi
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
DB="${POSTGRES_DB:-jarvis}"
USER="${POSTGRES_USER:-jarvis}"
echo "WARNING: This replaces data in database '$DB'."
read -r -p "Type RESTORE to continue: " confirm
[[ "$confirm" == "RESTORE" ]] || { echo "Aborted"; exit 1; }

if docker compose ps db 2>/dev/null | grep -q Up; then
  gunzip -c "$DUMP" | docker compose exec -T db psql -U "$USER" -d "$DB"
else
  gunzip -c "$DUMP" | psql "${DATABASE_URL:?set DATABASE_URL}"
fi
echo "OK: restore completed from $DUMP"
