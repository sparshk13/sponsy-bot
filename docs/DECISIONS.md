# Decisions log (the agent appends here)

When the agent must make a choice the docs do not cover, or the student approves a deviation from a doc, it records it here instead of editing the original docs. Format, newest at the bottom:

```
## D-001 short title
Date:
Context: what forced a decision
Decision: what was chosen
Why: the reason in one or two sentences
Affects: rule or doc IDs
```

## D-001 PostgreSQL and a React front end instead of SQLite and server-rendered pages
Date: 2026-10-17
Context: the student wanted a stronger database and a better-looking, more interactive front end than plain HTML and CSS with htmx.
Decision: PostgreSQL (SQLAlchemy 2.0, psycopg 3, Alembic, langgraph-checkpoint-postgres) and a React, TypeScript, Vite single-page app with hand-written CSS Modules over the design tokens. FastAPI becomes a JSON API. Docker Compose runs postgres, api, and caddy. Self-hosted Postgres is the default; Neon and Supabase free tiers were checked and judged risky for an always-on scheduler.
Why: row locks and partial unique indexes make duplicate prevention and the send queue safe under concurrency; React gives fast tables, slide-over review, and inline states. Next.js, Tailwind, shadcn, and icon packs were rejected for complexity and the generic look.
Affects: ARCHITECTURE, ROUTES, DESIGN, BUILD_PLAN, ACCEPTANCE, CODE-01, CODE-09, CODE-11, CODE-13, CODE-14, HUM-04, HUM-10, HUM-20, SEC-08, SEC-13, SEC-15, SEC-31, SEC-34 to SEC-38.

## D-002 Online deployment on one free cloud VM
Date: 2026-10-17
Context: the student wants the app online, not local only.
Decision: run the same Docker Compose stack on one always-free cloud VM (Oracle Always Free first, Google Cloud e2-micro as fallback), with Caddy for HTTPS. Add a deployment phase (Phase 10) with TOTP two-factor, Host and Origin checks, per-IP limits, encrypted off-server backups, and an admin System tab. Handover becomes Phase 11 and the Sheets stretch becomes Phase 12.
Why: Render's free tier sleeps and blocks SMTP ports; Fly.io and Koyeb have no free compute; hosted free Postgres suits an always-on scheduler poorly. A VM keeps one setup, free, with full control, at the cost of server upkeep and the provider's reclaim risk.
Affects: DEPLOYMENT, ARCHITECTURE, ROUTES, BUILD_PLAN, ACCEPTANCE, PRD section 12, SEC-08, SEC-31, SEC-34, SEC-39 to SEC-41, BUD-12.

## D-003 Refined generic copy check for unlock route
Date: 2026-10-18
Context: docs/ROUTES.md specifies route POST /api/targets/{id}/unlock for lifting 90-day cooldowns. The generic copy pattern in scripts/ai_tells_scan.py checked raw 'unlock', which triggered false positives on route paths, model fields, and generated TypeScript schemas.
Decision: Refine scripts/ai_tells_scan.py HUM-12 check to target marketing phrases ('unlock your', 'unlock the', etc.) while preserving the documented POST /api/targets/{id}/unlock route.
Why: Preserves strict route conformance with docs/ROUTES.md while catching generic marketing copy per HUM-12.
Affects: scripts/ai_tells_scan.py, ROUTES, HUM-12.
