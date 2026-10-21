# Architecture

## 1. Decisions and why
| Area | Choice | Reason |
|------|--------|--------|
| Back end | Python 3.12, FastAPI JSON API, pydantic validation | LangGraph, Gemini and Tavily SDKs are Python; FastAPI publishes an OpenAPI schema that generates the front end's types |
| Front end | React with TypeScript, Vite, React Router, TanStack Query | Fast filtering and sorting of a large tracker, slide-over draft review, inline editing, instant state changes. Hand-written CSS Modules over the design tokens, no component kit, so the look stays ours (HUM-04) |
| Not Next.js | Plain Vite single-page app served from the same origin | Next needs its own Node server and server rendering we do not need. One origin means no CORS and a simple CSP |
| Database | PostgreSQL 17 or current stable (verify) through SQLAlchemy 2.0 and psycopg 3, migrations with Alembic | Real concurrent writes, row locks (`FOR UPDATE SKIP LOCKED`) for claims and the send queue, partial unique indexes, `timestamptz`, JSONB, safe migrations |
| Workflow | LangGraph with `langgraph-checkpoint-postgres` | Required stack; the checkpointer pauses a graph at the approval step and resumes after the human acts |
| LLM | Google Gemini via `google-genai`, free tier | Free API; structured JSON output |
| Research | Tavily search | Free credits; returns text we can quote-check |
| Contacts | Manual and CSV first; Hunter domain search optional | Free credits are tiny |
| Mail | SMTP send and IMAP read with an app password, stdlib only | No OAuth token expiry; no extra dependency |
| Scheduler | APScheduler inside the API process, one instance guarded by a Postgres advisory lock | Reads due work from the DB, so downtime only delays, never loses |
| Passwords | argon2-cffi | Current best practice |
| Charts | Small hand-written SVG components | No chart library, matches the design |
| Running it | Docker Compose with three services: `postgres`, `api` (also serves the built front end), `caddy` (HTTPS). Locally for development, then on one free always-on cloud VM (`docs/DEPLOYMENT.md`) | Same setup everywhere, free, automatic HTTPS |

Verify every package name and version on pypi.org or npmjs.com before use (SEC-32, SEC-36).
Python direct dependencies (max 15): fastapi, uvicorn, python-multipart, sqlalchemy, psycopg, alembic, pydantic-settings, langgraph, langgraph-checkpoint-postgres, google-genai, tavily-python, httpx, argon2-cffi, apscheduler, pyotp (two-factor, added in Phase 10; that makes 15). Python dev tools (not counted): pytest, ruff, bandit, pip-audit.
Front-end runtime dependencies (max 6): react, react-dom, react-router, @tanstack/react-query. Front-end dev tools (not counted): typescript, vite, @vitejs/plugin-react, eslint with typescript-eslint, vitest, @testing-library/react, jsdom, openapi-typescript.

## 2. Folder layout (flat, do not add layers)
```
backend/
  app/
    main.py        app creation, middleware, router wiring, serves the built front end
    config.py      env settings
    db.py          engine and session
    models.py      all tables
    auth.py        login, sessions, csrf, throttle
    security.py    headers middleware
    budget.py      counted wrapper for every external call
    llm.py         Gemini client, prompts and response schemas (docs/PROMPTS.md)
    research.py    Tavily search, fact extraction, verification
    drafting.py    recommendation, email draft, draft validator
    classify.py    reply classification, summary, suggested reply
    contacts.py    manual, csv, hunter
    guard.py       guard.check for sending
    mailer.py      send (SMTP) and fetch replies (IMAP)
    followups.py   due follow-ups, closing rules
    scheduler.py   jobs only; logic lives in the modules above
    graphs.py      LangGraph definitions (two graphs, section 5)
    routes/        one file per area, exactly the routes in docs/ROUTES.md
  alembic/         migrations
  tests/
frontend/
  src/
    api/           generated types and one small fetch wrapper
    pages/         one folder per page in docs/ROUTES.md (front-end routes)
    components/    shared pieces: Shell, DataTable, StatusMark, EvidenceFlag, SlideOver, Notice
    styles/        tokens.css, base.css
  public/fonts/    self-hosted woff2 with licences
scripts/           create_admin.py, seed_dev.py, ai_tells_scan.py
compose.yaml  Caddyfile  .env.example
```

## 3. Data model (SQLAlchemy; all times UTC)
- `users`: id, email unique, name, password_hash, role (admin|organizer), is_active, created_at
- `sessions`: token_hash pk, user_id, csrf_token, created_at, last_seen_at
- `login_attempts`: email, ip, at (used for throttle)
- `campaigns`: id, name, event_summary, event_date, audience_note, cash_target_inr, goodies_note, credits_note, calendar_link, created_by
- `companies`: id, name, domain unique (normalized: lowercase, no scheme, no `www.`), category, website, first_added_at
- `contacts`: id, company_id, name, role, email unique, source (manual|csv|hunter), is_valid
- `company_facts`: id, company_id, kind (profile|past_sponsorship|other), claim, source_url, evidence_quote, status (verified|unverified), retrieved_at
- `targets`: id, campaign_id, company_id, unique(campaign_id, company_id), owner_id nullable, status, tier (cash|goodies|credits|null), priority (A|B|C|null), priority_score, ask_summary, ask_reasoning, ask_fact_ids (json), ask_basis (evidence|assumption), followup_count, next_followup_at, last_contacted_at, researched_at
- `messages`: id, target_id, contact_id, direction (out|in), kind (first|followup|reply|meeting), subject, body, status (draft|approved|sent|failed|discarded|received), facts_used (json), created_by, approved_by, approved_at, approved_hash, sent_at, message_id_header, in_reply_to, attachment_id nullable, classification nullable (interested|declined|question|auto_reply|bounce|other), summary, suggested_reply, classified_by_human bool
- `suppression`: id, kind (email|domain), value unique, reason, created_at
- `outcomes`: id, target_id, kind (cash|goodies|credits), amount_inr nullable, description, confirmed_by, confirmed_at
- `templates`: id, kind (first|followup|meeting), name, body (phase 8)
- `brochures`: id, tier, filename, stored_name, uploaded_by (phase 8)
- `api_usage`: day, provider, units, unique(day, provider)
- `settings_state`: key, value (holds `paused`)
- `audit_log`: id, at, user_id nullable, action, entity, entity_id, detail

PostgreSQL specifics:
- Use `timestamptz`, `jsonb` for the json columns, and `text` with `CHECK` constraints for status-like columns (easier to migrate than native enums).
- Emails are stored lowercase with a unique index on `lower(email)`.
- One message in flight per target is a partial unique index: `CREATE UNIQUE INDEX one_inflight_per_target ON messages (target_id) WHERE direction = 'out' AND status IN ('draft','approved')`.
- Add indexes only for real queries: `targets (campaign_id, status)`, `targets (owner_id)`, `messages (target_id)`, `messages (status, approved_at)`, `company_facts (company_id)`.
- The LangGraph checkpointer creates and manages its own tables; run its setup once at deploy time, not by hand-written SQL.
- The app role has table rights only (SEC-37). Alembic runs with a separate admin role.

## 4. Ownership and duplicate prevention (R9)
1. `companies.domain` is unique; import normalizes and rejects duplicates. A fuzzy name check (stdlib `difflib`) warns on near matches such as the same company under two domains.
2. A target is claimed with one atomic statement: `UPDATE targets SET owner_id=:u WHERE id=:t AND owner_id IS NULL RETURNING id`. If no row comes back, someone else owns it and the UI says who. Tests prove this with two concurrent transactions on real PostgreSQL.
3. Only the owner can draft, edit, or approve for that target. Admin can reassign (audited).
4. At most one message in `draft` or `approved` per target (partial unique index or checked in the same transaction).
5. Cross-campaign cooldown: if any message to this company was sent in the last 90 days, drafting is blocked until an admin unlocks it.

## 5. LangGraph design
Use LangGraph's current documented interrupt and resume API. Read the official docs for the installed version before coding (PROC-03). Persist graph state with the SQLite checkpointer; use one thread id per target.

**Graph A: prepare_target** (triggered by a human pressing "Prepare" on an owned target)
`load` then `research` then `extract_facts` then `recommend` then `find_contact` then `draft` then `validate_draft` then `await_approval` (interrupt) then `end`.
- `research`: up to 2 Tavily searches, cached 30 days (BUD-04, BUD-05).
- `extract_facts`: model returns claims, each with `source_url` and a verbatim `evidence_quote`. Code marks a fact `verified` only if the URL is one that was returned and the quote appears in that result's text after whitespace normalisation. Everything else is `unverified`.
- `recommend`: priority score and tier. Score is deterministic code: verified past sponsorship of tech or student events +3, category fit +2, verified company size or funding signal +1, a contact on file +1. Tier and ask text come from the model but may cite only verified fact ids; with none, `ask_basis=assumption` and confidence is shown low. Store reasoning on the target.
- `find_contact`: skip if a contact exists; otherwise leave a "needs contact" state (human adds one, or presses Find contact in phase 8). The graph pauses here if there is no contact.
- `draft`: model returns subject, body, `facts_used`. Inputs: campaign details, verified facts, the sender's name, the tier, and the matching brochure if any.
- `validate_draft` (pure code, `drafting.validate`): every id in `facts_used` is verified and belongs to this company; every number, year, or rupee amount in the body is in the campaign details or a used fact; no `[` `]` placeholders; sender identity and opt-out line present; plain text; length bounds; similarity to other drafts in the campaign below 0.8 after masking the company name (stdlib `difflib`). On failure, one regeneration, then flag for human.
- `await_approval`: interrupt. The graph resumes only from the approve route, never from a model output.

**Graph B: handle_event** (invoked per event, short-lived; long waits live in the DB, not in a sleeping graph)
`router` branches on the event:
- `sent`: set `contacted` or `follow_up`, set `next_followup_at`, or close if the limit is reached.
- `reply_received`: `classify` (one call: class, summary, suggested reply, after stripping addresses and phones) then branch:
  - `interested`: status `interested`; draft a meeting reply with the calendar link; queue for approval.
  - `declined`: status `declined`; suppress contact and domain.
  - `question` or `other`: flag for a human with the suggested reply.
  - `auto_reply` or `bounce`: do not count as a reply; bounce marks the contact invalid.
- `followup_due`: if count is below the limit, draft the follow-up (it uses new angle text, never a copy) and queue; else `closed_no_reply`.

## 6. Send path and pacing
1. Organizer clicks Approve. Server stores `approved_by`, `approved_at`, `approved_hash = sha256(to + subject + body)`.
2. A send job runs every minute. It takes the oldest approved message with `SELECT ... FOR UPDATE SKIP LOCKED` so two workers can never send the same one, calls `guard.check(message)` (SEC-19), waits for the jitter gap since the last send, sends with SMTP, stores `Message-ID`, sets `sent`, and invokes Graph B `sent`.
3. Editing an approved message sets it back to `draft` and logs `edit-after-approve`.
4. Failure: mark `failed` with a plain reason, keep it visible, never auto-retry more than twice.
5. The send window and daily cap come from settings (BUD-08). The queue page shows today's sent versus the cap.

## 7. Reply tracking
- Poll IMAP every 5 minutes. Match a reply to a sent message through `In-Reply-To` and `References`; fall back to the sender address matching a contact of a contacted target.
- Ignore messages with `Auto-Submitted` or `X-Autoreply` headers for status (record as `auto_reply`). Detect delivery failure notices and mark `bounce`.
- Fetch unseen only, mark processed by storing the IMAP UID; no deleting of mail.
- A new reply creates an in-app notification count on Today and in the nav.

## 8. Scheduler jobs (APScheduler; each job is a short function calling a module)
send queue (1 min), reply poll (5 min), due follow-ups (15 min), nightly backup, daily budget reset check. On start, run each once to catch up. Only one process runs the jobs: take `pg_try_advisory_lock` at start and skip the jobs if it is held.

## 9. External services (verify live before coding; numbers drift)
| Service | Free allowance seen in research | Use |
|---------|--------------------------------|-----|
| Gemini API | Free for Flash-class models; published limits vary by source (about 15 RPM and hundreds to 1,500 requests a day reported); billing must stay off | Facts, recommendation, drafts, classification |
| Tavily | 1,000 credits a month; basic search about 1 credit, advanced 2 | Research |
| Hunter | About 50 credits a month; API availability on free plan unclear | Optional contact discovery |
| PostgreSQL | Runs in Docker on the same free cloud VM as the app, so it has no database quota. Hosted free Postgres does not suit an always-on scheduler: Neon Free suspends after 5 idle minutes and gives about 100 compute-hours a month, Supabase Free pauses after a week idle | Main database |
| Cloud VM | Oracle Cloud Always Free VM (primary) or Google Cloud e2-micro (fallback); Render, Fly.io and Koyeb free tiers do not work for this app (see `docs/DEPLOYMENT.md` section 2) | Hosts everything |
| Gmail SMTP/IMAP | Personal Gmail allows far more than 40 a day | Mail |
Planned monthly load for a 60-company drive: about 120 Tavily searches, about 300 Gemini calls in total. Confirm the caps in `.env`.

## 10. Config (all in `.env.example`)
Settings are listed in `.env.example`. Add a setting only when code reads it.

## 11. Public routes and deployment
Public API routes: `/api/login`, `/api/login/code`, `/api/healthz`. Every other `/api` route requires a session (SEC-08). Static front-end files are public and carry no data.
Development runs `compose.yaml` on the student's computer (Vite dev server proxies `/api`). Production runs `compose.yaml` plus `compose.prod.yaml` on one free cloud VM behind Caddy, built in Phase 10 and operated by the student following `docs/DEPLOYMENT.md`. In production only Caddy publishes ports (80 and 443), PostgreSQL stays on the internal network, and the API trusts forwarded headers only from Caddy.

