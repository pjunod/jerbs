# jerbs 🔍

A Claude skill that screens your job-related emails against your personal criteria, drafts
follow-up replies, and tracks your recruiter correspondence — so you only spend time on
opportunities worth pursuing.

---

## What it does

- **Two-pass Gmail scan** — catches both job alert digests (LinkedIn, Indeed, etc.) and direct recruiter outreach
- **Configurable screening criteria** — salary floor, remote preference, dealbreakers, seniority, target industries, company whitelist/blacklist, and more
- **Verdict + reasoning** — each email gets a 🟢 Interested / 🟡 Maybe / 🔴 Filtered Out verdict with a one-sentence reason naming the specific criterion
- **Draft replies** — ready-to-copy reply drafts for anything worth pursuing, requesting any missing info in a single message
- **Send mode** — optionally have Claude send replies on your behalf automatically, with full logging
- **Correspondence tracking** — logs every sent reply and checks for recruiter responses on each run, surfacing active threads at the top of your report
- **Spreadsheet export** — optional `.xlsx` pipeline tracker with color-coded status dropdowns and collapsible dead-end groups
- **Auto-scheduler** — runs jerbs automatically on a variable cadence (15 min during business hours, 60 min off-hours, 5 min rapid mode after replies are sent)

---

## Files

```
jerbs/
├── README.md                    ← you are here
├── SKILL.md                     ← the Claude skill definition (load this into Claude)
├── criteria_template.json       ← full criteria schema with all fields and defaults
├── scripts/
│   └── export_results.py        ← exports screener results to a formatted .xlsx file
└── assets/
    └── scheduler.html           ← auto-scheduler widget (rendered inline by Claude)
```

**Runtime files** (created by Claude, not in the repo):
```
~/.claude/jerbs/criteria.json        ← your personal screening criteria profile
~/.claude/jerbs/correspondence.json  ← log of all sent replies and recruiter responses
```

---

## Setup

### Option A — Claude Project (recommended for web use)

1. Go to claude.ai → **Projects** → **New project**, name it "jerbs"
2. Open the project → **Project instructions** → paste in the full contents of `SKILL.md`
3. Upload `criteria_template.json` to the project files
4. Connect Gmail: **Settings → Connectors → Gmail**
5. Open a conversation inside the project and say `"run jerbs"`

On first run, Claude walks you through a setup wizard and outputs a `criteria.json`
file for you to upload to the project. After that, it's loaded automatically in every conversation.

### Option B — Claude Code (recommended for power users)

1. Clone this repo
2. Open Claude Code in the repo directory
3. Connect Gmail via the Claude.ai connector settings
4. Say `"run jerbs"` — Claude reads and writes files directly, no re-uploading needed

---

## How files are managed

jerbs adapts automatically to where it's running:

### Claude Code
Claude reads and writes `~/.claude/jerbs/criteria.json` and `~/.claude/jerbs/correspondence.json`
directly. Nothing extra needed — files stay in sync automatically after every run.

### Web / Claude Project
Claude reads both files from the project context at the start of every conversation.
Since it can't write back to project files directly, at the end of any run where something
changed, it outputs the updated JSON and prompts you to re-upload the file(s) to the project.
On clean runs with no changes, it stays quiet.

The re-upload step is quick — drag the file into the project to replace the old version —
and only happens when something actually changed (new screened emails, new correspondence,
criteria updates).

---

## Criteria profile

Your criteria are stored in `criteria.json`. Claude creates and updates this
file automatically. The full schema is in `criteria_template.json`.

Key sections:

| Section | What it covers |
|---|---|
| `identity` | Your name, title, target roles, seniority level |
| `target_companies` | Industries, company types, whitelist, blacklist |
| `role_requirements` | Employment type, remote preference, visa sponsorship |
| `compensation` | Base salary floor, TC target, sliding scale notes |
| `tech_stack` | Required, dealbreaker, and preferred tech |
| `hard_dealbreakers` | Automatic fail conditions |
| `required_info` | Fields to always ask about if missing (comp, equity, WFH policy, etc.) |
| `reply_settings` | Tone and signature for draft replies |
| `send_mode` | Whether Claude sends replies automatically (off by default) |

You can update any section at any time without re-doing the full wizard:

```
"Update my salary floor to $200k"
"Add Google to my dream companies"
"Add 'no unpaid take-homes' as a dealbreaker"
"Change my reply tone to brief"
"Enable send mode"
"Disable send mode"
```

---

## Send mode

By default, jerbs runs in **dry-run mode** — draft replies are shown as copy-paste text
and nothing is sent. You're always in control of what goes out.

**Send mode** allows Claude to send replies on your behalf automatically. Every sent
message is logged to the correspondence log.

To enable:
```
"Enable send mode"
```

Claude will warn you and ask for confirmation before switching it on. To disable:
```
"Disable send mode"
```

The current mode is always shown prominently at the start of every screening run — it
can never be ambiguous.

---

## Correspondence tracking

All sent replies (and dry-run drafts) are logged to `~/.claude/jerbs/correspondence.json`. Each
entry records the company, role, recipient, full message body, Gmail thread IDs, and
whether you're still waiting on a reply.

On every subsequent run, jerbs checks open threads for recruiter responses and surfaces
them at the top of your report:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACTIVE THREADS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📬 Reply received
  Acme Corp — Staff Engineer
  They replied 2 hours ago. Asking for your availability next week.

⏳ Awaiting reply (3 days)
  Initech — Principal Engineer
  Reached out on Mar 25. No response yet.
```

You can also ask:
```
"Show my correspondence log"
"Clear my correspondence log"
```

---

## Spreadsheet export

After a screening run, say `"export to spreadsheet"` and Claude runs:

```bash
python scripts/export_results.py results.json job_screener_YYYY-MM-DD.xlsx
```

The `.xlsx` has two sheets:

- **Summary** — run date, counts by verdict, full color-coded status guide
- **Results** — one row per opportunity, sorted pass → maybe → fail, with a **Status**
  dropdown tracking the full hiring pipeline from *New* through *Offer accepted* or *Rejected*

Dead-end rows (No response, Withdrew, Rejected, Filtered out) are grouped and collapsed
at the bottom — click `+` to expand.

### Requirements

```bash
pip install openpyxl
```

---

## Auto-scheduler

The scheduler runs jerbs automatically without manual prompting. Ask Claude to
`"start the scheduler"` and it renders an interactive widget in the conversation.

**Cadence:**

| Mode | Interval | Trigger |
|---|---|---|
| Business hours | 15 min | Within your configured hours |
| Off-hours | 60 min | Outside business hours |
| Rapid response | 5 min for 30 min | Auto-triggered when draft replies are generated |

The scheduler runs while the Claude.ai tab is open. It is not a background service —
it requires an active browser tab. For always-on operation without a browser, use
Claude Code.

---

## Constraints

- **Dry-run by default** — Claude never sends, deletes, labels, or archives Gmail messages
  unless you explicitly enable send mode and confirm
- **Send mode requires double confirmation** — Claude warns you clearly before enabling
- **You always see what was sent** — in send mode, the full text of every sent reply is
  shown in the run report
- **Spreadsheet export is always optional** — never created unless you ask

---

## License

MIT
