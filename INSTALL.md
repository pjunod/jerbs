# Installing jerbs

## Claude Code (recommended)

**Requirements:** Claude Code CLI or desktop app · Gmail connected

> **Marketplace listing coming soon.** For now, install manually:

```bash
git clone https://github.com/pjunod/jerbs.git
# Add the repo path as a skill in Claude Code settings
```

Then say **"set up jerbs"** or **"/jerbs"** to get started. The setup wizard handles the rest.

**Prerequisites:** Connect Gmail in Claude Code settings (Settings → MCP Servers → Gmail) before your first run.

---

## Claude.ai (browser)

**Requirements:** Claude.ai account · Gmail connected

1. Download **[`claude-web/jerbs.skill`](claude-web/jerbs.skill)**
2. Claude.ai → **Customize → Connectors → Gmail → Connect**
3. Claude.ai → **Customize → Skills → + → Create skill → Upload a skill** → upload `jerbs.skill`
4. New conversation → say **"set up jerbs"**

That's it. The setup wizard handles the rest.

---

## Local daemon (always-on, no browser needed)

**Requirements:** Python 3.11+ · Anthropic API key · Google Cloud project

```bash
git clone https://github.com/pjunod/jerbs.git
cd jerbs/claude-code
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
```

Set up Gmail API credentials → see [`docs/setup.md`](docs/setup.md)

```bash
python jerbs.py --setup   # first-time wizard
python jerbs.py           # start daemon
```

Full options and background service setup: [`docs/setup.md`](docs/setup.md)
