#!/usr/bin/env bash
# Database restore script for age-encrypted backups (SEC-31).
# Usage: ./deploy/restore.sh <backup_file.sql.gz.age> <age_identity_key_file>

set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <backup_file.sql.gz.age> <age_identity_key_file>" >&2
  exit 1
fi

BACKUP_FILE="$1"
KEY_FILE="$2"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Error: Backup file not found: ${BACKUP_FILE}" >&2
  exit 1
fi

if [ ! -f "$KEY_FILE" ]; then
  echo "Error: Identity key file not found: ${KEY_FILE}" >&2
  exit 1
fi

if ! command -v age >/dev/null 2>&1; then
  echo "Error: age decryption tool is not installed." >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ -f .env ]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' .env | xargs -0) 2>/dev/null || true
fi

COMPOSE_FILE="compose.prod.yaml"
if [ ! -f "$COMPOSE_FILE" ]; then
  COMPOSE_FILE="compose.yaml"
fi

echo "Restoring database from ${BACKUP_FILE}..."
age --decrypt -i "$KEY_FILE" "$BACKUP_FILE" \
  | gunzip -c \
  | docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "${POSTGRES_USER:-sponsy_app}" -d "${POSTGRES_DB:-sponsy}"

echo "Database restored successfully."
