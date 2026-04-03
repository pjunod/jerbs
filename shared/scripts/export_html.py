"""
export_html.py — Job Email Screener
Converts screener results JSON into a styled HTML results page.

Supports two themes:
  - "cards"    — clean card-based layout with light/dark toggle
  - "terminal" — IBM Plex Mono, CRT scanlines, expandable cards, filter bar

Usage:
    python export_html.py <results_json_file> <output_html_file> [--theme terminal]

Or import and call:
    from export_html import export_to_html
    export_to_html(results, "results-2026-04-02.html", theme="terminal")
"""

import json
import sys
from datetime import datetime, timedelta
from html import escape
from pathlib import Path

# ── Shared constants ─────────────────────────────────────────────────────────

VERDICT_LABELS = {"pass": "Interested", "maybe": "Maybe", "fail": "Filtered"}
VERDICT_CSS_CLASS = {"pass": "pass", "maybe": "maybe", "fail": "fail"}
VERDICT_BADGE_CLASS = {
    "pass": "badge-pass",
    "maybe": "badge-maybe",
    "fail": "badge-fail",
}

SOURCE_LABELS = {
    "Job Alert Listings": "Job Digest Postings",
    "Direct Outreach": "Direct Outreach",
    "LinkedIn DMs": "LinkedIn",
}

SOURCE_ORDER = ["Direct Outreach", "Job Alert Listings", "LinkedIn DMs"]

THEMES = ("cards", "terminal")
DEFAULT_THEME = "terminal"


# ── HTML helpers ─────────────────────────────────────────────────────────────


def _e(text):
    """Escape HTML entities."""
    return escape(str(text)) if text else ""


def _link(url, label):
    """Build an <a> tag if url is truthy, else return empty string."""
    if not url:
        return ""
    return f'<a href="{_e(url)}">{_e(label)}</a>'


def _group_by_source(items):
    """Group results by source in SOURCE_ORDER, returning [(source, items)]."""
    by_source = {}
    for item in items:
        src = item.get("source", "Other")
        by_source.setdefault(src, []).append(item)
    ordered = []
    for src in SOURCE_ORDER:
        if src in by_source:
            ordered.append((src, by_source.pop(src)))
    for src, group in by_source.items():
        ordered.append((src, group))
    return ordered


def _parse_date(date_str):
    """Parse a date string (YYYY-MM-DD or ISO format) into a datetime, or None."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _age_days(date_str, run_date_str=None):
    """Return the number of days between date_str and run_date (or today)."""
    dt = _parse_date(date_str)
    if dt is None:
        return None
    ref = _parse_date(run_date_str) or datetime.today()
    delta = (ref - dt).days
    return delta if delta >= 0 else None


def _age_label(days):
    """Return a human-readable age label from a day count."""
    if days is None:
        return ""
    if days == 0:
        return "today"
    if days == 1:
        return "1d ago"
    if days <= _PRUNE_DAYS:
        return f"{days}d ago"
    if days < 30:
        return f"{days // 7}w ago"
    return f"{days // 30}mo ago"


_PRUNE_DAYS = 14  # pending results pruned after this many days


def _age_color(days):
    """Return an HSL color string for the age badge.

    Gradient from green (0 days) → red (PRUNE_DAYS), clamped.
    Hue 120 = green, 60 = yellow, 0 = red.
    """
    if days is None:
        return None
    t = min(max(days / _PRUNE_DAYS, 0.0), 1.0)
    hue = 120 * (1 - t)
    return f"hsl({hue:.0f}, 70%, 42%)"


_AGE_BADGE_WIDTH = "58px"


def _age_badge_html(date_str, run_date_str=None, is_new=False):
    """Build a complete age badge <span> with gradient color, or empty string."""
    w = _AGE_BADGE_WIDTH
    if is_new:
        return (
            f' <span class="age-badge"'
            f' style="color:#58a6ff;border-color:#58a6ff;'
            f'min-width:{w};width:{w}">'
            f"new</span>"
        )
    days = _age_days(date_str, run_date_str)
    label = _age_label(days)
    if not label:
        return ""
    color = _age_color(days)
    color_style = f"color:{color};border-color:{color};" if color else ""
    return (
        f' <span class="age-badge" style="{color_style}min-width:{w};width:{w}">{_e(label)}</span>'
    )


def _sort_by_date_desc(items, run_date_str=None):
    """Sort items by email_date (or added_at) descending — newest first."""

    def sort_key(item):
        date_str = item.get("email_date") or item.get("added_at") or ""
        dt = _parse_date(date_str)
        if dt is None:
            return datetime.min
        return dt

    return sorted(items, key=sort_key, reverse=True)


def _build_persistence_summary(results_data):
    """Build an HTML block summarizing persistence activity for the run."""
    stats = results_data.get("persistence_stats", {})
    if not stats:
        return ""

    lines = []
    merged = stats.get("pending_merged", 0)
    if merged:
        lines.append(
            f"Merged {merged} pending result{'s' if merged != 1 else ''} from previous runs"
        )
    responses = stats.get("responses_found", 0)
    if responses:
        lines.append(
            f"Found {responses} recruiter response{'s' if responses != 1 else ''} to prior replies"
        )
    pruned_ids = stats.get("screened_ids_pruned", 0)
    if pruned_ids:
        lines.append(f"Pruned {pruned_ids} stale screening record{'s' if pruned_ids != 1 else ''}")
    pruned_corr = stats.get("correspondence_pruned", 0)
    if pruned_corr:
        lines.append(
            f"Pruned {pruned_corr} closed correspondence entr{'ies' if pruned_corr != 1 else 'y'}"
        )
    pending_total = stats.get("pending_total", 0)
    if pending_total and not merged:
        lines.append(
            f"{pending_total} pending result{'s' if pending_total != 1 else ''} carried forward"
        )

    if not lines:
        return ""

    items_html = "".join(f"<li>{_e(line)}</li>" for line in lines)
    return (
        '<div class="persistence-summary">'
        '<div class="persistence-label">Session activity</div>'
        f"<ul>{items_html}</ul></div>"
    )


# ── Cards theme CSS ──────────────────────────────────────────────────────────

CSS_CARDS = """\
:root {
  --bg: #0d1117; --surface: #161b22; --border: #30363d;
  --text: #e6edf3; --text-muted: #8b949e;
  --green: #3fb950; --green-bg: #12261e;
  --yellow: #d29922; --yellow-bg: #2a2013;
  --red: #f85149; --red-bg: #2d1214;
  --blue: #58a6ff; --purple: #bc8cff; --purple-bg: #1c1a2e;
  --accent: #58a6ff;
}
body.light {
  --bg: #ffffff; --surface: #f6f8fa; --border: #d0d7de;
  --text: #1f2328; --text-muted: #57606a; --accent: #0969da;
  --green: #1a7f37; --green-bg: #dafbe1;
  --yellow: #7d5600; --yellow-bg: #fff8c5;
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
.top-bar { display: flex; justify-content: space-between; align-items: center;
  flex-wrap: wrap; gap: 0.5rem; }
.subtitle { color: var(--text-muted); font-size: 0.9rem; margin-bottom: 2rem; }
.mode-badge {
  display: inline-block; background: var(--surface); border: 1px solid var(--blue);
  color: var(--blue); padding: 0.15rem 0.6rem; border-radius: 1rem;
  font-size: 0.8rem; font-weight: 500; margin-left: 0.5rem; vertical-align: middle;
}
.theme-toggle, .theme-select {
  background: var(--surface); border: 1px solid var(--border); border-radius: 0.375rem;
  color: var(--text-muted); padding: 0.3rem 0.7rem; font-size: 0.8rem; cursor: pointer;
}
.theme-toggle:hover, .theme-select:hover {
  color: var(--text); border-color: var(--text-muted); }
.stats { display: flex; gap: 1rem; margin-bottom: 2rem; flex-wrap: wrap; }
.stat {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 0.5rem; padding: 0.75rem 1.25rem; min-width: 120px;
}
.stat-num { font-size: 1.5rem; font-weight: 700; }
.stat-label { font-size: 0.8rem; color: var(--text-muted);
  text-transform: uppercase; letter-spacing: 0.05em; }
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
.section-toggle {
  font-size: 0.75rem; color: var(--text-muted); background: none;
  border: 1px solid var(--border); padding: 0.2rem 0.6rem; border-radius: 0.3rem;
  cursor: pointer; margin-left: auto; text-transform: lowercase;
}
.section-toggle:hover { color: var(--accent); border-color: var(--accent); }
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
.card.viewed { opacity: 0.6; }
.card.viewed:hover { opacity: 0.85; }
.card.viewed .badge-pass,
.card.viewed .badge-maybe,
.card.viewed .badge-fail { opacity: 0.4; }
.card-top { display: flex; justify-content: space-between; align-items: flex-start;
  gap: 1rem; flex-wrap: wrap; }
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
.card-body { margin-top: 0.5rem; font-size: 0.88rem; color: var(--text); opacity: 0.9; }
.card-field {
  margin-bottom: 0.4rem; padding: 0.5rem 0.65rem; border-radius: 0.3rem;
  border-left: 3px solid var(--border);
}
.pass .card-field { background: var(--green-bg); border-left-color: var(--green); }
.maybe .card-field { background: var(--yellow-bg); border-left-color: var(--yellow); }
.card-field-label {
  font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--text-muted); margin-bottom: 0.15rem;
}
.card-body .reason { color: var(--text); }
.card-links { margin-top: 0.5rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }
.card-links a {
  color: var(--blue); text-decoration: none; font-size: 0.85rem; font-weight: 500;
  padding: 0.35rem 0.8rem; border: 1px solid var(--blue); border-radius: 0.375rem;
  background: transparent; transition: background 0.15s, color 0.15s;
  display: inline-flex; align-items: center; min-height: 36px;
}
.card-links a:hover { background: var(--blue); color: #fff; text-decoration: none; }
.missing { font-size: 0.8rem; color: var(--text-muted); margin-top: 0.35rem; }
.missing strong { color: var(--yellow); font-weight: 500; }
.comp-note {
  font-size: 0.8rem; padding: 0.25rem 0.5rem; background: var(--surface);
  border: 1px solid var(--border); border-radius: 0.25rem;
  display: inline-block; margin-top: 0.25rem; color: var(--text);
}
.draft-block {
  margin-top: 0.5rem; padding: 0.75rem; background: var(--bg);
  border: 1px solid var(--border); border-radius: 0.35rem; font-size: 0.85rem;
}
.draft-block .draft-label { color: var(--blue); font-weight: 500; margin-bottom: 0.35rem; }
.draft-block .draft-text { color: var(--text); white-space: pre-wrap; opacity: 0.85; }
.draft-send-btn {
  display: inline-block; margin-top: 0.5rem; padding: 0.4rem 1rem;
  font-size: 0.8rem; font-weight: 600; color: #fff; background: var(--blue);
  border: none; border-radius: 0.375rem; text-decoration: none;
  cursor: pointer; transition: background 0.15s;
}
.draft-send-btn:hover { opacity: 0.85; }
.sent-label { color: var(--green); font-weight: 500; margin-top: 0.5rem; }
.verdict-label { font-size: 0.9rem; font-weight: 600; margin-bottom: 0.75rem; }
.verdict-label.pass { color: var(--green); }
.verdict-label.maybe { color: var(--yellow); }
.age-badge {
  display: inline-block; font-size: 0.7rem;
  background: transparent; border: 1px solid;
  padding: 0.05rem 0; border-radius: 0.8rem; white-space: nowrap;
  flex-shrink: 0; text-align: center; box-sizing: border-box;
}
.persistence-summary {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 0.5rem; padding: 0.75rem 1.25rem;
  margin-bottom: 1.5rem; font-size: 0.85rem;
}
.persistence-summary .persistence-label {
  font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--text-muted);
  margin-bottom: 0.35rem;
}
.persistence-summary ul {
  list-style: none; padding: 0; margin: 0;
  color: var(--text-muted);
}
.persistence-summary li::before {
  content: '\\b7 '; color: var(--text-muted);
}
.fail-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.fail-table th {
  text-align: left; color: var(--text-muted); font-weight: 500;
  padding: 0.4rem 0.75rem; border-bottom: 1px solid var(--border);
  font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em;
}
.fail-table td { padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border);
  vertical-align: top; }
.fail-table tr:last-child td { border-bottom: none; }
.fail-table .reason-col { color: var(--text-muted); }
.fail-table .blacklist { color: var(--red); }
.fail-table a {
  color: var(--blue); text-decoration: none; font-weight: 500;
  padding: 0.2rem 0.5rem; border: 1px solid var(--blue); border-radius: 0.25rem;
  transition: background 0.15s, color 0.15s;
}
.fail-table a:hover { background: var(--blue); color: #fff; }
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
.source-group {
  background: transparent; border: none; margin-bottom: 1.5rem;
}
.source-group > summary {
  font-size: 1.05rem; font-weight: 600; color: var(--text);
  padding: 0.5rem 0; border-bottom: 1px solid var(--border); margin-bottom: 0.75rem;
}
.verdict-group {
  background: transparent; border: none; margin-bottom: 0.75rem;
  margin-left: 0.5rem;
}
.verdict-group > summary {
  font-size: 0.85rem; font-weight: 600; padding: 0.4rem 0.5rem;
  border-radius: 0.3rem; margin-bottom: 0.5rem;
}
.verdict-group.interested > summary { color: var(--green); }
.verdict-group.maybe > summary { color: var(--yellow); }
.verdict-toggle {
  font-size: 0.7rem; color: var(--text-muted); background: none;
  border: 1px solid var(--border); padding: 0.15rem 0.5rem; border-radius: 0.25rem;
  cursor: pointer; margin-left: auto; text-transform: lowercase;
}
.verdict-toggle:hover { color: var(--accent); border-color: var(--accent); }
footer {
  margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--border);
  color: var(--text-muted); font-size: 0.8rem; text-align: center;
}
.dl-btn {
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text-muted); font-size: 0.8rem; padding: 0.4rem 0.8rem;
  border-radius: 0.4rem; cursor: pointer; transition: color 0.15s, border-color 0.15s;
}
.dl-btn:hover { color: var(--accent); border-color: var(--accent); }
.filter-bar {
  display: flex; gap: 0.5rem; flex-wrap: wrap; align-items: center;
  margin-bottom: 1.5rem;
}
.filter-label { font-size: 0.8rem; color: var(--text-muted); font-weight: 500; }
.filter-btn {
  font-size: 0.8rem; padding: 0.3rem 0.7rem; border-radius: 0.375rem;
  border: 1px solid var(--border); background: var(--surface);
  color: var(--text-muted); cursor: pointer; transition: all 0.15s;
}
.filter-btn:hover { border-color: var(--accent); color: var(--accent); }
.filter-btn.active-all { border-color: var(--text-muted); color: var(--text);
  background: var(--surface); }
.filter-btn.active-blue { border-color: var(--blue); color: var(--blue); }
.filter-btn.active-green { border-color: var(--green); color: var(--green); }
.filter-btn.active-amber { border-color: var(--yellow); color: var(--yellow); }
.filter-btn.active-red { border-color: var(--red); color: var(--red); }
.card.hidden, .filtered-item.hidden { display: none; }
@media (max-width: 700px) {
  body { padding: 1rem; }
  h1 { font-size: 1.35rem; }
  .top-bar { flex-direction: column; gap: 0.75rem; }
  .stats { gap: 0.5rem; }
  .stat { min-width: 0; flex: 1; padding: 0.6rem 0.75rem; }
  .stat-num { font-size: 1.25rem; }
  .card { padding: 0.85rem 1rem; }
  .card h3 { font-size: 0.95rem; }
  .card-top { flex-direction: column; gap: 0.5rem; }
  .card-links { flex-direction: column; }
  .card-links a { min-height: 44px; display: inline-flex; align-items: center;
    font-size: 0.9rem; }
  .draft-send-btn { min-height: 44px; padding: 0.5rem 1.2rem; font-size: 0.85rem; }
  .theme-toggle, .dl-btn { min-height: 44px; padding: 0.4rem 0.8rem;
    display: inline-flex; align-items: center; }
  .fail-table { font-size: 0.8rem; display: block; overflow-x: auto;
    -webkit-overflow-scrolling: touch; }
  .fail-table th, .fail-table td { padding: 0.4rem 0.5rem; white-space: nowrap; }
  details summary { min-height: 44px; }
  .action-banner { flex-direction: column; gap: 0.5rem; }
  footer { flex-direction: column; gap: 0.5rem; text-align: center; }
}
@media (max-width: 400px) {
  body { padding: 0.75rem; }
  h1 { font-size: 1.2rem; }
  .stats { flex-direction: column; }
  .stat { padding: 0.5rem 0.6rem; }
  .card { padding: 0.7rem 0.8rem; }
}"""

# ── Terminal theme CSS ───────────────────────────────────────────────────────

CSS_TERMINAL = """\
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');
:root {
  --bg:#0b0d0f; --bg2:#111418; --bg3:#181c22;
  --border:#1e2530; --border2:#252d38;
  --green:#2dff9b; --green-dim:#1a9960; --green-bg:rgba(45,255,155,0.06);
  --amber:#ffb340; --amber-dim:#9a6a1a; --amber-bg:rgba(255,179,64,0.06);
  --red:#ff4d4d; --red-dim:#7a2020; --red-bg:rgba(255,77,77,0.06);
  --blue:#3d9eff; --blue-bg:rgba(61,158,255,0.08);
  --purple:#bc8cff; --purple-bg:rgba(188,140,255,0.08);
  --text:#d4dae4; --text-dim:#8b95a5; --text-muted:#5a6577;
  --mono:'IBM Plex Mono',monospace; --sans:'IBM Plex Sans',sans-serif;
}
body.light{
  --bg:#f5f6f8; --bg2:#ffffff; --bg3:#ebedf0;
  --border:#d0d4dc; --border2:#bcc2cc;
  --green:#0e8a4f; --green-dim:#0e8a4f; --green-bg:rgba(14,138,79,0.08);
  --amber:#a06800; --amber-dim:#a06800; --amber-bg:rgba(160,104,0,0.08);
  --red:#cc3333; --red-dim:#cc3333; --red-bg:rgba(204,51,51,0.06);
  --blue:#1a6dd4; --blue-bg:rgba(26,109,212,0.08);
  --purple:#7c3aed; --purple-bg:rgba(124,58,237,0.08);
  --text:#1a1d23; --text-dim:#4a5568; --text-muted:#6b7280;
}
body.light::before{display:none;}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:var(--sans);
  font-size:14px;line-height:1.6;min-height:100vh;}
body::before{content:'';position:fixed;inset:0;
  background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,0,0,0.08) 2px,rgba(0,0,0,0.08) 4px);
  pointer-events:none;z-index:1000;}
.header{border-bottom:1px solid var(--border);padding:28px 40px 24px;
  display:flex;align-items:flex-start;justify-content:space-between;gap:20px;flex-wrap:wrap;}
.logo{font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:0.18em;
  text-transform:uppercase;color:var(--green);margin-bottom:4px;display:flex;align-items:center;gap:8px;}
.logo::before{content:'>';color:var(--green-dim);}
.run-title{font-family:var(--mono);font-size:22px;font-weight:500;letter-spacing:-0.02em;}
.run-meta{font-family:var(--mono);font-size:11px;color:var(--text-dim);margin-top:6px;
  display:flex;gap:20px;flex-wrap:wrap;}
.run-meta span{display:flex;align-items:center;gap:5px;}
.run-meta span::before{content:'\\b7';color:var(--text-muted);}
.run-meta span:first-child::before{display:none;}
.stats-pills{display:flex;gap:8px;flex-wrap:wrap;align-items:center;}
.pill{font-family:var(--mono);font-size:11px;font-weight:600;padding:6px 14px;
  border-radius:4px;letter-spacing:0.05em;display:flex;align-items:center;gap:6px;}
.pill-green{background:var(--green-bg);color:var(--green);border:1px solid rgba(45,255,155,0.2);}
.pill-amber{background:var(--amber-bg);color:var(--amber);border:1px solid rgba(255,179,64,0.2);}
.pill-red{background:var(--red-bg);color:var(--red);border:1px solid rgba(255,77,77,0.15);}
.pill-num{font-size:16px;font-weight:300;}
.filter-bar{padding:14px 40px;border-bottom:1px solid var(--border);
  display:flex;gap:6px;flex-wrap:wrap;align-items:center;}
.filter-label{font-family:var(--mono);font-size:10px;color:var(--text-muted);
  letter-spacing:0.1em;text-transform:uppercase;margin-right:4px;}
.filter-btn{font-family:var(--mono);font-size:11px;padding:5px 12px;border-radius:3px;
  border:1px solid var(--border2);background:transparent;color:var(--text-dim);
  cursor:pointer;transition:all 0.15s;letter-spacing:0.04em;}
.filter-btn:hover{border-color:var(--blue);color:var(--blue);}
.filter-btn.active-all{border-color:var(--text-dim);color:var(--text);background:var(--bg3);}
.filter-btn.active-blue{border-color:var(--blue);color:var(--blue);background:var(--blue-bg,rgba(88,166,255,0.08));}
.filter-btn.active-green{border-color:var(--green);color:var(--green);background:var(--green-bg);}
.filter-btn.active-amber{border-color:var(--amber);color:var(--amber);background:var(--amber-bg);}
.filter-btn.active-red{border-color:var(--red);color:var(--red);background:var(--red-bg);}
.theme-select{font-family:var(--mono);font-size:11px;padding:5px 12px;border-radius:3px;
  border:1px solid var(--border2);background:var(--bg3);color:var(--text-dim);cursor:pointer;}
.main{padding:32px 40px 60px;max-width:1100px;}
.section-label{font-family:var(--mono);font-size:11px;font-weight:600;letter-spacing:0.1em;
  text-transform:uppercase;margin:28px 0 12px;display:flex;align-items:center;gap:8px;}
.section-toggle{font-family:var(--mono);font-size:10px;color:var(--text-dim);
  background:none;border:1px solid var(--border2);padding:2px 8px;border-radius:3px;
  cursor:pointer;letter-spacing:0.04em;margin-left:auto;text-transform:lowercase;}
.section-toggle:hover{color:var(--text);border-color:var(--text-dim);}
.section-label.interested{color:var(--green);}
.section-label.maybe{color:var(--amber);}
.section-label.filtered{color:var(--red-dim);}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:6px;
  margin-bottom:10px;overflow:hidden;transition:border-color 0.15s;}
.card:hover{border-color:var(--border2);}
.card.pass{border-left:3px solid var(--green-dim);}
.card.maybe{border-left:3px solid var(--amber-dim);}
.card.fail{border-left:3px solid var(--red-dim);opacity:0.7;}
.card-header{padding:14px 18px 12px;display:flex;align-items:flex-start;gap:14px;
  cursor:pointer;user-select:none;}
.verdict-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;margin-top:5px;
  transition:opacity 0.4s,box-shadow 0.4s;}
.pass .verdict-dot{background:var(--green);box-shadow:0 0 6px var(--green);}
.maybe .verdict-dot{background:var(--amber);box-shadow:0 0 6px var(--amber);}
.fail .verdict-dot{background:var(--red-dim);}
.card.viewed .verdict-dot{opacity:0.2;box-shadow:none;}
.card-main{flex:1;min-width:0;}
.card-title-row{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:4px;}
.company{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--text-dim);
  letter-spacing:0.04em;text-transform:uppercase;}
.role{font-weight:500;font-size:14px;}
.card-meta{font-family:var(--mono);font-size:11px;color:var(--text-dim);display:flex;gap:16px;flex-wrap:wrap;}
.card-right{display:flex;flex-direction:column;align-items:center;
  justify-content:space-between;flex-shrink:0;gap:6px;}
.card-toggle{font-family:var(--mono);font-size:16px;color:var(--text-muted);flex-shrink:0;
  transition:transform 0.2s;}
.card.open .card-toggle{transform:rotate(90deg);}
.card-body{display:none;padding:0 18px 16px 40px;border-top:1px solid var(--border);}
.card.open .card-body{display:block;}
.body-row{margin-top:12px;font-size:13px;line-height:1.65;}
.body-label{font-family:var(--mono);font-size:10px;letter-spacing:0.12em;
  text-transform:uppercase;color:var(--text-dim);margin-bottom:4px;}
.body-verdict{background:rgba(255,255,255,0.04);border-left:3px solid var(--border2);
  padding:10px 14px;border-radius:0 4px 4px 0;font-size:13px;line-height:1.6;color:var(--text);}
.pass .body-verdict{border-left-color:var(--green);background:rgba(45,255,155,0.05);}
.maybe .body-verdict{border-left-color:var(--amber);background:rgba(255,179,64,0.05);}
.missing-tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:4px;}
.missing-tag{font-family:var(--mono);font-size:10px;background:rgba(255,179,64,0.08);
  border:1px solid rgba(255,179,64,0.2);color:var(--amber);border-radius:3px;
  padding:2px 8px;letter-spacing:0.04em;}
.links-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;}
.link-btn{font-family:var(--mono);font-size:11px;padding:5px 12px;border-radius:3px;
  border:1px solid var(--border2);background:var(--bg3);color:var(--blue);
  text-decoration:none;transition:all 0.15s;letter-spacing:0.04em;}
.link-btn:hover{border-color:var(--blue);background:var(--blue-bg);}
.filtered-list{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:24px;}
.filtered-item{background:var(--bg2);border:1px solid var(--border);border-left:3px solid var(--red-dim);
  border-radius:4px;padding:9px 14px;display:flex;align-items:flex-start;gap:10px;opacity:0.65;}
.fi-dot{width:6px;height:6px;border-radius:50%;background:var(--red-dim);flex-shrink:0;margin-top:5px;}
.fi-name{font-size:12.5px;font-weight:500;opacity:0.8;}
.fi-reason{font-family:var(--mono);font-size:10px;color:var(--text-dim);margin-top:2px;}
.callout{background:var(--amber-bg);border:1px solid rgba(255,179,64,0.25);
  border-radius:6px;padding:16px 20px;margin-bottom:10px;display:flex;gap:14px;align-items:flex-start;}
.callout-title{font-family:var(--mono);font-size:11px;font-weight:600;color:var(--amber);
  letter-spacing:0.08em;text-transform:uppercase;margin-bottom:4px;}
.callout-body{font-size:13px;line-height:1.6;}
.callout-body a{color:var(--blue);text-decoration:none;}
.callout-body a:hover{text-decoration:underline;}
.action-banner{background:var(--purple-bg);border:1px solid var(--purple);
  border-radius:6px;padding:16px 20px;margin-bottom:10px;display:flex;gap:14px;align-items:flex-start;}
.action-banner h3{font-family:var(--mono);font-size:11px;font-weight:600;color:var(--purple);
  letter-spacing:0.08em;text-transform:uppercase;margin-bottom:4px;}
.action-banner p{font-size:13px;line-height:1.6;}
.action-banner a{font-family:var(--mono);font-size:11px;padding:5px 12px;border-radius:3px;
  border:1px solid var(--border2);background:var(--bg3);color:var(--blue);
  text-decoration:none;transition:all 0.15s;letter-spacing:0.04em;
  display:inline-flex;align-items:center;white-space:nowrap;}
.action-banner a:hover{border-color:var(--blue);background:var(--blue-bg);}
.draft-block{margin-top:10px;background:var(--bg3);border-left:2px solid var(--blue);
  padding:10px 14px;border-radius:0 4px 4px 0;font-size:12px;}
.draft-block .draft-label{font-family:var(--mono);font-size:10px;color:var(--blue);
  letter-spacing:0.08em;text-transform:uppercase;margin-bottom:4px;}
.draft-block .draft-text{color:var(--text);opacity:0.85;white-space:pre-wrap;font-family:var(--mono);font-size:12px;}
.draft-send-btn{display:inline-block;margin-top:10px;padding:7px 16px;font-family:var(--mono);
  font-size:11px;font-weight:600;letter-spacing:0.04em;color:#fff;background:var(--blue);
  border:none;border-radius:4px;text-decoration:none;cursor:pointer;transition:background 0.15s;}
.draft-send-btn:hover{background:#2b88e6;}
.sent-label{font-family:var(--mono);font-size:10px;color:var(--green);letter-spacing:0.08em;
  text-transform:uppercase;margin-top:10px;margin-bottom:4px;}
.age-badge{font-family:var(--mono);font-size:10px;
  background:transparent;border:1px solid;padding:1px 0;
  border-radius:8px;white-space:nowrap;flex-shrink:0;align-self:center;
  text-align:center;box-sizing:border-box;}
.persistence-summary{background:var(--bg2);border:1px solid var(--border);
  border-radius:6px;padding:14px 20px;margin-bottom:20px;
  font-family:var(--mono);font-size:11px;}
.persistence-summary .persistence-label{font-size:10px;font-weight:600;
  letter-spacing:0.1em;text-transform:uppercase;color:var(--text-dim);
  margin-bottom:6px;}
.persistence-summary ul{list-style:none;padding:0;margin:0;color:var(--text-dim);}
.persistence-summary li{padding:2px 0;}
.persistence-summary li::before{content:'\\b7 ';color:var(--text-muted);}
footer{border-top:1px solid var(--border);padding:20px 40px;font-family:var(--mono);
  font-size:11px;color:var(--text-muted);display:flex;gap:16px;flex-wrap:wrap;
  justify-content:space-between;}
.card.hidden,.filtered-item.hidden,.callout.hidden{display:none;}
.source-group{background:transparent;border:none;margin-bottom:24px;}
.source-group>summary{font-family:var(--mono);font-size:13px;font-weight:600;
  color:var(--text);padding:10px 0;border-bottom:1px solid var(--border);
  margin-bottom:10px;letter-spacing:0.04em;list-style:none;display:flex;
  align-items:center;gap:8px;cursor:pointer;}
.source-group>summary::before{content:'\\25b6';font-size:9px;color:var(--text-dim);
  transition:transform 0.2s;}
.source-group[open]>summary::before{transform:rotate(90deg);}
.source-group>summary::-webkit-details-marker{display:none;}
.verdict-group{background:transparent;border:none;margin-bottom:12px;margin-left:8px;}
.verdict-group>summary{font-family:var(--mono);font-size:11px;font-weight:600;
  padding:6px 10px;border-radius:3px;letter-spacing:0.06em;
  list-style:none;display:flex;align-items:center;gap:6px;cursor:pointer;
  text-transform:uppercase;}
.verdict-group>summary::before{content:'\\25b6';font-size:7px;transition:transform 0.2s;}
.verdict-group[open]>summary::before{transform:rotate(90deg);}
.verdict-group>summary::-webkit-details-marker{display:none;}
.verdict-group.interested>summary{color:var(--green);}
.verdict-group.maybe>summary{color:var(--amber);}
.verdict-toggle{font-family:var(--mono);font-size:10px;color:var(--text-dim);
  background:none;border:1px solid var(--border2);padding:2px 8px;border-radius:3px;
  cursor:pointer;letter-spacing:0.04em;margin-left:auto;text-transform:lowercase;}
.verdict-toggle:hover{color:var(--text);border-color:var(--text-dim);}
.filtered-group{background:transparent;border:none;margin-bottom:24px;}
.filtered-group>summary{font-family:var(--mono);font-size:11px;font-weight:600;
  color:var(--red-dim);padding:8px 0;list-style:none;display:flex;
  align-items:center;gap:8px;cursor:pointer;letter-spacing:0.06em;text-transform:uppercase;}
.filtered-group>summary::before{content:'\\25b6';font-size:7px;color:var(--red-dim);
  transition:transform 0.2s;}
.filtered-group[open]>summary::before{transform:rotate(90deg);}
.filtered-group>summary::-webkit-details-marker{display:none;}
.dl-btn{background:var(--bg3);border:1px solid var(--border2);color:var(--text-dim);
  font-family:var(--mono);font-size:11px;padding:6px 12px;border-radius:4px;
  cursor:pointer;letter-spacing:0.04em;transition:color 0.15s,border-color 0.15s;}
.dl-btn:hover{color:var(--green);border-color:var(--green-dim);}
@keyframes fadein{from{opacity:0;transform:translateY(4px);}to{opacity:1;transform:translateY(0);}}
.card,.filtered-item,.callout,.action-banner{animation:fadein 0.4s ease both;}
@media(max-width:700px){
  .header,.filter-bar,.main,footer{padding-left:16px;padding-right:16px;}
  .header{flex-direction:column;padding:20px 16px 16px;gap:12px;}
  .run-title{font-size:18px;}
  .run-meta{font-size:10px;gap:10px;}
  .stats-pills{width:100%;gap:6px;}
  .pill{padding:8px 12px;font-size:10px;min-height:44px;align-items:center;}
  .pill-num{font-size:14px;}
  .filter-bar{gap:8px;overflow-x:auto;-webkit-overflow-scrolling:touch;
    flex-wrap:nowrap;padding:10px 16px;}
  .filter-btn{min-height:44px;padding:10px 14px;font-size:12px;white-space:nowrap;}
  .main{padding:20px 16px 40px;}
  .section-label{font-size:12px;flex-wrap:wrap;gap:6px;}
  .section-toggle{min-height:36px;padding:6px 10px;font-size:11px;}
  .card-header{padding:16px 14px 14px;min-height:56px;}
  .card-toggle{font-size:20px;padding:4px;min-width:32px;text-align:center;}
  .verdict-dot{width:10px;height:10px;margin-top:4px;}
  .company{font-size:11px;}
  .role{font-size:13px;}
  .card-meta{font-size:10px;gap:8px;}
  .card-body{padding:0 14px 14px 28px;}
  .body-row{margin-top:10px;}
  .body-verdict{padding:8px 12px;font-size:12.5px;}
  .filtered-list{grid-template-columns:1fr;}
  .filtered-item{padding:12px 14px;min-height:44px;}
  .fi-name{font-size:13px;}
  .fi-reason{font-size:11px;}
  .links-row{gap:6px;}
  .link-btn{min-height:44px;padding:10px 14px;font-size:12px;
    display:inline-flex;align-items:center;}
  .draft-send-btn{min-height:44px;padding:10px 18px;font-size:12px;}
  .dl-btn{min-height:44px;padding:10px 14px;font-size:12px;}
  .draft-block{padding:10px 12px;}
  .draft-block .draft-text{font-size:11.5px;}
  .action-banner,.callout{flex-direction:column;gap:8px;padding:14px 16px;}
  footer{padding:16px;flex-direction:column;gap:8px;text-align:center;}
}
@media(max-width:400px){
  .header{padding:16px 12px 12px;}
  .filter-bar{padding:8px 12px;}
  .main{padding:16px 12px 32px;}
  .card-header{padding:14px 12px 12px;}
  .card-body{padding:0 12px 12px 20px;}
  .stats-pills{flex-direction:column;align-items:stretch;}
  .pill{justify-content:center;}
  footer{padding:12px;font-size:10px;}
}"""

# ── JavaScript ───────────────────────────────────────────────────────────────

JS = """\
var _viewedKey='jerbs-viewed';
function _getViewed(){
  try{var s=localStorage.getItem(_viewedKey);return s?JSON.parse(s):[];}
  catch(e){return [];}
}
function _saveViewed(ids){
  try{localStorage.setItem(_viewedKey,JSON.stringify(ids));}catch(e){}
}
function _markViewed(el){
  if(el.classList.contains('viewed'))return;
  el.classList.add('viewed');
  var id=el.dataset.id;
  if(id){var v=_getViewed();if(v.indexOf(id)<0){v.push(id);_saveViewed(v);}}
}
function toggleCard(el){el.classList.toggle('open');_markViewed(el);}
function setFilter(type,btn){
  document.querySelectorAll('.filter-btn').forEach(function(b){b.className='filter-btn';});
  if(type==='all')btn.classList.add('active-all');
  else if(type==='new')btn.classList.add('active-blue');
  else if(type==='unread')btn.classList.add('active-all');
  else if(type==='interested')btn.classList.add('active-green');
  else if(type==='maybe')btn.classList.add('active-amber');
  else if(type==='filtered')btn.classList.add('active-red');
  document.querySelectorAll('[data-verdict]').forEach(function(el){
    if(type==='all')el.classList.remove('hidden');
    else if(type==='new'){
      if(el.dataset.isnew==='true')el.classList.remove('hidden');
      else el.classList.add('hidden');
    }
    else if(type==='unread'){
      if(!el.classList.contains('viewed'))el.classList.remove('hidden');
      else el.classList.add('hidden');
    }
    else if(el.dataset.verdict===type)el.classList.remove('hidden');
    else el.classList.add('hidden');
  });
}
function toggleLight(){
  document.body.classList.toggle('light');
  var btn=document.getElementById('theme-btn');
  if(btn)btn.textContent=document.body.classList.contains('light')?'Dark':'Light';
}
function toggleSection(btn){
  var group=btn.closest('.section-label').nextElementSibling;
  if(!group)return;
  var cards=group.querySelectorAll('.card');
  var allOpen=Array.from(cards).every(function(c){return c.classList.contains('open');});
  cards.forEach(function(c){
    if(allOpen)c.classList.remove('open');
    else{c.classList.add('open');_markViewed(c);}
  });
  btn.textContent=allOpen?'expand all':'collapse all';
}
function toggleAllCards(btn){
  var det=btn.closest('.verdict-group');
  if(!det)return;
  var cards=det.querySelectorAll('.card');
  var allOpen=Array.from(cards).every(function(c){return c.classList.contains('open');});
  cards.forEach(function(c){
    if(allOpen)c.classList.remove('open');
    else{c.classList.add('open');_markViewed(c);}
  });
  btn.textContent=allOpen?'expand all':'collapse all';
  if(btn.event)btn.event.stopPropagation();
}
document.addEventListener('DOMContentLoaded',function(){
  var viewed=_getViewed();
  if(viewed.length){
    document.querySelectorAll('.card[data-id]').forEach(function(el){
      if(viewed.indexOf(el.dataset.id)>=0)el.classList.add('viewed');
    });
  }
});
function downloadPage(){
  var html=document.documentElement.outerHTML;
  var blob=new Blob(['<!DOCTYPE html>\\n'+html],{type:'text/html'});
  var a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  var d=document.querySelector('title').textContent.match(/\\d{4}-\\d{2}-\\d{2}/);
  a.download='jerbs-results-'+(d?d[0]:'report')+'.html';
  a.click();URL.revokeObjectURL(a.href);
}
document.addEventListener('DOMContentLoaded',function(){
  document.querySelectorAll('.card,.filtered-item,.callout,.action-banner').forEach(
    function(el,i){el.style.animationDelay=(0.03+i*0.02)+'s';});
});"""


# ── Card builders (shared by both themes) ────────────────────────────────────


def _build_missing_tags(missing):
    """Build missing-info tags (terminal) or inline text (cards)."""
    if not missing:
        return ""
    tags = "".join(f'<span class="missing-tag">{_e(m)}</span>' for m in missing)
    return f'<div class="missing-tags">{tags}</div>'


def _build_link_buttons(item):
    """Build link buttons for a card."""
    links = []
    posting_url = item.get("posting_url", "")
    email_url = item.get("email_url", "")
    if email_url:
        links.append(
            f'<a class="link-btn" href="{_e(email_url)}" target="_blank">\U0001f4e7 Email</a>'
        )
    if posting_url:
        links.append(
            f'<a class="link-btn" href="{_e(posting_url)}" target="_blank">\U0001f517 Posting</a>'
        )
    return '<div class="links-row">' + "".join(links) + "</div>" if links else ""


def _build_draft_html(item):
    """Build draft reply block."""
    reply_draft = item.get("reply_draft", "")
    draft_url = item.get("draft_url", "")
    sent = item.get("sent", False)
    if not reply_draft:
        return ""
    if sent:
        return (
            '<div class="sent-label">Sent — logged</div>'
            '<div class="draft-block">'
            f'<div class="draft-text">{_e(reply_draft)}</div></div>'
        )
    send_btn = (
        f'<a class="draft-send-btn" href="{_e(draft_url)}" target="_blank">'
        "\U0001f4e8 Review &amp; Send</a>"
        if draft_url
        else ""
    )
    return (
        '<div class="draft-block">'
        '<div class="draft-label">Draft reply</div>'
        f'<div class="draft-text">{_e(reply_draft)}</div>'
        f"{send_btn}</div>"
    )


def build_terminal_card(item, verdict, run_date=None):
    """Build an expandable card for the terminal theme."""
    css = VERDICT_CSS_CLASS.get(verdict, "")
    company = _e(item.get("company", "Unknown"))
    role = _e(item.get("role", ""))
    location = _e(item.get("location", ""))
    reason = _e(item.get("reason", ""))
    comp = item.get("comp_assessment", "")
    missing = item.get("missing_fields") or []
    source = item.get("source", "")
    source_label = SOURCE_LABELS.get(source, source)
    date_str = item.get("email_date") or item.get("added_at") or ""
    is_new = item.get("status") != "pending"

    comp_meta = f" \u00b7 {_e(comp)}" if comp else ""
    age_html = _age_badge_html(date_str, run_date, is_new=is_new)
    body_parts = []
    if reason:
        body_parts.append(
            '<div class="body-row"><div class="body-label">Verdict</div>'
            f'<div class="body-verdict">{reason}</div></div>'
        )
    if comp:
        body_parts.append(
            '<div class="body-row"><div class="body-label">Comp</div>'
            f'<div class="body-verdict">{_e(comp)}</div></div>'
        )
    if missing:
        body_parts.append(
            '<div class="body-row"><div class="body-label">Missing info</div>'
            f"{_build_missing_tags(missing)}</div>"
        )
    body_parts.append(_build_draft_html(item))
    body_parts.append(_build_link_buttons(item))

    msg_id = _e(item.get("message_id", ""))
    new_attr = ' data-isnew="true"' if is_new else ""
    id_attr = f' data-id="{msg_id}"' if msg_id else ""
    return (
        f'<div class="card {css}" data-verdict="{css}"{new_attr}{id_attr}>'
        '<div class="card-header" onclick="toggleCard(this.parentElement)">'
        '<div class="verdict-dot"></div>'
        '<div class="card-main">'
        '<div class="card-title-row">'
        f'<span class="company">{company}</span>'
        f'<span class="role">{role}</span>'
        "</div>"
        f'<div class="card-meta"><span>{location}</span>'
        f"<span>{_e(source_label)}{comp_meta}</span></div>"
        '</div><div class="card-right">'
        f"{age_html}"
        '<div class="card-toggle">\u25ba</div>'
        "</div></div>"
        f'<div class="card-body">{"".join(body_parts)}</div></div>'
    )


def build_terminal_fail(item):
    """Build a compact filtered item for the terminal theme."""
    company = _e(item.get("company", "Unknown"))
    role = _e(item.get("role", ""))
    reason = _e(item.get("reason", ""))
    return (
        '<div class="filtered-item" data-verdict="filtered">'
        '<div class="fi-dot"></div><div class="fi-main">'
        f'<div class="fi-name">{company} \u2014 {role}</div>'
        f'<div class="fi-reason">{reason}</div></div></div>'
    )


def build_cards_card(item, verdict, run_date=None):
    """Build a card for the cards theme."""
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
    source = item.get("source", "")
    source_label = SOURCE_LABELS.get(source, source)
    source_badge = (
        f'<span class="badge badge-source">{_e(source_label)}</span>' if source_label else ""
    )
    date_str = item.get("email_date") or item.get("added_at") or ""
    is_new = item.get("status") != "pending"
    age_html = _age_badge_html(date_str, run_date, is_new=is_new)
    links = []
    if posting_url:
        links.append(_link(posting_url, "View posting"))
    if email_url:
        links.append(_link(email_url, "View email"))

    reason_html = (
        f'<div class="card-field"><div class="card-field-label">Verdict</div>'
        f'<div class="reason">{reason}</div></div>'
        if reason
        else ""
    )
    comp_html = (
        f'<div class="card-field"><div class="card-field-label">Comp</div>'
        f'<div class="comp-note">{_e(comp)}</div></div>'
        if comp
        else ""
    )
    missing_html = (
        f'<div class="card-field"><div class="card-field-label">Missing</div>'
        f'<div class="missing">{_e(", ".join(missing))}</div></div>'
        if missing
        else ""
    )

    msg_id = _e(item.get("message_id", ""))
    new_attr = ' data-isnew="true"' if is_new else ""
    id_attr = f' data-id="{msg_id}"' if msg_id else ""
    return (
        f'<div class="card {css_class}" data-verdict="{css_class}"{new_attr}{id_attr}>'
        '<div class="card-top" onclick="_markViewed(this.parentElement)">'
        f"<div><h3>{company} — {role}</h3>"
        f'<span class="location">{location}</span></div>'
        f"<div>{age_html}"
        f' <span class="badge {badge_class}">{badge_label}</span>'
        f"{source_badge}</div></div>"
        f'<div class="card-body">{reason_html}'
        f"{comp_html}{missing_html}{_build_draft_html(item)}</div>"
        f'<div class="card-links">{" ".join(links)}</div></div>'
    )


def build_cards_fail_row(item):
    """Build a table row for the cards theme filtered table."""
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


# Legacy aliases
build_stats_html = None  # defined below
build_action_banner = None
build_card = None
build_fail_row = None
build_fail_table = None


def _build_stats_html(counts, action_count=0):
    """Build the stat boxes row (cards theme)."""
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


def _build_action_banner(action):
    """Build an action-needed banner."""
    title = _e(action.get("title", "Action Needed"))
    body = _e(action.get("body", ""))
    links_html = ""
    for link in action.get("links", []):
        links_html += f' <a href="{_e(link["url"])}">{_e(link["label"])}</a>'
    return (
        '<div class="action-banner" data-verdict="maybe">'
        f"<h3>{title}</h3>"
        f"<p>{body}</p>"
        f'<div class="card-links" style="margin-top: 0.5rem;">{links_html}</div>'
        "</div>"
    )


def _build_fail_table(items):
    """Build the collapsible table for filtered items (cards theme)."""
    rows = [build_cards_fail_row(item) for item in items]
    return (
        '<table class="fail-table"><thead>'
        "<tr><th>Company</th><th>Role</th><th>Location</th>"
        "<th>Source</th><th>Reason</th></tr>"
        "</thead><tbody>" + "\n".join(rows) + "</tbody></table>"
    )


# Set module-level aliases for backward compatibility and tests
build_stats_html = _build_stats_html
build_action_banner = _build_action_banner
build_card = build_cards_card
build_fail_row = build_cards_fail_row
build_fail_table = _build_fail_table


# ── Pending results helpers ──────────────────────────────────────────────────

CRITERIA_PATHS = [
    Path.home() / ".claude" / "jerbs" / "criteria.json",
    Path.home() / ".jerbs" / "criteria.json",
]


def _load_pending_fallback():
    """
    Load pending_results from the criteria file on disk as a fallback
    when results.json doesn't include them. Returns [] if not found.
    """
    for path in CRITERIA_PATHS:
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    criteria = json.load(f)
                cutoff = (datetime.today() - timedelta(days=14)).strftime("%Y-%m-%d")
                return [
                    entry
                    for entry in criteria.get("pending_results", [])
                    if entry.get("added_at", "") >= cutoff
                ]
            except (json.JSONDecodeError, OSError):
                continue
    return []


def _resolve_pending(results_data, new_message_ids):
    """
    Get pending results to display: use results.json field first,
    fall back to criteria.json on disk only when the key is absent.
    Excludes any items that appear in this run's new results.
    """
    if "pending_results" in results_data:
        pending = results_data["pending_results"] or []
    else:
        pending = _load_pending_fallback()
    # Exclude items that were re-screened in the current run
    return [p for p in pending if p.get("message_id") not in new_message_ids]


# ── Main export ──────────────────────────────────────────────────────────────


def export_to_html(results_data, output_path, theme=None):
    """Generate a self-contained HTML results page with theme switcher."""
    theme = theme or results_data.get("theme", DEFAULT_THEME)
    if theme not in THEMES:
        theme = DEFAULT_THEME

    run_date = results_data.get("run_date", datetime.today().strftime("%Y-%m-%d"))
    profile_name = results_data.get("profile_name", "Job Search")
    mode = results_data.get("mode", "dry-run")
    lookback = results_data.get("lookback_days", "1")
    actions = results_data.get("actions", [])
    results = results_data.get("results", [])

    # Merge pending results into the main results list so they appear
    # in the same source/verdict groups, distinguished only by age badge.
    new_ids = {r["message_id"] for r in results if r.get("message_id")}
    pending = _resolve_pending(results_data, new_ids)
    results = results + pending

    passes = [r for r in results if r.get("verdict") == "pass"]
    maybes = [r for r in results if r.get("verdict") == "maybe"]
    fails = [r for r in results if r.get("verdict") == "fail"]
    counts = {
        "pass": len(passes),
        "maybe": len(maybes),
        "fail": len(fails),
    }
    total = sum(counts.values())

    mode_label = "Dry-run" if mode == "dry-run" else "Send mode"
    css = CSS_TERMINAL if theme == "terminal" else CSS_CARDS

    head = (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f"<title>jerbs — Screening Report · {_e(run_date)}</title>\n"
        f"<style>{css}</style>\n"
        f"<script>{JS}</script>\n"
        "</head><body>\n"
    )

    # Terminal header
    term_header = (
        '<div class="header">'
        "<div>"
        f'<div class="logo">jerbs</div>'
        '<div class="run-title">Screening Report</div>'
        '<div class="run-meta">'
        f"<span>{_e(run_date)}</span>"
        f"<span>{total} results</span>"
        f"<span>{_e(mode_label)}</span>"
        "</div></div>"
        '<div class="stats-pills">'
        f'<div class="pill pill-green"><span class="pill-num">{counts["pass"]}</span> Interested</div>'
        f'<div class="pill pill-amber"><span class="pill-num">{counts["maybe"]}</span> Maybe</div>'
        f'<div class="pill pill-red"><span class="pill-num">{counts["fail"]}</span> Filtered</div>'
        ' <button class="dl-btn" id="theme-btn" onclick="toggleLight()">Light</button>'
        ' <button class="dl-btn" onclick="downloadPage()">'
        "\u2913 Save</button>"
        "</div></div>\n"
    )

    # Cards header
    cards_header = (
        '<div class="top-bar">'
        f'<h1>Jerbs Results <span class="mode-badge">{_e(mode_label)}</span></h1>'
        "<div>"
        '<button class="theme-toggle" id="theme-btn" onclick="toggleLight()">Light</button> '
        '<button class="dl-btn" onclick="downloadPage()">\u2913 Save</button>'
        "</div></div>\n"
        f'<p class="subtitle">{_e(run_date)} · {_e(str(lookback))}-day lookback'
        f" · {_e(profile_name)}</p>\n"
        f"{_build_stats_html(counts, len(actions))}\n"
    )

    # Filter bar (terminal theme)
    filter_bar = (
        '<div class="filter-bar">'
        '<span class="filter-label">Show</span>'
        '<button class="filter-btn active-all" onclick="setFilter(\'all\', this)">All</button>'
        '<button class="filter-btn" onclick="setFilter(\'new\', this)">'
        "\U0001f539 New</button>"
        '<button class="filter-btn" onclick="setFilter(\'unread\', this)">'
        "\u25cf Unread</button>"
        '<button class="filter-btn" onclick="setFilter(\'pass\', this)">'
        "\U0001f7e2 Interested</button>"
        '<button class="filter-btn" onclick="setFilter(\'maybe\', this)">'
        "\U0001f7e1 Maybe</button>"
        '<button class="filter-btn" onclick="setFilter(\'filtered\', this)">'
        "\U0001f534 Filtered</button>"
        "</div>\n"
        if theme in ("terminal", "cards")
        else ""
    )

    # Build body content — single theme only
    header = term_header if theme == "terminal" else cards_header
    parts = [head, header, filter_bar, '<div class="main">\n']

    # Persistence summary (if stats provided)
    persistence_html = _build_persistence_summary(results_data)
    if persistence_html:
        parts.append(persistence_html)

    # Action banners first
    if actions:
        parts.append('<div class="section">')
        parts.append('<div class="section-header">Action Needed</div>')
        for action in actions:
            parts.append(_build_action_banner(action))
        parts.append("</div>\n")

    # Results — group non-fail items by source, then verdict
    non_fail = [r for r in results if r.get("verdict") != "fail"]
    source_groups = _group_by_source(non_fail)

    for source, items in source_groups:
        source_label = SOURCE_LABELS.get(source, source)
        src_passes = _sort_by_date_desc([i for i in items if i.get("verdict") == "pass"], run_date)
        src_maybes = _sort_by_date_desc([i for i in items if i.get("verdict") == "maybe"], run_date)
        if not src_passes and not src_maybes:
            continue

        parts.append('<details class="source-group" open>')
        parts.append(f"<summary>{_e(source_label)} ({len(src_passes) + len(src_maybes)})</summary>")

        toggle_btn = (
            ' <button class="verdict-toggle"'
            ' onclick="event.stopPropagation();toggleAllCards(this)">'
            "expand all</button>"
        )

        if theme == "terminal":
            if src_passes:
                parts.append('<details class="verdict-group interested" open>')
                parts.append(
                    f"<summary>\U0001f7e2 Interested ({len(src_passes)}){toggle_btn}</summary>"
                )
                parts.append('<div class="section-group">')
                for item in src_passes:
                    parts.append(build_terminal_card(item, "pass", run_date))
                parts.append("</div></details>")

            if src_maybes:
                parts.append('<details class="verdict-group maybe" open>')
                parts.append(f"<summary>\U0001f7e1 Maybe ({len(src_maybes)}){toggle_btn}</summary>")
                parts.append('<div class="section-group">')
                for item in src_maybes:
                    parts.append(build_terminal_card(item, "maybe", run_date))
                parts.append("</div></details>")

        else:
            if src_passes:
                parts.append('<details class="verdict-group interested" open>')
                parts.append(f"<summary>\U0001f7e2 Interested ({len(src_passes)})</summary>")
                for item in src_passes:
                    parts.append(build_cards_card(item, "pass", run_date))
                parts.append("</details>")

            if src_maybes:
                parts.append('<details class="verdict-group maybe" open>')
                parts.append(f"<summary>\U0001f7e1 Maybe ({len(src_maybes)})</summary>")
                for item in src_maybes:
                    parts.append(build_cards_card(item, "maybe", run_date))
                parts.append("</details>")

        parts.append("</details>\n")

    # Filtered section — collapsible, default collapsed
    if fails:
        if theme == "terminal":
            parts.append('<details class="filtered-group">')
            parts.append(f"<summary>\U0001f534 Filtered ({len(fails)})</summary>")
            parts.append('<div class="filtered-list">')
            for item in fails:
                parts.append(build_terminal_fail(item))
            parts.append("</div></details>")
        else:
            parts.append(
                f"<details><summary>\U0001f534 Filtered ({len(fails)})</summary>"
                f"{_build_fail_table(fails)}</details>"
            )
    parts.append("</div>\n")  # close main

    parts.append(
        f"<footer><span>jerbs · {_e(run_date)}</span>"
        f"<span>{total} results · {_e(mode_label)} mode</span></footer>\n"
    )
    parts.append("</body></html>")

    html = "\n".join(parts)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Exported {total} results → {output_path}")


if __name__ == "__main__":
    theme_arg = DEFAULT_THEME
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for i, a in enumerate(sys.argv[1:], 1):
        if a == "--theme" and i + 1 < len(sys.argv):
            theme_arg = sys.argv[i + 1]
    if len(args) < 2:
        print("Usage: python export_html.py <results.json> <output.html> [--theme terminal|cards]")
        sys.exit(1)
    with open(args[0], encoding="utf-8") as f:
        data = json.load(f)
    export_to_html(data, args[1], theme=theme_arg)
