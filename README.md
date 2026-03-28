# jerbs

Automated job email screener. Screens recruiter emails against your criteria, filters the noise, and drafts replies for anything worth pursuing.

Two versions:
- **Claude.ai** — installs as a skill, runs in the browser, scheduler widget included
- **Local daemon** — runs continuously in the background via Claude Code / Python

---

## Quick start — Claude.ai

### 1. Download the skill

Grab [`claude-ai/jerbs.skill`](claude-ai/jerbs.skill) from this repo.

### 2. Connect Gmail

In Claude.ai: **Settings → Connectors → Gmail → Connect**

Jerbs needs Gmail access to fetch and screen your emails. It operates in read-only mode by default — it never sends, deletes, or modifies anything.

### 3. Install the skill

In Claude.ai: **Settings → Skills → Install from file** → upload `jerbs.skill`

### 4. Set up your criteria

Start a new conversation and say:

> "set up jerbs"

The wizard walks you through configuring everything: target roles, comp floor, dealbreakers, required info, reply tone, business hours. Saves to a JSON file you own.

### 5. Run it

> "run jerbs" or "check my job emails"

Jerbs runs two passes every cycle:
- **Pass 1** — LinkedIn/Indeed job alert digests
- **Pass 2** — Direct recruiter outreach

Results come back as interested / maybe / filtered out, with draft replies for anything worth pursuing.

### 6. Automate it (optional)

> "start the jerbs scheduler"

A scheduler widget appears with configurable business hours. It runs automatically on a variable cadence — no babysitting required:

| Mode | Interval | Condition |
|---|---|---|
| Off-hours | 60 min | Outside business hours |
| Business hours | 15 min | Within business hours |
| Rapid | 5 min × 30 min | Auto-triggered when draft replies are generated |

Rapid mode kicks in automatically when a run produces draft replies (watching for quick responses), then reverts on its own after 30 minutes.

### 7. Export to spreadsheet (optional)

> "export those results to a spreadsheet"

Exports an `.xlsx` file importable to Google Sheets with a full pipeline status tracker — from "New" through "Offer accepted," with collapsible dead-end categories.

---

## Quick start — local daemon

For true background operation (no browser tab needed).

```bash
git clone https://github.com/pauljunod/jerbs.git
cd jerbs/claude-code
pip install -r requirements.txt

# Set your Anthropic API key
export ANTHROPIC_API_KEY=sk-ant-...

# Set up Gmail API credentials (see docs/setup.md)
# Then run the setup wizard
python jerbs.py --setup

# Start the daemon
python jerbs.py
```

See [`docs/setup.md`](docs/setup.md) for Gmail API setup, launchd/systemd background service config, and all CLI options.

---

## Criteria

Everything is driven by your criteria file — comp floor, target industries, dealbreakers, required info, reply tone, business hours. The setup wizard builds it interactively. You can edit it directly or update specific sections by telling jerbs what to change.

**Salary range rule:** If your base floor falls *within* a stated range (e.g. floor is $200k, range is $180k–$300k), the role passes — you can negotiate to your number. Only fails if the top of the range is below your floor.

Full schema: [`shared/criteria_template.json`](shared/criteria_template.json)

---

## Repo structure

```
jerbs/
├── claude-ai/
│   ├── jerbs.skill          ← Install this in Claude.ai
│   ├── SKILL.md             ← Skill instructions (bundled inside .skill)
│   └── assets/
│       └── scheduler.html   ← Scheduler widget (bundled inside .skill)
├── claude-code/
│   ├── jerbs.py             ← Daemon entry point
│   ├── scheduler.py         ← Interval state machine
│   ├── screener.py          ← Anthropic API screening logic
│   ├── gmail_client.py      ← Google Gmail API wrapper
│   ├── setup_wizard.py      ← First-time setup
│   └── requirements.txt
├── shared/
│   ├── criteria_template.json   ← Full criteria schema with defaults
│   └── scripts/
│       └── export_results.py    ← xlsx export (shared by both versions)
├── docs/
│   └── setup.md             ← Detailed setup guide
└── README.md
```

---

## How it works

### Automatic rapid mode
When a screening run generates draft replies, the scheduler automatically switches to 5-minute intervals for 30 minutes to catch quick responses. No manual trigger needed — it detects draft replies in Claude's output automatically.

### Screening memory
Screened email IDs are saved to your criteria file after each run. Emails already screened won't appear again in future runs.

### First run vs. recurring
- **First run:** looks back 7 days, no result cap — catches everything recent
- **Recurring:** looks back 1 day, 100 emails per pass — fast and focused

### Read-only by default
The Claude.ai version never sends, deletes, labels, or modifies anything. The local daemon has an optional `--send` flag for auto-sending draft replies if you want full automation.

---

## Privacy

- Criteria and screening history stored locally (`~/.jerbs/` for daemon, your machine for Claude.ai)
- Gmail credentials never leave your machine
- Email content is sent to the Anthropic API for screening — subject to [Anthropic's privacy policy](https://www.anthropic.com/privacy)

---

## Contributing

PRs welcome. Ideas:
- Outlook / other email provider support
- Notion / Airtable export
- TUI dashboard for the daemon
- Slack/Discord notifications for high-interest matches

---

## License

MIT
