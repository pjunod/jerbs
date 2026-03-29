"""
Unit tests for jerbs.py — daemon entry point helpers.
"""

import json
import pytest
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch, MagicMock

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
        output = self._capture_summary({
            "profile_name": "My Search",
            "compensation": {"base_salary_floor": 200000, "total_comp_target": 350000},
            "screened_message_ids": [],
            "last_run_date": "never",
        })
        assert "My Search" in output

    def test_shows_base_floor(self):
        output = self._capture_summary({
            "profile_name": "Test",
            "compensation": {"base_salary_floor": 245000, "total_comp_target": 400000},
            "screened_message_ids": [],
            "last_run_date": "",
        })
        assert "245" in output

    def test_shows_screened_count(self):
        output = self._capture_summary({
            "profile_name": "Test",
            "compensation": {"base_salary_floor": 200000, "total_comp_target": 300000},
            "screened_message_ids": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "last_run_date": "",
        })
        assert "3" in output

    def test_shows_last_run_date(self):
        output = self._capture_summary({
            "profile_name": "Test",
            "compensation": {"base_salary_floor": 200000, "total_comp_target": 300000},
            "screened_message_ids": [],
            "last_run_date": "2026-03-28",
        })
        assert "2026-03-28" in output

    def test_handles_missing_compensation_fields(self):
        # Should not raise even if fields are missing
        jerbs.print_summary({
            "profile_name": "Minimal",
            "compensation": {},
            "screened_message_ids": [],
            "last_run_date": "",
        })


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
            "identity": {"name": "", "background_summary": "", "seniority_level": "", "target_roles": []},
            "target_companies": {"industries": [], "prestige_requirement": "", "whitelist": [], "blacklist": []},
            "role_requirements": {"employment_type": ["full-time"], "remote_preference": ""},
            "compensation": {"base_salary_floor": 225000, "total_comp_target": 350000, "sliding_scale_notes": ""},
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
            "identity": {"name": "", "background_summary": "", "seniority_level": "", "target_roles": []},
            "target_companies": {"industries": [], "prestige_requirement": "", "whitelist": [], "blacklist": []},
            "role_requirements": {"employment_type": ["full-time"], "remote_preference": ""},
            "compensation": {"base_salary_floor": 225000, "total_comp_target": 350000, "sliding_scale_notes": ""},
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
        import json as _json

        screener = Screener(api_key="test")
        content_block = MagicMock()
        content_block.text = _json.dumps(api_json)
        mock_response = MagicMock()
        mock_response.content = [content_block]

        gmail = MagicMock()
        gmail.search.return_value = [{"id": "msg001"}]
        gmail.get_message.return_value = {
            "id": "msg001", "threadId": "t001",
            "subject": "Staff Eng at TechCorp", "from": "r@tc.com",
            "date": "2026-03-28", "body": "Hi, Staff Eng role, $300k, remote.",
        }
        return screener, gmail, mock_response

    def test_had_drafts_true_when_reply_generated(self, tmp_path):
        api_result = {
            "company": "TechCorp", "role": "Staff Engineer", "location": "Remote",
            "verdict": "pass", "reason": "Clears criteria.",
            "dealbreaker_triggered": None, "comp_assessment": "Strong.",
            "missing_fields": [], "reply_draft": "Interested!\n\nAlex",
        }
        screener, gmail, mock_response = self._make_deps(api_result)
        criteria = {
            "profile_name": "Test",
            "compensation": {"base_salary_floor": 200000, "total_comp_target": 350000},
            "screened_message_ids": [],
            "last_run_date": "",
            "search_settings": {},
            "identity": {"name": "Alex", "background_summary": "", "seniority_level": "", "target_roles": []},
            "target_companies": {"industries": [], "prestige_requirement": "", "whitelist": [], "blacklist": []},
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
            "company": "BadCo", "role": "Junior Dev", "location": "On-site",
            "verdict": "fail", "reason": "Junior role.",
            "dealbreaker_triggered": "Junior role", "comp_assessment": None,
            "missing_fields": [], "reply_draft": None,
        }
        screener, gmail, mock_response = self._make_deps(api_result)
        criteria = {
            "profile_name": "Test",
            "compensation": {"base_salary_floor": 200000, "total_comp_target": 350000},
            "screened_message_ids": [],
            "last_run_date": "",
            "search_settings": {},
            "identity": {"name": "Alex", "background_summary": "", "seniority_level": "", "target_roles": []},
            "target_companies": {"industries": [], "prestige_requirement": "", "whitelist": [], "blacklist": []},
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
