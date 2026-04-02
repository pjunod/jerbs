"""
export_html.py — Job Email Screener
Converts screener results JSON into a styled HTML results page.

Usage:
    python export_html.py <results_json_file> <output_html_file>

Or import and call:
    from export_html import export_to_html
    export_to_html(results, "results-2026-04-02.html")
"""

import json
import sys
from datetime import datetime
from html import escape

# ── Design tokens (shared with all output contexts) ─────────────────────────

COLORS = {
    "bg": "#0d1117",
    "surface": "#161b22",
    "border": "#30363d",
    "text": "#e6edf3",
    "text_muted": "#8b949e",
    "green": "#3fb950",
    "green_bg": "#12261e",
    "yellow": "#d29922",
    "yellow_bg": "#2a2013",
    "red": "#f85149",
    "red_bg": "#2d1214",
    "blue": "#58a6ff",
    "purple": "#bc8cff",
    "purple_bg": "#1c1a2e",
}

VERDICT_LABELS = {"pass": "Pass", "maybe": "Maybe", "fail": "Filtered"}
VERDICT_CSS_CLASS = {"pass": "pass", "maybe": "maybe", "fail": "fail"}
VERDICT_BADGE_CLASS = {
    "pass": "badge-pass",
    "maybe": "badge-maybe",
    "fail": "badge-fail",
}

SOURCE_LABELS = {
    "Job Alert Listings": "Job Alert",
    "Direct Outreach": "Direct",
    "LinkedIn DMs": "LinkedIn",
}

# ── CSS ──────────────────────────────────────────────────────────────────────

CSS = """\
:root {
  --bg: #0d1117; --surface: #161b22; --border: #30363d;
  --text: #e6edf3; --text-muted: #8b949e;
  --green: #3fb950; --green-bg: #12261e;
  --yellow: #d29922; --yellow-bg: #2a2013;
  --red: #f85149; --red-bg: #2d1214;
  --blue: #58a6ff; --purple: #bc8cff; --purple-bg: #1c1a2e;
}
.light {
  --bg: #ffffff; --surface: #f6f8fa; --border: #d0d7de;
  --text: #1f2328; --text-muted: #656d76;
  --green: #1a7f37; --green-bg: #dafbe1;
  --yellow: #9a6700; --yellow-bg: #fff8c5;
  --red: #cf222e; --red-bg: #ffebe9;
  --blue: #0969da; --purple: #8250df; --purple-bg: #fbefff;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.6;
  padding: 2rem; max-width: 1100px; margin: 0 auto;
}
h1 { font-size: 1.75rem; font-weight: 600; margin-bottom: 0.25rem; }
.top-bar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; }
.subtitle { color: var(--text-muted); font-size: 0.9rem; margin-bottom: 2rem; }
.mode-badge {
  display: inline-block; background: var(--surface); border: 1px solid var(--blue);
  color: var(--blue); padding: 0.15rem 0.6rem; border-radius: 1rem;
  font-size: 0.8rem; font-weight: 500; margin-left: 0.5rem; vertical-align: middle;
}
.theme-toggle {
  background: var(--surface); border: 1px solid var(--border); border-radius: 0.375rem;
  color: var(--text-muted); padding: 0.3rem 0.7rem; font-size: 0.8rem; cursor: pointer;
}
.theme-toggle:hover { color: var(--text); border-color: var(--text-muted); }
.stats { display: flex; gap: 1rem; margin-bottom: 2rem; flex-wrap: wrap; }
.stat {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 0.5rem; padding: 0.75rem 1.25rem; min-width: 120px;
}
.stat-num { font-size: 1.5rem; font-weight: 700; }
.stat-label {
  font-size: 0.8rem; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.05em;
}
.stat-num.green { color: var(--green); }
.stat-num.yellow { color: var(--yellow); }
.stat-num.red { color: var(--red); }
.stat-num.purple { color: var(--purple); }
.section { margin-bottom: 2.5rem; }
.section-header {
  font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.1em;
  color: var(--text-muted); border-bottom: 1px solid var(--border);
  padding-bottom: 0.5rem; margin-bottom: 1rem;
}
.action-banner {
  background: var(--purple-bg); border: 1px solid var(--purple);
  border-radius: 0.5rem; padding: 1rem 1.25rem; margin-bottom: 0.75rem;
}
.action-banner h3 { color: var(--purple); font-size: 0.95rem; margin-bottom: 0.35rem; }
.action-banner p { font-size: 0.9rem; color: var(--text); }
.action-banner a { color: var(--purple); }
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 0.5rem; padding: 1rem 1.25rem; margin-bottom: 0.75rem;
  border-left: 3px solid transparent; transition: border-color 0.15s;
}
.card:hover { border-color: var(--blue); }
.card.pass { border-left-color: var(--green); }
.card.maybe { border-left-color: var(--yellow); }
.card-top {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 1rem; flex-wrap: wrap;
}
.card h3 { font-size: 1rem; font-weight: 600; margin-bottom: 0.1rem; }
.card .location { color: var(--text-muted); font-size: 0.85rem; }
.badge {
  display: inline-block; padding: 0.1rem 0.5rem; border-radius: 1rem;
  font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.04em; white-space: nowrap;
}
.badge-pass { background: var(--green-bg); color: var(--green); border: 1px solid var(--green); }
.badge-maybe { background: var(--yellow-bg); color: var(--yellow); border: 1px solid var(--yellow); }
.badge-fail { background: var(--red-bg); color: var(--red); border: 1px solid var(--red); }
.badge-source {
  background: var(--surface); color: var(--text-muted); border: 1px solid var(--border);
  font-size: 0.7rem; padding: 0.05rem 0.4rem; margin-left: 0.4rem;
}
.card-body { margin-top: 0.5rem; font-size: 0.88rem; color: var(--text-muted); }
.card-body .reason { color: var(--text); margin-bottom: 0.35rem; }
.card-links { margin-top: 0.5rem; display: flex; gap: 1rem; flex-wrap: wrap; }
.card-links a { color: var(--blue); text-decoration: none; font-size: 0.85rem; }
.card-links a:hover { text-decoration: underline; }
.missing { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.35rem; }
.missing strong { color: var(--yellow); font-weight: 500; }
.comp-note {
  font-size: 0.8rem; padding: 0.25rem 0.5rem; background: var(--surface);
  border: 1px solid var(--border); border-radius: 0.25rem;
  display: inline-block; margin-top: 0.25rem;
}
.draft-block {
  margin-top: 0.5rem; padding: 0.75rem; background: var(--bg);
  border: 1px solid var(--border); border-radius: 0.35rem; font-size: 0.85rem;
}
.draft-block .draft-label { color: var(--blue); font-weight: 500; margin-bottom: 0.35rem; }
.draft-block .draft-label a { color: var(--blue); }
.draft-block .draft-text { color: var(--text-muted); white-space: pre-wrap; }
.sent-label { color: var(--green); font-weight: 500; margin-top: 0.5rem; }
.verdict-label { font-size: 0.9rem; font-weight: 600; margin-bottom: 0.75rem; }
.verdict-label.pass { color: var(--green); }
.verdict-label.maybe { color: var(--yellow); }
.fail-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.fail-table th {
  text-align: left; color: var(--text-muted); font-weight: 500;
  padding: 0.4rem 0.75rem; border-bottom: 1px solid var(--border);
  font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em;
}
.fail-table td {
  padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border);
  vertical-align: top;
}
.fail-table tr:last-child td { border-bottom: none; }
.fail-table .reason-col { color: var(--text-muted); }
.fail-table .blacklist { color: var(--red); }
details {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 0.5rem; overflow: hidden;
}
details summary {
  cursor: pointer; padding: 0.75rem 1rem; font-weight: 500;
  color: var(--text-muted); font-size: 0.9rem; list-style: none;
  display: flex; align-items: center; gap: 0.5rem;
}
details summary::before { content: '\\25b6'; font-size: 0.65rem; transition: transform 0.2s; }
details[open] summary::before { transform: rotate(90deg); }
details summary::-webkit-details-marker { display: none; }
details .fail-table { padding: 0 0.5rem 0.5rem; }
footer {
  margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--border);
  color: var(--text-muted); font-size: 0.8rem; text-align: center;
}"""

THEME_JS = """\
function toggleTheme(){
  document.body.classList.toggle('light');
  var btn=document.getElementById('theme-btn');
  btn.textContent=document.body.classList.contains('light')?'Dark':'Light';
}"""


# ── HTML builders ────────────────────────────────────────────────────────────


def _e(text):
    """Escape HTML entities."""
    return escape(str(text)) if text else ""


def _link(url, label):
    """Build an <a> tag if url is truthy, else return empty string."""
    if not url:
        return ""
    return f'<a href="{_e(url)}">{_e(label)}</a>'


def build_stats_html(counts, action_count=0):
    """Build the stat boxes row."""
    parts = [
        f'<div class="stat"><div class="stat-num green">{counts["pass"]}</div>'
        '<div class="stat-label">Interested</div></div>',
        f'<div class="stat"><div class="stat-num yellow">{counts["maybe"]}</div>'
        '<div class="stat-label">Maybe</div></div>',
        f'<div class="stat"><div class="stat-num red">{counts["fail"]}</div>'
        '<div class="stat-label">Filtered</div></div>',
    ]
    if action_count > 0:
        parts.append(
            f'<div class="stat"><div class="stat-num purple">{action_count}</div>'
            '<div class="stat-label">Action Needed</div></div>'
        )
    return '<div class="stats">' + "\n".join(parts) + "</div>"


def build_action_banner(action):
    """Build a purple action-needed banner."""
    title = _e(action.get("title", "Action Needed"))
    body = _e(action.get("body", ""))
    links_html = ""
    for link in action.get("links", []):
        links_html += f' <a href="{_e(link["url"])}">{_e(link["label"])}</a>'
    return (
        '<div class="action-banner">'
        f"<h3>{title}</h3>"
        f"<p>{body}</p>"
        f'<div class="card-links" style="margin-top: 0.5rem;">{links_html}</div>'
        "</div>"
    )


def build_card(item, verdict):
    """Build a result card for a pass or maybe item."""
    css_class = VERDICT_CSS_CLASS.get(verdict, "")
    badge_class = VERDICT_BADGE_CLASS.get(verdict, "badge-fail")
    badge_label = VERDICT_LABELS.get(verdict, verdict.title())

    company = _e(item.get("company", "Unknown"))
    role = _e(item.get("role", ""))
    location = _e(item.get("location", ""))
    reason = _e(item.get("reason", ""))
    comp = item.get("comp_assessment", "")
    missing = item.get("missing_fields") or []
    posting_url = item.get("posting_url", "")
    email_url = item.get("email_url", "")
    reply_draft = item.get("reply_draft", "")
    draft_url = item.get("draft_url", "")
    sent = item.get("sent", False)
    source = item.get("source", "")

    # Source badge
    source_badge = ""
    source_label = SOURCE_LABELS.get(source, source)
    if source_label:
        source_badge = f'<span class="badge badge-source">{_e(source_label)}</span>'

    links = []
    if posting_url:
        links.append(_link(posting_url, "View posting"))
    if email_url:
        links.append(_link(email_url, "View email"))
    links_html = " ".join(links)

    comp_html = f'<div class="comp-note">{_e(comp)}</div>' if comp else ""

    missing_html = ""
    if missing:
        missing_html = (
            f'<div class="missing"><strong>Missing:</strong> {_e(", ".join(missing))}</div>'
        )

    draft_html = ""
    if reply_draft and not sent:
        draft_label = _link(draft_url, "click to review &amp; send") if draft_url else "draft"
        draft_html = (
            '<div class="draft-block">'
            f'<div class="draft-label">Draft reply — {draft_label}</div>'
            f'<div class="draft-text">{_e(reply_draft)}</div>'
            "</div>"
        )
    elif reply_draft and sent:
        draft_html = (
            '<div class="sent-label">Sent — logged to correspondence log</div>'
            '<div class="draft-block">'
            f'<div class="draft-text">{_e(reply_draft)}</div>'
            "</div>"
        )

    return (
        f'<div class="card {css_class}">'
        '<div class="card-top">'
        f"<div><h3>{company} — {role}</h3>"
        f'<span class="location">{location}</span></div>'
        f'<div><span class="badge {badge_class}">{badge_label}</span>'
        f"{source_badge}</div>"
        "</div>"
        '<div class="card-body">'
        f'<div class="reason">{reason}</div>'
        f"{comp_html}{missing_html}{draft_html}"
        "</div>"
        f'<div class="card-links">{links_html}</div>'
        "</div>"
    )


def build_fail_row(item):
    """Build a single <tr> for a filtered item."""
    company = _e(item.get("company", ""))
    role = _e(item.get("role", ""))
    location = _e(item.get("location", ""))
    reason = _e(item.get("reason", ""))
    dealbreaker = item.get("dealbreaker") or ""
    email_url = item.get("email_url", "")
    source = item.get("source", "")
    source_label = SOURCE_LABELS.get(source, source)

    company_cell = _link(email_url, company) if email_url else company
    reason_class = "reason-col blacklist" if "blacklist" in dealbreaker.lower() else "reason-col"
    return (
        f"<tr><td>{company_cell}</td><td>{role}</td>"
        f"<td>{location}</td><td>{_e(source_label)}</td>"
        f'<td class="{reason_class}">{reason}</td></tr>'
    )


def build_fail_table(items):
    """Build the collapsible table for filtered items."""
    rows = [build_fail_row(item) for item in items]
    return (
        '<table class="fail-table"><thead>'
        "<tr><th>Company</th><th>Role</th><th>Location</th>"
        "<th>Source</th><th>Reason</th></tr>"
        "</thead><tbody>" + "\n".join(rows) + "</tbody></table>"
    )


# ── Main export ──────────────────────────────────────────────────────────────


def export_to_html(results_data, output_path):
    """Generate a self-contained HTML results page."""
    run_date = results_data.get("run_date", datetime.today().strftime("%Y-%m-%d"))
    profile_name = results_data.get("profile_name", "Job Search")
    mode = results_data.get("mode", "dry-run")
    lookback = results_data.get("lookback_days", "1")
    actions = results_data.get("actions", [])
    results = results_data.get("results", [])

    # Group by verdict (single integrated list — no per-source sections)
    passes = [r for r in results if r.get("verdict") == "pass"]
    maybes = [r for r in results if r.get("verdict") == "maybe"]
    fails = [r for r in results if r.get("verdict") == "fail"]
    counts = {"pass": len(passes), "maybe": len(maybes), "fail": len(fails)}

    mode_label = "Dry-run" if mode == "dry-run" else "Send mode"

    parts = [
        "<!DOCTYPE html>",
        '<html lang="en"><head>',
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        f"<title>Jerbs Results — {_e(run_date)}</title>",
        f"<style>{CSS}</style>",
        f"<script>{THEME_JS}</script>",
        "</head><body>",
        '<div class="top-bar">',
        f'<h1>Jerbs Results <span class="mode-badge">{_e(mode_label)}</span></h1>',
        '<button class="theme-toggle" id="theme-btn" onclick="toggleTheme()">Light</button>',
        "</div>",
        f'<p class="subtitle">{_e(run_date)} &middot; {_e(str(lookback))}-day'
        f" lookback &middot; {_e(profile_name)}</p>",
        build_stats_html(counts, len(actions)),
    ]

    # Action banners first — most important
    if actions:
        parts.append('<div class="section">')
        parts.append('<div class="section-header">Action Needed</div>')
        for action in actions:
            parts.append(build_action_banner(action))
        parts.append("</div>")

    # Results section — all sources integrated
    parts.append('<div class="section">')
    parts.append('<div class="section-header">Results</div>')

    if passes:
        parts.append('<div class="verdict-label pass">Interested</div>')
        for item in passes:
            parts.append(build_card(item, "pass"))

    if maybes:
        parts.append('<div class="verdict-label maybe" style="margin-top: 1.5rem;">Maybe</div>')
        for item in maybes:
            parts.append(build_card(item, "maybe"))

    if fails:
        parts.append('<div style="margin-top: 1.5rem;">')
        parts.append("<details>")
        parts.append(f"<summary>Filtered out &middot; {len(fails)} listings</summary>")
        parts.append(build_fail_table(fails))
        parts.append("</details></div>")

    parts.append("</div>")  # close results section

    parts.append(
        f"<footer>Generated by jerbs &middot; {_e(run_date)}"
        f" &middot; {_e(mode_label)} mode</footer>"
    )
    parts.append("</body></html>")

    html = "\n".join(parts)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    total = sum(counts.values())
    print(f"Exported {total} results → {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python export_html.py <results.json> <output.html>")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
    export_to_html(data, sys.argv[2])
