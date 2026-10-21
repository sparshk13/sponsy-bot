#!/usr/bin/env bash
# Application zero-downtime update script (SEC-41, Acceptance 10.3).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="compose.prod.yaml"
if [ ! -f "$COMPOSE_FILE" ]; then
  COMPOSE_FILE="compose.yaml"
fi

echo "Pulling container base images..."
docker compose -f "$COMPOSE_FILE" pull postgres caddy

echo "Building API service..."
docker compose -f "$COMPOSE_FILE" build api

echo "Running database migrations..."
docker compose -f "$COMPOSE_FILE" run --rm api alembic upgrade head

echo "Restarting services..."
docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

echo "Verifying service health..."
sleep 3
for i in {1..10}; do
  if docker compose -f "$COMPOSE_FILE" exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/healthz')" >/dev/null 2>&1; then
    echo "Health check passed. Update completed successfully."
    exit 0
  fi
  echo "Waiting for API to become healthy (attempt $i/10)..."
  sleep 2
done

echo "Error: Health check failed after update." >&2
exit 1
