#!/bin/sh
set -e

echo "==> Running database migrations..."
alembic upgrade head

echo "==> Checking if initial user exists..."
python -c "
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, '.')
from app.db import SessionLocal
from app.models import User
from sqlalchemy import select

db = SessionLocal()
try:
    has_users = db.scalar(select(User).limit(1)) is not None
finally:
    db.close()

if not has_users:
    sys.exit(0)
sys.exit(1)
" && {
    echo "==> Fresh database detected. Seeding demo campaigns and admin account..."
    python scripts/seed_demo.py
} || echo "==> Database already contains users. Skipping initial seed."

echo "==> Starting Sponsy Bot server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
