"""
Unit tests for jerbs.py — daemon entry point helpers.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "claude-code"))

import jerbs

# ---------------------------------------------------------------------------
# load_criteria
# ---------------------------------------------------------------------------


class TestLoadCriteria:
    def test_loads_valid_file(self, tmp_path):
        criteria = {"profile_name": "Test", "compensation": {"base_salary_floor": 200000}}
        p = tmp_path / "criteria.json"
        p.write_text(json.dumps(criteria))
        result = jerbs.load_criteria(p)
        assert result["profile_name"] == "Test"

    def test_exits_when_file_missing(self, tmp_path):
        p = tmp_path / "nonexistent.json"
        with pytest.raises(SystemExit):
            jerbs.load_criteria(p)

    def test_returns_dict(self, tmp_path):
        p = tmp_path / "criteria.json"
        p.write_text('{"foo": "bar"}')
        result = jerbs.load_criteria(p)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# save_criteria
# ---------------------------------------------------------------------------


class TestSaveCriteria:
    def test_saves_to_file(self, tmp_path):
        p = tmp_path / "criteria.json"
        criteria = {"profile_name": "Saved"}
        jerbs.save_criteria(criteria, p)
        assert p.exists()
        saved = json.loads(p.read_text())
        assert saved["profile_name"] == "Saved"

    def test_creates_parent_directories(self, tmp_path):
        p = tmp_path / "nested" / "deep" / "criteria.json"
        jerbs.save_criteria({"x": 1}, p)
        assert p.exists()

    def test_overwrites_existing_file(self, tmp_path):
        p = tmp_path / "criteria.json"
        p.write_text('{"old": true}')
        jerbs.save_criteria({"new": True}, p)
        saved = json.loads(p.read_text())
        assert saved == {"new": True}
        assert "old" not in saved

    def test_saved_json_is_valid(self, tmp_path):
        p = tmp_path / "criteria.json"
        jerbs.save_criteria({"a": [1, 2, 3], "b": None}, p)
        parsed = json.loads(p.read_text())
        assert parsed["a"] == [1, 2, 3]
        assert parsed["b"] is None


# ---------------------------------------------------------------------------
# print_summary
# ---------------------------------------------------------------------------


class TestPrintSummary:
    def _capture_summary(self, criteria: dict) -> str:
        with patch("builtins.print") as mock_print:
            jerbs.print_summary(criteria)
            lines = [str(call.args[0]) for call in mock_print.call_args_list if call.args]
        return "\n".join(lines)

    def test_shows_profile_name(self):
        output = self._capture_summary(
            {
                "profile_name": "My Search",
                "compensation": {"base_salary_floor": 200000, "total_comp_target": 350000},
                "screened_message_ids": [],
                "last_run_date": "never",
            }
        )
        assert "My Search" in output

    def test_shows_base_floor(self):
        output = self._capture_summary(
            {
                "profile_name": "Test",
                "compensation": {"base_salary_floor": 245000, "total_comp_target": 400000},
                "screened_message_ids": [],
                "last_run_date": "",
            }
        )
        assert "245" in output

    def test_shows_screened_count(self):
        output = self._capture_summary(
            {
                "profile_name": "Test",
                "compensation": {"base_salary_floor": 200000, "total_comp_target": 300000},
                "screened_message_ids": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
                "last_run_date": "",
            }
        )
        assert "3" in output

    def test_shows_last_run_date(self):
        output = self._capture_summary(
            {
                "profile_name": "Test",
                "compensation": {"base_salary_floor": 200000, "total_comp_target": 300000},
                "screened_message_ids": [],
                "last_run_date": "2026-03-28",
            }
        )
        assert "2026-03-28" in output

    def test_handles_missing_compensation_fields(self):
        # Should not raise even if fields are missing
        jerbs.print_summary(
            {
                "profile_name": "Minimal",
                "compensation": {},
                "screened_message_ids": [],
                "last_run_date": "",
            }
        )


# ---------------------------------------------------------------------------
# run_screen — comp range logic
# These test the screening logic described in SKILL.md via the prompt builder.
# We verify that the prompt correctly encodes the range rule so Claude applies it.
# ---------------------------------------------------------------------------


class TestCompRangeRuleInPrompt:
    """
    The comp range rule lives in screener._build_prompt(). These tests verify
    the prompt text encodes the rule correctly so the model applies it.
    """

    def test_range_rule_says_fail_only_if_top_below_floor(self):
        from screener import Screener

        s = Screener(api_key="test")
        criteria = {
            "identity": {
                "name": "",
                "background_summary": "",
                "seniority_level": "",
                "target_roles": [],
            },
            "target_companies": {
                "industries": [],
                "prestige_requirement": "",
                "whitelist": [],
                "blacklist": [],
            },
            "role_requirements": {"employment_type": ["full-time"], "remote_preference": ""},
            "compensation": {
                "base_salary_floor": 225000,
                "total_comp_target": 350000,
                "sliding_scale_notes": "",
            },
            "tech_stack": {"required": [], "dealbreaker": [], "preferred": []},
            "hard_dealbreakers": [],
            "required_info": [],
            "reply_settings": {"tone": "professional", "signature": ""},
        }
        prompt = s._build_prompt(criteria)
        assert "225,000" in prompt
        # The range rule should instruct: only fail if TOP of range is below floor
        assert "top" in prompt.lower() or "passes" in prompt.lower()

    def test_floor_in_range_passes_note_in_prompt(self):
        from screener import Screener

        s = Screener(api_key="test")
        criteria = {
            "identity": {
                "name": "",
                "background_summary": "",
                "seniority_level": "",
                "target_roles": [],
            },
            "target_companies": {
                "industries": [],
                "prestige_requirement": "",
                "whitelist": [],
                "blacklist": [],
            },
            "role_requirements": {"employment_type": ["full-time"], "remote_preference": ""},
            "compensation": {
                "base_salary_floor": 225000,
                "total_comp_target": 350000,
                "sliding_scale_notes": "",
            },
            "tech_stack": {"required": [], "dealbreaker": [], "preferred": []},
            "hard_dealbreakers": [],
            "required_info": [],
            "reply_settings": {"tone": "professional", "signature": ""},
        }
        prompt = s._build_prompt(criteria)
        # Range rule explicitly says floor-within-range passes
        assert "PASSES" in prompt or "passes" in prompt.lower()


# ---------------------------------------------------------------------------
# run_screen — had_drafts flag
# ---------------------------------------------------------------------------


class TestRunScreen:
    def _make_deps(self, api_json: dict):
        from screener import Screener

        screener = Screener(api_key="test")
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.input = api_json
        mock_response = MagicMock()
        mock_response.content = [tool_block]

        gmail = MagicMock()
        gmail.search.return_value = [{"id": "msg001"}]
        gmail.get_message.return_value = {
            "id": "msg001",
            "threadId": "t001",
            "subject": "Staff Eng at TechCorp",
            "from": "r@tc.com",
            "date": "2026-03-28",
            "body": "Hi, Staff Eng role, $300k, remote.",
        }
        return screener, gmail, mock_response

    def test_had_drafts_true_when_reply_generated(self, tmp_path):
        api_result = {
            "company": "TechCorp",
            "role": "Staff Engineer",
            "location": "Remote",
            "verdict": "pass",
            "reason": "Clears criteria.",
            "dealbreaker_triggered": None,
            "comp_assessment": "Strong.",
            "missing_fields": [],
            "reply_draft": "Interested!\n\nAlex",
        }
        screener, gmail, mock_response = self._make_deps(api_result)
        criteria = {
            "profile_name": "Test",
            "compensation": {"base_salary_floor": 200000, "total_comp_target": 350000},
            "screened_message_ids": [],
            "last_run_date": "",
            "search_settings": {},
            "identity": {
                "name": "Alex",
                "background_summary": "",
                "seniority_level": "",
                "target_roles": [],
            },
            "target_companies": {
                "industries": [],
                "prestige_requirement": "",
                "whitelist": [],
                "blacklist": [],
            },
            "role_requirements": {"employment_type": ["full-time"], "remote_preference": ""},
            "tech_stack": {"required": [], "dealbreaker": [], "preferred": []},
            "hard_dealbreakers": [],
            "required_info": [],
            "reply_settings": {"tone": "professional", "signature": "Alex"},
        }
        criteria_path = tmp_path / "criteria.json"

        with patch.object(screener.client.messages, "create", return_value=mock_response):
            with patch("jerbs.CRITERIA_PATH", criteria_path):
                with patch("jerbs.save_criteria"):
                    had_drafts = jerbs.run_screen(criteria, gmail, screener)

        assert had_drafts is True

    def test_had_drafts_false_when_all_fail(self, tmp_path):
        api_result = {
            "company": "BadCo",
            "role": "Junior Dev",
            "location": "On-site",
            "verdict": "fail",
            "reason": "Junior role.",
            "dealbreaker_triggered": "Junior role",
            "comp_assessment": None,
            "missing_fields": [],
            "reply_draft": None,
        }
        screener, gmail, mock_response = self._make_deps(api_result)
        criteria = {
            "profile_name": "Test",
            "compensation": {"base_salary_floor": 200000, "total_comp_target": 350000},
            "screened_message_ids": [],
            "last_run_date": "",
            "search_settings": {},
            "identity": {
                "name": "Alex",
                "background_summary": "",
                "seniority_level": "",
                "target_roles": [],
            },
            "target_companies": {
                "industries": [],
                "prestige_requirement": "",
                "whitelist": [],
                "blacklist": [],
            },
            "role_requirements": {"employment_type": ["full-time"], "remote_preference": ""},
            "tech_stack": {"required": [], "dealbreaker": [], "preferred": []},
            "hard_dealbreakers": [],
            "required_info": [],
            "reply_settings": {"tone": "professional", "signature": "Alex"},
        }
        criteria_path = tmp_path / "criteria.json"

        with patch.object(screener.client.messages, "create", return_value=mock_response):
            with patch("jerbs.CRITERIA_PATH", criteria_path):
                with patch("jerbs.save_criteria"):
                    had_drafts = jerbs.run_screen(criteria, gmail, screener)

        assert had_drafts is False


# ---------------------------------------------------------------------------
# log
# ---------------------------------------------------------------------------


class TestLog:
    def test_prints_timestamped_message(self, capsys):
        jerbs.log("hello world", path=Path("/nonexistent/__nope__/jerbs.log"))
        captured = capsys.readouterr()
        assert "hello world" in captured.out
        assert "[" in captured.out  # timestamp bracket

    def test_writes_to_log_file(self, tmp_path):
        log_path = tmp_path / "jerbs.log"
        jerbs.log("written to file", path=log_path)
        assert log_path.exists()
        assert "written to file" in log_path.read_text()

    def test_swallows_write_exception(self, tmp_path):
        log_path = tmp_path / "jerbs.log"
        with patch("builtins.open", side_effect=PermissionError("denied")):
            # Should not raise even if the file write fails
            jerbs.log("test", path=log_path)

    def test_appends_to_existing_log(self, tmp_path):
        log_path = tmp_path / "jerbs.log"
        jerbs.log("first", path=log_path)
        jerbs.log("second", path=log_path)
        content = log_path.read_text()
        assert "first" in content
        assert "second" in content


# ---------------------------------------------------------------------------
# run_screen — branch coverage
# ---------------------------------------------------------------------------


def _minimal_criteria():
    return {
        "profile_name": "Test",
        "compensation": {"base_salary_floor": 200000, "total_comp_target": 350000},
        "screened_message_ids": [],
        "last_run_date": "",
        "search_settings": {},
    }


class TestRunScreenBranches:
    def test_empty_results_returns_false(self):
        screener = MagicMock()
        screener.run.return_value = ([], False)
        gmail = MagicMock()
        criteria = _minimal_criteria()
        with patch("jerbs.log"):
            result = jerbs.run_screen(criteria, gmail, screener)
        assert result is False

    def test_dealbreaker_is_logged(self):
        screener = MagicMock()
        screener.run.return_value = (
            [
                {
                    "verdict": "maybe",
                    "company": "Acme",
                    "role": "SRE",
                    "dealbreaker": "No remote",
                    "missing_fields": [],
                    "reply_draft": None,
                    "message_id": "m1",
                }
            ],
            False,
        )
        gmail = MagicMock()
        criteria = _minimal_criteria()
        log_calls = []
        with patch("jerbs.log", side_effect=lambda msg, **kw: log_calls.append(msg)):
            with patch("jerbs.save_criteria"):
                jerbs.run_screen(criteria, gmail, screener)
        assert any("No remote" in c for c in log_calls)

    def test_missing_fields_are_logged(self):
        screener = MagicMock()
        screener.run.return_value = (
            [
                {
                    "verdict": "pass",
                    "company": "Acme",
                    "role": "SRE",
                    "dealbreaker": None,
                    "missing_fields": ["salary", "location"],
                    "reply_draft": None,
                    "message_id": "m2",
                }
            ],
            False,
        )
        gmail = MagicMock()
        criteria = _minimal_criteria()
        log_calls = []
        with patch("jerbs.log", side_effect=lambda msg, **kw: log_calls.append(msg)):
            with patch("jerbs.save_criteria"):
                jerbs.run_screen(criteria, gmail, screener)
        assert any("salary" in c for c in log_calls)

    def test_send_mode_calls_send_draft(self):
        screener = MagicMock()
        screener.run.return_value = (
            [
                {
                    "verdict": "pass",
                    "company": "Acme",
                    "role": "SRE",
                    "dealbreaker": None,
                    "missing_fields": [],
                    "reply_draft": "Hi there!",
                    "thread_id": "t99",
                    "message_id": "m3",
                }
            ],
            True,
        )
        gmail = MagicMock()
        criteria = _minimal_criteria()
        with patch("jerbs.log"):
            with patch("jerbs.save_criteria"):
                with patch("jerbs._send_draft") as mock_send:
                    jerbs.run_screen(criteria, gmail, screener, send_mode=True)
        mock_send.assert_called_once()

    def test_export_mode_calls_export_results(self):
        screener = MagicMock()
        screener.run.return_value = (
            [
                {
                    "verdict": "fail",
                    "company": "Acme",
                    "role": "SRE",
                    "dealbreaker": None,
                    "missing_fields": [],
                    "reply_draft": None,
                    "message_id": "m4",
                }
            ],
            False,
        )
        gmail = MagicMock()
        criteria = _minimal_criteria()
        with patch("jerbs.log"):
            with patch("jerbs.save_criteria"):
                with patch("jerbs._export_results") as mock_export:
                    jerbs.run_screen(criteria, gmail, screener, export=True)
        mock_export.assert_called_once()


# ---------------------------------------------------------------------------
# _send_draft
# ---------------------------------------------------------------------------


class TestSendDraft:
    def test_skips_if_no_draft(self):
        gmail = MagicMock()
        jerbs._send_draft(gmail, {"thread_id": "t1", "reply_draft": None}, {})
        gmail.send_reply.assert_not_called()

    def test_skips_if_no_thread_id(self):
        gmail = MagicMock()
        jerbs._send_draft(gmail, {"thread_id": None, "reply_draft": "Hi!"}, {})
        gmail.send_reply.assert_not_called()

    def test_sends_reply_with_signature(self):
        gmail = MagicMock()
        result = {"thread_id": "t1", "reply_draft": "Hi!", "company": "Acme", "role": "SWE"}
        criteria = {"reply_settings": {"signature": "Best, Alex"}}
        with patch("jerbs.log"):
            jerbs._send_draft(gmail, result, criteria)
        gmail.send_reply.assert_called_once_with(thread_id="t1", body="Hi!", signature="Best, Alex")

    def test_sends_reply_with_empty_signature_when_missing(self):
        gmail = MagicMock()
        result = {"thread_id": "t1", "reply_draft": "Hi!", "company": "Acme", "role": "SWE"}
        with patch("jerbs.log"):
            jerbs._send_draft(gmail, result, {})
        gmail.send_reply.assert_called_once_with(thread_id="t1", body="Hi!", signature="")

    def test_logs_error_on_send_exception(self):
        gmail = MagicMock()
        gmail.send_reply.side_effect = Exception("network error")
        result = {"thread_id": "t1", "reply_draft": "Hi!", "company": "Acme", "role": "SWE"}
        log_calls = []
        with patch("jerbs.log", side_effect=lambda msg, **kw: log_calls.append(msg)):
            jerbs._send_draft(gmail, result, {})
        assert any("Failed" in c or "network error" in c for c in log_calls)


# ---------------------------------------------------------------------------
# _export_results
# ---------------------------------------------------------------------------


class TestExportResults:
    def test_calls_export_to_xlsx(self):
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"export_results": mock_module}):
            with patch("jerbs.log"):
                jerbs._export_results([{"verdict": "pass"}], {})
        mock_module.export_to_xlsx.assert_called_once()

    def test_includes_results_in_export_payload(self):
        mock_module = MagicMock()
        results = [{"verdict": "pass", "company": "Acme"}]
        with patch.dict("sys.modules", {"export_results": mock_module}):
            with patch("jerbs.log"):
                jerbs._export_results(results, {})
        payload = mock_module.export_to_xlsx.call_args[0][0]
        assert payload["results"] == results

    def test_logs_export_path_on_success(self):
        mock_module = MagicMock()
        log_calls = []
        with patch.dict("sys.modules", {"export_results": mock_module}):
            with patch("jerbs.log", side_effect=lambda msg, **kw: log_calls.append(msg)):
                jerbs._export_results([], {})
        assert any("Exported" in c or "jerbs_" in c for c in log_calls)

    def test_logs_error_on_exception(self):
        mock_module = MagicMock()
        mock_module.export_to_xlsx.side_effect = Exception("disk full")
        log_calls = []
        with patch.dict("sys.modules", {"export_results": mock_module}):
            with patch("jerbs.log", side_effect=lambda msg, **kw: log_calls.append(msg)):
                jerbs._export_results([], {})
        assert any("Export failed" in c or "disk full" in c for c in log_calls)


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------


def _write_criteria(path: Path) -> None:
    criteria = {
        "profile_name": "Test Search",
        "compensation": {"base_salary_floor": 200000, "total_comp_target": 350000},
        "screened_message_ids": [],
        "last_run_date": "never",
        "search_settings": {
            "biz_start_hour": 9,
            "biz_end_hour": 17,
            "timezone": "America/New_York",
        },
    }
    path.write_text(json.dumps(criteria))


class TestMain:
    def test_setup_flag_runs_wizard(self, tmp_path):
        cfile = tmp_path / "criteria.json"
        with patch("sys.argv", ["jerbs", "--setup", "--criteria", str(cfile)]):
            with patch("jerbs.run_setup_wizard") as mock_wizard:
                with patch("builtins.print"):
                    jerbs.main()
        mock_wizard.assert_called_once_with(cfile)

    def test_once_mode_calls_run_screen_then_exits(self, tmp_path):
        cfile = tmp_path / "criteria.json"
        _write_criteria(cfile)
        with patch("sys.argv", ["jerbs", "--once", "--criteria", str(cfile)]):
            with patch("jerbs.GmailClient"):
                with patch("jerbs.Screener"):
                    with patch("jerbs.run_screen", return_value=False) as mock_run:
                        with patch("builtins.print"):
                            jerbs.main()
        mock_run.assert_called_once()

    def test_send_mode_cancelled_skips_screening(self, tmp_path):
        cfile = tmp_path / "criteria.json"
        _write_criteria(cfile)
        with patch("sys.argv", ["jerbs", "--send", "--once", "--criteria", str(cfile)]):
            with patch("builtins.input", return_value="no"):
                with patch("builtins.print"):
                    with patch("jerbs.run_screen") as mock_run:
                        jerbs.main()
        mock_run.assert_not_called()

    def test_send_mode_confirmed_proceeds(self, tmp_path):
        cfile = tmp_path / "criteria.json"
        _write_criteria(cfile)
        with patch("sys.argv", ["jerbs", "--send", "--once", "--criteria", str(cfile)]):
            with patch("builtins.input", return_value="yes"):
                with patch("builtins.print"):
                    with patch("jerbs.GmailClient"):
                        with patch("jerbs.Screener"):
                            with patch("jerbs.run_screen", return_value=False) as mock_run:
                                jerbs.main()
        mock_run.assert_called_once()

    def test_daemon_loop_runs_one_iteration(self, tmp_path):
        cfile = tmp_path / "criteria.json"
        _write_criteria(cfile)

        mock_event = MagicMock()
        # is_set: False (enter loop) → True (exit loop after one iteration)
        mock_event.is_set.side_effect = [False, True]
        mock_event.wait.return_value = False  # don't break early inside loop

        with patch("sys.argv", ["jerbs", "--criteria", str(cfile)]):
            with patch("jerbs.GmailClient"):
                with patch("jerbs.Screener"):
                    with patch("jerbs.run_screen", return_value=False) as mock_run:
                        with patch("jerbs.log"):
                            with patch("builtins.print"):
                                with patch("jerbs.signal.signal"):
                                    with patch("threading.Event", return_value=mock_event):
                                        jerbs.main()
        mock_run.assert_called_once()

    def test_daemon_loop_triggers_rapid_mode_on_drafts(self, tmp_path):
        cfile = tmp_path / "criteria.json"
        _write_criteria(cfile)

        mock_event = MagicMock()
        mock_event.is_set.side_effect = [False, True]
        mock_event.wait.return_value = False

        mock_scheduler = MagicMock()
        mock_scheduler.biz_start = 9
        mock_scheduler.biz_end = 17
        mock_scheduler.tz_name = "America/New_York"
        mock_scheduler.current_interval.return_value = 300
        mock_scheduler.current_mode.return_value = "normal"

        with patch("sys.argv", ["jerbs", "--criteria", str(cfile)]):
            with patch("jerbs.GmailClient"):
                with patch("jerbs.Screener"):
                    with patch("jerbs.run_screen", return_value=True):
                        with patch("jerbs.Scheduler", return_value=mock_scheduler):
                            with patch("jerbs.log"):
                                with patch("builtins.print"):
                                    with patch("jerbs.signal.signal"):
                                        with patch("threading.Event", return_value=mock_event):
                                            jerbs.main()
        mock_scheduler.trigger_rapid.assert_called_once()
        mock_scheduler.tick.assert_called_once()

    def test_daemon_loop_breaks_when_wait_returns_true(self, tmp_path):
        """Covers the `break` on line 230 when stop_event.wait() returns True."""
        cfile = tmp_path / "criteria.json"
        _write_criteria(cfile)

        mock_event = MagicMock()
        mock_event.is_set.return_value = False  # enter the loop
        mock_event.wait.return_value = True  # break immediately

        with patch("sys.argv", ["jerbs", "--criteria", str(cfile)]):
            with patch("jerbs.GmailClient"):
                with patch("jerbs.Screener"):
                    with patch("jerbs.run_screen") as mock_run:
                        with patch("jerbs.log"):
                            with patch("builtins.print"):
                                with patch("jerbs.signal.signal"):
                                    with patch("threading.Event", return_value=mock_event):
                                        jerbs.main()
        # run_screen should not be reached because we broke out before it
        mock_run.assert_not_called()

    def test_handle_signal_logs_and_sets_stop_event(self, tmp_path):
        """Covers handle_signal body (lines 214-215): log + stop_event.set()."""
        import signal as _signal

        cfile = tmp_path / "criteria.json"
        _write_criteria(cfile)

        captured = {}

        def capture_signal(sig, handler):
            captured[sig] = handler

        mock_event = MagicMock()
        mock_event.is_set.return_value = True  # skip the loop

        log_calls = []

        with patch("sys.argv", ["jerbs", "--criteria", str(cfile)]):
            with patch("jerbs.GmailClient"):
                with patch("jerbs.Screener"):
                    with patch("jerbs.log", side_effect=lambda msg, **kw: log_calls.append(msg)):
                        with patch("builtins.print"):
                            with patch("jerbs.signal.signal", side_effect=capture_signal):
                                with patch("threading.Event", return_value=mock_event):
                                    jerbs.main()
                            # Call the captured handler while jerbs.log is still patched
                            captured[_signal.SIGINT](_signal.SIGINT, None)

        assert any("Shutting down" in c for c in log_calls)
        mock_event.set.assert_called_once()

    def test_script_guard_calls_main(self, tmp_path):
        """Covers `if __name__ == '__main__': main()` on line 245."""
        import runpy

        cfile = tmp_path / "criteria.json"
        jerbs_path = str(Path(__file__).parent.parent.parent / "claude-code" / "jerbs.py")

        with patch("sys.argv", ["jerbs.py", "--setup", "--criteria", str(cfile)]):
            with patch("setup_wizard.run_setup_wizard"):
                with patch("builtins.print"):
                    runpy.run_path(jerbs_path, run_name="__main__")
