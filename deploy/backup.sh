#!/usr/bin/env bash
# Nightly encrypted PostgreSQL backup script (SEC-31).
# Keeps last 7 backups encrypted with age.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f .env ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | xargs -0) 2>/dev/null || true
fi

BACKUP_DIR="${ROOT_DIR}/backups"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

TIMESTAMP="$(date -u +"%Y%m%d_%H%M%SZ")"
BACKUP_FILE="${BACKUP_DIR}/sponsy_backup_${TIMESTAMP}.sql.gz.age"

if [ -z "${BACKUP_AGE_RECIPIENT:-}" ]; then
  echo "Error: BACKUP_AGE_RECIPIENT is not set in environment or .env." >&2
  exit 1
fi

if ! command -v age >/dev/null 2>&1; then
  echo "Error: age encryption tool is not installed." >&2
  exit 1
fi

COMPOSE_FILE="compose.prod.yaml"
if [ ! -f "$COMPOSE_FILE" ]; then
  COMPOSE_FILE="compose.yaml"
fi

echo "Starting database backup at ${TIMESTAMP}..."
docker compose -f "$COMPOSE_FILE" exec -T postgres pg_dump -U "${POSTGRES_USER:-sponsy_app}" "${POSTGRES_DB:-sponsy}" \
  | gzip -c \
  | age -r "$BACKUP_AGE_RECIPIENT" > "$BACKUP_FILE"

chmod 600 "$BACKUP_FILE"
echo "Backup saved and encrypted to: ${BACKUP_FILE}"

# Retention: keep the 7 most recent backups, delete older
find "$BACKUP_DIR" -name "sponsy_backup_*.sql.gz.age" -type f | sort -r | tail -n +8 | while read -r old_file; do
  echo "Removing old backup: ${old_file}"
  rm -f "$old_file"
done

echo "Backup complete."
