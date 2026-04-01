"""
Unit tests for setup_wizard.py — interactive first-time setup.

All input() calls are mocked; no interactive prompts are shown.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "claude-code"))

from setup_wizard import ask, ask_bool, ask_int, ask_list, run_setup_wizard

# ---------------------------------------------------------------------------
# ask
# ---------------------------------------------------------------------------


class TestAsk:
    def test_returns_user_input(self):
        with patch("builtins.input", return_value="my answer"):
            assert ask("Question") == "my answer"

    def test_returns_default_when_empty_input(self):
        with patch("builtins.input", return_value=""):
            assert ask("Question", "default_val") == "default_val"

    def test_user_input_overrides_default(self):
        with patch("builtins.input", return_value="override"):
            assert ask("Question", "default_val") == "override"

    def test_no_default_empty_input_returns_empty(self):
        with patch("builtins.input", return_value=""):
            assert ask("Question") == ""

    def test_strips_whitespace(self):
        with patch("builtins.input", return_value="  trimmed  "):
            assert ask("Q") == "trimmed"


# ---------------------------------------------------------------------------
# ask_list
# ---------------------------------------------------------------------------


class TestAskList:
    def test_returns_parsed_list(self):
        with patch("builtins.input", return_value="foo, bar, baz"):
            result = ask_list("Items")
        assert result == ["foo", "bar", "baz"]

    def test_empty_input_returns_empty_list(self):
        with patch("builtins.input", return_value=""):
            result = ask_list("Items")
        assert result == []

    def test_prints_examples_when_provided(self):
        with patch("builtins.input", return_value=""), patch("builtins.print") as mock_print:
            ask_list("Items", examples="A, B, C")
        # Should have printed the examples
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        assert "A, B, C" in printed

    def test_does_not_print_when_no_examples(self):
        with patch("builtins.input", return_value=""), patch("builtins.print") as mock_print:
            ask_list("Items", examples="")
        mock_print.assert_not_called()

    def test_strips_individual_items(self):
        with patch("builtins.input", return_value=" a , b , c "):
            result = ask_list("Items")
        assert result == ["a", "b", "c"]

    def test_filters_empty_items(self):
        with patch("builtins.input", return_value="a,,b,"):
            result = ask_list("Items")
        assert result == ["a", "b"]


# ---------------------------------------------------------------------------
# ask_int
# ---------------------------------------------------------------------------


class TestAskInt:
    def test_returns_integer_from_valid_input(self):
        with patch("builtins.input", return_value="42"):
            assert ask_int("Number", 10) == 42

    def test_returns_default_for_empty_input(self):
        with patch("builtins.input", return_value=""):
            assert ask_int("Number", 10) == 10

    def test_returns_default_for_non_numeric_input(self):
        with patch("builtins.input", return_value="not a number"):
            assert ask_int("Number", 99) == 99


# ---------------------------------------------------------------------------
# ask_bool
# ---------------------------------------------------------------------------


class TestAskBool:
    def test_y_returns_true(self):
        with patch("builtins.input", return_value="y"):
            assert ask_bool("Confirm") is True

    def test_yes_returns_true(self):
        with patch("builtins.input", return_value="yes"):
            assert ask_bool("Confirm") is True

    def test_n_returns_false(self):
        with patch("builtins.input", return_value="n"):
            assert ask_bool("Confirm") is False

    def test_empty_input_uses_default_true(self):
        with patch("builtins.input", return_value=""):
            assert ask_bool("Confirm", default=True) is True

    def test_empty_input_uses_default_false(self):
        with patch("builtins.input", return_value=""):
            assert ask_bool("Confirm", default=False) is False

    def test_case_insensitive(self):
        with patch("builtins.input", return_value="Y"):
            assert ask_bool("Confirm") is True


# ---------------------------------------------------------------------------
# run_setup_wizard
# ---------------------------------------------------------------------------

# Input values for a full wizard run accepting all defaults (empty string = accept default).
# The wizard makes exactly 32 input() calls (31 original + 1 LinkedIn opt-in).
_ALL_DEFAULTS = [""] * 32


class TestRunSetupWizard:
    def test_saves_criteria_file(self, tmp_path):
        out = tmp_path / "criteria.json"
        with patch("builtins.input", side_effect=_ALL_DEFAULTS), patch("builtins.print"):
            run_setup_wizard(out)
        assert out.exists()
        data = json.loads(out.read_text())
        assert "compensation" in data

    def test_creates_parent_directories(self, tmp_path):
        out = tmp_path / "nested" / "deep" / "criteria.json"
        with patch("builtins.input", side_effect=_ALL_DEFAULTS), patch("builtins.print"):
            run_setup_wizard(out)
        assert out.exists()

    def test_default_salary_floor_is_set(self, tmp_path):
        out = tmp_path / "criteria.json"
        with patch("builtins.input", side_effect=_ALL_DEFAULTS), patch("builtins.print"):
            run_setup_wizard(out)
        data = json.loads(out.read_text())
        assert data["compensation"]["base_salary_floor"] == 150000

    def test_custom_name_saved(self, tmp_path):
        out = tmp_path / "criteria.json"
        # Provide "Alice" as name (first input), rest default
        inputs = ["Alice"] + [""] * 31
        with patch("builtins.input", side_effect=inputs), patch("builtins.print"):
            run_setup_wizard(out)
        data = json.loads(out.read_text())
        assert data["identity"]["name"] == "Alice"

    def test_cancel_does_not_save(self, tmp_path):
        out = tmp_path / "criteria.json"
        # Return "n" on the last prompt ("Save this profile?")
        inputs = [""] * 31 + ["n"]
        with patch("builtins.input", side_effect=inputs), patch("builtins.print"):
            run_setup_wizard(out)
        assert not out.exists()

    def test_custom_target_roles_saved(self, tmp_path):
        out = tmp_path / "criteria.json"
        # 4th input() call is ask_list("Target roles"), return something non-empty
        # Calls: name, title, background, seniority, target_roles(4th)
        inputs = ["", "", "", "", "Staff Eng, Principal Eng"] + [""] * 27
        with patch("builtins.input", side_effect=inputs), patch("builtins.print"):
            run_setup_wizard(out)
        data = json.loads(out.read_text())
        assert "Staff Eng" in data["identity"]["target_roles"]

    def test_full_time_only_false_includes_contract(self, tmp_path):
        out = tmp_path / "criteria.json"
        # The "Full-time only?" ask_bool is input call #11 (index 10)
        inputs = [""] * 10 + ["n"] + [""] * 21
        with patch("builtins.input", side_effect=inputs), patch("builtins.print"):
            run_setup_wizard(out)
        data = json.loads(out.read_text())
        assert "contract" in data["role_requirements"]["employment_type"]

    def test_decline_default_dealbreakers_results_in_empty_list(self, tmp_path):
        out = tmp_path / "criteria.json"
        # "Use these defaults?" for dealbreakers is input call #21 (index 20)
        inputs = [""] * 20 + ["n"] + [""] * 11
        with patch("builtins.input", side_effect=inputs), patch("builtins.print"):
            run_setup_wizard(out)
        data = json.loads(out.read_text())
        assert data["hard_dealbreakers"] == []
