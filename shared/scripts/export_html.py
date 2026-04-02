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
from datetime import datetime
from html import escape

# ── Shared constants ─────────────────────────────────────────────────────────

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
.draft-block .draft-text { color: var(--text); white-space: pre-wrap; opacity: 0.85; }
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
.fail-table td { padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border);
  vertical-align: top; }
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
}
.dl-btn {
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text-muted); font-size: 0.8rem; padding: 0.4rem 0.8rem;
  border-radius: 0.4rem; cursor: pointer; transition: color 0.15s, border-color 0.15s;
}
.dl-btn:hover { color: var(--accent); border-color: var(--accent); }"""

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
.verdict-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;margin-top:5px;}
.pass .verdict-dot{background:var(--green);box-shadow:0 0 6px var(--green);}
.maybe .verdict-dot{background:var(--amber);box-shadow:0 0 6px var(--amber);}
.fail .verdict-dot{background:var(--red-dim);}
.card-main{flex:1;min-width:0;}
.card-title-row{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-bottom:4px;}
.company{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--text-dim);
  letter-spacing:0.04em;text-transform:uppercase;}
.role{font-weight:500;font-size:14px;}
.card-meta{font-family:var(--mono);font-size:11px;color:var(--text-dim);display:flex;gap:16px;flex-wrap:wrap;}
.card-toggle{font-family:var(--mono);font-size:16px;color:var(--text-muted);flex-shrink:0;
  transition:transform 0.2s;margin-top:2px;}
.card.open .card-toggle{transform:rotate(90deg);}
.card-body{display:none;padding:0 18px 16px 40px;border-top:1px solid var(--border);}
.card.open .card-body{display:block;}
.body-row{margin-top:12px;font-size:13px;line-height:1.65;}
.body-label{font-family:var(--mono);font-size:10px;letter-spacing:0.12em;
  text-transform:uppercase;color:var(--text-muted);margin-bottom:4px;}
.body-verdict{background:var(--bg3);border-left:2px solid var(--border2);
  padding:10px 14px;border-radius:0 4px 4px 0;font-size:13px;line-height:1.6;}
.pass .body-verdict{border-left-color:var(--green-dim);}
.maybe .body-verdict{border-left-color:var(--amber-dim);}
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
@media(max-width:700px){.filtered-list{grid-template-columns:1fr;}}
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
.action-banner a{color:var(--blue);text-decoration:none;}
.draft-block{margin-top:10px;background:var(--bg3);border-left:2px solid var(--blue);
  padding:10px 14px;border-radius:0 4px 4px 0;font-size:12px;}
.draft-block .draft-label{font-family:var(--mono);font-size:10px;color:var(--blue);
  letter-spacing:0.08em;text-transform:uppercase;margin-bottom:4px;}
.draft-block .draft-text{color:var(--text);opacity:0.85;white-space:pre-wrap;font-family:var(--mono);font-size:12px;}
.sent-label{font-family:var(--mono);font-size:10px;color:var(--green);letter-spacing:0.08em;
  text-transform:uppercase;margin-top:10px;margin-bottom:4px;}
footer{border-top:1px solid var(--border);padding:20px 40px;font-family:var(--mono);
  font-size:11px;color:var(--text-muted);display:flex;gap:16px;flex-wrap:wrap;
  justify-content:space-between;}
.card.hidden,.filtered-item.hidden,.callout.hidden{display:none;}
.dl-btn{background:var(--bg3);border:1px solid var(--border2);color:var(--text-dim);
  font-family:var(--mono);font-size:11px;padding:6px 12px;border-radius:4px;
  cursor:pointer;letter-spacing:0.04em;transition:color 0.15s,border-color 0.15s;}
.dl-btn:hover{color:var(--green);border-color:var(--green-dim);}
@media(max-width:700px){.header,.filter-bar,.main,footer{padding-left:20px;padding-right:20px;}}
@keyframes fadein{from{opacity:0;transform:translateY(4px);}to{opacity:1;transform:translateY(0);}}
.card,.filtered-item,.callout,.action-banner{animation:fadein 0.4s ease both;}"""

# ── JavaScript ───────────────────────────────────────────────────────────────

JS = """\
function toggleCard(el){el.classList.toggle('open');}
function setFilter(type,btn){
  document.querySelectorAll('.filter-btn').forEach(function(b){b.className='filter-btn';});
  if(type==='all')btn.classList.add('active-all');
  else if(type==='interested')btn.classList.add('active-green');
  else if(type==='maybe')btn.classList.add('active-amber');
  else if(type==='filtered')btn.classList.add('active-red');
  document.querySelectorAll('[data-verdict]').forEach(function(el){
    if(type==='all'||el.dataset.verdict===type)el.classList.remove('hidden');
    else el.classList.add('hidden');
  });
}
function switchTheme(sel){
  var cards=document.getElementById('css-cards');
  var term=document.getElementById('css-terminal');
  if(sel.value==='cards'){cards.disabled=false;term.disabled=true;}
  else{cards.disabled=true;term.disabled=false;}
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
    if(allOpen)c.classList.remove('open');else c.classList.add('open');
  });
  btn.textContent=allOpen?'expand all':'collapse all';
}
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
    label = f'<a href="{_e(draft_url)}">review &amp; send</a>' if draft_url else "draft"
    return (
        '<div class="draft-block">'
        f'<div class="draft-label">Draft reply — {label}</div>'
        f'<div class="draft-text">{_e(reply_draft)}</div></div>'
    )


def build_terminal_card(item, verdict):
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

    comp_meta = f" \u00b7 {_e(comp)}" if comp else ""

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

    return (
        f'<div class="card {css}" data-verdict="{css}">'
        '<div class="card-header" onclick="toggleCard(this.parentElement)">'
        '<div class="verdict-dot"></div>'
        '<div class="card-main">'
        '<div class="card-title-row">'
        f'<span class="company">{company}</span>'
        f'<span class="role">{role}</span></div>'
        f'<div class="card-meta"><span>{location}</span>'
        f"<span>{_e(source_label)}{comp_meta}</span></div>"
        '</div><div class="card-toggle">\u25ba</div></div>'
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


def build_cards_card(item, verdict):
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

    links = []
    if posting_url:
        links.append(_link(posting_url, "View posting"))
    if email_url:
        links.append(_link(email_url, "View email"))

    comp_html = f'<div class="comp-note">{_e(comp)}</div>' if comp else ""
    missing_html = (
        f'<div class="missing"><strong>Missing:</strong> {_e(", ".join(missing))}</div>'
        if missing
        else ""
    )

    return (
        f'<div class="card {css_class}" data-verdict="{css_class}">'
        '<div class="card-top">'
        f"<div><h3>{company} — {role}</h3>"
        f'<span class="location">{location}</span></div>'
        f'<div><span class="badge {badge_class}">{badge_label}</span>'
        f"{source_badge}</div></div>"
        f'<div class="card-body"><div class="reason">{reason}</div>'
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

    passes = [r for r in results if r.get("verdict") == "pass"]
    maybes = [r for r in results if r.get("verdict") == "maybe"]
    fails = [r for r in results if r.get("verdict") == "fail"]
    counts = {"pass": len(passes), "maybe": len(maybes), "fail": len(fails)}
    total = sum(counts.values())

    mode_label = "Dry-run" if mode == "dry-run" else "Send mode"
    cards_disabled = "disabled" if theme == "terminal" else ""
    term_disabled = "disabled" if theme == "cards" else ""

    # Both CSS themes are embedded; one is disabled via <style disabled>
    head = (
        "<!DOCTYPE html>\n"
        '<html lang="en"><head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f"<title>jerbs — Screening Report · {_e(run_date)}</title>\n"
        f'<style id="css-cards" {cards_disabled}>{CSS_CARDS}</style>\n'
        f'<style id="css-terminal" {term_disabled}>{CSS_TERMINAL}</style>\n'
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
        ' <button class="dl-btn" onclick="downloadPage()">'
        "\u2913 Save</button>"
        "</div></div>\n"
    )

    # Cards header
    cards_header = (
        '<div class="top-bar">'
        f'<h1>Jerbs Results <span class="mode-badge">{_e(mode_label)}</span></h1>'
        "<div>"
        '<select class="theme-select" onchange="switchTheme(this)">'
        f'<option value="terminal" {"selected" if theme == "terminal" else ""}>Terminal</option>'
        f'<option value="cards" {"selected" if theme == "cards" else ""}>Cards</option>'
        "</select> "
        '<button class="theme-toggle" id="theme-btn" onclick="toggleLight()">Light</button> '
        '<button class="dl-btn" onclick="downloadPage()">\u2913 Save</button>'
        "</div></div>\n"
        f'<p class="subtitle">{_e(run_date)} · {_e(str(lookback))}-day lookback'
        f" · {_e(profile_name)}</p>\n"
        f"{_build_stats_html(counts, len(actions))}\n"
    )

    # Filter bar (terminal only, but present in DOM — cards theme hides .filter-bar via absence)
    filter_bar = (
        '<div class="filter-bar">'
        '<span class="filter-label">Show</span>'
        '<button class="filter-btn active-all" onclick="setFilter(\'all\', this)">All</button>'
        '<button class="filter-btn" onclick="setFilter(\'pass\', this)">'
        "\U0001f7e2 Interested</button>"
        '<button class="filter-btn" onclick="setFilter(\'maybe\', this)">'
        "\U0001f7e1 Maybe</button>"
        '<button class="filter-btn" onclick="setFilter(\'filtered\', this)">'
        "\U0001f534 Filtered</button>"
        " "
        '<select class="theme-select" onchange="switchTheme(this)">'
        f'<option value="terminal" {"selected" if theme == "terminal" else ""}>Terminal</option>'
        f'<option value="cards" {"selected" if theme == "cards" else ""}>Cards</option>'
        "</select>"
        "</div>\n"
    )

    # Build body content — render for both themes, show based on active CSS
    parts = [head, term_header, cards_header, filter_bar, '<div class="main">\n']

    # Action banners first
    if actions:
        parts.append('<div class="section">')
        parts.append('<div class="section-header">Action Needed</div>')
        for action in actions:
            parts.append(_build_action_banner(action))
        parts.append("</div>\n")

    # Results
    parts.append('<div class="section">')

    toggle_btn = '<button class="section-toggle" onclick="toggleSection(this)">expand all</button>'

    if passes:
        parts.append(
            f'<div class="section-label interested">\U0001f7e2 Interested{toggle_btn}</div>'
        )
        parts.append('<div class="section-group">')
        for item in passes:
            parts.append(build_terminal_card(item, "pass"))
        parts.append("</div>")

    if maybes:
        parts.append(f'<div class="section-label maybe">\U0001f7e1 Maybe{toggle_btn}</div>')
        parts.append('<div class="section-group">')
        for item in maybes:
            parts.append(build_terminal_card(item, "maybe"))
        parts.append("</div>")

    if fails:
        parts.append('<div class="section-label filtered">\U0001f534 Filtered</div>')
        parts.append('<div class="filtered-list">')
        for item in fails:
            parts.append(build_terminal_fail(item))
        parts.append("</div>")

    parts.append("</div>\n")  # close section
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
