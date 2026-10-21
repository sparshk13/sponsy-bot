# Acceptance

An item is done only when a real test (or the stated manual check) proves it. The agent maps each item to a test name in the Phase Report.

## A. Requirements
| ID | Item | Proof |
|----|------|-------|
| R1 | Tracker lists every company with tier, status, owner and the full email history | tests for list and detail; manual |
| R2 | Research stores facts with sources; priority score explained | tests with a fake search client |
| R3 | Ask is cash, goodies or credits, with reasoning that cites facts; no facts means Assumption label | tests |
| R4 | Two different companies produce different drafts; each uses at least one verified fact | tests (similarity bound) |
| R5 | Unapproved message cannot send; edit after approval voids approval; only the approve route sets approved | tests plus a grep test |
| R6 | Sent mail is matched to replies; classes interested, declined, no reply (by absence), plus auto-reply, bounce, question | tests with sample IMAP messages |
| R7 | Max 2 follow-ups then closed_no_reply; a reply cancels the schedule; catch-up is idempotent | tests with a controllable clock |
| R8 | Interested reply produces a meeting draft with the calendar link; status moves on organizer confirmation | tests |
| R9 | Duplicate company rejected; simultaneous claims give one owner; other users blocked; 90-day cooldown | tests with concurrent transactions on real PostgreSQL |
| R10 | No paid path exists; every external call goes through the counted wrapper; cache prevents repeat searches | tests plus code search |
| R11 | 40 approved messages in a day send in window, spaced, under cap; cap setting above 40 is refused | tests with fake transport and clock |
| R12 | Unverified facts are flagged and never used in drafts or reasoning; invented numbers and years are rejected | tests |

## B. Good to have
G1 contact discovery only on click and within credits; G2 one approval triggers send plus next-step scheduling; G3 dashboard numbers equal the database; G4 calendar link in meeting replies; G5 brochure matches tier and passes upload checks; G6 templates used as a base; G8 reply summary and suggested response stored; G9 reply count appears in nav; G10 memory lists past sponsors with outcomes.

## C. Security (every item needs a test or a stated manual check)
1. Every route except `/login` and `/healthz` redirects to login when logged out.
2. POST without a valid CSRF token is rejected on every mutation route.
3. Five bad logins lock the account and IP pair; the lock survives a restart.
4. An organizer cannot read or change another organizer's target, a user record, or admin pages (IDOR and role tests).
5. Stored text containing `<script>` or HTML renders as plain text in every component that shows outside text, and `dangerouslySetInnerHTML` appears nowhere in `frontend/src` (grep test).
6. API responses carry the CSP and the other headers; the built `index.html` has no inline script, style, or event attribute; the browser console shows no CSP violations.
7. A CR or LF in recipient or subject is rejected.
8. Every guard check in SEC-19 has a refusal test.
9. A reply containing prompt-injection text cannot change status, approve, or send.
10. Off-schema model output is discarded and flagged; it never reaches the database as a fact.
11. Logs from a full test run contain no email body, token, password, or full address.
12. `pip-audit` and `bandit` are clean or each finding is explained in writing.
13. `.env`, database, backups and uploads are not tracked by git.
14. Brochure upload rejects a renamed non-PDF, an oversized file, and a path-like filename.
15. No token or secret is in `localStorage`, `sessionStorage`, or a `VITE_*` variable.
16. `/docs`, `/redoc`, `/openapi.json` return 404 when `APP_ENV` is not `dev`.
17. The Postgres port is not reachable from outside the compose network, and the app role cannot create or drop tables.
18. `npm audit` is clean or each finding is explained, and `package-lock.json` is committed with exact versions.

## D. Quality gates
- `ruff check` and `ruff format --check` clean; `pytest` green; `python scripts/ai_tells_scan.py` reports 0 findings.
- Python direct dependencies at most 15 and front-end runtime dependencies at most 6, each listed in `docs/DEPENDENCIES.md`.
- No TODO, commented-out code, unused function, or comment that restates code.
- Every page checked at 1280px and 360px; keyboard-only run of the approve flow succeeds.
- Contrast checked for every token pair.

## E. Test seams and fixtures
- Fake only at four seams: `llm` (Gemini client), `search` (Tavily client), `Mailer` transport (SMTP and IMAP), and the clock. Everything else runs for real against a disposable PostgreSQL database that tests create and drop.
- Fixtures live in `tests/fixtures/` (see `docs/PROMPTS.md`). They are plainly fake and used only in tests.
- A grep test fails the build if any string that sets a message to `approved` exists outside the approve route's code path.
- Live provider calls never run in the test suite.

## F. Document checks
- Every route in `docs/ROUTES.md` exists, with the stated auth, and no unlisted route exists (a test reads the app's route table).
- Prompts and schemas in `app/llm.py` match `docs/PROMPTS.md`.
- Emails in tests pass the voice checks that code can check: length bounds, no banned phrases, no em dash, opt-out line present.

## G. Front-end gates
- `npm run typecheck`, `npm run lint`, and `npm run test` pass; `npm run gen:api` reproduces the committed generated types exactly.
- Component tests cover: the Approve button only appears for the owner, an edited draft shows "approval no longer applies", unverified facts show the amber flag and are never listed as reasons, a target owned by someone else shows their name and a disabled action.
- Every route in `docs/ROUTES.md` exists with the stated auth, and no unlisted route exists (a test reads the OpenAPI route table).

## H. Online operation (Phase 10 and 11)
1. In prod mode a wrong `Host` or a wrong `Origin` on a state-changing request is rejected.
2. Right password with no or a wrong second-step code creates no session; a recovery code works once; wrong codes count toward the lockout.
3. Per-IP limits return 429 after the limit; the client IP comes from forwarded headers only when the request comes from Caddy.
4. Prod configuration: Secure cookie, HSTS, `/docs` 404, containers non-root, only Caddy publishes ports (a test reads the compose files).
5. A backup is encrypted, a restore into an empty database reproduces the data, and the private key is not stored with the backups.
6. `GET /api/admin/system` shows last mail check, last send, last backup, database size, and free disk; Today shows a notice when the scheduler has been silent for 30 minutes.
7. After a container or VM restart the scheduler catches up and no message is sent twice.
8. The student signs off the live checklist in `docs/DEPLOYMENT.md` (HTTPS from a phone on mobile data, 2FA enrolled, a test email sent, reboot recovery).
