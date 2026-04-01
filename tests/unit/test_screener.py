"""
Unit tests for screener.py — email screening logic.

All Anthropic API calls are mocked — no real API calls are made.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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


def mock_api_response(result: dict) -> MagicMock:
    """Build a mock Anthropic messages.create response with a tool_use block."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = result
    response = MagicMock()
    response.content = [tool_block]
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

    def test_reply_settings_in_prompt(self):
        s = make_screener()
        prompt = s._build_prompt(MINIMAL_CRITERIA)
        assert "REPLY SETTINGS" in prompt
        assert "direct and professional" in prompt

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
        haiku_result = {
            "company": "TechCorp",
            "role": "Staff Engineer",
            "location": "Remote",
            "verdict": "pass",
            "reason": "Looks good.",
            "dealbreaker_triggered": None,
            "comp_assessment": None,
            "missing_fields": [],
            "reply_draft": None,
        }
        sonnet_result = {
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
            s.client.messages,
            "create",
            side_effect=[mock_api_response(haiku_result), mock_api_response(sonnet_result)],
        ):
            result = s._screen_one(SAMPLE_EMAIL, "system prompt", "Direct Outreach")

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
        # Fail verdict: only Haiku is called — single response
        with patch.object(s.client.messages, "create", return_value=mock_api_response(api_result)):
            result = s._screen_one(SAMPLE_EMAIL, "system prompt", "Direct Outreach")

        assert result["verdict"] == "fail"
        assert result["dealbreaker"] == "Junior or mid-level role"
        assert result["reply_draft"] is None

    def test_maybe_verdict_parsed(self):
        s = make_screener()
        haiku_result = {
            "company": "MaybeCorp",
            "role": "Staff Engineer",
            "location": "Hybrid",
            "verdict": "maybe",
            "reason": "Needs more info.",
            "dealbreaker_triggered": None,
            "comp_assessment": None,
            "missing_fields": [],
            "reply_draft": None,
        }
        sonnet_result = {
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
            s.client.messages,
            "create",
            side_effect=[mock_api_response(haiku_result), mock_api_response(sonnet_result)],
        ):
            result = s._screen_one(SAMPLE_EMAIL, "system prompt", "Direct Outreach")

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
        # Fail verdict: single Haiku call
        with patch.object(s.client.messages, "create", return_value=mock_api_response(api_result)):
            result = s._screen_one(SAMPLE_EMAIL, "system prompt", "LinkedIn Alert")

        assert result["source"] == "LinkedIn Alert"


# ---------------------------------------------------------------------------
# _screen_one — error handling
# ---------------------------------------------------------------------------


class TestScreenOneErrors:
    def test_api_exception_falls_back_to_maybe(self):
        s = make_screener()
        with patch.object(s.client.messages, "create", side_effect=Exception("API timeout")):
            result = s._screen_one(SAMPLE_EMAIL, "system prompt", "Direct Outreach")

        assert result["verdict"] == "maybe"
        assert result["message_id"] == "msg001"

    def test_no_tool_block_in_response_falls_back_to_maybe(self):
        s = make_screener()
        # Response with no tool_use block (e.g. model returned text only)
        text_block = MagicMock()
        text_block.type = "text"
        response = MagicMock()
        response.content = [text_block]
        with patch.object(s.client.messages, "create", return_value=response):
            result = s._screen_one(SAMPLE_EMAIL, "system prompt", "Direct Outreach")

        assert result["verdict"] == "maybe"
        assert result["message_id"] == "msg001"


# ---------------------------------------------------------------------------
# Model tiering and _call_api
# ---------------------------------------------------------------------------


class TestModelTiering:
    def _fail_result(self):
        return {
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

    def _pass_result(self):
        return {
            "company": "GoodCo",
            "role": "Staff Engineer",
            "location": "Remote",
            "verdict": "pass",
            "reason": "Clears all criteria.",
            "dealbreaker_triggered": None,
            "comp_assessment": "Strong.",
            "missing_fields": [],
            "reply_draft": "Interested!\n\nAlex Rivera",
        }

    def test_fail_verdict_calls_api_once(self):
        """Haiku says fail → Sonnet is never called."""
        s = make_screener()
        with patch.object(
            s.client.messages, "create", return_value=mock_api_response(self._fail_result())
        ) as mock_create:
            s._screen_one(SAMPLE_EMAIL, "prompt", "Direct Outreach")
        assert mock_create.call_count == 1

    def test_pass_verdict_calls_api_twice(self):
        """Haiku says pass → Sonnet is called for full judgment."""
        s = make_screener()
        with patch.object(
            s.client.messages,
            "create",
            side_effect=[
                mock_api_response(self._pass_result()),
                mock_api_response(self._pass_result()),
            ],
        ) as mock_create:
            s._screen_one(SAMPLE_EMAIL, "prompt", "Direct Outreach")
        assert mock_create.call_count == 2

    def test_haiku_model_used_for_first_call(self):
        """First API call must use the Haiku model."""
        from screener import _HAIKU_MODEL

        s = make_screener()
        with patch.object(
            s.client.messages,
            "create",
            side_effect=[
                mock_api_response(self._pass_result()),
                mock_api_response(self._pass_result()),
            ],
        ) as mock_create:
            s._screen_one(SAMPLE_EMAIL, "prompt", "Direct Outreach")
        first_call_model = (
            mock_create.call_args_list[0].kwargs.get("model")
            or mock_create.call_args_list[0].args[0]
        )
        assert first_call_model == _HAIKU_MODEL

    def test_sonnet_model_used_for_second_call(self):
        """Second API call must use the Sonnet model."""
        s = make_screener()
        with patch.object(
            s.client.messages,
            "create",
            side_effect=[
                mock_api_response(self._pass_result()),
                mock_api_response(self._pass_result()),
            ],
        ) as mock_create:
            s._screen_one(SAMPLE_EMAIL, "prompt", "Direct Outreach")
        second_call_kwargs = mock_create.call_args_list[1].kwargs
        assert second_call_kwargs["model"] == s.model

    def test_sonnet_call_includes_extended_thinking(self):
        """The Sonnet escalation call must pass thinking parameters."""
        s = make_screener()
        with patch.object(
            s.client.messages,
            "create",
            side_effect=[
                mock_api_response(self._pass_result()),
                mock_api_response(self._pass_result()),
            ],
        ) as mock_create:
            s._screen_one(SAMPLE_EMAIL, "prompt", "Direct Outreach")
        second_call_kwargs = mock_create.call_args_list[1].kwargs
        assert "thinking" in second_call_kwargs
        assert second_call_kwargs["thinking"]["type"] == "enabled"

    def test_haiku_call_has_no_extended_thinking(self):
        """The Haiku fast-path must NOT use extended thinking."""
        from screener import _HAIKU_MODEL

        s = make_screener()
        with patch.object(
            s.client.messages,
            "create",
            side_effect=[
                mock_api_response(self._pass_result()),
                mock_api_response(self._pass_result()),
            ],
        ) as mock_create:
            s._screen_one(SAMPLE_EMAIL, "prompt", "Direct Outreach")
        first_call_kwargs = mock_create.call_args_list[0].kwargs
        assert "thinking" not in first_call_kwargs
        assert first_call_kwargs["model"] == _HAIKU_MODEL

    def test_sonnet_result_used_when_haiku_passes(self):
        """When Haiku escalates, the final result comes from Sonnet, not Haiku."""
        s = make_screener()
        haiku_shallow = {**self._pass_result(), "company": "HaikuGuess", "comp_assessment": None}
        sonnet_deep = {
            **self._pass_result(),
            "company": "SonnetAccurate",
            "comp_assessment": "Top quartile.",
        }
        with patch.object(
            s.client.messages,
            "create",
            side_effect=[mock_api_response(haiku_shallow), mock_api_response(sonnet_deep)],
        ):
            result = s._screen_one(SAMPLE_EMAIL, "prompt", "Direct Outreach")
        assert result["company"] == "SonnetAccurate"
        assert result["comp_assessment"] == "Top quartile."


class TestCallApi:
    def test_returns_tool_input(self):
        s = make_screener()
        expected = {"verdict": "pass", "reason": "good", "missing_fields": []}
        with patch.object(s.client.messages, "create", return_value=mock_api_response(expected)):
            result = s._call_api("content", "system", s.model)
        assert result == expected

    def test_extended_thinking_sets_thinking_param(self):
        from screener import _THINKING_BUDGET

        s = make_screener()
        with patch.object(
            s.client.messages,
            "create",
            return_value=mock_api_response(
                {"verdict": "pass", "reason": "x", "missing_fields": []}
            ),
        ) as mock_create:
            s._call_api("content", "system", s.model, extended_thinking=True)
        kwargs = mock_create.call_args.kwargs
        assert kwargs["thinking"] == {"type": "enabled", "budget_tokens": _THINKING_BUDGET}

    def test_extended_thinking_increases_max_tokens(self):
        from screener import _THINKING_BUDGET

        s = make_screener()
        with patch.object(
            s.client.messages,
            "create",
            return_value=mock_api_response(
                {"verdict": "pass", "reason": "x", "missing_fields": []}
            ),
        ) as mock_create:
            s._call_api("content", "system", s.model, extended_thinking=True)
        kwargs = mock_create.call_args.kwargs
        assert kwargs["max_tokens"] == _THINKING_BUDGET + 1024

    def test_no_extended_thinking_uses_standard_max_tokens(self):
        s = make_screener()
        with patch.object(
            s.client.messages,
            "create",
            return_value=mock_api_response(
                {"verdict": "pass", "reason": "x", "missing_fields": []}
            ),
        ) as mock_create:
            s._call_api("content", "system", s.model, extended_thinking=False)
        kwargs = mock_create.call_args.kwargs
        assert kwargs["max_tokens"] == 1024
        assert "thinking" not in kwargs

    def test_thinking_blocks_in_response_are_ignored(self):
        """If API returns thinking + tool_use blocks, only tool_use input is returned."""
        s = make_screener()
        thinking_block = MagicMock()
        thinking_block.type = "thinking"
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.input = {"verdict": "pass", "reason": "ok", "missing_fields": []}
        response = MagicMock()
        response.content = [thinking_block, tool_block]
        with patch.object(s.client.messages, "create", return_value=response):
            result = s._call_api("content", "system", s.model, extended_thinking=True)
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
        # Two passes × one email each = up to 4 calls if both pass Haiku
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
        # Pass verdict: Haiku + Sonnet per message (2 passes × 2 calls = 4)
        with patch.object(
            s.client.messages,
            "create",
            side_effect=[mock_api_response(api_result)] * 4,
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
        with patch.object(s.client.messages, "create", return_value=mock_api_response(api_result)):
            results, had_drafts = s.run(criteria, gmail, lookback_days=1)

        assert had_drafts is False

    def test_empty_gmail_results(self):
        s = make_screener()
        criteria = {**MINIMAL_CRITERIA, "screened_message_ids": []}
        gmail = self._mock_gmail([], SAMPLE_EMAIL)

        results, had_drafts = s.run(criteria, gmail, lookback_days=1)
        assert results == []
        assert had_drafts is False

    def test_extra_keywords_applied_to_pass1_query(self):
        s = make_screener()
        criteria = {
            **MINIMAL_CRITERIA,
            "screened_message_ids": [],
            "search_settings": {"extra_keywords": ["python", "django"], "extra_exclusions": []},
        }
        gmail = self._mock_gmail([], SAMPLE_EMAIL)
        s.run(criteria, gmail)
        # Verify search was called (extra_kw branch executed without error)
        gmail.search.assert_called()

    def test_extra_exclusions_applied_to_pass2_query(self):
        s = make_screener()
        criteria = {
            **MINIMAL_CRITERIA,
            "screened_message_ids": [],
            "search_settings": {"extra_keywords": [], "extra_exclusions": ["spam@evil.com"]},
        }
        gmail = self._mock_gmail([], SAMPLE_EMAIL)
        s.run(criteria, gmail)
        gmail.search.assert_called()

    def test_warns_when_max_results_limit_hit(self, capsys):
        s = make_screener()
        criteria = {**MINIMAL_CRITERIA, "screened_message_ids": []}
        # Return exactly max_per_pass messages so the limit warning fires
        gmail = MagicMock()
        gmail.search.return_value = [{"id": f"m{i}"} for i in range(5)]
        gmail.get_message.return_value = {}  # empty → skipped
        s.run(criteria, gmail, max_per_pass=5)
        captured = capsys.readouterr()
        assert "limit" in captured.out.lower() or "more" in captured.out.lower()

    def test_skips_empty_message_from_get_message(self):
        s = make_screener()
        criteria = {**MINIMAL_CRITERIA, "screened_message_ids": []}
        gmail = MagicMock()
        gmail.search.return_value = [{"id": "m1"}]
        gmail.get_message.return_value = {}  # falsy → continue
        results, _ = s.run(criteria, gmail)
        assert results == []


# ---------------------------------------------------------------------------
# Query builders
# ---------------------------------------------------------------------------


class TestQueryBuilders:
    def test_pass1_includes_base_keywords(self):
        s = make_screener()
        q = s._build_pass1_query(MINIMAL_CRITERIA, 1)
        assert "opportunity" in q
        assert "newer_than:1d" in q

    def test_pass1_includes_extra_keywords(self):
        s = make_screener()
        criteria = {
            **MINIMAL_CRITERIA,
            "search_settings": {"extra_keywords": ["python", "django"], "extra_exclusions": []},
        }
        q = s._build_pass1_query(criteria, 7)
        assert "python" in q
        assert "django" in q
        assert "newer_than:7d" in q

    def test_pass2_excludes_linkedin(self):
        s = make_screener()
        q = s._build_pass2_query(MINIMAL_CRITERIA, 1)
        assert "-from:linkedin.com" in q
        assert "-from:noreply" in q

    def test_pass2_includes_extra_exclusions(self):
        s = make_screener()
        criteria = {
            **MINIMAL_CRITERIA,
            "search_settings": {"extra_keywords": [], "extra_exclusions": ["spam@evil.com"]},
        }
        q = s._build_pass2_query(criteria, 1)
        assert "-from:spam@evil.com" in q

    def test_pass1_extra_keywords_not_before_newer_than(self):
        """Extra keywords must appear inside the subject clause, not floating before newer_than."""
        s = make_screener()
        criteria = {
            **MINIMAL_CRITERIA,
            "search_settings": {"extra_keywords": ["ml", "ai"], "extra_exclusions": []},
        }
        q = s._build_pass1_query(criteria, 1)
        # newer_than must come at the end, not have keywords injected before it
        assert q.endswith("newer_than:1d")


# ---------------------------------------------------------------------------
# Criteria hash cache
# ---------------------------------------------------------------------------


class TestCriteriaHashCache:
    def test_prompt_cached_on_repeated_call(self):
        s = make_screener()
        p1 = s._get_prompt(MINIMAL_CRITERIA)
        p2 = s._get_prompt(MINIMAL_CRITERIA)
        assert p1 is p2  # same object — not rebuilt

    def test_prompt_rebuilt_when_criteria_changes(self):
        s = make_screener()
        p1 = s._get_prompt(MINIMAL_CRITERIA)
        changed = {
            **MINIMAL_CRITERIA,
            "compensation": {**MINIMAL_CRITERIA["compensation"], "base_salary_floor": 999999},
        }
        p2 = s._get_prompt(changed)
        assert p1 is not p2
        assert "999,999" in p2

    def test_hash_updates_on_criteria_change(self):
        s = make_screener()
        s._get_prompt(MINIMAL_CRITERIA)
        h1 = s._criteria_hash
        changed = {**MINIMAL_CRITERIA, "profile_name": "different"}
        s._get_prompt(changed)
        assert s._criteria_hash != h1


# ---------------------------------------------------------------------------
# ImportError handler (screener.py lines 13–14)
# ---------------------------------------------------------------------------


class TestImportError:
    def test_raises_helpful_message_when_anthropic_missing(self):
        import importlib

        import screener as screener_mod

        with patch.dict(sys.modules, {"anthropic": None}):
            with pytest.raises(ImportError, match="Anthropic SDK not installed"):
                importlib.reload(screener_mod)
        importlib.reload(screener_mod)  # restore to working state


# ---------------------------------------------------------------------------
# on_result callback (run real-time path, screener.py line 189)
# ---------------------------------------------------------------------------


class TestOnResultCallback:
    def _mock_gmail(self, messages, email):
        gmail = MagicMock()
        gmail.search.return_value = messages
        gmail.get_message.return_value = email
        return gmail

    def test_on_result_called_for_each_screened_email(self):
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
            "comp_assessment": None,
            "missing_fields": [],
            "reply_draft": None,
        }
        collected = []
        with patch.object(s.client.messages, "create", return_value=mock_api_response(api_result)):
            s.run(criteria, gmail, on_result=lambda r: collected.append(r))
        # Two passes each with one new message → two calls
        assert len(collected) == 2
        assert all(r["company"] == "TechCorp" for r in collected)

    def test_on_result_not_called_when_none(self):
        """Passing on_result=None should not raise and run normally."""
        s = make_screener()
        criteria = {**MINIMAL_CRITERIA, "screened_message_ids": []}
        gmail = self._mock_gmail([{"id": "msg001"}], SAMPLE_EMAIL)
        api_result = {
            "verdict": "fail",
            "reason": "Bad fit.",
            "dealbreaker_triggered": "Junior",
            "company": "",
            "role": "",
            "location": "",
            "comp_assessment": None,
            "missing_fields": [],
            "reply_draft": None,
        }
        with patch.object(s.client.messages, "create", return_value=mock_api_response(api_result)):
            results, _ = s.run(criteria, gmail, on_result=None)
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# _screen_batch (screener.py lines 308–355)
# ---------------------------------------------------------------------------


def _make_batch_result_item(custom_id: str, tool_input: dict):
    """Build a mock batch result item that looks like the Anthropic SDK's BatchResult."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = tool_input

    inner = MagicMock()
    inner.type = "succeeded"
    inner.message = MagicMock()
    inner.message.content = [tool_block]

    item = MagicMock()
    item.custom_id = custom_id
    item.result = inner
    return item


def _make_failed_batch_item(custom_id: str):
    item = MagicMock()
    item.custom_id = custom_id
    item.result = MagicMock()
    item.result.type = "errored"
    return item


class TestScreenBatch:
    def _msgs(self, n: int) -> list[dict]:
        return [
            {
                "id": f"msg{i}",
                "threadId": f"t{i}",
                "subject": f"Role {i}",
                "from": f"r{i}@co.com",
                "date": "2026-03-28",
                "body": "Hi, interested?",
                "_source": "Direct Outreach",
                "_pass_num": 2,
            }
            for i in range(n)
        ]

    def _haiku_fail(self) -> dict:
        return {
            "verdict": "fail",
            "reason": "Bad fit.",
            "dealbreaker_triggered": "Junior",
            "company": "BadCo",
            "role": "Junior Dev",
            "location": "Onsite",
            "comp_assessment": None,
            "missing_fields": [],
            "reply_draft": None,
        }

    def _pass_result(self) -> dict:
        return {
            "verdict": "pass",
            "reason": "Great fit.",
            "dealbreaker_triggered": None,
            "company": "GoodCo",
            "role": "Staff Engineer",
            "location": "Remote",
            "comp_assessment": "Strong.",
            "missing_fields": [],
            "reply_draft": "Hi,\n\nAlex",
        }

    def test_all_haiku_fails_no_sonnet_batch(self):
        """When every Haiku verdict is fail, no Sonnet batch should be submitted."""
        s = make_screener()
        msgs = self._msgs(2)
        fail = self._haiku_fail()

        haiku_items = [_make_batch_result_item(f"h{i}", fail) for i in range(2)]
        mock_batch = MagicMock()
        mock_batch.id = "batch-haiku"
        mock_batch.processing_status = "ended"

        with (
            patch.object(
                s.client.messages.batches, "create", return_value=mock_batch
            ) as mock_create,
            patch.object(s.client.messages.batches, "retrieve", return_value=mock_batch),
            patch.object(s.client.messages.batches, "results", return_value=iter(haiku_items)),
        ):
            results = s._screen_batch(msgs, "prompt")

        # Only one batch (Haiku); Sonnet never submitted
        mock_create.assert_called_once()
        assert len(results) == 2
        assert all(r["verdict"] == "fail" for r in results)

    def test_pass_verdict_triggers_sonnet_batch(self):
        """pass/maybe Haiku verdicts escalate to a second Sonnet batch."""
        s = make_screener()
        msgs = self._msgs(2)
        haiku_pass = self._pass_result()
        sonnet_pass = {**self._pass_result(), "company": "SonnetCo"}

        haiku_items = [_make_batch_result_item(f"h{i}", haiku_pass) for i in range(2)]
        sonnet_items = [_make_batch_result_item(f"s{i}", sonnet_pass) for i in range(2)]

        haiku_batch = MagicMock()
        haiku_batch.id = "batch-haiku"
        haiku_batch.processing_status = "ended"
        sonnet_batch = MagicMock()
        sonnet_batch.id = "batch-sonnet"
        sonnet_batch.processing_status = "ended"

        create_calls = [haiku_batch, sonnet_batch]
        retrieve_map = {"batch-haiku": haiku_batch, "batch-sonnet": sonnet_batch}
        results_map = {"batch-haiku": iter(haiku_items), "batch-sonnet": iter(sonnet_items)}

        with (
            patch.object(s.client.messages.batches, "create", side_effect=create_calls),
            patch.object(
                s.client.messages.batches,
                "retrieve",
                side_effect=lambda bid: retrieve_map[bid],
            ),
            patch.object(
                s.client.messages.batches,
                "results",
                side_effect=lambda bid: results_map[bid],
            ),
        ):
            results = s._screen_batch(msgs, "prompt")

        assert len(results) == 2
        assert all(r["company"] == "SonnetCo" for r in results)

    def test_failed_batch_item_returns_none_verdict(self):
        """A batch item with result.type != 'succeeded' yields an empty parsed dict."""
        s = make_screener()
        msgs = self._msgs(1)
        failed_item = _make_failed_batch_item("h0")

        batch = MagicMock()
        batch.id = "batch-haiku"
        batch.processing_status = "ended"

        with (
            patch.object(s.client.messages.batches, "create", return_value=batch),
            patch.object(s.client.messages.batches, "retrieve", return_value=batch),
            patch.object(s.client.messages.batches, "results", return_value=iter([failed_item])),
        ):
            results = s._screen_batch(msgs, "prompt")

        assert len(results) == 1
        # verdict falls back to empty parsed dict → "maybe" default
        assert results[0]["verdict"] == "maybe"


# ---------------------------------------------------------------------------
# _wait_for_batch — polling loop (screener.py lines 359–377)
# ---------------------------------------------------------------------------


class TestWaitForBatch:
    def test_polls_until_ended(self):
        """retrieve is called repeatedly until processing_status == 'ended'."""
        s = make_screener()

        pending = MagicMock()
        pending.processing_status = "in_progress"
        ended = MagicMock()
        ended.processing_status = "ended"

        tool_input = {"verdict": "pass", "reason": "ok", "missing_fields": []}
        item = _make_batch_result_item("c0", tool_input)

        with (
            patch.object(
                s.client.messages.batches,
                "retrieve",
                side_effect=[pending, ended],
            ),
            patch.object(s.client.messages.batches, "results", return_value=iter([item])),
            patch("screener.time.sleep"),
        ):
            result = s._wait_for_batch("batch-abc", poll_interval=1)

        assert result == {"c0": tool_input}

    def test_returns_none_for_failed_items(self):
        s = make_screener()
        ended = MagicMock()
        ended.processing_status = "ended"
        failed = _make_failed_batch_item("c0")

        with (
            patch.object(s.client.messages.batches, "retrieve", return_value=ended),
            patch.object(s.client.messages.batches, "results", return_value=iter([failed])),
        ):
            result = s._wait_for_batch("batch-xyz")

        assert result == {"c0": None}

    def test_returns_none_when_no_tool_block(self):
        """A succeeded item with no tool_use block yields None."""
        s = make_screener()
        ended = MagicMock()
        ended.processing_status = "ended"

        item = MagicMock()
        item.custom_id = "c0"
        item.result = MagicMock()
        item.result.type = "succeeded"
        item.result.message = MagicMock()
        item.result.message.content = []  # no tool_use block

        with (
            patch.object(s.client.messages.batches, "retrieve", return_value=ended),
            patch.object(s.client.messages.batches, "results", return_value=iter([item])),
        ):
            result = s._wait_for_batch("batch-xyz")

        assert result == {"c0": None}


# ---------------------------------------------------------------------------
# use_batch path in run() (screener.py lines 172–177)
# ---------------------------------------------------------------------------


class TestRunBatchPath:
    def _mock_gmail(self, n: int) -> MagicMock:
        msgs = [{"id": f"m{i}"} for i in range(n)]
        email = {
            "id": "m0",
            "threadId": "t0",
            "subject": "Role",
            "from": "r@co.com",
            "date": "2026-03-28",
            "body": "Hi",
        }
        gmail = MagicMock()
        gmail.search.return_value = msgs
        gmail.get_message.return_value = email
        return gmail

    def test_batch_path_taken_when_use_batch_and_above_threshold(self):
        from screener import _BATCH_THRESHOLD

        s = make_screener()
        criteria = {**MINIMAL_CRITERIA, "screened_message_ids": []}
        gmail = self._mock_gmail(_BATCH_THRESHOLD + 1)

        batch_result = {
            "verdict": "fail",
            "reason": "No.",
            "dealbreaker_triggered": "x",
            "company": "",
            "role": "",
            "location": "",
            "comp_assessment": None,
            "missing_fields": [],
            "reply_draft": None,
            "message_id": "m0",
        }

        with (
            patch.object(
                s, "_screen_batch", return_value=[batch_result] * (_BATCH_THRESHOLD + 1)
            ) as mock_batch,
            patch.object(s, "_screen_one") as mock_rt,
        ):
            results, _ = s.run(criteria, gmail, use_batch=True)

        mock_batch.assert_called_once()
        mock_rt.assert_not_called()

    def test_realtime_path_taken_when_use_batch_false(self):
        s = make_screener()
        criteria = {**MINIMAL_CRITERIA, "screened_message_ids": []}
        gmail = self._mock_gmail(1)

        fail_result = {
            "verdict": "fail",
            "reason": "No.",
            "dealbreaker_triggered": "x",
            "company": "",
            "role": "",
            "location": "",
            "comp_assessment": None,
            "missing_fields": [],
            "reply_draft": None,
        }

        with (
            patch.object(s, "_screen_batch") as mock_batch,
            patch.object(
                s,
                "_screen_one",
                return_value={
                    **fail_result,
                    "source": "LinkedIn Alert",
                    "message_id": "m0",
                    "thread_id": "t0",
                    "subject": "Role",
                    "from": "r@co.com",
                    "email_date": "2026-03-28",
                },
            ) as mock_rt,
        ):
            s.run(criteria, gmail, use_batch=False)

        mock_batch.assert_not_called()
        mock_rt.assert_called()

    def test_realtime_path_when_below_threshold(self):
        """Even with use_batch=True, fewer than threshold emails use real-time path."""
        s = make_screener()
        criteria = {**MINIMAL_CRITERIA, "screened_message_ids": []}
        gmail = self._mock_gmail(1)  # below threshold

        with (
            patch.object(s, "_screen_batch") as mock_batch,
            patch.object(s, "_screen_one", return_value=None),
        ):
            s.run(criteria, gmail, use_batch=True)

        mock_batch.assert_not_called()

    def test_had_drafts_true_in_batch_path(self):
        from screener import _BATCH_THRESHOLD

        s = make_screener()
        criteria = {**MINIMAL_CRITERIA, "screened_message_ids": []}
        gmail = self._mock_gmail(_BATCH_THRESHOLD + 1)

        draft_result = {
            "verdict": "pass",
            "reason": "Great.",
            "dealbreaker_triggered": None,
            "company": "Co",
            "role": "SWE",
            "location": "Remote",
            "comp_assessment": None,
            "missing_fields": [],
            "reply_draft": "Hi!\n\nAlex",
            "source": "LinkedIn Alert",
            "message_id": "m0",
            "thread_id": "t0",
            "subject": "Role",
            "from": "r@co.com",
            "email_date": "2026-03-28",
        }

        with patch.object(s, "_screen_batch", return_value=[draft_result] * (_BATCH_THRESHOLD + 1)):
            _, had_drafts = s.run(criteria, gmail, use_batch=True)

        assert had_drafts is True
