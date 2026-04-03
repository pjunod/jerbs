"""
Unit tests for export_html.py — HTML export logic.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared" / "scripts"))

from export_html import (
    CSS_CARDS,
    CSS_TERMINAL,
    DEFAULT_THEME,
    JS,
    SOURCE_LABELS,
    THEMES,
    VERDICT_BADGE_CLASS,
    VERDICT_CSS_CLASS,
    VERDICT_LABELS,
    _age_badge_html,
    _age_color,
    _age_days,
    _age_label,
    _build_missing_tags,
    _build_persistence_summary,
    _e,
    _link,
    _load_pending_fallback,
    _parse_date,
    _resolve_pending,
    _sort_by_date_desc,
    build_action_banner,
    build_card,
    build_cards_card,
    build_fail_row,
    build_fail_table,
    build_stats_html,
    build_terminal_card,
    build_terminal_fail,
    export_to_html,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_result(verdict="pass", company="TechCorp", role="Staff SRE", **kwargs):
    r = {
        "verdict": verdict,
        "company": company,
        "role": role,
        "location": "Remote",
        "source": "Job Alert Listings",
        "reason": "Clears all criteria.",
        "dealbreaker": None,
        "comp_assessment": "Strong comp.",
        "missing_fields": [],
        "reply_draft": "",
        "draft_url": "",
        "email_url": "",
        "posting_url": "",
        "sent": False,
    }
    r.update(kwargs)
    return r


def run_html_export(items, **kwargs):
    data = {
        "run_date": kwargs.get("run_date", "2026-04-02"),
        "profile_name": kwargs.get("profile_name", "Test Profile"),
        "mode": kwargs.get("mode", "dry-run"),
        "lookback_days": kwargs.get("lookback_days", "1"),
        "actions": kwargs.get("actions", []),
        "pending_results": kwargs.get("pending_results", []),
        "results": items,
    }
    if "persistence_stats" in kwargs:
        data["persistence_stats"] = kwargs["persistence_stats"]
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w") as f:
        path = f.name
    try:
        export_to_html(data, path, theme=kwargs.get("theme"))
        with open(path, encoding="utf-8") as f:
            return f.read()
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# _e (HTML escaping)
# ---------------------------------------------------------------------------


class TestEscape:
    def test_escapes_angle_brackets(self):
        assert (
            _e("<script>alert('xss')</script>")
            == "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
        )

    def test_escapes_ampersand(self):
        assert _e("A & B") == "A &amp; B"

    def test_escapes_quotes(self):
        assert "&quot;" in _e('"hello"')

    def test_empty_string(self):
        assert _e("") == ""

    def test_none_returns_empty(self):
        assert _e(None) == ""

    def test_number_converted_to_string(self):
        assert _e(42) == "42"


# ---------------------------------------------------------------------------
# _link
# ---------------------------------------------------------------------------


class TestLink:
    def test_returns_anchor_tag(self):
        result = _link("https://example.com", "Click me")
        assert '<a href="https://example.com">Click me</a>' == result

    def test_empty_url_returns_empty(self):
        assert _link("", "label") == ""

    def test_none_url_returns_empty(self):
        assert _link(None, "label") == ""

    def test_escapes_special_chars_in_url(self):
        result = _link("https://example.com?a=1&b=2", "link")
        assert "&amp;" in result

    def test_escapes_special_chars_in_label(self):
        result = _link("https://example.com", "<bold>")
        assert "&lt;bold&gt;" in result


# ---------------------------------------------------------------------------
# build_stats_html
# ---------------------------------------------------------------------------


class TestBuildStatsHtml:
    def test_contains_all_counts(self):
        html = build_stats_html({"pass": 3, "maybe": 5, "fail": 10})
        assert ">3<" in html
        assert ">5<" in html
        assert ">10<" in html

    def test_contains_labels(self):
        html = build_stats_html({"pass": 0, "maybe": 0, "fail": 0})
        assert "Interested" in html
        assert "Maybe" in html
        assert "Filtered" in html

    def test_no_action_stat_when_zero(self):
        html = build_stats_html({"pass": 0, "maybe": 0, "fail": 0}, action_count=0)
        assert "Action Needed" not in html

    def test_action_stat_shown_when_nonzero(self):
        html = build_stats_html({"pass": 0, "maybe": 0, "fail": 0}, action_count=2)
        assert "Action Needed" in html
        assert ">2<" in html

    def test_wraps_in_stats_div(self):
        html = build_stats_html({"pass": 0, "maybe": 0, "fail": 0})
        assert html.startswith('<div class="stats">')


# ---------------------------------------------------------------------------
# build_action_banner
# ---------------------------------------------------------------------------


class TestBuildActionBanner:
    def test_renders_title_and_body(self):
        action = {"title": "Reply needed", "body": "Tom is waiting."}
        html = build_action_banner(action)
        assert "Reply needed" in html
        assert "Tom is waiting." in html

    def test_renders_links(self):
        action = {
            "title": "Action",
            "body": "Do something.",
            "links": [{"url": "https://gmail.com/123", "label": "View in Gmail"}],
        }
        html = build_action_banner(action)
        assert "https://gmail.com/123" in html
        assert "View in Gmail" in html

    def test_empty_links_ok(self):
        action = {"title": "T", "body": "B", "links": []}
        html = build_action_banner(action)
        assert "action-banner" in html

    def test_defaults_title(self):
        html = build_action_banner({})
        assert "Action Needed" in html

    def test_escapes_body(self):
        action = {"title": "T", "body": "<script>bad</script>"}
        html = build_action_banner(action)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# build_card
# ---------------------------------------------------------------------------


class TestBuildCard:
    def test_pass_card_has_green_class(self):
        html = build_card(make_result("pass"), "pass")
        assert "card pass" in html

    def test_maybe_card_has_yellow_class(self):
        html = build_card(make_result("maybe"), "maybe")
        assert "card maybe" in html

    def test_fail_card_has_fail_class(self):
        html = build_card(make_result("fail"), "fail")
        assert "card fail" in html

    def test_contains_company_and_role(self):
        html = build_card(make_result(company="Acme", role="SRE"), "pass")
        assert "Acme" in html
        assert "SRE" in html

    def test_contains_location(self):
        html = build_card(make_result(location="NYC"), "pass")
        assert "NYC" in html

    def test_contains_reason(self):
        html = build_card(make_result(reason="Great match."), "pass")
        assert "Great match." in html

    def test_comp_assessment_shown(self):
        html = build_card(make_result(comp_assessment="Above floor."), "pass")
        assert "Above floor." in html
        assert "comp-note" in html

    def test_comp_assessment_hidden_when_empty(self):
        html = build_card(make_result(comp_assessment=""), "pass")
        assert "comp-note" not in html

    def test_missing_fields_shown(self):
        html = build_card(make_result(missing_fields=["Salary", "Equity"]), "maybe")
        assert "Missing" in html
        assert "Salary" in html
        assert "Equity" in html

    def test_missing_fields_hidden_when_empty(self):
        html = build_card(make_result(missing_fields=[]), "pass")
        assert "Missing:" not in html

    def test_draft_reply_shown_in_dryrun(self):
        html = build_card(make_result(reply_draft="Hi, interested.", sent=False), "pass")
        assert "Hi, interested." in html
        assert "draft-block" in html

    def test_draft_url_clickable(self):
        html = build_card(
            make_result(
                reply_draft="Hi",
                draft_url="https://mail.google.com/drafts/123",
                sent=False,
            ),
            "pass",
        )
        assert "https://mail.google.com/drafts/123" in html

    def test_sent_reply_shows_sent_label(self):
        html = build_card(make_result(reply_draft="Sent text here.", sent=True), "pass")
        assert "Sent" in html
        assert "logged" in html
        assert "Sent text here." in html

    def test_no_draft_when_empty(self):
        html = build_card(make_result(reply_draft=""), "pass")
        assert "draft-block" not in html

    def test_posting_url_link(self):
        html = build_card(make_result(posting_url="https://jobs.example.com/123"), "pass")
        assert "View posting" in html
        assert "https://jobs.example.com/123" in html

    def test_email_url_link(self):
        html = build_card(make_result(email_url="https://mail.google.com/abc"), "pass")
        assert "View email" in html

    def test_no_links_when_urls_empty(self):
        html = build_card(make_result(posting_url="", email_url=""), "pass")
        assert "View posting" not in html
        assert "View email" not in html

    def test_source_badge_shown(self):
        html = build_card(make_result(source="Direct Outreach"), "pass")
        assert "Direct" in html
        assert "badge-source" in html

    def test_source_badge_job_alert(self):
        html = build_card(make_result(source="Job Alert Listings"), "pass")
        assert "Job Digest Postings" in html

    def test_escapes_company_name(self):
        html = build_card(make_result(company="A&B <Corp>"), "pass")
        assert "A&amp;B" in html
        assert "&lt;Corp&gt;" in html

    def test_verdict_badge_present(self):
        html = build_card(make_result(), "pass")
        assert "badge-pass" in html
        assert "Interested" in html

    def test_maybe_badge(self):
        html = build_card(make_result("maybe"), "maybe")
        assert "badge-maybe" in html

    def test_draft_without_url_shows_draft_label(self):
        html = build_card(make_result(reply_draft="Hello", draft_url="", sent=False), "pass")
        assert "draft-block" in html
        assert "draft" in html


# ---------------------------------------------------------------------------
# build_fail_row / build_fail_table
# ---------------------------------------------------------------------------


class TestBuildFailTable:
    def test_fail_row_contains_company(self):
        html = build_fail_row(make_result("fail", company="BadCo"))
        assert "BadCo" in html

    def test_fail_row_contains_source(self):
        html = build_fail_row(make_result("fail", source="Direct Outreach"))
        assert "Direct" in html

    def test_fail_row_blacklist_class(self):
        html = build_fail_row(make_result("fail", dealbreaker="Company on personal blacklist"))
        assert "blacklist" in html

    def test_fail_row_no_blacklist_class(self):
        html = build_fail_row(make_result("fail", dealbreaker="Wrong role"))
        assert "blacklist" not in html

    def test_fail_row_email_url_linked(self):
        html = build_fail_row(make_result("fail", email_url="https://mail.google.com/x"))
        assert "https://mail.google.com/x" in html

    def test_fail_row_no_email_url(self):
        html = build_fail_row(make_result("fail", email_url=""))
        assert "<a " not in html

    def test_fail_row_none_dealbreaker(self):
        html = build_fail_row(make_result("fail", dealbreaker=None))
        assert "reason-col" in html
        assert "blacklist" not in html

    def test_fail_table_has_header_row(self):
        html = build_fail_table([make_result("fail")])
        assert "<th>" in html
        assert "Company" in html
        assert "Source" in html
        assert "Reason" in html

    def test_fail_table_multiple_items(self):
        items = [
            make_result("fail", company="A"),
            make_result("fail", company="B"),
        ]
        html = build_fail_table(items)
        assert "A" in html
        assert "B" in html

    def test_fail_table_empty(self):
        html = build_fail_table([])
        assert "<tbody></tbody>" in html


# ---------------------------------------------------------------------------
# export_to_html (full page)
# ---------------------------------------------------------------------------


class TestExportToHtml:
    def test_page_has_doctype(self):
        html = run_html_export([])
        assert html.startswith("<!DOCTYPE html>")

    def test_page_has_title(self):
        html = run_html_export([], run_date="2026-04-02")
        assert "2026-04-02</title>" in html

    def test_page_has_selected_theme_css(self):
        html_term = run_html_export([], theme="terminal")
        assert "IBM Plex Mono" in html_term
        html_cards = run_html_export([], theme="cards")
        assert "Segoe UI" in html_cards or "sans-serif" in html_cards

    def test_page_has_single_theme_only(self):
        html = run_html_export([], theme="terminal")
        # Should not contain cards-only elements
        assert "top-bar" not in html

    def test_page_has_light_toggle(self):
        html = run_html_export([])
        assert "theme-btn" in html
        assert "toggleLight" in html

    def test_dryrun_mode_badge(self):
        html = run_html_export([], mode="dry-run")
        assert "Dry-run" in html

    def test_send_mode_badge(self):
        html = run_html_export([], mode="send")
        assert "Send mode" in html

    def test_profile_name_shown(self):
        html = run_html_export([], profile_name="Paul's Job Search", theme="cards")
        assert "Paul&#x27;s Job Search" in html

    def test_lookback_shown(self):
        html = run_html_export([], lookback_days="7", theme="cards")
        assert "7-day" in html

    def test_actions_section_at_top(self):
        actions = [{"title": "Reply to Tom", "body": "He's waiting."}]
        html = run_html_export([make_result()], actions=actions)
        action_pos = html.index("Reply to Tom")
        # Action banners should appear before result cards
        card_pos = html.index("card pass")
        assert action_pos < card_pos

    def test_actions_section_absent_when_empty(self):
        html = run_html_export([])
        assert "Action Needed</div>" not in html

    def test_pass_cards_present(self):
        html = run_html_export([make_result("pass", company="GoodCo")])
        assert "GoodCo" in html
        assert "card pass" in html

    def test_maybe_cards_present(self):
        html = run_html_export([make_result("maybe", company="MaybeCo")])
        assert "MaybeCo" in html
        assert "card maybe" in html

    def test_fail_items_present(self):
        html = run_html_export([make_result("fail", company="BadCo")])
        assert "BadCo" in html
        assert "Filtered" in html

    def test_results_grouped_by_source(self):
        items = [
            make_result("pass", source="Job Alert Listings", company="AlertCo"),
            make_result("pass", source="Direct Outreach", company="DirectCo"),
        ]
        html = run_html_export(items)
        assert "AlertCo" in html
        assert "DirectCo" in html
        assert "source-group" in html
        # Direct Outreach should appear before Job Alert Listings
        assert html.index("Direct Outreach (1)") < html.index("Job Digest Postings (1)")

    def test_source_group_with_unknown_source(self):
        items = [make_result("pass", source="Carrier Pigeon", company="PigeonCo")]
        html = run_html_export(items)
        assert "PigeonCo" in html
        assert "Carrier Pigeon" in html

    def test_source_group_skips_fail_only_sources(self):
        items = [make_result("fail", source="Direct Outreach", company="FailCo")]
        html = run_html_export(items)
        # Fail items are in the flat filtered section, not in a source group
        assert "FailCo" in html
        assert '<details class="source-group"' not in html

    def test_source_group_skips_unknown_verdict(self):
        items = [make_result("unknown", source="Direct Outreach", company="WeirdCo")]
        html = run_html_export(items)
        # Non-pass/maybe/fail items don't generate source groups
        assert '<details class="source-group"' not in html

    def test_source_badges_on_cards(self):
        items = [
            make_result("pass", source="Direct Outreach"),
            make_result("pass", source="Job Alert Listings"),
        ]
        html = run_html_export(items, theme="cards")
        assert "badge-source" in html

    def test_fail_items_contain_reason(self):
        items = [
            make_result("fail", reason="Wrong role entirely"),
        ]
        html = run_html_export(items)
        assert "Wrong role entirely" in html

    def test_empty_results_no_verdict_cards(self):
        html = run_html_export([])
        assert "card pass" not in html
        assert "card maybe" not in html

    def test_counts_correct(self):
        items = [
            make_result("pass"),
            make_result("pass"),
            make_result("maybe"),
            make_result("fail"),
        ]
        # Terminal uses pill-num spans
        html = run_html_export(items, theme="terminal")
        assert 'pill-num">2<' in html  # 2 interested
        # Cards uses stat-num spans
        html_cards = run_html_export(items, theme="cards")
        assert 'green">2<' in html_cards

    def test_footer_present(self):
        html = run_html_export([], run_date="2026-04-02")
        assert "jerbs" in html
        assert "2026-04-02" in html
        assert "<footer>" in html

    def test_file_written_to_disk(self):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            export_to_html({"results": [], "pending_results": []}, path)
            assert os.path.exists(path)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            assert "<!DOCTYPE html>" in content
        finally:
            os.unlink(path)

    def test_prints_export_message(self, capsys):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            export_to_html({"results": [make_result()], "pending_results": []}, path)
            captured = capsys.readouterr()
            assert "Exported 1 results" in captured.out
        finally:
            os.unlink(path)

    def test_defaults_when_fields_missing(self):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            export_to_html({"results": [], "pending_results": []}, path, theme="cards")
            with open(path, encoding="utf-8") as f:
                html = f.read()
            assert "Job Search" in html  # default profile name
            assert "Dry-run" in html  # default mode
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------


class TestConstants:
    def test_verdict_labels_complete(self):
        assert set(VERDICT_LABELS.keys()) == {"pass", "maybe", "fail"}

    def test_verdict_css_classes_complete(self):
        assert set(VERDICT_CSS_CLASS.keys()) == {"pass", "maybe", "fail"}

    def test_verdict_badge_classes_complete(self):
        assert set(VERDICT_BADGE_CLASS.keys()) == {"pass", "maybe", "fail"}

    def test_source_labels_have_expected_keys(self):
        assert "Job Alert Listings" in SOURCE_LABELS
        assert "Direct Outreach" in SOURCE_LABELS
        assert "LinkedIn DMs" in SOURCE_LABELS

    def test_css_cards_not_empty(self):
        assert len(CSS_CARDS) > 100

    def test_css_terminal_not_empty(self):
        assert len(CSS_TERMINAL) > 100

    def test_js_not_empty(self):
        assert "toggleCard" in JS
        assert "toggleLight" in JS

    def test_css_cards_has_light_theme(self):
        assert ".light" in CSS_CARDS

    def test_themes_tuple(self):
        assert "cards" in THEMES
        assert "terminal" in THEMES

    def test_default_theme(self):
        assert DEFAULT_THEME in THEMES


# ---------------------------------------------------------------------------
# export_html.py __main__ guard
# ---------------------------------------------------------------------------


class TestScriptGuard:
    _export_path = str(
        Path(__file__).parent.parent.parent / "shared" / "scripts" / "export_html.py"
    )

    def test_too_few_args_exits_with_error(self):
        import runpy

        import pytest

        with patch("sys.argv", ["export_html.py"]):
            with patch("builtins.print"):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path(self._export_path, run_name="__main__")
        assert exc_info.value.code == 1

    def test_runs_export_when_args_provided(self, tmp_path):
        import runpy

        data = {"run_date": "2026-04-02", "results": []}
        data_file = tmp_path / "data.json"
        data_file.write_text(json.dumps(data))
        output_file = tmp_path / "out.html"

        with patch("sys.argv", ["export_html.py", str(data_file), str(output_file)]):
            with patch("builtins.print"):
                runpy.run_path(self._export_path, run_name="__main__")
        assert output_file.exists()
        content = output_file.read_text()
        assert "<!DOCTYPE html>" in content

    def test_runs_with_theme_flag(self, tmp_path):
        import runpy

        data = {"run_date": "2026-04-02", "results": []}
        data_file = tmp_path / "data.json"
        data_file.write_text(json.dumps(data))
        output_file = tmp_path / "out.html"

        with patch(
            "sys.argv",
            ["export_html.py", str(data_file), str(output_file), "--theme", "cards"],
        ):
            with patch("builtins.print"):
                runpy.run_path(self._export_path, run_name="__main__")
        assert output_file.exists()


# ---------------------------------------------------------------------------
# Terminal theme builders
# ---------------------------------------------------------------------------


class TestTerminalCard:
    def test_expandable_card_structure(self):
        html = build_terminal_card(make_result("pass", company="Google"), "pass")
        assert "card pass" in html
        assert "toggleCard" in html
        assert "Google" in html

    def test_verdict_dot(self):
        html = build_terminal_card(make_result("pass"), "pass")
        assert "verdict-dot" in html

    def test_company_uppercase(self):
        html = build_terminal_card(make_result(company="Acme"), "pass")
        assert 'class="company"' in html
        assert "Acme" in html

    def test_comp_in_body(self):
        html = build_terminal_card(make_result(comp_assessment="Strong."), "pass")
        assert "Strong." in html
        assert "body-verdict" in html

    def test_missing_tags(self):
        html = build_terminal_card(make_result(missing_fields=["Salary", "Equity"]), "maybe")
        assert "missing-tag" in html
        assert "Salary" in html

    def test_links_in_body(self):
        html = build_terminal_card(make_result(email_url="https://mail.google.com/x"), "pass")
        assert "link-btn" in html

    def test_draft_in_body(self):
        html = build_terminal_card(make_result(reply_draft="Hello", sent=False), "pass")
        assert "draft-block" in html

    def test_source_in_meta(self):
        html = build_terminal_card(make_result(source="Direct Outreach"), "pass")
        assert "Direct" in html

    def test_no_missing_no_tags(self):
        assert _build_missing_tags([]) == ""
        assert _build_missing_tags(None) == ""
        html = build_terminal_card(make_result(missing_fields=[]), "pass")
        assert "missing-tag" not in html

    def test_posting_url_link_btn(self):
        html = build_terminal_card(
            make_result(posting_url="https://jobs.example.com/123", email_url=""),
            "pass",
        )
        assert "Posting" in html
        assert "link-btn" in html


class TestTerminalFail:
    def test_filtered_item_structure(self):
        html = build_terminal_fail(make_result("fail", company="BadCo"))
        assert "filtered-item" in html
        assert "fi-dot" in html
        assert "BadCo" in html

    def test_reason_shown(self):
        html = build_terminal_fail(make_result("fail", reason="Wrong role"))
        assert "Wrong role" in html
        assert "fi-reason" in html


# ---------------------------------------------------------------------------
# Theme switching
# ---------------------------------------------------------------------------


class TestThemeSwitching:
    def test_default_theme_is_terminal(self):
        html = run_html_export([make_result()])
        # Terminal CSS should be present (IBM Plex Mono font)
        assert "IBM Plex Mono" in html
        # Cards-only elements should not be present
        assert "top-bar" not in html

    def test_cards_theme_explicit(self):
        html = run_html_export([make_result()], theme="cards")
        # Cards CSS should be present (stat boxes)
        assert "stat-num" in html
        # Filter bar should be present in both themes
        assert "filter-bar" in html

    def test_invalid_theme_falls_back_to_default(self):
        html = run_html_export([], theme="invalid")
        # Should fall back to terminal
        assert "IBM Plex Mono" in html


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------


class TestParseDate:
    def test_parses_yyyy_mm_dd(self):
        dt = _parse_date("2026-04-01")
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 4
        assert dt.day == 1

    def test_parses_iso_format(self):
        dt = _parse_date("2026-04-01T14:30:00Z")
        assert dt is not None
        assert dt.day == 1

    def test_empty_string_returns_none(self):
        assert _parse_date("") is None

    def test_none_returns_none(self):
        assert _parse_date(None) is None

    def test_invalid_string_returns_none(self):
        assert _parse_date("not-a-date") is None


# ---------------------------------------------------------------------------
# _age_days
# ---------------------------------------------------------------------------


class TestAgeDays:
    def test_same_day(self):
        assert _age_days("2026-04-03", "2026-04-03") == 0

    def test_one_day(self):
        assert _age_days("2026-04-02", "2026-04-03") == 1

    def test_several_days(self):
        assert _age_days("2026-03-30", "2026-04-03") == 4

    def test_empty_returns_none(self):
        assert _age_days("", "2026-04-03") is None

    def test_none_returns_none(self):
        assert _age_days(None, "2026-04-03") is None

    def test_future_returns_none(self):
        assert _age_days("2026-04-05", "2026-04-03") is None


# ---------------------------------------------------------------------------
# _age_label (takes day count)
# ---------------------------------------------------------------------------


class TestAgeLabel:
    def test_today(self):
        assert _age_label(0) == "today"

    def test_one_day_ago(self):
        assert _age_label(1) == "1d ago"

    def test_days_ago(self):
        assert _age_label(4) == "4d ago"

    def test_14d_ago(self):
        assert _age_label(14) == "14d ago"

    def test_weeks_ago(self):
        assert _age_label(19) == "2w ago"

    def test_month_ago(self):
        assert _age_label(33) == "1mo ago"

    def test_none_returns_empty(self):
        assert _age_label(None) == ""


# ---------------------------------------------------------------------------
# _age_color
# ---------------------------------------------------------------------------


class TestAgeColor:
    def test_zero_days_is_green(self):
        assert _age_color(0) == "hsl(120, 70%, 42%)"

    def test_14_days_is_red(self):
        assert _age_color(14) == "hsl(0, 70%, 42%)"

    def test_7_days_is_midpoint(self):
        assert _age_color(7) == "hsl(60, 70%, 42%)"

    def test_none_returns_none(self):
        assert _age_color(None) is None

    def test_clamps_above_prune(self):
        assert _age_color(30) == "hsl(0, 70%, 42%)"


# ---------------------------------------------------------------------------
# _age_badge_html
# ---------------------------------------------------------------------------


class TestAgeBadgeHtml:
    def test_new_badge_is_blue(self):
        html = _age_badge_html("2026-04-03", "2026-04-03", is_new=True)
        assert "new" in html
        assert "#58a6ff" in html

    def test_pending_badge_has_age(self):
        html = _age_badge_html("2026-04-01", "2026-04-03", is_new=False)
        assert "2d ago" in html
        assert "hsl(" in html

    def test_empty_date_returns_empty(self):
        assert _age_badge_html("", "2026-04-03") == ""

    def test_fixed_width(self):
        html = _age_badge_html("2026-04-03", "2026-04-03", is_new=True)
        assert "58px" in html


# ---------------------------------------------------------------------------
# _sort_by_date_desc
# ---------------------------------------------------------------------------


class TestSortByDateDesc:
    def test_sorts_newest_first(self):
        items = [
            {"email_date": "2026-03-30", "company": "Old"},
            {"email_date": "2026-04-02", "company": "New"},
            {"email_date": "2026-04-01", "company": "Mid"},
        ]
        result = _sort_by_date_desc(items)
        assert [r["company"] for r in result] == ["New", "Mid", "Old"]

    def test_uses_added_at_as_fallback(self):
        items = [
            {"added_at": "2026-03-28", "company": "Old"},
            {"email_date": "2026-04-01", "company": "New"},
        ]
        result = _sort_by_date_desc(items)
        assert result[0]["company"] == "New"

    def test_items_without_date_sort_last(self):
        items = [
            {"company": "NoDate"},
            {"email_date": "2026-04-01", "company": "HasDate"},
        ]
        result = _sort_by_date_desc(items)
        assert result[0]["company"] == "HasDate"
        assert result[1]["company"] == "NoDate"

    def test_empty_list(self):
        assert _sort_by_date_desc([]) == []

    def test_preserves_original_list(self):
        items = [
            {"email_date": "2026-03-30"},
            {"email_date": "2026-04-02"},
        ]
        _sort_by_date_desc(items)
        assert items[0]["email_date"] == "2026-03-30"


# ---------------------------------------------------------------------------
# _build_persistence_summary
# ---------------------------------------------------------------------------


class TestBuildPersistenceSummary:
    def test_empty_when_no_stats(self):
        assert _build_persistence_summary({}) == ""
        assert _build_persistence_summary({"persistence_stats": {}}) == ""

    def test_empty_when_all_zero(self):
        stats = {
            "persistence_stats": {
                "pending_merged": 0,
                "responses_found": 0,
                "screened_ids_pruned": 0,
                "correspondence_pruned": 0,
            }
        }
        assert _build_persistence_summary(stats) == ""

    def test_shows_merged_pending(self):
        html = _build_persistence_summary({"persistence_stats": {"pending_merged": 3}})
        assert "Merged 3 pending results" in html
        assert "persistence-summary" in html

    def test_shows_responses_found(self):
        html = _build_persistence_summary({"persistence_stats": {"responses_found": 1}})
        assert "Found 1 recruiter response" in html

    def test_shows_pruned_ids(self):
        html = _build_persistence_summary({"persistence_stats": {"screened_ids_pruned": 12}})
        assert "Pruned 12 stale screening records" in html

    def test_shows_correspondence_pruned(self):
        html = _build_persistence_summary({"persistence_stats": {"correspondence_pruned": 2}})
        assert "Pruned 2 closed correspondence entries" in html

    def test_shows_pending_total_when_no_merge(self):
        html = _build_persistence_summary({"persistence_stats": {"pending_total": 5}})
        assert "5 pending results carried forward" in html

    def test_hides_pending_total_when_merged(self):
        html = _build_persistence_summary(
            {"persistence_stats": {"pending_merged": 2, "pending_total": 5}}
        )
        assert "carried forward" not in html

    def test_singular_forms(self):
        html = _build_persistence_summary({"persistence_stats": {"pending_merged": 1}})
        assert "1 pending result from" in html
        assert "results" not in html

    def test_multiple_stats_combined(self):
        html = _build_persistence_summary(
            {
                "persistence_stats": {
                    "pending_merged": 2,
                    "responses_found": 1,
                    "screened_ids_pruned": 5,
                }
            }
        )
        assert "Merged 2" in html
        assert "Found 1" in html
        assert "Pruned 5" in html


# ---------------------------------------------------------------------------
# Age badges in cards
# ---------------------------------------------------------------------------


class TestAgeBadgeBasic:
    def test_terminal_card_shows_age_badge(self):
        item = make_result(email_date="2026-04-01")
        html = build_terminal_card(item, "pass", run_date="2026-04-03")
        assert "age-badge" in html

    def test_terminal_card_new_badge_without_date(self):
        item = make_result()
        html = build_terminal_card(item, "pass", run_date="2026-04-03")
        # New items always get a blue "new" badge even without a date
        assert "age-badge" in html
        assert "new" in html

    def test_cards_card_shows_age_badge(self):
        item = make_result(email_date="2026-04-03")
        html = build_cards_card(item, "pass", run_date="2026-04-03")
        assert "age-badge" in html

    def test_cards_card_new_badge_without_date(self):
        item = make_result()
        html = build_cards_card(item, "pass", run_date="2026-04-03")
        assert "age-badge" in html
        assert "new" in html

    def test_uses_added_at_for_age_on_pending(self):
        item = make_pending(added_at="2026-04-02")
        html = build_terminal_card(item, "pass", run_date="2026-04-03")
        assert "age-badge" in html
        assert "1d ago" in html


# ---------------------------------------------------------------------------
# Sorting in full export
# ---------------------------------------------------------------------------


class TestSortingInExport:
    def test_results_sorted_newest_first_within_section(self):
        items = [
            make_result("pass", company="OldCo", email_date="2026-03-30"),
            make_result("pass", company="NewCo", email_date="2026-04-02"),
        ]
        html = run_html_export(items, run_date="2026-04-03")
        assert html.index("NewCo") < html.index("OldCo")

    def test_maybe_results_also_sorted(self):
        items = [
            make_result("maybe", company="OldMaybe", email_date="2026-03-28"),
            make_result("maybe", company="NewMaybe", email_date="2026-04-01"),
        ]
        html = run_html_export(items, run_date="2026-04-03")
        assert html.index("NewMaybe") < html.index("OldMaybe")


# ---------------------------------------------------------------------------
# Persistence summary in full export
# ---------------------------------------------------------------------------


class TestPersistenceSummaryInExport:
    def test_persistence_summary_rendered(self):
        html = run_html_export(
            [],
            persistence_stats={"pending_merged": 3},
        )
        assert "persistence-summary" in html
        assert "Merged 3" in html

    def test_no_persistence_summary_when_empty(self):
        html = run_html_export([])
        assert '<div class="persistence-summary">' not in html


# ---------------------------------------------------------------------------
# Pending results rendering
# ---------------------------------------------------------------------------


def make_pending(verdict="pass", company="OldCorp", role="Staff SRE", **kw):
    r = make_result(verdict=verdict, company=company, role=role, **kw)
    r["status"] = "pending"
    r["added_at"] = kw.get("added_at", "2026-04-01")
    r["message_id"] = kw.get("message_id", f"msg_{company}")
    return r


class TestResolvePending:
    def test_uses_pending_from_results_data(self):
        data = {"pending_results": [make_pending()]}
        result = _resolve_pending(data, set())
        assert len(result) == 1
        assert result[0]["company"] == "OldCorp"

    def test_excludes_rescreened_items(self):
        data = {"pending_results": [make_pending(message_id="abc")]}
        result = _resolve_pending(data, {"abc"})
        assert len(result) == 0

    def test_empty_list_respected_no_fallback(self):
        data = {"pending_results": []}
        with patch(
            "export_html._load_pending_fallback",
            return_value=[make_pending()],
        ):
            result = _resolve_pending(data, set())
        assert len(result) == 0

    def test_missing_key_triggers_fallback(self):
        data = {"results": []}
        with patch(
            "export_html._load_pending_fallback",
            return_value=[make_pending()],
        ):
            result = _resolve_pending(data, set())
        assert len(result) == 1


class TestLoadPendingFallback:
    def test_loads_from_criteria_file(self, tmp_path):
        criteria = {
            "pending_results": [
                make_pending(added_at="2026-04-01"),
            ]
        }
        criteria_file = tmp_path / "criteria.json"
        criteria_file.write_text(json.dumps(criteria))
        with patch("export_html.CRITERIA_PATHS", [criteria_file]):
            result = _load_pending_fallback()
        assert len(result) == 1

    def test_prunes_old_entries(self, tmp_path):
        criteria = {
            "pending_results": [
                make_pending(added_at="2020-01-01"),
            ]
        }
        criteria_file = tmp_path / "criteria.json"
        criteria_file.write_text(json.dumps(criteria))
        with patch("export_html.CRITERIA_PATHS", [criteria_file]):
            result = _load_pending_fallback()
        assert len(result) == 0

    def test_returns_empty_when_no_file(self):
        with patch(
            "export_html.CRITERIA_PATHS",
            [Path("/nonexistent/criteria.json")],
        ):
            result = _load_pending_fallback()
        assert result == []

    def test_handles_corrupt_json(self, tmp_path):
        criteria_file = tmp_path / "criteria.json"
        criteria_file.write_text("not valid json{{{")
        with patch("export_html.CRITERIA_PATHS", [criteria_file]):
            result = _load_pending_fallback()
        assert result == []


class TestAgeBadgeInCards:
    def test_terminal_card_shows_new_badge_for_new_item(self):
        item = make_result()
        html = build_terminal_card(item, "pass", "2026-04-02")
        assert "#58a6ff" in html
        assert "new" in html

    def test_terminal_card_shows_age_for_pending(self):
        item = make_pending()
        html = build_terminal_card(item, "pass", "2026-04-02")
        assert "d ago" in html or "today" in html
        assert "hsl(" in html

    def test_cards_card_shows_new_badge_for_new_item(self):
        item = make_result()
        html = build_cards_card(item, "pass", "2026-04-02")
        assert "#58a6ff" in html
        assert "new" in html

    def test_cards_card_shows_age_for_pending(self):
        item = make_pending()
        html = build_cards_card(item, "pass", "2026-04-02")
        assert "d ago" in html or "today" in html
        assert "hsl(" in html

    def test_badges_have_fixed_width(self):
        new_html = build_terminal_card(make_result(), "pass", "2026-04-02")
        pend_html = build_terminal_card(make_pending(), "pass", "2026-04-02")
        assert "58px" in new_html
        assert "58px" in pend_html


class TestPendingMergedInFullExport:
    def test_pending_merged_into_source_groups(self):
        pending = [make_pending()]
        html = run_html_export(
            [make_result(company="NewCo")],
            pending_results=pending,
        )
        assert "OldCorp" in html
        assert "NewCo" in html
        # No separate "Previous Results" section
        assert "Previous Results" not in html

    def test_pending_counted_in_header(self):
        pending = [make_pending("pass", message_id="p1")]
        html = run_html_export(
            [make_result("pass", company="NewCo")],
            pending_results=pending,
        )
        # 2 pass total (1 new + 1 pending)
        assert ">2<" in html

    def test_pending_deduped_against_new(self):
        pending = [make_pending(message_id="same_id")]
        new = [make_result(company="NewCo", message_id="same_id")]
        html = run_html_export(new, pending_results=pending)
        # OldCorp should be excluded (same message_id as NewCo)
        assert "OldCorp" not in html

    def test_only_pending_no_new_results(self):
        pending = [make_pending()]
        html = run_html_export([], pending_results=pending)
        assert "OldCorp" in html
