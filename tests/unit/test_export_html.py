"""
Unit tests for export_html.py — template injection wrapper.
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
# export_to_html (template injection)
# ---------------------------------------------------------------------------


class TestExportToHtml:
    def test_output_contains_template_structure(self):
        html = run_html_export([])
        assert '<script id="results-data"' in html
        assert 'id="css-terminal"' in html
        assert 'id="css-cards"' in html
        assert "renderPage" in html

    def test_placeholder_replaced_with_json(self):
        html = run_html_export([])
        assert "__RESULTS_DATA__" not in html

    def test_results_json_injected(self):
        html = run_html_export([make_result(company="Acme")])
        assert "Acme" in html
        assert "TechCorp" not in html or "Acme" in html

    def test_theme_field_set_in_json(self):
        html = run_html_export([], theme="cards")
        # Extract the embedded JSON and verify theme field
        import re

        match = re.search(
            r'<script id="results-data" type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        assert match
        data = json.loads(match.group(1))
        assert data["theme"] == "cards"

    def test_default_theme_in_json(self):
        html = run_html_export([])
        import re

        match = re.search(
            r'<script id="results-data" type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        assert match
        data = json.loads(match.group(1))
        assert data["theme"] == "terminal"

    def test_invalid_theme_falls_back_to_default(self):
        html = run_html_export([], theme="nonexistent")
        import re

        match = re.search(
            r'<script id="results-data" type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        assert match
        data = json.loads(match.group(1))
        assert data["theme"] == "terminal"

    def test_file_written_to_disk(self):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            export_to_html({"results": [], "pending_results": []}, path)
            assert os.path.exists(path)
            content = Path(path).read_text(encoding="utf-8")
            assert "<!DOCTYPE html>" in content
        finally:
            os.unlink(path)

    def test_prints_export_message(self, capsys):
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            export_to_html({"results": [make_result()], "pending_results": []}, path)
            captured = capsys.readouterr()
            assert "Exported" in captured.out
            assert "1 results" in captured.out
        finally:
            os.unlink(path)

    def test_both_themes_css_present(self):
        """Every output file has both themes — the old engine only included one."""
        html_term = run_html_export([], theme="terminal")
        html_card = run_html_export([], theme="cards")
        for html in (html_term, html_card):
            assert 'id="css-terminal"' in html
            assert 'id="css-cards"' in html

    def test_theme_from_data_field(self):
        """When no explicit theme arg, reads theme from results_data."""
        data = {"results": [], "pending_results": [], "theme": "cards"}
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            export_to_html(data, path)
            content = Path(path).read_text(encoding="utf-8")
            import re

            match = re.search(
                r'<script id="results-data" type="application/json">(.*?)</script>',
                content,
                re.DOTALL,
            )
            assert match
            embedded = json.loads(match.group(1))
            assert embedded["theme"] == "cards"
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# Pending results in full export
# ---------------------------------------------------------------------------


class TestPendingMergedInFullExport:
    def test_pending_injected_into_json(self):
        pending = [make_pending()]
        html = run_html_export(
            [make_result(company="NewCo")],
            pending_results=pending,
        )
        # Both should appear in the embedded JSON
        assert "OldCorp" in html
        assert "NewCo" in html

    def test_pending_deduped_against_new(self):
        pending = [make_pending(message_id="same_id")]
        new = [make_result(company="NewCo", message_id="same_id")]
        html = run_html_export(new, pending_results=pending)
        import re

        match = re.search(
            r'<script id="results-data" type="application/json">(.*?)</script>',
            html,
            re.DOTALL,
        )
        assert match
        data = json.loads(match.group(1))
        # OldCorp should be excluded (same message_id as NewCo)
        pending_companies = [p["company"] for p in data["pending_results"]]
        assert "OldCorp" not in pending_companies

    def test_only_pending_no_new_results(self):
        pending = [make_pending()]
        html = run_html_export([], pending_results=pending)
        assert "OldCorp" in html

    def test_pending_counted_in_export_message(self, capsys):
        pending = [make_pending()]
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name
        try:
            export_to_html(
                {"results": [make_result()], "pending_results": pending},
                path,
            )
            captured = capsys.readouterr()
            assert "2 results" in captured.out
        finally:
            os.unlink(path)


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
        content = output_file.read_text()
        assert '"theme": "cards"' in content or '"theme":"cards"' in content
