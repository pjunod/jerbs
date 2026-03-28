# jerbs 🔍

A Claude skill that screens your job-related emails against your personal criteria and drafts follow-up replies — so you only spend time on opportunities worth pursuing.

---

## What it does

- **Two-pass Gmail scan** — catches both job alert digests (LinkedIn, Indeed, etc.) and direct recruiter outreach
- **Configurable screening criteria** — salary floor, remote preference, dealbreakers, seniority, target industries, company whitelist/blacklist, and more
- **Verdict + reasoning** — each email gets a 🟢 Interested / 🟡 Maybe / 🔴 Filtered Out verdict with a one-sentence reason naming the specific criterion
- **Draft replies** — ready-to-copy reply drafts for anything worth pursuing, requesting any missing info in a single message
- **Spreadsheet export** — optional `.xlsx` pipeline tracker with color-coded status dropdowns and collapsible dead-end groups
- **Auto-scheduler** — runs jerbs automatically on a variable cadence (15 min during business hours, 60 min off-hours, 5 min rapid mode after draft replies are generated)

---

## Files

```
jerbs/
├── README.md                  ← you are here
├── SKILL.md                   ← the Claude skill definition (load this into Claude)
├── criteria_template.json     ← full criteria schema with all fields and defaults
├── scripts/
│   └── export_results.py      ← exports screener results to a formatted .xlsx file
└── assets/
    └── scheduler.html         ← auto-scheduler widget (rendered inline by Claude)
```

---

## Setup

### 1. Add the skill to Claude

Upload `SKILL.md` to your Claude skills, or paste it into your Claude system prompt.

### 2. Connect Gmail

jerbs requires the **Gmail MCP connector** in Claude.ai. Enable it in **Settings → Connectors → Gmail**.

### 3. Run it

Start a conversation with Claude and say any of:

- `"run jerbs"`
- `"check my job emails"`
- `"screen my recruiter emails"`
- `"set up my job screener"`

On first run, Claude walks you through a setup wizard to capture your criteria. On subsequent runs, it loads your saved profile and goes straight to screening.

---

## Criteria profile

Your criteria are stored in a JSON file (default: `~/job-screener-criteria.json`). Claude creates and updates this file automatically. The full schema is in `criteria_template.json`.

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

You can update any section at any time without re-doing the full wizard:

```
"Update my salary floor to $200k"
"Add Google to my dream companies"
"Add 'no unpaid take-homes' as a dealbreaker"
"Change my reply tone to brief"
```

---

## Spreadsheet export

After a screening run, say `"export to spreadsheet"` and Claude runs:

```bash
python scripts/export_results.py results.json job_screener_YYYY-MM-DD.xlsx
```

The `.xlsx` has two sheets:

- **Summary** — run date, counts by verdict, full color-coded status guide
- **Results** — one row per opportunity, sorted pass → maybe → fail, with a **Status** dropdown tracking the full hiring pipeline from *New* through *Offer accepted* or *Rejected*

Dead-end rows (No response, Withdrew, Rejected, Filtered out) are grouped and collapsed at the bottom — click `+` to expand.

### Requirements

```bash
pip install openpyxl
```

---

## Auto-scheduler

The scheduler runs jerbs automatically without manual prompting. Ask Claude to `"start the scheduler"` and it renders an interactive widget in the conversation.

**Cadence:**

| Mode | Interval | Trigger |
|---|---|---|
| Business hours | 15 min | Within your configured hours |
| Off-hours | 60 min | Outside business hours |
| Rapid response | 5 min for 30 min | Auto-triggered when draft replies are generated |

The scheduler runs while the Claude.ai tab is open. It is not a background service — it requires an active browser tab.

---

## Constraints

- **Read-only by default** — jerbs never sends, deletes, labels, archives, or creates Gmail drafts unless you explicitly enable send mode
- **Draft replies are copy-and-send** — you always review before anything goes out
- **Spreadsheet export is always optional** — never created unless you ask

---

## License

MIT
