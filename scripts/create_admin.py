"""Bootstrap script to create the initial admin user (SEC-04)."""

import argparse
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import func, select

from app.audit import log_audit
from app.auth import hash_password
from app.db import SessionLocal
from app.models import User


def create_admin(email: str, name: str, password: str) -> None:
    normalized_email = email.strip().lower()
    if len(password) < 12:
        print("Error: Password must be at least 12 characters long.")
        sys.exit(1)

    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(func.lower(User.email) == normalized_email))
        if existing:
            print(f"Error: User {normalized_email} already exists.")
            sys.exit(1)

        admin = User(
            email=normalized_email,
            name=name.strip(),
            role="admin",
            password_hash=hash_password(password),
            is_active=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)

        log_audit(
            db,
            admin.id,
            "create_admin",
            "users",
            str(admin.id),
            "Initial admin bootstrapped",
        )
        print(f"Admin user {normalized_email} created successfully.")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Create initial admin user for Sponsy Bot.")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--name", required=True, help="Admin full name")
    parser.add_argument("--password", required=True, help="Admin password (min 12 chars)")
    args = parser.parse_args()

    create_admin(args.email, args.name, args.password)


if __name__ == "__main__":
    main()
