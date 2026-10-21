# Routes

Two kinds: JSON API routes under `/api` (the back end) and screens (the React front end). The agent must not add either kind without asking (PROC-16). Every `/api` route except the three public ones needs a session (SEC-08). Auth key: P = public, U = any logged-in user, O = owner of the target (or admin), A = admin. CSRF header is required on every non-GET (SEC-10). Role and ownership are checked on the server every time (SEC-09). Inputs and outputs are pydantic models; the front end uses types generated from the OpenAPI schema.

## API
| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | /api/healthz | P | liveness |
| POST | /api/login | P | sign in (throttled) |
| POST | /api/logout | U | sign out |
| GET | /api/session | U | current user and CSRF token |
| POST | /api/account/password | U | change own password |
| POST | /api/account/2fa/setup | U | start two-factor, returns the secret once |
| POST | /api/account/2fa/confirm | U | confirm with a code, returns recovery codes once |
| POST | /api/login/code | P | second login step with a TOTP or recovery code (needs the pending login from /api/login) |
| GET | /api/today | U | counts and short lists for the Today screen |
| GET | /api/targets | U | tracker rows with filters and sorting |
| POST | /api/targets/import | U | CSV import, returns a report of skipped rows |
| POST | /api/targets | U | add one company and target |
| GET | /api/targets/{id} | U | detail: facts, recommendation, draft, thread |
| POST | /api/targets/{id}/claim | U | atomic ownership claim |
| POST | /api/targets/{id}/prepare | O | run Graph A (research, recommend, draft) |
| POST | /api/targets/{id}/refresh-research | O | re-run research, spends credits |
| PUT | /api/targets/{id}/contact | O | add or edit contact |
| POST | /api/targets/{id}/find-contact | O | Hunter lookup on click, budget checked |
| POST | /api/targets/{id}/status | O | organizer sets meeting_booked or secured |
| POST | /api/targets/{id}/outcome | O | record what was secured |
| POST | /api/targets/{id}/reassign | A | change owner (audited) |
| POST | /api/targets/{id}/unlock | A | lift the 90-day cooldown |
| GET | /api/queue | U | drafts waiting (own, or all for admin) |
| PUT | /api/messages/{id} | O | save an edit; voids any approval |
| POST | /api/messages/{id}/approve | O | the only route that approves (SEC-20) |
| POST | /api/messages/{id}/discard | O | discard a draft |
| GET | /api/inbox | U | replies with class, summary, suggestion |
| PUT | /api/messages/{id}/class | O | human override of classification |
| POST | /api/messages/{id}/suggested-reply | O | turn the suggested reply into a draft in the queue |
| GET | /api/dashboard | U | pipeline, rates, secured |
| GET | /api/memory | U | past sponsors and outcomes |
| GET | /api/usage | U | free-tier budgets |
| GET | /api/export/tracker.csv | A | tracker export (audited) |
| GET, POST, PUT | /api/admin/users | A | list, create, deactivate, reset password |
| GET, POST, PUT | /api/admin/campaigns | A | list, create, edit |
| GET, POST, DELETE | /api/admin/suppression | A | list, add, remove |
| GET | /api/admin/audit | A | audit log, read only |
| GET | /api/admin/system | A | last mail check, last send, last backup, database size, free disk |
| POST | /api/admin/revoke-sessions | A | sign everyone out (audited) |
| POST | /api/admin/users/{id}/reset-2fa | A | reset a user's two-factor (audited) |
| POST | /api/admin/contacts/{id}/erase | A | erase contact data (SEC-28) |
| PUT | /api/admin/pause | A | pause or resume all sending |
| GET, POST, PUT, DELETE | /api/admin/templates | A | template CRUD (phase 8) |
| POST | /api/admin/brochures | A | upload per tier (phase 8) |
| GET | /api/brochures/{id} | U | authenticated download (SEC-17) |

## Screens (front-end routes)
`/login`, `/` (Today), `/targets`, `/targets/:id`, `/queue`, `/inbox`, `/dashboard`, `/memory`, `/usage`, `/admin` (tabs: users, campaigns, suppression, audit). Unknown paths show a plain "Page not found" in the same shell. A logged-out visit to any screen except `/login` goes to `/login`.

The scheduler and the graphs call module functions directly; they never call HTTP routes.
