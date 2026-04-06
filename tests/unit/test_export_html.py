"""
Unit tests for export_html.py — template copy + results-data.js wrapper.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared" / "scripts"))

from export_html import (
    DEFAULT_THEME,
    TEMPLATE_PATH,
    THEMES,
    _load_pending_fallback,
    _load_scheduler_settings,
    _resolve_pending,
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


def make_pending(verdict="pass", company="OldCorp", role="Staff SRE", **kw):
    r = make_result(verdict=verdict, company=company, role=role, **kw)
    r["status"] = "pending"
    r["added_at"] = kw.get("added_at", "2026-04-01")
    r["message_id"] = kw.get("message_id", f"msg_{company}")
    return r


def _parse_js_data(js_path):
    """Parse results-data.js and return the JSON data."""
    raw = Path(js_path).read_text(encoding="utf-8")
    json_str = raw.removeprefix("var JERBS_RESULTS = ").removesuffix(";")
    return json.loads(json_str)


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
    if "scheduler" in kwargs:
        data["scheduler"] = kwargs["scheduler"]
    with tempfile.TemporaryDirectory() as tmp:
        html_path = os.path.join(tmp, "out.html")
        js_path = os.path.join(tmp, "results-data.js")
        export_to_html(data, html_path, theme=kwargs.get("theme"))
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        results_json = _parse_js_data(js_path)
        return html, results_json


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_themes_tuple(self):
        assert "terminal" in THEMES
        assert "cards" in THEMES

    def test_default_theme(self):
        assert DEFAULT_THEME == "terminal"

    def test_template_path_exists(self):
        assert TEMPLATE_PATH.exists(), f"Template not found at {TEMPLATE_PATH}"


# ---------------------------------------------------------------------------
# export_to_html (template copy + results-data.js)
# ---------------------------------------------------------------------------


class TestExportToHtml:
    def test_output_contains_template_structure(self):
        html, _ = run_html_export([])
        assert '<script id="results-data"' in html
        assert 'id="css-terminal"' in html
        assert 'id="css-cards"' in html
        assert "renderPage" in html

    def test_placeholder_remains_in_html(self):
        """Template is copied as-is — placeholder stays for fallback use."""
        html, _ = run_html_export([])
        assert "__RESULTS_DATA__" in html

    def test_results_js_written(self):
        """Data goes into results-data.js next to the HTML file."""
        _, results_json = run_html_export([make_result(company="Acme")])
        companies = [r["company"] for r in results_json.get("results", [])]
        assert "Acme" in companies

    def test_theme_field_set_in_json(self):
        _, results_json = run_html_export([], theme="cards")
        assert results_json["theme"] == "cards"

    def test_default_theme_in_json(self):
        _, results_json = run_html_export([])
        assert results_json["theme"] == "terminal"

    def test_invalid_theme_falls_back_to_default(self):
        _, results_json = run_html_export([], theme="nonexistent")
        assert results_json["theme"] == "terminal"

    def test_files_written_to_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            html_path = os.path.join(tmp, "out.html")
            js_path = os.path.join(tmp, "results-data.js")
            export_to_html({"results": [], "pending_results": []}, html_path)
            assert os.path.exists(html_path)
            assert os.path.exists(js_path)
            content = Path(html_path).read_text(encoding="utf-8")
            assert "<!DOCTYPE html>" in content

    def test_prints_export_message(self, capsys):
        with tempfile.TemporaryDirectory() as tmp:
            html_path = os.path.join(tmp, "out.html")
            export_to_html({"results": [make_result()], "pending_results": []}, html_path)
            captured = capsys.readouterr()
            assert "Exported" in captured.out
            assert "1 results" in captured.out

    def test_both_themes_css_present(self):
        """Every output file has both themes — the template always has both."""
        html_term, _ = run_html_export([], theme="terminal")
        html_card, _ = run_html_export([], theme="cards")
        for html in (html_term, html_card):
            assert 'id="css-terminal"' in html
            assert 'id="css-cards"' in html

    def test_theme_from_data_field(self):
        """When no explicit theme arg, reads theme from results_data."""
        data = {"results": [], "pending_results": [], "theme": "cards"}
        with tempfile.TemporaryDirectory() as tmp:
            html_path = os.path.join(tmp, "out.html")
            js_path = os.path.join(tmp, "results-data.js")
            export_to_html(data, html_path)
            embedded = _parse_js_data(js_path)
            assert embedded["theme"] == "cards"


# ---------------------------------------------------------------------------
# Scheduler injection from criteria
# ---------------------------------------------------------------------------


class TestSchedulerInjection:
    def test_scheduler_injected_from_criteria(self, tmp_path):
        criteria = {
            "business_hours": {
                "timezone": "America/Chicago",
                "start_hour": 8,
                "end_hour": 18,
            }
        }
        criteria_file = tmp_path / "criteria.json"
        criteria_file.write_text(json.dumps(criteria))
        with patch("export_html.CRITERIA_PATHS", [criteria_file]):
            _, results_json = run_html_export([])
        sched = results_json.get("scheduler")
        assert sched is not None
        assert sched["timezone"] == "America/Chicago"
        assert sched["bizStart"] == 8
        assert sched["bizEnd"] == 18

    def test_scheduler_not_injected_without_criteria(self):
        with patch(
            "export_html.CRITERIA_PATHS",
            [Path("/nonexistent/criteria.json")],
        ):
            _, results_json = run_html_export([])
        assert "scheduler" not in results_json

    def test_scheduler_not_overwritten_when_present(self, tmp_path):
        criteria = {
            "business_hours": {
                "timezone": "America/Chicago",
                "start_hour": 8,
                "end_hour": 18,
            }
        }
        criteria_file = tmp_path / "criteria.json"
        criteria_file.write_text(json.dumps(criteria))
        existing_sched = {"timezone": "UTC", "bizStart": 0, "bizEnd": 24}
        with patch("export_html.CRITERIA_PATHS", [criteria_file]):
            _, results_json = run_html_export([], scheduler=existing_sched)
        assert results_json["scheduler"]["timezone"] == "UTC"

    def test_load_scheduler_settings_returns_none_no_file(self):
        with patch(
            "export_html.CRITERIA_PATHS",
            [Path("/nonexistent/criteria.json")],
        ):
            result = _load_scheduler_settings()
        assert result is None

    def test_load_scheduler_settings_returns_none_no_timezone(self, tmp_path):
        criteria = {"business_hours": {}}
        criteria_file = tmp_path / "criteria.json"
        criteria_file.write_text(json.dumps(criteria))
        with patch("export_html.CRITERIA_PATHS", [criteria_file]):
            result = _load_scheduler_settings()
        assert result is None

    def test_load_scheduler_settings_defaults(self, tmp_path):
        criteria = {"business_hours": {"timezone": "Europe/London"}}
        criteria_file = tmp_path / "criteria.json"
        criteria_file.write_text(json.dumps(criteria))
        with patch("export_html.CRITERIA_PATHS", [criteria_file]):
            result = _load_scheduler_settings()
        assert result == {"timezone": "Europe/London", "bizStart": 9, "bizEnd": 17}

    def test_load_scheduler_settings_handles_corrupt_json(self, tmp_path):
        criteria_file = tmp_path / "criteria.json"
        criteria_file.write_text("not valid json{{{")
        with patch("export_html.CRITERIA_PATHS", [criteria_file]):
            result = _load_scheduler_settings()
        assert result is None


# ---------------------------------------------------------------------------
# Pending results in full export
# ---------------------------------------------------------------------------


class TestPendingMergedInFullExport:
    def test_pending_injected_into_json(self):
        pending = [make_pending()]
        _, results_json = run_html_export(
            [make_result(company="NewCo")],
            pending_results=pending,
        )
        # Both should appear in the results-data.js
        result_companies = [r["company"] for r in results_json.get("results", [])]
        pending_companies = [p["company"] for p in results_json.get("pending_results", [])]
        assert "NewCo" in result_companies
        assert "OldCorp" in pending_companies

    def test_pending_deduped_against_new(self):
        pending = [make_pending(message_id="same_id")]
        new = [make_result(company="NewCo", message_id="same_id")]
        _, results_json = run_html_export(new, pending_results=pending)
        pending_companies = [p["company"] for p in results_json.get("pending_results", [])]
        assert "OldCorp" not in pending_companies

    def test_only_pending_no_new_results(self):
        pending = [make_pending()]
        _, results_json = run_html_export([], pending_results=pending)
        pending_companies = [p["company"] for p in results_json.get("pending_results", [])]
        assert "OldCorp" in pending_companies

    def test_pending_counted_in_export_message(self, capsys):
        pending = [make_pending()]
        with tempfile.TemporaryDirectory() as tmp:
            html_path = os.path.join(tmp, "out.html")
            export_to_html(
                {"results": [make_result()], "pending_results": pending},
                html_path,
            )
            captured = capsys.readouterr()
            assert "2 results" in captured.out


# ---------------------------------------------------------------------------
# _resolve_pending
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _load_pending_fallback
# ---------------------------------------------------------------------------


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
        assert "renderPage" in content
        # results-data.js should also exist
        js_file = tmp_path / "results-data.js"
        assert js_file.exists()

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
        js_file = tmp_path / "results-data.js"
        assert js_file.exists()
        result_data = _parse_js_data(js_file)
        assert result_data["theme"] == "cards"
