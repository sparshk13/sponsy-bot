# Deployment: going online

For the student first, the agent second. The agent writes the files in section 6 during Phase 10. The student does every step that touches a cloud account or a server. The agent never runs commands on a server and never touches Git (PROC-17).

## 1. What "online" means here
One small Linux VM on a free cloud tier runs the same three Docker services used in development: `postgres`, `api` (which also serves the built front end), and `caddy` (HTTPS). Organizers open an https address from anywhere. The VM must stay on, because the scheduler checks the mailbox, creates follow-up drafts, and paces sending.

## 2. Host options (checked October 2026; free tiers change, verify before relying)
| Option | What is free | Catch | Verdict |
|--------|--------------|-------|---------|
| Oracle Cloud Always Free VM | Always-free VMs with no expiry: Arm Ampere A1 (reported cut to 2 OCPUs and 12 GB in June 2026) and small AMD micro VMs (1 GB RAM), block storage | A card is needed for verification. No SLA. Idle instances can be reclaimed (reports mention about 7 days of very low use). Capacity in a region can run out. The home region cannot be changed after signup | Primary choice |
| Google Cloud e2-micro | One always-free e2-micro (1 GB RAM, 30 GB disk) in us-west1, us-central1 or us-east1, and 1 GB outbound traffic a month | Billing account required. 1 GB RAM is tight for Postgres plus the API, so use swap and low memory settings. US regions only | Fallback |
| Render free | 512 MB web service | Sleeps after 15 idle minutes, blocks outbound ports 25, 465 and 587 (so no SMTP), free Postgres expires after 30 days | Not suitable |
| Fly.io | No free allowance for new accounts | Paid | Not suitable |
| Koyeb | No free compute | Paid | Not suitable |
| PythonAnywhere free | Small web app | Restricted outbound access | Not suitable |
| Club computer plus a tunnel | Free | Needs a stable hostname (usually a domain), a machine that never sleeps, a network that allows it; not researched | Only if no card is possible; verify first |

## 3. Name and HTTPS
Caddy gets certificates automatically but needs a hostname that points at the VM's public IP, with ports 80 and 443 open. Use a subdomain from your college IT team, a club domain, or a free dynamic DNS name (verify the provider's current terms). Put the result in `PUBLIC_URL`.

## 4. Before the first deploy (student tasks)
1. Create the cloud account. Choose the region and, for Oracle, the home region with care. Create only resources marked Always Free. Set a budget alert (BUD-12).
2. Create an SSH key pair on your own computer (ed25519). Put only the public key on the VM.
3. Create a private repository. Add a read-only deploy key so the server can pull. You push by hand; the agent never does.
4. Choose the hostname and point its DNS at the VM's IP.
5. Generate a backup key pair with `age` on your own computer. Only the public key goes on the server (`BACKUP_AGE_RECIPIENT`). Keep the private key with two admins.

## 5. Server checklist (student runs; each item is a security control)
- Create a non-root user with sudo. Disable root login and password login for SSH (`PermitRootLogin no`, `PasswordAuthentication no`).
- Two firewalls on Oracle: the cloud network rules and the OS firewall. Both must allow 80 and 443; allow 22 only from your IP if you can. On other hosts use `ufw`: default deny incoming, allow 22, 80, 443.
- Turn on automatic security updates (`unattended-upgrades`).
- Install Docker Engine from Docker's official instructions, not from an unverified script.
- On 1 GB machines add a swap file and set the memory limits from `compose.prod.yaml`.
- Keep the secrets file at `/opt/sponsy/.env`, owner the deploy user, mode 600. Never in the repository.
- Confirm from another computer that only ports 80 and 443 answer. The Postgres port must not.
- Gmail may show a security alert for a first sign-in from a new server. Approve it in your Google account. Keep using an app password.

## 6. Files the agent builds in Phase 10
- `compose.prod.yaml`: `restart: unless-stopped`, health checks, non-root users, memory limits, no published ports except Caddy.
- Production `Caddyfile` for `PUBLIC_URL`.
- `deploy/update.sh`: back up, pull, build, run migrations with the admin role, restart, check `/api/healthz`. The student runs it on the server.
- `deploy/backup.sh`: `pg_dump`, compress, encrypt to `BACKUP_AGE_RECIPIENT`, keep 7. `deploy/restore.sh` and the restore steps.
- TOTP two-factor for every account, Host and Origin checks, per-IP rate limits, the Admin System tab, revoke-all-sessions (SEC-39 to SEC-41; routes in `docs/ROUTES.md`).
- A short ops README for humans: run, update, back up, restore, rotate keys, what to do in an incident.

## 7. Updating
Commit by hand on your computer, push to the private repository, connect to the server by SSH, run `./deploy/update.sh`. The script backs up before it migrates. If a migration fails, restore the backup and redeploy the previous version.

## 8. Backups (the free VM can vanish)
Nightly encrypted dump on the VM, 7 kept. Weekly, an admin copies the newest file off the server to their own computer or personal storage. Test a restore into an empty database before going live and again every term.

## 9. Monitoring
- A free external uptime monitor calls `/api/healthz` (it returns only "ok").
- The Admin System tab shows: last mail check, last send, last backup, database size, free disk. The Today page shows a notice if the scheduler has not run for 30 minutes.

## 10. If something goes wrong
Pause sending (Admin). Rotate the Gmail app password and API keys. Sign everyone out (Admin). Stop Caddy to take the site offline. Restore from the last good backup. Then read the audit log.

## 11. Staying free
Use only always-free resources and no paid add-ons. Check the cloud billing page monthly. Idle reclaim on Oracle is the main risk: if the provider offers an upgrade that keeps free resources free and exempts you from reclaim, read the current terms before using it. Either way, keep off-server backups and be ready to rebuild from this runbook in about an hour.

## 12. Verify yourself (these may be stale)
Oracle's current Always Free shapes and reclaim rule; Google's free-tier regions and billing requirement; that outbound port 587 and inbound 80 and 443 are open on your host; the DNS provider's terms; that `age` is available for your server's operating system.
