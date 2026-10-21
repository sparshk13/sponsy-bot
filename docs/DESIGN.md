# Design system and voice

These decisions are final. The agent implements them and does not substitute its own taste (HUM rules). The student may change values in `tokens.css`; the agent may not.

## 1. Concept
A well-kept ledger. Sponsy is a work tool used by tired students between lectures. It should feel like a tidy paper register: ruled lines instead of boxes, words instead of icons, numbers lined up, nothing performing for the user. Reference feel: plain, dense, accessible government and library forms, old accounting registers, a good spreadsheet. Not reference: SaaS landing pages, dashboards with glowing charts, clean white minimalism. The page should feel slightly worn and warm, with one deep colour giving it structure.

## 2. Tokens (`frontend/src/styles/tokens.css`)
The ground is putty, a dingy warm off-white, like an old register page. Never pure white, never pure black. A second brand colour, petrol (a dark blue-green), carries the structure: the navigation rail, table header bars, page titles. Green stays reserved for "go".
```
--paper:      #E6E1D1;   page background (putty)
--paper-2:    #D9D3BF;   quiet panels, notices, hover rows
--field:      #F0EDE0;   input background (lightest tone allowed)
--ink:        #14171A;   text, strong rules
--ink-2:      #4A4F52;   secondary text
--rule:       #B5AE97;   hairlines
--rail:       #24404F;   petrol: nav rail, table headers, page titles
--rail-ink:   #E6E1D1;   text on petrol
--rail-ink-2: #B9C4C8;   quiet text on petrol
--approve:    #1F5A46;   primary action, interested, secured
--approve-ink:#F0EDE0;   text on green
--warn-bg:    #EBCB7A;   unverified and assumption flags
--warn-ink:   #5A3D00;
--stop:       #9C2F23;   decline, destructive actions
```
Meanings: petrol is structure, green means go or good, amber means "check this", red means stop. No other colors. Compute contrast for every text and background pair (including text on petrol and on putty) and adjust a token only if a pair falls below 4.5:1. Light theme only.

## 3. Type
Self-hosted woff2 in `frontend/public/fonts/`, `font-display: swap`, all open-licence (verify licence and download from the official source or fontsource; keep the licence files next to the fonts).
- Headings, navigation, table headers, buttons: **Archivo** (700 for headings, 500 for labels).
- Body and forms: **Atkinson Hyperlegible Next** (400, 500). If unavailable, use **Source Sans 3** and tell the student.
- Data (emails, counts, rupee amounts, ids, dates in tables): **IBM Plex Mono** 400, right-aligned for numbers.
- Fallback stacks end in plain `sans-serif` or `monospace`.

Scale (px): 13, 15, 17, 21, 27. Body is 15 with line-height 1.55. Page title 27, section heading 21, sub-heading 17. Never weight 600 for body. Reading text max 70ch.

Spacing scale (px): 3, 6, 10, 16, 26, 42, 68. Use only these.
Radius: 2px for inputs, buttons, tags. 0 elsewhere. Elevation: none; use a 1px border.

## 4. Layout
- Left navigation rail, 200px, solid `--rail` with `--rail-ink` text, links only, counts in mono beside Approvals and Inbox. The active item is a tab: a `--paper` block that runs to the rail's right edge with `--ink` text, no rounded pill. Items: Today, Targets, Approvals, Inbox, Dashboard, Memory, Usage, Admin.
- Main column padded 26px top, 42px sides, content max-width 1180px. Page title left-aligned with one plain line under it saying the current state ("14 targets, 3 yours, 2 waiting for approval"). Primary page action sits at the right of the title row. Page titles are set in `--rail`. A 3px `--rail` rule closes the title block.
- Sections are separated by a 1px rule and a heading, not boxed.
- Forms: one column, label above field, helper text below in ink-2, 520px max width.
- Tables are the main structure. Header row is a solid `--rail` bar with `--rail-ink` text; rows separated by 1px `--rule`; row padding 10px 10px; hover changes background to `--paper-2`. Numbers and ids in mono, right-aligned. The wrapper scrolls horizontally on narrow screens.
- At 360px the navigation becomes a text row at the top that wraps; nothing is hidden behind a hamburger icon.

## 5. Components
- **Primary button**: `--approve` fill, `--approve-ink` text, 2px radius, Archivo 500, height 34px. Used at most once per view for the main action (Approve, Save). **Secondary**: transparent, 1px ink border. **Destructive**: text in `--stop`, underlined, with a confirmation step in plain words.
- **Links**: ink, underlined; on hover the underline thickens.
- **Focus**: 2px `--approve` outline, 2px offset, on every interactive element.
- **Status** is a word plus a CSS-drawn shape (no characters, no icon font). Shapes: hollow square = not contacted; solid square = contacted; solid diamond = follow-up; solid green circle = interested; green ring = meeting booked; solid green square = secured; solid red triangle = declined; hollow grey circle = closed, no reply.
- **Tier**: the plain word (Cash, Goodies, Credits). **Priority**: A, B or C in mono inside a 20px square: A is filled `--rail` with `--rail-ink` text, B is a 1px ink outline, C is outlined in `--ink-2`.
- **Evidence flags**: `Verified` in ink-2 with the source domain as a link; `Unverified` and `Assumption` on `--warn-bg` with `--warn-ink`, 13px Archivo 500, 2px radius. They appear next to every fact, reason, and ask that depends on them.
- **Messages in a thread**: a plain list with a date gutter in mono on the left, sender and subject in the heading line, body in the body face with `white-space: pre-wrap`. Sent and received differ by the label word ("You wrote" and "They wrote"), not by bubbles.
- **Notices**: a single line bar at the top of the main column, 1px border, no icon, no colored side bar. Amber background for limits, plain for confirmations.
- **Charts**: small hand-written SVG components with solid shapes only: a pipeline bar (solid `--rail` and `--approve` segments with labels) and a response line (2px `--rail` stroke, no fill, no gradient, numbers in mono at the ends). No axes clutter, no legends, no chart library. Tables with inline bars are the fallback.
- **Icons**: none by default. If a case truly needs one, hand-draw it as an inline SVG, 1.5px stroke, at most 8 in the whole app.
- **Motion**: none, except 120ms background-color and opacity changes, and a 160ms slide for the slide-over panel and for a row leaving a list. Respect `prefers-reduced-motion`.

## 5b. Front-end behaviour
Built as React components on native elements, styled with CSS Modules that read the tokens. Shared pieces: `Shell` (rail and page frame), `DataTable`, `StatusMark`, `EvidenceFlag`, `SlideOver` (a native `dialog`), `Notice`.
- Tables sort and filter instantly on the client; filters live in the URL so a view can be shared. Header row sticks. A density switch (comfortable or compact) is remembered per user.
- Queue: opening a draft slides a panel in from the right with the full text, the evidence it used, and the validation result. Approve is a button click only. No keyboard shortcut approves anything.
- Keyboard: `j` and `k` move between rows, `Enter` opens, `Esc` closes a panel, `/` focuses search. Shortcuts are listed in a plain "Keys" line in the footer of the rail.
- Server state changes are shown only after the server confirms them. The one exception is moving a row out of a list after discard. Sending is never optimistic.
- Loading is the text "Loading targets." style line. Errors use the copy table. No skeletons, no spinners that spin forever.
- Forms validate on submit and show the message under the field in `--stop` with a text prefix, not color alone.
- Every page works from 360px to wide desktop, with tables scrolling inside their wrapper.

## 6. Pages
1. **Login**: a `--rail` strip on the left holding the wordmark "Sponsy" (Archivo 700, `--rail-ink`), then the form in a 360px column aligned left in the putty area. No panel, no illustration, no centered box.
2. **Today**: three ruled lists: "Waiting for your approval", "Replies to read", "Follow-ups due". Under them a line: "Sent today: 12 of 30". Each item links straight to its action.
3. **Targets**: filter row (status, tier, owner, search) above one dense table: Company, Tier, Priority, Status, Owner, Contact, Last contact, Next follow-up. Import CSV and Add company in the title row. Rows owned by someone else show their name and a disabled action.
4. **Target detail**: header with company, status, owner. Two columns above 900px. Left: Evidence table (claim, kind, source, flag), then Recommendation (tier, ask, reasoning that cites facts, flag for assumption). Right: the draft editor (subject, body, contact, brochure), a `Save changes` button and the primary `Approve` button, and the validation messages if the draft failed a check. Below both: the thread, then Outcome (record what was secured).
5. **Queue**: table of drafts waiting, each row expandable inline to read and edit; Approve per row. Today's sent versus cap and the next send time shown above. No bulk approve (SEC-20).
6. **Inbox**: replies newest first: company, classification (editable by a human), the one-line summary, suggested response (editable, goes to the queue like any draft).
7. **Dashboard**: pipeline table (stage, count, bar), response rate, interest rate, declined, secured amount in rupees and list of non-cash benefits, per-organizer counts.
8. **Memory** (past sponsors across campaigns with what they gave and what worked), **Usage** (each provider: used, cap, resets), **Admin** with tabs for users, campaigns, suppression list, pause switch, audit log.

## 7. Voice and copy
Plain, specific, sentence case, first person plural only when the club speaks. Say what happened and what to do. No exclamation marks. No em dashes. No emoji.

| Place | Write |
|-------|-------|
| Today, nothing waiting | Nothing is waiting for your approval. |
| Queue, empty | No drafts in the queue. Prepare a target to create one. |
| Inbox, empty | No replies yet. We check the mailbox every 5 minutes. |
| Targets, empty | No companies yet. Import a CSV or add one by hand. |
| Approve confirmation | Approved. It will go out between 09:30 and 17:30, after the other emails ahead of it. |
| Edited after approval | You changed the text, so the approval no longer applies. Approve again to send. |
| Someone else owns it | Priya owns this company. Ask an admin if it needs to move. |
| Unverified fact | We could not confirm this in the sources we found. Check it before relying on it. |
| No evidence for ask | No sponsorship history found in the sources searched. This ask is an assumption. |
| Quota reached | Gemini's free quota for today is used up. Drafting resumes tomorrow. Nothing is lost. |
| Mail server down | We could not reach the mail server. The email stays approved and will be retried. |
| Session expired | You were signed out after being away. Sign in to continue. |
| Daily cap reached | 30 of 30 sent today. The rest will go out tomorrow morning. |
| Login failure | That email and password do not match. |
| Declined reply | They said no. We will not contact them again. You can undo this in Admin. |
| Paused | Sending is paused by an admin. Nothing will go out until it is resumed. |

Email drafts: short, written as a student writing to a person, one specific reason this company is relevant that comes from a verified fact, one clear ask, one line about the event, the sender's name and club, and an opt-out line such as "If this is not for you, tell me and I will not write again." Never write "I hope this email finds you well", "excited to reach out", "synergy", or "partnership opportunity of a lifetime".

## 8. Anti-AI checklist (every UI change)
Run `python scripts/ai_tells_scan.py`, which checks the mechanical tells: gradients, pure white or black, banned fonts, purple and indigo, kits and icon packs, glow and glass, large radius, animation, generic copy, placeholder data, em dashes, emoji. Then check by eye: no hero, no row of three cards, no centered marketing layout, no colored left borders, no uniform rounded cards, no decorative icons, nothing that looks like the default output of a UI kit. If the page could be a template for any other product, it is wrong.
