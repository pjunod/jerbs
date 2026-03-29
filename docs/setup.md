# Setup guide

## Claude.ai version

The Claude.ai version requires no local installation. Everything runs in your browser via Claude's MCP connector system.

### Requirements
- Claude.ai account (Pro or above recommended for higher message limits)
- Gmail connected in Claude.ai Settings → Connectors

### Install
1. Download `claude-ai/jerbs.skill`
2. In Claude.ai, go to Settings → Skills → Install from file
3. Upload the `.skill` file
4. Go to Settings → Connectors → Gmail → Connect
5. Start a new conversation and say: "set up jerbs"

### First run
The wizard will walk you through configuring your criteria. After setup, say "run jerbs" or "check my job emails" to start screening. Use the scheduler widget to automate.

---

## Local daemon version

### Requirements
- Python 3.11 or later
- Anthropic API key ($5 in free credits for new accounts, or pay-as-you-go)
- Google Cloud project with Gmail API enabled (free)

### Step 1 — Python setup

```bash
git clone https://github.com/pjunod/jerbs.git
cd jerbs/claude-code
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2 — Anthropic API key

1. Go to https://console.anthropic.com/
2. Create an API key
3. Export it:

```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

Add to `~/.zshrc` or `~/.bashrc` to persist across sessions.

Typical cost: screening 20 emails uses about $0.01–$0.03 per run depending on email length.

### Step 3 — Gmail API setup

jerbs needs read access to your Gmail (and optionally send access if you enable `--send`).

1. Go to https://console.cloud.google.com/
2. Create a new project (e.g. "jerbs")
3. Search for "Gmail API" in the search bar → Enable it
4. Go to APIs & Services → OAuth consent screen
   - User type: External
   - Fill in app name ("jerbs"), your email
   - Scopes: add `gmail.readonly` (and `gmail.send` if you want auto-send)
   - Add your email as a test user
5. Go to APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: Desktop app
   - Name: "jerbs"
6. Download the JSON file
7. Move it to `~/.jerbs/credentials.json`:

```bash
mkdir -p ~/.jerbs
mv ~/Downloads/client_secret_*.json ~/.jerbs/credentials.json
```

On first run, jerbs opens a browser window for you to authorize. After that, credentials are cached and refreshed automatically.

### Step 4 — Configure criteria

```bash
python jerbs.py --setup
```

This asks you a series of questions and saves your criteria to `~/.jerbs/criteria.json`.

### Step 5 — Test run

```bash
python jerbs.py --once
```

This runs a single screen and prints results. Check that it's finding and correctly screening your emails.

### Step 6 — Start the daemon

```bash
python jerbs.py
```

The daemon runs continuously, logging to stdout and `~/.jerbs/jerbs.log`. Stop it with `Ctrl+C`.

---

## Running as a system service

See the README for launchd (macOS) and systemd (Linux) configuration.

---

## Troubleshooting

**`FileNotFoundError: Gmail credentials not found`**
→ Make sure `~/.jerbs/credentials.json` exists. Re-download from Google Cloud Console.

**`Token has been expired or revoked`**
→ Delete `~/.jerbs/gmail_token.json` and re-run. A browser window will open to re-authorize.

**`anthropic.AuthenticationError`**
→ Check that `ANTHROPIC_API_KEY` is set correctly: `echo $ANTHROPIC_API_KEY`

**Emails not appearing in results**
→ The first run looks back 7 days. Subsequent runs only look back 1 day. If you want to re-scan old emails, clear `screened_message_ids` in your criteria file.

**`zoneinfo.ZoneInfoNotFoundError`**
→ Install the timezone database: `pip install tzdata`
