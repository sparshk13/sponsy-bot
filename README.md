# Sponsy Bot

Sponsy Bot is an internal sponsor outreach and relationship tracking tool for student engineering clubs. It combines automated company research, draft personalization, email delivery pacing, and incoming reply classification with a strict human approval requirement: no email is ever dispatched without a signed-off human review in the queue.

## Stack

- Frontend: React 19, TypeScript (strict mode), Vite, TanStack Query, hand-crafted CSS Modules adhering to the project design tokens.
- Backend: FastAPI, Python 3.12, SQLAlchemy 2.0 ORM, psycopg 3, LangGraph for draft generation workflows.
- Database: PostgreSQL with Alembic schema migrations.
- Reverse Proxy: Caddy with automated HTTPS and strict Content Security Policy.
- Deployment: Docker Compose on a single VM running non-root service containers.

## Core Rules and Guarantees

1. Human in the loop: Exactly one endpoint (`POST /api/messages/{id}/approve`) sets an outreach draft to approved. The approval records the user ID, timestamp, and a SHA-256 hash of recipient, subject, and body. Any subsequent edit immediately voids approval.
2. Free-tier discipline: The system operates entirely within free API allowances (Gemini, Tavily, Hunter). External requests pass through counted budget guards with local SQLite/Postgres caches.
3. Plain-text outreach: Outgoing messages use plain text with honest sender identity, no tracking pixels, and a mandatory one-line opt-out sentence.
4. Security: Denial by default on all API routes, CSRF token validation on every mutation, argon2id password hashing, TOTP two-factor authentication in production, Host header verification, and per-IP rate limits.

## Local Development Setup

### Prerequisites

- Docker and Docker Compose (or Colima on macOS)
- Python 3.12+
- Node.js 22+ and npm

### 1. Start database and reverse proxy

```bash
docker compose up -d postgres caddy
```

### 2. Configure backend environment

Copy the example environment file and fill in required values:

```bash
cp backend/.env.example backend/.env
```

Create a virtual environment and install backend dependencies:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

Run database migrations:

```bash
alembic upgrade head
```

Create your administrator account:

```bash
python scripts/create_admin.py admin@example.com "Admin User" "YourSecurePassword123"
```

Alternatively, to explore the platform with populated demo campaigns, companies, and drafts:

```bash
python scripts/seed_demo.py
# Demo sign-in: admin@example.com / Password12345!
```

Start the FastAPI backend server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Configure frontend

```bash
cd ../frontend
npm ci
npm run dev
```

Open `http://localhost:3000` (or your configured port) in your browser.

## Running in Production

Production configuration lives in `compose.prod.yaml` and `Caddyfile.prod`. Detailed provisioning steps for a clean cloud VM are documented in `docs/DEPLOYMENT.md`.

```bash
# On the production host:
docker compose -f compose.prod.yaml up -d --build
```

Ensure `APP_ENV=prod` is set in your production `.env` file. This turns on:
- Secure, HttpOnly, SameSite=Lax cookies with HSTS headers.
- Disables `/docs`, `/redoc`, and `/openapi.json`.
- Enforces TOTP two-factor authentication on all user logins.
- Validates incoming `Host` and `Origin` headers against `PUBLIC_URL`.

## Backup and Restore Runbook

Backups are encrypted using `age` public-key encryption before being written to disk (`deploy/backup.sh`). The private key is never kept on the production server.

### Creating an encrypted backup

Run the automated backup script:

```bash
./deploy/backup.sh
```

Backups are stored in `backups/sponsy_backup_YYYYMMDD_HHMMSS.sql.gz.age`. The script automatically keeps the 7 most recent backup archives.

### Restoring from an encrypted backup

To restore into a fresh database container:

```bash
# Provide the private key path and backup archive path
./deploy/restore.sh /path/to/backup_private_key.txt backups/sponsy_backup_YYYYMMDD_HHMMSS.sql.gz.age
```

## Key and Secret Rotation Runbook

When an organizer leaves the club, or every 90 days, rotate secrets in `backend/.env`:

1. Mail credentials (`MAIL_PASSWORD`):
   Generate a new Google Workspace or Gmail App Password. Update `backend/.env` and restart the API container:
   ```bash
   docker compose -f compose.prod.yaml restart api
   ```
2. Session secret (`SESSION_SECRET`):
   Generate a new 32-byte secret:
   ```bash
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```
   Update `backend/.env` and run `POST /api/admin/revoke-sessions` from the admin panel to invalidate all existing cookies.
3. Gemini API key (`GEMINI_API_KEY`):
   Create a new key in Google AI Studio with billing disabled. Replace the key in `.env`.
4. Tavily & Hunter keys (`TAVILY_API_KEY`, `HUNTER_API_KEY`):
   Regenerate keys in their respective provider consoles and update `.env`.
5. Administrator two-factor recovery:
   If an organizer loses access to their authenticator device, an administrator can reset their 2FA state from the Admin screen (`POST /api/admin/users/{id}/reset-2fa`). The user will be prompted to enroll a fresh device on their next sign-in.

## Operational Checks and Diagnostics

- Liveness check: `GET /api/healthz` returns `{"status": "ok"}`.
- System diagnostics: `GET /api/admin/system` displays database size, free disk space, last email dispatched, and last IMAP mail poll.
- Audit ledger: An append-only record of administrative actions, user logins, approvals, and suppressions is visible under the Admin screen and stored in the `audit_log` database table.
