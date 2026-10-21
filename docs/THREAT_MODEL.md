# Threat model

Short on purpose. It tells the agent and the reviewer what is being defended and which rules do it.

**Assets:** the club's mailbox and reputation; API keys; sponsor contact data and replies; the tracker; the integrity of the approval step.

**Actors:** an outsider on the internet; a curious or careless club member; a malicious sponsor or web page whose text reaches the model; a compromised dependency; the AI coding agent itself making a mistake.

| Threat | Result if it happens | Defence (rule IDs) |
|--------|----------------------|--------------------|
| An email goes out without approval | Reputation damage, spam complaints | One send path, guard checks, approval bound to a hash, no route or model can approve (SEC-19, SEC-20) |
| Approved text changed after approval | Unreviewed content sent | Hash mismatch voids approval (SEC-19b) |
| Same company contacted twice | Looks careless, hurts the club | Unique domain, atomic claim, one in-flight message, cooldown (PRD R9) |
| Declined contact emailed again | Trust and compliance problem | Suppression at contact and domain level, checked in the guard (SEC-22) |
| Prompt injection in a web page or reply | Model tries to change status or write harmful text | Delimited data, no tools, schema output, humans approve (SEC-24 to SEC-26) |
| Fabricated company facts in an email | Embarrassment, lost sponsor | Quote verification, validator, unverified flag (PRD section 7) |
| Stolen session or CSRF | Attacker approves or exports | Server sessions, HttpOnly cookies, CSRF, CSP (SEC-07, SEC-10, SEC-15) |
| Account takeover by guessing | Same | Argon2, throttle, long passwords (SEC-05, SEC-06) |
| One user reading or changing another's work | Duplicate outreach or data leak | Ownership checks on every mutation (SEC-09) |
| Secrets leak through git or logs | Mailbox or API abuse | `.env` ignored, no secrets in code or logs (SEC-01, SEC-29) |
| Malicious or invented package | Supply chain compromise | Verify on pypi.org, pin, audit (SEC-32, CODE-09) |
| Malicious file upload | Code execution or malware spread | PDF magic bytes, size cap, outside static, attachment only (SEC-17) |
| Free quota exhausted or exceeded | Service stops or charges appear | Counted wrapper, caps, billing off (BUD rules) |
| Agent edits its own rules or runs destructive commands | Silent weakening of controls | Rules read-only, terminal safety, human review (PROC-04, PROC-06) |
| Sponsor or web text rendered in the browser runs script | Session theft, forced actions | React escaping, no `dangerouslySetInnerHTML`, strict CSP, no tokens in JS (SEC-13, SEC-15, SEC-35) |
| Malicious npm package | Supply chain compromise, token theft | Verify on npmjs.com, exact pins, `ignore-scripts`, `npm audit` (SEC-36) |
| Database exposed or app over-privileged | Data theft or deletion | Internal network only, least-privilege role, TLS for hosted DBs (SEC-37) |
| Two workers send or claim the same item | Double outreach | Row locks, `SKIP LOCKED`, partial unique index, single scheduler lock (SEC-37, PRD R9) |

| Password guessing or scanning from the open internet | Account takeover, unauthorised sends | Throttle, per-IP limits, TOTP two-factor, Host and Origin checks (SEC-05, SEC-06, SEC-39, SEC-40) |
| Server reached through SSH or a stale package | Full access to keys and data | SSH keys only, firewalls, automatic updates, non-root containers, secrets file mode 600 (SEC-41, `docs/DEPLOYMENT.md`) |
| Free VM reclaimed or lost | History and data gone | Encrypted off-server backups, tested restore, rebuild runbook (SEC-31) |
| Accidental paid resources | Surprise bill | Always-free resources only, billing alert (BUD-12) |

**Out of scope for this project:** a nation-state attacker, physical access to the host, a compromised Google or Tavily account. Say so in the README rather than pretending otherwise.
