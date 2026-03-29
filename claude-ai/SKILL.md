---
name: jerbs
description: >
  Screens job-related emails in Gmail against a candidate's personal criteria and drafts
  follow-up replies for anything worth pursuing. Use this skill whenever a user wants to
  filter recruiter emails, screen job opportunities, triage job alert digests, evaluate
  inbound recruiter outreach, or automate any part of the applicant-side hiring process.
  Also use when the user says things like "check my job emails", "screen my recruiter
  emails", "what job leads came in this week", "run my job screener", "set up my job
  screener", or "update my screening criteria". Requires Gmail to be connected. Runs two
  passes automatically (job alert digests + direct outreach) and combines results into one
  report. Optionally exports results to a formatted .xlsx / Google Sheets file with a
  built-in pipeline status tracker.
compatibility: "Requires Gmail MCP (gmail_search_messages, gmail_read_message). Never use gmail_create_draft or take any write action on emails unless the user has explicitly enabled send mode."
---

# Job Email Screener

A fully configurable job email screener that works for any role, industry, and experience
level. Screens Gmail in two passes, applies the user's criteria, surfaces draft replies,
and optionally exports results to a spreadsheet pipeline tracker.

---

## How criteria are stored

Criteria are stored in a JSON profile that Claude reads at the start of each run and
writes when updated. In Claude.ai Projects, the profile lives as a project file named
`criteria.json`. On first run, Claude creates it interactively via the setup wizard and
outputs it for upload. On subsequent runs, Claude loads it from the project context and
prints a summary before screening.

The bundled `criteria_template.json` shows the full schema with all fields and defaults.

---

## Step 0 — Load or set up criteria

**At the start of every interaction**, check whether a criteria file exists:

```
Does the user have a criteria file? 
→ Yes: Load it, print a brief summary, ask if they want to adjust anything before running.
→ No: Run the setup wizard (below).
```

**If criteria file exists and they want to adjust:** Ask which section they want to change
(compensation / dealbreakers / target companies / stack / reply settings / etc.) and update
only that section — never make them redo everything.

---

## Step 1 — Setup wizard (first-time or full reset)

Walk through these sections conversationally. Ask one section at a time. Don't overwhelm.
Offer sensible defaults and examples. At the end, confirm the full profile before saving.

### 1a — Identity
```
What's your name and current title? 
Briefly describe your background (e.g. "10 years backend engineering, Apple and Meta").
What roles are you targeting? (can be multiple, e.g. "Staff Engineer, Principal SRE, Engineering Manager")
What seniority level? (e.g. Senior and above / mid-level and above / executive)
```

### 1b — Target companies
```
What industries or company types are you interested in?
  Examples: FAANG-tier tech, fintech, crypto, hedge funds / HFT, healthcare tech,
  e-commerce, startups, enterprise SaaS, government, non-profit

Any company stages you prefer? (early-stage, Series B+, public, any)

Any prestige / pedigree requirement? 
  Examples: "top-tier only — no unknown companies", "any legitimate company", "prefer well-known brands"

Are there specific companies you ALWAYS want to hear about (dream companies)?
Are there specific companies or recruiters you want to ALWAYS ignore (blacklist)?

Any entire industries to block?
  Examples: defense / weapons, tobacco, gambling, MLM, predatory lending
```

### 1c — Role requirements
```
Employment type: full-time only / open to contract / open to part-time?
Remote preference: remote only / hybrid OK / depends on location / open to on-site?
  If hybrid is OK, what's the max number of in-office days per week you'd consider?
Maximum travel you'd accept? (e.g. none, <10%, <25%, doesn't matter)
Do you need visa/work authorization sponsorship?
```

### 1d — Compensation
```
What's your minimum acceptable base salary? (hard floor — reject anything explicitly listed below this)
  Currency? (USD, GBP, EUR, etc.)

What's your target total compensation? (including equity, bonus, etc.)

Is equity required, or is a strong cash bonus acceptable instead?

Any nuances to your comp expectations? This is your sliding scale — describe how your 
expectations shift based on factors like:
  - Remote vs. in-office (and how many days)
  - How interesting / novel the work is
  - Company prestige or brand value
  - Startup equity upside potential
  - Seniority / scope of the role
  - Cost of living / location

Examples:
  "I'll accept lower base for fully remote roles or for genuinely exciting greenfield work"
  "In-office 4+ days needs to pay significantly more to be worth it"
  "Founding-team equity can offset a lower base if the company is promising"
```

### 1e — Tech/stack (skip if not applicable)
```
Any tech/stack that's a hard requirement? (e.g. Linux-only environments, specific languages)
Any tech/stack that's an immediate dealbreaker? (e.g. Windows servers, legacy COBOL)
Any preferred stack or tech that would make a role more attractive?
```

### 1f — Hard dealbreakers
Start with common suggestions and let them add/remove:

Suggested defaults (user picks which apply):
- Contract / part-time / freelance (when targeting full-time)
- Wrong seniority level (junior/intern/mid-level if targeting senior)
- Salary explicitly listed below base floor
- Generic/mass emails with no personalization (no name, boilerplate, "Hi there")
- Completely unknown company with no pedigree, funding signal, or recognizable name
- Company on personal blacklist
- Industry on personal blocklist
- Requires relocation to unwanted location
- Unpaid trial or take-home assignment
- Requires security clearance (if not applicable)
- Role is in entirely wrong field

Let user add any custom dealbreakers.

### 1g — Required info (what to always ask about if missing)
Start with common suggestions:

Suggested defaults:
- Salary / compensation range (base + total comp)
- Equity details (type, vesting schedule)
- Remote / hybrid / in-office policy
- Number of in-office days if hybrid
- Interview process overview
- Company name (if obscured)

Additional options:
- Nature of work (greenfield vs. maintenance)
- Tech stack details
- Team size
- Reporting structure
- Benefits (health, 401k, etc.)
- Bonus structure
- Start date flexibility

### 1h — Interview process preferences (optional)
```
Maximum number of interview rounds you'll tolerate? (or leave blank for no limit)
Unpaid take-home assignments: dealbreaker yes/no?
Any other interview process dealbreakers?
```

### 1i — Reply settings
```
What tone should draft replies use? (professional / direct / warm / brief)
What name/signature should replies use?
  Example: "Best, Sarah Chen" or "Thanks, Marcus | Staff Engineer"
```

### 1j — Search settings
```
Any extra keywords to include in searches beyond the defaults?
Any specific senders or domains to always exclude?
```

Note: Do NOT ask about lookback window or max results during setup — these are set
automatically based on run history (see Step 3).

### Confirm and save
Show the full criteria summary and ask: "Does this look right? Anything to adjust before
I save it?" Then write to the criteria JSON file.

---

## Step 2 — Print criteria summary

At the start of every screening run, print a concise summary so the user can verify:

```
📋 Screening with: [Profile Name]
   Roles: [target roles]
   Base floor: $[X]  |  TC target: $[X]+
   Dealbreakers: [list]
   Required info: [list]
   Looking back: [N] days  |  Max per pass: [N]
```

Ask: "Run with these settings? (or say 'update [section]' to change something)"

---

## Step 3 — Run two Gmail passes

### Search window and result limits

**First run** (no entries in `screened_message_ids` yet):
- Lookback: 7 days — cast a wide net to catch everything still in play
- Max results per pass: unlimited (fetch all results)
- Goal: get a complete picture of what's come in recently

**Subsequent runs** (screening history exists):
- Lookback: 1 day — only new emails since the last run
- Max results per pass: 100
- If either pass returns exactly 100 results, assume there may be more — tell the user:
  > "Pass [1/2] hit the 100-result limit — there may be more emails matching. Want me to
  > increase the limit? (suggest a number, or say 'get all of them')"
  Wait for their answer before continuing with that pass. If they say get all, remove
  the limit; if they give a number, use that.

The user can always override with explicit instructions ("look back 3 days", "get everything").
After each run, update `last_run_date` in the criteria file.

### Pass 1 — Job alert digests (LinkedIn / Indeed)

Base query (customize with user's extra_keywords and extra_exclusions):
```
(subject:(opportunity OR role OR position OR opening OR hiring [+ user keywords]) OR
from:(linkedin.com OR jobalerts.indeed.com OR indeedemail.com)) newer_than:[N]d
```

These are subscription digest emails containing multiple listings. Screen the **individual
job listings** within each digest. The "generic mass email" dealbreaker does NOT apply to
digest emails — they're subscription alerts, not personal outreach.

Skip any message IDs already in `screened_message_ids` (previously screened).

### Pass 2 — Direct recruiter outreach

Base query:
```
newer_than:[N]d -from:linkedin.com -from:jobalerts.indeed.com -from:indeedemail.com
-from:noreply -from:no-reply [+ user exclusions]
(subject:(opportunity OR role OR position OR opening OR hiring OR "reaching out" OR
"your background" OR "your profile" OR "came across") OR ("your experience" OR
"your background" OR "came across your profile" OR "reaching out" OR "great fit" OR "perfect fit"))
```

Filter out non-job noise before screening: surveys, loyalty emails, newsletters, mailing
list patches, government/non-profit announcements, etc.

Apply the "generic mass email" dealbreaker here: no name, boilerplate, no reference to
specific background = hard fail.

Skip any message IDs already in `screened_message_ids`.

After screening, add all newly screened message IDs to `screened_message_ids`, set
`last_run_date` to today, and save the criteria file.

---

## Step 4 — Screen each item

### Verdicts
- **pass** (Interested) — clears all dealbreakers, worth pursuing
- **maybe** — uncertain on something; worth a conversation but needs more info
- **fail** (Filtered out) — one or more hard dealbreakers triggered

### Comp rule
Apply the user's base floor with range-aware logic:

- **No salary mentioned** → flag as missing, request in reply
- **Single number listed at or above floor** → passes, no issue
- **Single number listed below floor** → hard fail
- **Range listed where floor falls within the range** (e.g. floor is $225k, range is $192k–$288k) → **passes** — the candidate can negotiate to their number. Add a note flagging the low end, but do not reject. Only fail on a range if the *top* of the range is below the floor, or if the entire range is clearly unachievable.
- **Range listed where top of range is below floor** → hard fail

In short: fail only when there is genuinely no path to the floor within what's stated. If the floor is reachable within the range, it passes.

Then give an honest sliding-scale comp assessment using the user's nuance notes —
informational only, never changes the verdict.

### Company whitelist / blacklist
- Whitelist match → upgrade to at least "maybe", note it explicitly
- Blacklist match → instant fail regardless of other criteria

### Required info
For any pass/maybe, check which required fields are missing and draft a single reply
requesting all of them at once.

### Draft replies
- Only for pass and maybe verdicts
- Use user's configured tone and signature
- Direct — no sycophantic opener
- Request all missing required fields in one message
- User copies and sends manually (unless send mode is explicitly enabled)

---

## Step 5 — Present results

Two labelled sections, each with grouped verdicts:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
JOB ALERT LISTINGS (Pass 1)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🟢 INTERESTED
...

🟡 MAYBE
...

🔴 FILTERED OUT
...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIRECT OUTREACH (Pass 2)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
...
```

For each result include:
- Company + role + location
- Verdict reason (one sentence; name specific dealbreaker for fails)
- Comp assessment (honest sliding-scale take)
- Missing fields (if any)
- Draft reply (pass/maybe only — "copy and send manually")

At the end, offer: "Want me to export these to a spreadsheet?"

---

## Step 6 — Optional spreadsheet export

See `scripts/export_results.py` for the full export logic.

Run the export:
```bash
python scripts/export_results.py results.json job_screener_YYYY-MM-DD.xlsx
```

The spreadsheet has two sheets:
- **Summary** — run date, counts by verdict, full color-coded status guide
- **Results** — one row per item, sorted pass → maybe → fail, with:
  Date · Source · Company · Role · Location · From · Verdict · **Status** · Reason ·
  Dealbreaker · Comp assessment · Missing info · **Notes** · Draft reply

**Status column** tracks the full hiring pipeline with a dropdown:
- Pre-contact: New → Reply drafted → Awaiting info → Info received
- Active: Interested → Intro call → Interviewing → Final round
- Outcomes: Offer received → Negotiating → Offer accepted / Offer declined
- Dead ends: No response, Withdrew, Rejected, Filtered out (collapsed by default)

**Dead-end categories** (Offer declined, No response, Withdrew, Rejected, Filtered out)
are grouped and collapsed at the bottom of the Results sheet — click `+` to expand.

**Notes column** is blank and highlighted for free-text notes as the process moves forward.

**Google Sheets import:** sheets.google.com → File → Import → Upload the .xlsx.
If Google Drive MCP is connected, offer to upload directly instead.

---

## Criteria update commands

Users can update any section at any time without re-doing the full wizard:

- "Update my salary expectations" → re-run only section 1d
- "Add [company] to my blacklist" → append to blacklist, save
- "Add [company] to my dream companies" → append to whitelist, save
- "Change my reply tone to brief" → update reply_settings.tone, save
- "Add 'no take-home assignments' as a dealbreaker" → append to hard_dealbreakers, save
- "Reset my criteria" → re-run full wizard
- "Show my current criteria" → print full profile summary
- "Clear my screening history" → empty screened_message_ids, save

Always confirm changes before saving: "Got it — I'll [change]. Save?"

---

## Important constraints

- **Never** send, delete, label, archive, modify, or create drafts in Gmail unless the
  user has explicitly enabled send mode
- Draft replies are always presented as copy-and-send-manually text
- Spreadsheet export is always optional — never create one unless requested
- The criteria file is the source of truth — always load it at run start, always save
  after updates or after adding newly screened message IDs
- If Gmail is not connected, tell the user to connect it in Settings before running
- If Google Drive is not connected and upload is requested, fall back to download mode
  and suggest connecting Drive in Settings → Connectors

---

## Criteria file schema reference

See `criteria_template.json` for the full schema with all fields, types, and defaults.
Key fields:

```json
{
  "profile_name": "My Job Search",
  "identity": { "name", "background_summary", "seniority_level", "target_roles" },
  "target_companies": { "industries", "company_types", "whitelist", "blacklist" },
  "target_industries_blocklist": [],
  "role_requirements": { "employment_type", "remote_preference", "visa_sponsorship_required" },
  "compensation": { "base_salary_floor", "total_comp_target", "sliding_scale_notes" },
  "tech_stack": { "required", "dealbreaker", "preferred" },
  "hard_dealbreakers": [],
  "required_info": [],
  "interview_process": { "no_unpaid_takehome", "max_rounds" },
  "reply_settings": { "tone", "signature" },
  "search_settings": { "lookback_days", "max_results_per_pass", "extra_keywords" },
  "screened_message_ids": []
}
```

---

## Auto-scheduler (optional)

The scheduler widget runs jerbs automatically on a variable cadence. It lives in the
conversation as a persistent widget and uses JavaScript timers to fire `sendPrompt()`
with the full screening command.

### Interval state machine

| State | Interval | Condition |
|---|---|---|
| Off-hours | 60 min | Outside user-defined business hours |
| Business hours | 15 min | Within business hours |
| Rapid response | 5 min | For 30 min after a reply was sent |

Rapid mode reverts after 30 minutes with no new replies — back to business hours (15 min)
or off-hours (60 min), whichever applies at that moment.

### Business hours definition
User sets: timezone, start hour, end hour. Defaults to 9 AM–5 PM Eastern.

### Automatic rapid mode trigger
Rapid mode is triggered automatically — no user action required. At the very end of any
screening response that includes one or more draft replies, Claude MUST include the exact
token on its own line:

```
JERBS:RAPID_START
```

Do not explain or annotate this token — just include it silently at the end. The scheduler
widget watches the conversation via MutationObserver and triggers rapid mode the moment it
detects the token. This is the only mechanism for rapid mode — there is no manual button.

### What the scheduler sends
When the timer fires, it sends `sendPrompt()` with the full jerbs screening command
including all criteria, read-only mode instruction, and the instruction to include
`JERBS:RAPID_START` if any draft replies were generated.

### Controls
- Start / Pause — toggle the scheduler on and off
- Run now — fires an immediate run without resetting the timer
- I sent a reply — triggers rapid mode manually

### Important note
The scheduler only runs while the browser tab with this conversation is open. It is not
a background service — it requires the Claude.ai tab to be active.

---

## Scheduler widget

The scheduler is bundled at `assets/scheduler.html`. Display it using the `show_widget`
tool (read the file contents and pass as `widget_code`) whenever the user asks to:
- "start the scheduler"
- "automate jerbs"
- "run jerbs automatically"
- "set up the scheduler"
- or any similar phrasing

### How to render it

```python
with open("assets/scheduler.html") as f:
    html = f.read()
# Pass html as widget_code to show_widget
```

The widget is self-contained — it handles all timer logic, business hours detection,
mode switching, and automatic rapid mode via MutationObserver. No additional setup needed.

### Rapid mode token

When a screening run generates draft replies, Claude MUST include this token on its own
line at the very end of the response:

```
JERBS:RAPID_START
```

The widget's MutationObserver detects this token and triggers rapid mode (5 min × 30 min)
automatically. Do not explain the token — just include it silently when drafts were generated.

### Widget persistence

The widget runs only while the browser tab is open. Inform the user of this if they ask
about true background automation — the Claude Code local daemon version is the answer for
always-on operation without a browser.
