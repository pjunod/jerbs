# jerbs 🔍

[![Unit tests](https://github.com/pjunod/jerbs/actions/workflows/test.yml/badge.svg)](https://github.com/pjunod/jerbs/actions/workflows/test.yml)
[![Lint](https://github.com/pjunod/jerbs/actions/workflows/lint.yml/badge.svg)](https://github.com/pjunod/jerbs/actions/workflows/lint.yml)
[![Test coverage: 100%](https://img.shields.io/badge/test_coverage-100%25-brightgreen)](https://github.com/pjunod/jerbs/actions/workflows/test.yml)
[![Prompt injection security](https://github.com/pjunod/jerbs/actions/workflows/redteam.yml/badge.svg)](https://github.com/pjunod/jerbs/actions/workflows/redteam.yml)

A Claude skill that screens your job-related emails against your personal criteria, drafts
follow-up replies, and tracks your recruiter correspondence — so you only spend time on
opportunities worth pursuing.

**[Live demo →](https://pjunod.github.io/jerbs/)**

---

## Screenshots

### Terminal theme

<img src="docs/images/terminal-hero.png" alt="Terminal theme — screening report overview with verdict counts, action banners, and result cards" width="800">

<details>
<summary>Expanded card with verdict, comp assessment, and draft reply</summary>

<img src="docs/images/terminal-card-detail.png" alt="Terminal theme — expanded card showing verdict reasoning, comp assessment, missing info tags, and a draft reply with Review & Send button" width="700">

</details>

### Cards theme

<img src="docs/images/cards-hero.png" alt="Cards theme (dark) — clean card layout with stat tiles, filter bar, and action banners" width="800">

<details>
<summary>Expanded card detail</summary>

<img src="docs/images/cards-card-detail.png" alt="Cards theme — expanded card with verdict, comp, missing fields, draft reply, and action links" width="700">

</details>

<details>
<summary>Light mode</summary>

<img src="docs/images/cards-light.png" alt="Cards theme in light mode" width="800">

</details>

> Both themes are fully interactive — try the **[live demo](https://pjunod.github.io/jerbs/)** to click through filters, expand cards, and toggle light/dark mode.

---

## What it does

- **Two-pass Gmail scan** — catches both job alert digests (LinkedIn, Indeed, etc.) and direct recruiter outreach
- **Configurable screening criteria** — salary floor, remote preference, dealbreakers, seniority, target industries, company whitelist/blacklist, and more
- **Verdict + reasoning** — each email gets a 🟢 Interested / 🟡 Maybe / 🔴 Filtered Out verdict with a one-sentence reason naming the specific criterion
- **Draft replies** — ready-to-copy reply drafts for anything worth pursuing, requesting any missing info in a single message
- **Send mode** — optionally have Claude send replies on your behalf automatically, with full logging
- **Correspondence tracking** — logs every sent reply and checks for recruiter responses on each run, surfacing active threads at the top of your report
- **Spreadsheet export** — optional `.xlsx` pipeline tracker with color-coded status dropdowns and collapsible dead-end groups
- **Auto-scheduler** — runs jerbs automatically on a two-tier cadence (every 15 min during active sessions, hourly off-hours via remote trigger)

---

## Repository structure

```
jerbs/
├── README.md                        ← you are here
├── INSTALL.md                       ← quick-start installation guide
├── SKILL.md                         ← Claude Code skill definition
├── pyproject.toml                   ← Python linter/formatter config (ruff)
├── .yamllint.yaml                   ← YAML linter config
├── criteria_template.json           ← (legacy root copy — see shared/)
│
├── .claude-plugin/                  ← marketplace packaging
│   ├── plugin.json                  ← plugin metadata, version, MCP requirements
│   └── marketplace.json             ← marketplace listing for /plugin install
│
├── claude-web/                       ← Claude.ai browser version (see "Two SKILL.md files" below)
│   ├── SKILL.md                     ← streamlined skill spec for Claude.ai web/project sessions
│   ├── jerbs.skill                  ← packaged .skill file for one-click install
│   └── assets/
│       └── (empty)                  ← reserved for future assets
│
├── claude-code/                     ← local Python daemon (always-on, no browser)
│   ├── jerbs.py                     ← main entry point / daemon runner
│   ├── screener.py                  ← email screening logic (Anthropic API)
│   ├── gmail_client.py              ← Gmail API OAuth2 wrapper
│   ├── scheduler.py                 ← interval state machine (biz/off-hours)
│   ├── setup_wizard.py              ← interactive first-time setup
│   └── requirements.txt             ← Python dependencies
│
├── shared/                          ← files shared across deployment modes
│   ├── criteria_template.json       ← full criteria schema with all fields and defaults
│   └── scripts/
│       └── export_results.py        ← exports screener results to a formatted .xlsx file
│
├── tests/
│   ├── unit/                        ← pytest unit tests (run on every push/PR)
│   └── redteam/                     ← prompt injection security test harness
│       ├── server.py                ← FastAPI harness wrapping the screening pipeline
│       ├── promptfooconfig.yaml     ← auto-generated attack suite (40 tests)
│       ├── promptfooconfig-manual.yaml ← hand-crafted kill chain tests (10 scenarios)
│       ├── test_criteria.json       ← fake bait criteria for the harness
│       └── README.md                ← red team setup and usage
│
└── docs/
    ├── setup.md                     ← detailed setup guide for all deployment modes
    ├── demo/                        ← live demo HTML (deployed to GitHub Pages)
    └── images/                      ← screenshots for README
```

### Two SKILL.md files

There are two versions of the skill spec, each tailored for its deployment context:

| File | Used by | What it includes |
|---|---|---|
| `SKILL.md` (root) | Claude Code | **Full spec.** Environment detection, filesystem paths, correspondence tracking, send mode with safety caps, active thread management (Step 2.5), screened ID pruning, and all security guards. |
| `claude-web/SKILL.md` | Claude.ai web/project sessions | **Streamlined subset.** Same screening logic, criteria, setup wizard, and result format, but omits Claude Code filesystem paths, correspondence log, send mode details, active threads, and pruning to reduce context usage. |

**Keeping them in sync:** When changing shared behavior (screening logic, criteria fields,
setup wizard, result format, security rules), update **both files**. When changing Claude
Code-only features (environment detection, correspondence log, send mode toggle, Step 2.5,
screened ID pruning), only the root file needs changes. After editing `claude-web/SKILL.md`,
run `./scripts/build_skill.sh` to rebuild the packaged `.skill` file — CI will fail if
it's stale.

**Runtime files** (not in the repo — created automatically on first run):

| Deployment | Criteria file | Correspondence log |
|---|---|---|
| Claude Code (CLI) | `~/.claude/jerbs/criteria.json` | `~/.claude/jerbs/correspondence.json` |
| Local daemon | `~/.jerbs/criteria.json` | *(tracked in criteria file)* |
| Claude.ai Project | Project file (re-upload after changes) | Project file (re-upload after changes) |

---

## Deployment modes

jerbs runs in three modes. Pick the one that fits your setup.

### Claude.ai (browser)

Best for: casual use, no local setup required.

- Runs entirely in your browser via Claude's MCP connector system
- Gmail is connected via Settings → Connectors — no API keys needed
- Auto-scheduler runs via `/loop` during active sessions, remote trigger for off-hours
- Criteria and correspondence log are stored as project files; Claude outputs updated JSON at the end of any run where something changed, and prompts you to re-upload

See [INSTALL.md](INSTALL.md) for setup steps.

### Claude Code (CLI)

Best for: power users who want zero-friction local file management.

**Install from marketplace:**
```
/plugin marketplace add pjunod/jerbs
```

Or install manually — see [INSTALL.md](INSTALL.md).

- Runs inside the Claude Code CLI with Gmail connected via Claude.ai connectors
- Reads and writes `~/.claude/jerbs/criteria.json` and `~/.claude/jerbs/correspondence.json` directly — no re-uploading
- `/jerbs` available as a slash command once installed

### Local daemon

Best for: always-on background screening with no browser required.

- Standalone Python process, runs continuously in the background or as a system service
- Uses the Anthropic API directly (bring your own API key)
- Authenticates with Gmail via Google Cloud OAuth2 credentials
- Supports `--once`, `--send`, `--export` flags
- Runtime files live at `~/.jerbs/`

See [docs/setup.md](docs/setup.md) for full setup including Gmail API credentials and system service configuration.

---

## How files are managed

### Claude Code
Claude reads and writes `~/.claude/jerbs/criteria.json` and `~/.claude/jerbs/correspondence.json`
directly. Nothing extra needed — files stay in sync automatically after every run.

On first run, if no criteria file is found at the default location, Claude asks if you have
an existing file elsewhere and copies it over. The working copy is always `~/.claude/jerbs/`.

### Claude.ai Project
Claude reads both files from the project context at the start of every conversation.
Since it can't write back to project files directly, at the end of any run where something
changed, it outputs the updated JSON and prompts you to re-upload the file(s) to the project.
On clean runs with no changes, it stays quiet.

### Local daemon
The daemon reads and writes `~/.jerbs/criteria.json` directly. Pass `--criteria /path/to/file`
to use a different location.

---

## Criteria profile

Your criteria are stored in `criteria.json`. Claude (or the daemon wizard) creates and updates
this file automatically. The full schema is in `shared/criteria_template.json`.

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

**Send mode** allows Claude (or the daemon) to send replies on your behalf automatically.
Every sent message is logged to the correspondence log.

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

All sent replies (and dry-run drafts) are logged to the correspondence log. Each entry
records the company, role, recipient, full message body, Gmail thread IDs, and whether
you're still waiting on a reply.

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

After a screening run, say `"export to spreadsheet"` and Claude runs `shared/scripts/export_results.py`.

The `.xlsx` has two sheets:

- **Summary** — run date, counts by verdict, full color-coded status guide
- **Results** — one row per opportunity, sorted pass → maybe → fail, with columns for
  company, role, location, posting URL, verdict, comp assessment, and a **Status** dropdown
  tracking the full hiring pipeline from *New* through *Offer accepted* or *Rejected*

Dead-end rows (No response, Withdrew, Rejected, Filtered out) are grouped and collapsed
at the bottom — click `+` to expand.

### Requirements

```bash
pip install openpyxl
```

---

## Auto-scheduler

The scheduler runs jerbs automatically without manual prompting using a two-tier model.

**Tier 1 — Active session (every 15 min):**
Ask Claude to `"start the scheduler"` and it uses `/loop 15m` to run screening every
15 minutes inline in the conversation. No widget — results appear naturally in the chat.
Runs while the session is open.

**Tier 2 — Off-hours background (every 60 min):**
A remote trigger (scheduled agent) runs the screener hourly via cron when no session is
active. Set up once via `/schedule` with Gmail MCP connected. Runs autonomously in
Anthropic's cloud — no browser tab required.

The local daemon (`claude-code/`) also supports two-tier scheduling as a true background
process.

---

## Constraints

- **Dry-run by default** — Claude never sends, deletes, labels, or archives Gmail messages
  unless you explicitly enable send mode and confirm
- **Send mode requires double confirmation** — Claude warns you clearly before enabling
- **You always see what was sent** — in send mode, the full text of every sent reply is
  shown in the run report
- **Spreadsheet export is always optional** — never created unless you ask

---

## Contributing

### Linting

Python code is linted and formatted with [ruff](https://docs.astral.sh/ruff/) (covers PEP 8,
pyflakes, isort, bugbear, and pyupgrade). YAML is checked with yamllint. Both run as a
**Lint** job in CI on every push and PR.

```bash
pip install ruff yamllint

ruff check .          # lint
ruff format .         # format (Black-compatible)
yamllint .            # YAML
```

Config lives in [`pyproject.toml`](pyproject.toml) and [`.yamllint.yaml`](.yamllint.yaml).

### Running the red team

Comment `/redteam` on any PR to kick off the full prompt injection security suite against
that branch. See [`tests/redteam/README.md`](tests/redteam/README.md) for local setup and
what each test covers.

---

## License

MIT
