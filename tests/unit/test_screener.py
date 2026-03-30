"""
Unit tests for screener.py — email screening logic.

All Anthropic API calls are mocked — no real API calls are made.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "claude-code"))

from screener import Screener

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MINIMAL_CRITERIA = {
    "identity": {
        "name": "Alex Rivera",
        "background_summary": "10 years backend engineering",
        "seniority_level": "Staff and above",
        "target_roles": ["Staff Engineer", "Principal Engineer"],
    },
    "target_companies": {
        "industries": ["fintech", "developer tools"],
        "prestige_requirement": "Upper-tier only",
        "whitelist": ["Stripe", "Anthropic"],
        "blacklist": ["Initech"],
    },
    "role_requirements": {
        "employment_type": ["full-time"],
        "remote_preference": "remote only",
    },
    "compensation": {
        "base_salary_floor": 200000,
        "total_comp_target": 350000,
        "sliding_scale_notes": "Remote roles more flexible.",
    },
    "tech_stack": {
        "required": ["Python"],
        "dealbreaker": ["COBOL"],
        "preferred": ["Go", "Rust"],
    },
    "hard_dealbreakers": [
        "Contract or freelance only",
        "Junior or mid-level role",
    ],
    "required_info": [
        "Base salary range",
        "Remote policy",
    ],
    "reply_settings": {
        "tone": "direct and professional",
        "signature": "Alex Rivera",
    },
}

SAMPLE_EMAIL = {
    "id": "msg001",
    "threadId": "thread001",
    "subject": "Staff Engineer at TechCorp",
    "from": "recruiter@techcorp.com",
    "date": "Mon, 28 Mar 2026 09:00:00 -0700",
    "body": "Hi Alex, we have a Staff Engineer role, remote, $250k base. Interested?",
}


def make_screener() -> Screener:
    return Screener(api_key="test-key")


def mock_api_response(text: str) -> MagicMock:
    """Build a mock Anthropic messages.create response."""
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_salary_floor_in_prompt(self):
        s = make_screener()
        prompt = s._build_prompt(MINIMAL_CRITERIA)
        assert "200,000" in prompt

    def test_tc_target_in_prompt(self):
        s = make_screener()
        prompt = s._build_prompt(MINIMAL_CRITERIA)
        assert "350,000" in prompt

    def test_salary_range_rule_in_prompt(self):
        s = make_screener()
        prompt = s._build_prompt(MINIMAL_CRITERIA)
        assert "floor" in prompt.lower()
        assert "range" in prompt.lower()

    def test_dealbreakers_in_prompt(self):
        s = make_screener()
        prompt = s._build_prompt(MINIMAL_CRITERIA)
        assert "Contract or freelance only" in prompt
        assert "Junior or mid-level role" in prompt

    def test_required_info_in_prompt(self):
        s = make_screener()
        prompt = s._build_prompt(MINIMAL_CRITERIA)
        assert "Base salary range" in prompt
        assert "Remote policy" in prompt

    def test_signature_in_prompt(self):
        s = make_screener()
        prompt = s._build_prompt(MINIMAL_CRITERIA)
        assert "Alex Rivera" in prompt

    def test_tone_in_prompt(self):
        s = make_screener()
        prompt = s._build_prompt(MINIMAL_CRITERIA)
        assert "direct and professional" in prompt

    def test_blacklist_in_prompt(self):
        s = make_screener()
        prompt = s._build_prompt(MINIMAL_CRITERIA)
        assert "Initech" in prompt

    def test_target_roles_in_prompt(self):
        s = make_screener()
        prompt = s._build_prompt(MINIMAL_CRITERIA)
        assert "Staff Engineer" in prompt

    def test_stack_dealbreaker_in_prompt(self):
        s = make_screener()
        prompt = s._build_prompt(MINIMAL_CRITERIA)
        assert "COBOL" in prompt

    def test_sliding_scale_notes_in_prompt(self):
        s = make_screener()
        prompt = s._build_prompt(MINIMAL_CRITERIA)
        assert "Remote roles more flexible" in prompt

    def test_json_output_instruction_in_prompt(self):
        s = make_screener()
        prompt = s._build_prompt(MINIMAL_CRITERIA)
        assert "verdict" in prompt
        assert "reply_draft" in prompt

    def test_empty_blacklist_shows_none(self):
        criteria = {
            **MINIMAL_CRITERIA,
            "target_companies": {**MINIMAL_CRITERIA["target_companies"], "blacklist": []},
        }
        s = make_screener()
        prompt = s._build_prompt(criteria)
        assert "none" in prompt.lower()


# ---------------------------------------------------------------------------
# _screen_one — happy path
# ---------------------------------------------------------------------------


class TestScreenOne:
    def test_pass_verdict_parsed(self):
        s = make_screener()
        api_result = {
            "company": "TechCorp",
            "role": "Staff Engineer",
            "location": "Remote",
            "verdict": "pass",
            "reason": "Clears all criteria.",
            "dealbreaker_triggered": None,
            "comp_assessment": "Strong comp.",
            "missing_fields": ["Equity details"],
            "reply_draft": "Hi, I'm interested. Can you share equity details?\n\nAlex Rivera",
        }
        with patch.object(
            s.client.messages, "create", return_value=mock_api_response(json.dumps(api_result))
        ):
            result = s._screen_one(SAMPLE_EMAIL, "system prompt", "Direct Outreach", 2)

        assert result["verdict"] == "pass"
        assert result["company"] == "TechCorp"
        assert result["role"] == "Staff Engineer"
        assert result["reply_draft"] is not None
        assert result["message_id"] == "msg001"
        assert result["thread_id"] == "thread001"

    def test_fail_verdict_parsed(self):
        s = make_screener()
        api_result = {
            "company": "CheapCorp",
            "role": "Junior Engineer",
            "location": "On-site",
            "verdict": "fail",
            "reason": "Junior role — dealbreaker.",
            "dealbreaker_triggered": "Junior or mid-level role",
            "comp_assessment": None,
            "missing_fields": [],
            "reply_draft": None,
        }
        with patch.object(
            s.client.messages, "create", return_value=mock_api_response(json.dumps(api_result))
        ):
            result = s._screen_one(SAMPLE_EMAIL, "system prompt", "Direct Outreach", 2)

        assert result["verdict"] == "fail"
        assert result["dealbreaker"] == "Junior or mid-level role"
        assert result["reply_draft"] is None

    def test_maybe_verdict_parsed(self):
        s = make_screener()
        api_result = {
            "company": "MaybeCorp",
            "role": "Staff Engineer",
            "location": "Hybrid",
            "verdict": "maybe",
            "reason": "Missing comp info.",
            "dealbreaker_triggered": None,
            "comp_assessment": "Unclear.",
            "missing_fields": ["Base salary range", "Remote policy"],
            "reply_draft": "Interested — can you share comp details?\n\nAlex Rivera",
        }
        with patch.object(
            s.client.messages, "create", return_value=mock_api_response(json.dumps(api_result))
        ):
            result = s._screen_one(SAMPLE_EMAIL, "system prompt", "Direct Outreach", 2)

        assert result["verdict"] == "maybe"
        assert "Base salary range" in result["missing_fields"]

    def test_source_label_preserved(self):
        s = make_screener()
        api_result = {
            "company": "X",
            "role": "Y",
            "location": "",
            "verdict": "fail",
            "reason": "r",
            "dealbreaker_triggered": None,
            "comp_assessment": None,
            "missing_fields": [],
            "reply_draft": None,
        }
        with patch.object(
            s.client.messages, "create", return_value=mock_api_response(json.dumps(api_result))
        ):
            result = s._screen_one(SAMPLE_EMAIL, "system prompt", "LinkedIn Alert", 1)

        assert result["source"] == "LinkedIn Alert"


# ---------------------------------------------------------------------------
# _screen_one — error handling
# ---------------------------------------------------------------------------


class TestScreenOneErrors:
    def test_json_parse_error_falls_back_to_maybe(self):
        s = make_screener()
        with patch.object(
            s.client.messages, "create", return_value=mock_api_response("not valid json at all")
        ):
            result = s._screen_one(SAMPLE_EMAIL, "system prompt", "Direct Outreach", 2)

        assert result["verdict"] == "maybe"
        assert "parse error" in result["reason"].lower()

    def test_api_exception_falls_back_to_maybe(self):
        s = make_screener()
        with patch.object(s.client.messages, "create", side_effect=Exception("API timeout")):
            result = s._screen_one(SAMPLE_EMAIL, "system prompt", "Direct Outreach", 2)

        assert result["verdict"] == "maybe"
        assert result["message_id"] == "msg001"

    def test_partial_json_falls_back_to_maybe(self):
        s = make_screener()
        with patch.object(
            s.client.messages, "create", return_value=mock_api_response('{"verdict": "pass"')
        ):  # truncated
            result = s._screen_one(SAMPLE_EMAIL, "system prompt", "Direct Outreach", 2)

        assert result["verdict"] == "maybe"

    def test_json_in_code_block_stripped(self):
        s = make_screener()
        api_result = {
            "company": "TechCorp",
            "role": "Staff Engineer",
            "location": "Remote",
            "verdict": "pass",
            "reason": "Clears all criteria.",
            "dealbreaker_triggered": None,
            "comp_assessment": None,
            "missing_fields": [],
            "reply_draft": None,
        }
        wrapped = f"```json\n{json.dumps(api_result)}\n```"
        with patch.object(s.client.messages, "create", return_value=mock_api_response(wrapped)):
            result = s._screen_one(SAMPLE_EMAIL, "system prompt", "Direct Outreach", 2)

        assert result["verdict"] == "pass"


# ---------------------------------------------------------------------------
# run — integration with mocked Gmail and API
# ---------------------------------------------------------------------------


class TestRun:
    def _mock_gmail(self, messages: list, email: dict) -> MagicMock:
        gmail = MagicMock()
        gmail.search.return_value = messages
        gmail.get_message.return_value = email
        return gmail

    def test_skips_already_screened_ids(self):
        s = make_screener()
        criteria = {
            **MINIMAL_CRITERIA,
            "screened_message_ids": [{"id": "msg001", "screened_at": "2026-03-01"}],
        }
        gmail = self._mock_gmail([{"id": "msg001"}], SAMPLE_EMAIL)

        with patch.object(s.client.messages, "create") as mock_create:
            results, had_drafts = s.run(criteria, gmail, lookback_days=1)

        mock_create.assert_not_called()
        assert results == []

    def test_new_message_is_screened(self):
        s = make_screener()
        criteria = {**MINIMAL_CRITERIA, "screened_message_ids": []}
        gmail = self._mock_gmail([{"id": "msg001"}], SAMPLE_EMAIL)

        api_result = {
            "company": "TechCorp",
            "role": "Staff Engineer",
            "location": "Remote",
            "verdict": "pass",
            "reason": "Clears criteria.",
            "dealbreaker_triggered": None,
            "comp_assessment": "Strong.",
            "missing_fields": [],
            "reply_draft": "Interested!\n\nAlex Rivera",
        }
        with patch.object(
            s.client.messages, "create", return_value=mock_api_response(json.dumps(api_result))
        ):
            results, had_drafts = s.run(criteria, gmail, lookback_days=1)

        assert len(results) >= 1
        assert had_drafts is True

    def test_had_drafts_false_when_no_reply_drafts(self):
        s = make_screener()
        criteria = {**MINIMAL_CRITERIA, "screened_message_ids": []}
        gmail = self._mock_gmail([{"id": "msg001"}], SAMPLE_EMAIL)

        api_result = {
            "company": "BadCo",
            "role": "Junior Dev",
            "location": "On-site",
            "verdict": "fail",
            "reason": "Junior role.",
            "dealbreaker_triggered": "Junior or mid-level role",
            "comp_assessment": None,
            "missing_fields": [],
            "reply_draft": None,
        }
        with patch.object(
            s.client.messages, "create", return_value=mock_api_response(json.dumps(api_result))
        ):
            results, had_drafts = s.run(criteria, gmail, lookback_days=1)

        assert had_drafts is False

    def test_empty_gmail_results(self):
        s = make_screener()
        criteria = {**MINIMAL_CRITERIA, "screened_message_ids": []}
        gmail = self._mock_gmail([], SAMPLE_EMAIL)

        results, had_drafts = s.run(criteria, gmail, lookback_days=1)
        assert results == []
        assert had_drafts is False
