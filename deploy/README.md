# Sponsy Bot Operator Runbook

This runbook covers production operations, security configuration, backups, restore procedures, and 2FA recovery.

## 1. Stack architecture and security

Sponsy Bot runs in Docker Compose with three services:
1. `caddy`: The only internet-facing service. Handles automatic TLS certificates, passes security headers, and reverse proxies to the API. Listens on ports 80 and 443.
2. `api`: FastAPI application running as a non-root user (`appuser`, UID 1000). Communicates only on the internal Docker network. Memory is capped at 512M.
3. `postgres`: PostgreSQL 17 database running on Alpine. Listens only on the internal network with no exposed host ports. Memory is capped at 256M.

All state-changing requests require a valid CSRF token and Origin matching `PUBLIC_URL`. Request Host headers are verified against `PUBLIC_URL` host in production. Per-IP rate limits protect `/api/login`, `/api/login/code`, and the general API.

## 2. Initial server setup

1. Install Docker Engine and the Docker Compose plugin.
2. Install `age` (file encryption tool):
   - Debian / Ubuntu: `apt-get install -y age`
   - Alpine: `apk add age`
3. Generate an age key pair on a secure offline machine (never generate or store the private key on the server):
   ```bash
   age-keygen -o key.txt
   ```
   Note the public recipient string (starts with `age1...`).
4. Clone the repository and configure `.env`:
   ```bash
   chmod 600 .env
   ```
   Ensure `APP_ENV=prod`, `PUBLIC_URL=https://sponsy.yourclub.org`, `DOMAIN=sponsy.yourclub.org`, and `BACKUP_AGE_RECIPIENT=age1...` are set.
5. Build and launch services:
   ```bash
   docker compose -f compose.prod.yaml up -d
   ```
6. Run migrations and bootstrap initial admin:
   ```bash
   docker compose -f compose.prod.yaml exec -T api alembic upgrade head
   docker compose -f compose.prod.yaml exec -T api python scripts/create_admin.py --email admin@club.org --name "Admin Name" --password "ChangeMeNow1234!"
   ```

## 3. Backups

Nightly backups are managed by `deploy/backup.sh`. The script:
1. Dumps the database via `pg_dump`.
2. Compresses the dump with `gzip`.
3. Encrypts the stream with `age` using `BACKUP_AGE_RECIPIENT`.
4. Writes to `backups/sponsy_backup_<TIMESTAMP>.sql.gz.age` with permissions `600`.
5. Retains the 7 most recent backups and deletes older files.

Add this entry to root's crontab (`crontab -e`):
```text
0 2 * * * /opt/sponsy-bot/deploy/backup.sh >> /var/log/sponsy_backup.log 2>&1
```

Once a week, an administrator should securely copy one backup file off-site.

## 4. Disaster recovery and restore

To restore from a backup:
1. Ensure the PostgreSQL service is running:
   ```bash
   docker compose -f compose.prod.yaml up -d postgres
   ```
2. Copy the offline age private key file (e.g. `key.txt`) temporarily to the restore machine, or stream via SSH.
3. Run the restore script:
   ```bash
   ./deploy/restore.sh backups/sponsy_backup_YYYYMMDD_HHMMSSZ.sql.gz.age /path/to/key.txt
   ```
4. Verify the database contents and remove the key file from the server immediately after restore.

## 5. Two-factor authentication (2FA) and recovery

In production (`APP_ENV=prod`), two-factor authentication is required for every user account.
- When an account sets up 2FA, 10 single-use recovery codes are generated. Users must save these codes in a password manager.
- If a user loses their authenticator device, they can sign in using one of their unused recovery codes in the 2FA prompt.
- If all recovery codes are lost, an administrator can reset the user's 2FA:
  - Through the Admin panel under Users: click "Reset 2FA".
  - Or via API: `POST /api/admin/users/{user_id}/reset-2fa`.
  The user can then log in and set up a new authenticator app.

## 6. Updating the application

To deploy code updates with migrations:
```bash
./deploy/update.sh
```
The update script pulls base images, rebuilds the container, applies Alembic migrations, restarts containers, and polls `/api/healthz` to confirm health.
