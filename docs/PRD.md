# Product requirements: Sponsy Bot

## 1. Purpose
Replace scattered spreadsheets, forgotten follow-ups, and generic mass emails with one system that helps a student club find, prioritise, contact, and follow up with sponsors. The system researches each company, decides what to ask for, drafts a personal email, and tracks every conversation. A human organizer approves each outgoing email with one click. Nothing is sent otherwise.

## 2. Users
- **Organizer**: reviews research, edits drafts, approves emails, reads replies, runs outreach for the targets they own.
- **Admin**: an organizer who also manages users, campaign settings, suppression list, brochures, the global pause switch, and reassigns ownership.
- Invite-only. About 3 to 10 people. No public signup.

## 3. Core concepts
- **Campaign**: one sponsorship drive (for example a 24-hour hackathon), with the event summary, cash target in rupees, goodies and credits wanted, a meeting calendar link, and optional brochures per tier.
- **Company**: one row per organization, global across campaigns, unique by normalized domain. Holds facts and contacts.
- **Target**: a company inside a campaign. Holds tier, priority, recommended ask, status, owner, follow-up count, and the message history.
- **Fact**: one claim about a company, with a source URL and a verified or unverified flag.
- **Message**: a draft, approved, sent, or received email.
- **Suppression**: an email or domain that must never be contacted again.

## 4. Mandatory requirements

| ID | Requirement | Notes |
|----|-------------|-------|
| R1 | Sponsor tracker: every company with category/tier, status, owner, and full email history | Statuses in section 5 |
| R2 | Research each company; use its profile and past sponsorship history to prioritise and categorise | Priority is a deterministic score, explained on screen |
| R3 | Recommend what to ask for (cash, goodies, or infrastructure credits) from the company's history, and show the reasoning | Reasoning cites fact ids; guesses are labelled "assumption" |
| R4 | Personalised, company-specific email per target; never one template sent to everyone | Draft must use verified facts, and drafts must differ from each other |
| R5 | Human in the loop: no email is sent without an organizer's approval; the organizer can edit before approving | Approval is bound to the exact text (SEC-19) |
| R6 | Send approved emails, track replies, classify each as interested, no reply, or declined | Also flags auto-replies, bounces, and questions for a human |
| R7 | Schedule follow-ups automatically within a fixed limit (default 2, then stop) | Follow-up drafts still need approval |
| R8 | Move interested sponsors to the next step: a virtual meeting | Reply draft carries the calendar link; status becomes meeting_booked when confirmed |
| R9 | Prevent duplicate outreach: two members never contact the same company | Unique company, ownership claim, one active thread per company |
| R10 | Only free APIs and free tiers, used smartly | Caching, counters, caps (BUD rules) |
| R11 | Handle 20 to 40 outgoing emails a day inside those limits | Daily cap 30 by default, hard maximum 40 |
| R12 | Never fabricate company details or past sponsorships; unverified information is flagged, not shown as fact | Verified means a source URL plus a quote found in the retrieved text |

## 5. Status model
`not_contacted` then `contacted` then `follow_up` (count 1 or 2) then one of:
- `interested` then `meeting_booked` then `secured` (outcome recorded)
- `declined` (closed; contact and domain suppressed)
- `closed_no_reply` (after the last follow-up and its wait period)

Rules: a reply moves the target out of `contacted`/`follow_up` immediately. Only one message may be in `draft` or `approved` state per target at a time. A closed target cannot be drafted again in the same campaign. A company contacted in an earlier campaign within 90 days shows a warning and needs an admin to unlock.

## 6. Follow-up policy
- Defaults: first follow-up 4 days after the first email, second 5 days after the first follow-up, maximum 2, then `closed_no_reply`. All three numbers are settings.
- The system creates the follow-up draft when it is due and puts it in the approval queue. It is sent only after approval.
- Any reply stops the schedule. A decline suppresses the contact.

## 7. Evidence and anti-fabrication (R12 in detail)
- Every fact has a `source_url` and an `evidence_quote` that must appear in the retrieved text. If not, the fact is saved as `unverified`.
- Unverified facts show an amber "Unverified" label everywhere, and are never used in emails or as reasoning for the ask.
- If nothing is found, the target says "No sponsorship history found in the sources searched" and the ask is labelled "Assumption, not evidence".
- The draft validator rejects any email that uses a fact id that is not verified, includes a number, year, or rupee amount that is not in the campaign details or a verified fact, or contains placeholder brackets.

## 8. Screens
Today (what needs me), Targets (tracker table), Target detail (facts, recommendation, draft editor, thread), Approval queue, Inbox (replies with classification, summary, suggested response), Dashboard, Campaigns, Memory (past sponsors across campaigns), Usage (API budgets), Admin (users, suppression, pause, audit log). Details in `docs/DESIGN.md`.

## 9. Good to have (built after the mandatory set)
| ID | Feature | Phase |
|----|---------|-------|
| G1 | Contact discovery (Hunter) for targets with no contact | 8 |
| G2 | One-click next step: one approval sends, schedules the follow-up, and for interested replies sends the meeting reply | 7 |
| G3 | Dashboard: pipeline stages, response rate, money and benefits secured | 9 |
| G4 | Meeting booking via calendar link | 7 |
| G5 | Brochure per tier attached to the first email | 8 |
| G6 | Reusable first-contact and follow-up templates | 8 |
| G7 | Google Sheets sync (one-way export) | 12, stretch |
| G8 | Reply summary and suggested response | 6 |
| G9 | Notification when a sponsor replies (in-app) | 6 |
| G10 | Institutional memory: past sponsors and outcomes for future teams | 9 |

## 10. Out of scope
Bulk approve, auto-send, HTML or tracked emails, open or click tracking, social media outreach, payments, public pages, multi-club tenancy, mobile app.

## 11. Success looks like
A club can import 60 companies, get researched and drafted targets within a day, approve about 30 emails a day without exceeding any limit, never double-contact a company, never email someone who declined, and see at any moment who contacted whom and where each sponsor stands.

## 12. Operating requirements
- O1 Organizers reach the app over HTTPS from anywhere. It runs always-on on a free cloud VM.
- O2 Every account uses two-factor (TOTP) before the app goes online.
- O3 Data survives loss of the VM: encrypted backups, a weekly off-server copy, and a tested restore.
- O4 Hosting uses only always-free resources, with a billing alert, so nothing can charge the club.
- O5 Admins can see system health (last mail check, last send, last backup, disk) and can sign everyone out.
