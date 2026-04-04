"""
export_html.py — Job Email Screener
Thin wrapper that injects screening results JSON into the client-side HTML
template (results-template.html) to produce a self-contained results page.

The template handles all rendering: both themes (terminal/cards), light/dark
mode, filtering, expandable cards, age badges, and theme switching at runtime.

Usage:
    python export_html.py <results_json_file> <output_html_file> [--theme terminal|cards]

Or import and call:
    from export_html import export_to_html
    export_to_html(results, "results-2026-04-02.html", theme="terminal")
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Constants ───────────────────────────────────────────────────────────────

THEMES = ("cards", "terminal")
DEFAULT_THEME = "terminal"

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "results-template.html"

CRITERIA_PATHS = [
    Path.home() / ".claude" / "jerbs" / "criteria.json",
    Path.home() / ".jerbs" / "criteria.json",
]


# ── Pending results helpers ─────────────────────────────────────────────────


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
    Get pending results to display: use results_data field first,
    fall back to criteria.json on disk only when the key is absent.
    Excludes any items that appear in this run's new results.
    """
    if "pending_results" in results_data:
        pending = results_data["pending_results"] or []
    else:
        pending = _load_pending_fallback()
    return [p for p in pending if p.get("message_id") not in new_message_ids]


# ── Main export ─────────────────────────────────────────────────────────────


def export_to_html(results_data, output_path, theme=None):
    """Generate a self-contained HTML results page by injecting JSON into the template."""
    theme = theme or results_data.get("theme", DEFAULT_THEME)
    if theme not in THEMES:
        theme = DEFAULT_THEME

    # Resolve pending results (disk fallback for daemon mode)
    new_ids = {r.get("message_id") for r in results_data.get("results", []) if r.get("message_id")}
    pending = _resolve_pending(results_data, new_ids)
    results_data["pending_results"] = pending
    results_data["theme"] = theme

    # Read template and inject JSON data
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template.replace("__RESULTS_DATA__", json.dumps(results_data))

    Path(output_path).write_text(html, encoding="utf-8")

    total = len(results_data.get("results", [])) + len(pending)
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
