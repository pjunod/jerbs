"""
Unit tests for setup_wizard.py — interactive first-time setup.

All input() calls are mocked; no interactive prompts are shown.
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "claude-code"))

from setup_wizard import (
    _save_linkedin_cookies,
    _setup_linkedin,
    _try_browser_cookie3,
    _try_playwright_login,
    ask,
    ask_bool,
    ask_int,
    ask_list,
    run_setup_wizard,
)

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
# The wizard makes exactly 36 input() calls (35 original + 1 LinkedIn opt-in).
_ALL_DEFAULTS = [""] * 36


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
        inputs = ["Alice"] + [""] * 35
        with patch("builtins.input", side_effect=inputs), patch("builtins.print"):
            run_setup_wizard(out)
        data = json.loads(out.read_text())
        assert data["identity"]["name"] == "Alice"

    def test_cancel_does_not_save(self, tmp_path):
        out = tmp_path / "criteria.json"
        # Return "n" on the last prompt ("Save this profile?")
        inputs = [""] * 35 + ["n"]
        with patch("builtins.input", side_effect=inputs), patch("builtins.print"):
            run_setup_wizard(out)
        assert not out.exists()

    def test_custom_target_roles_saved(self, tmp_path):
        out = tmp_path / "criteria.json"
        # 4th input() call is ask_list("Target roles"), return something non-empty
        # Calls: name, title, background, seniority, target_roles(4th)
        inputs = ["", "", "", "", "Staff Eng, Principal Eng"] + [""] * 31
        with patch("builtins.input", side_effect=inputs), patch("builtins.print"):
            run_setup_wizard(out)
        data = json.loads(out.read_text())
        assert "Staff Eng" in data["identity"]["target_roles"]

    def test_full_time_only_false_includes_contract(self, tmp_path):
        out = tmp_path / "criteria.json"
        # The "Full-time only?" ask_bool is input call #15 (index 14)
        # (shifted +4 from original index 10 due to location section)
        inputs = [""] * 14 + ["n"] + [""] * 21
        with patch("builtins.input", side_effect=inputs), patch("builtins.print"):
            run_setup_wizard(out)
        data = json.loads(out.read_text())
        assert "contract" in data["role_requirements"]["employment_type"]

    def test_location_saved(self, tmp_path):
        out = tmp_path / "criteria.json"
        # Location fields start at index 10: current_location, target_locations,
        # open_to_relocation (bool), location_notes
        inputs = [""] * 10 + ["Austin, TX", "SF, NYC, Austin", "n", "Remote preferred"] + [""] * 22
        with patch("builtins.input", side_effect=inputs), patch("builtins.print"):
            run_setup_wizard(out)
        data = json.loads(out.read_text())
        assert data["location"]["current_location"] == "Austin, TX"
        assert "SF" in data["location"]["target_locations"]
        assert data["location"]["open_to_relocation"] is False
        assert data["location"]["location_notes"] == "Remote preferred"

    def test_location_with_relocation(self, tmp_path):
        out = tmp_path / "criteria.json"
        # When open_to_relocation=True, an extra input for conditions is asked (5 location inputs)
        inputs = (
            [""] * 10
            + ["Boston", "NYC, SF", "y", "Only if they cover relo", "EU citizen"]
            + [""] * 22
        )
        with patch("builtins.input", side_effect=inputs), patch("builtins.print"):
            run_setup_wizard(out)
        data = json.loads(out.read_text())
        assert data["location"]["open_to_relocation"] is True
        assert data["location"]["relocation_conditions"] == "Only if they cover relo"
        assert data["location"]["location_notes"] == "EU citizen"

    def test_decline_default_dealbreakers_results_in_empty_list(self, tmp_path):
        out = tmp_path / "criteria.json"
        # "Use these defaults?" for dealbreakers is input call #25 (index 24)
        # (shifted +4 from original index 20 due to location section)
        inputs = [""] * 24 + ["n"] + [""] * 11
        with patch("builtins.input", side_effect=inputs), patch("builtins.print"):
            run_setup_wizard(out)
        data = json.loads(out.read_text())
        assert data["hard_dealbreakers"] == []

    def test_linkedin_enabled_saves_enabled_true(self, tmp_path):
        out = tmp_path / "criteria.json"
        # Input #34 (index 33) is the LinkedIn ask_bool. Say "y".
        # _setup_linkedin is mocked so no extra inputs needed.
        # Remaining: profile_name (#35) + confirm (#36) = 2 more.
        inputs = [""] * 33 + ["y"] + [""] * 2
        with (
            patch("builtins.input", side_effect=inputs),
            patch("builtins.print"),
            patch("setup_wizard._setup_linkedin", return_value=True),
        ):
            run_setup_wizard(out)
        data = json.loads(out.read_text())
        assert data["linkedin"]["enabled"] is True

    def test_linkedin_enabled_but_setup_fails(self, tmp_path):
        out = tmp_path / "criteria.json"
        inputs = [""] * 33 + ["y"] + [""] * 2
        with (
            patch("builtins.input", side_effect=inputs),
            patch("builtins.print"),
            patch("setup_wizard._setup_linkedin", return_value=False),
        ):
            run_setup_wizard(out)
        data = json.loads(out.read_text())
        assert data["linkedin"]["enabled"] is False


# ---------------------------------------------------------------------------
# LinkedIn setup functions
# ---------------------------------------------------------------------------


class TestSaveLinkedInCookies:
    def test_saves_cookies_and_validates(self, tmp_path):
        cookies_path = tmp_path / "cookies.json"
        mock_li_mod = MagicMock()
        mock_li_mod.LinkedInClient.return_value.api.get_user_profile.return_value = {
            "firstName": "Jane",
            "lastName": "Doe",
        }
        with (
            patch("setup_wizard.LINKEDIN_COOKIES_PATH", cookies_path),
            patch.dict("sys.modules", {"linkedin_client": mock_li_mod}),
            patch("builtins.print"),
        ):
            result = _save_linkedin_cookies("AQE123", "ajax:456")
        assert result is True
        saved = json.loads(cookies_path.read_text())
        assert saved["li_at"] == "AQE123"

    def test_returns_true_even_on_validation_failure(self, tmp_path):
        cookies_path = tmp_path / "cookies.json"
        mock_li_mod = MagicMock()
        mock_li_mod.LinkedInClient.side_effect = Exception("bad")
        with (
            patch("setup_wizard.LINKEDIN_COOKIES_PATH", cookies_path),
            patch.dict("sys.modules", {"linkedin_client": mock_li_mod}),
            patch("builtins.print"),
        ):
            result = _save_linkedin_cookies("AQE123", "ajax:456")
        assert result is True
        assert cookies_path.exists()


class TestTryBrowserCookie3:
    def test_returns_cookies_when_found(self):
        mock_bc3 = MagicMock()
        cookie_li = MagicMock()
        cookie_li.name = "li_at"
        cookie_li.value = "AQE123"
        cookie_js = MagicMock()
        cookie_js.name = "JSESSIONID"
        cookie_js.value = "ajax:456"
        mock_bc3.chrome.return_value = [cookie_li, cookie_js]

        with (
            patch.dict("sys.modules", {"browser_cookie3": mock_bc3}),
            patch("builtins.print"),
        ):
            result = _try_browser_cookie3("chrome")
        assert result == ("AQE123", "ajax:456")

    def test_returns_none_when_not_installed(self):
        with (
            patch.dict("sys.modules", {"browser_cookie3": None}),
            patch("builtins.print"),
        ):
            result = _try_browser_cookie3("chrome")
        assert result is None

    def test_returns_none_for_unsupported_browser(self):
        mock_bc3 = MagicMock()
        with (
            patch.dict("sys.modules", {"browser_cookie3": mock_bc3}),
            patch("builtins.print"),
        ):
            result = _try_browser_cookie3("opera")
        assert result is None

    def test_returns_none_when_cookies_not_found(self):
        mock_bc3 = MagicMock()
        other_cookie = MagicMock()
        other_cookie.name = "other"
        other_cookie.value = "val"
        mock_bc3.chrome.return_value = [other_cookie]
        with (
            patch.dict("sys.modules", {"browser_cookie3": mock_bc3}),
            patch("builtins.print"),
        ):
            result = _try_browser_cookie3("chrome")
        assert result is None

    def test_returns_none_on_exception(self):
        mock_bc3 = MagicMock()
        mock_bc3.chrome.side_effect = Exception("permission denied")
        with (
            patch.dict("sys.modules", {"browser_cookie3": mock_bc3}),
            patch("builtins.print"),
        ):
            result = _try_browser_cookie3("chrome")
        assert result is None

    def test_firefox_browser(self):
        mock_bc3 = MagicMock()
        cookie_li = MagicMock()
        cookie_li.name = "li_at"
        cookie_li.value = "FF_AQE"
        cookie_js = MagicMock()
        cookie_js.name = "JSESSIONID"
        cookie_js.value = "FF_AJAX"
        mock_bc3.firefox.return_value = [cookie_li, cookie_js]
        with (
            patch.dict("sys.modules", {"browser_cookie3": mock_bc3}),
            patch("builtins.print"),
        ):
            result = _try_browser_cookie3("firefox")
        assert result == ("FF_AQE", "FF_AJAX")

    def test_safari_browser(self):
        mock_bc3 = MagicMock()
        cookie_li = MagicMock()
        cookie_li.name = "li_at"
        cookie_li.value = "SF_AQE"
        cookie_js = MagicMock()
        cookie_js.name = "JSESSIONID"
        cookie_js.value = "SF_AJAX"
        mock_bc3.safari.return_value = [cookie_li, cookie_js]
        with (
            patch.dict("sys.modules", {"browser_cookie3": mock_bc3}),
            patch("builtins.print"),
        ):
            result = _try_browser_cookie3("safari")
        assert result == ("SF_AQE", "SF_AJAX")


class TestTryPlaywrightLogin:
    def test_returns_none_when_playwright_not_installed(self):
        with (
            patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}),
            patch("builtins.print"),
        ):
            result = _try_playwright_login()
        assert result is None

    def test_returns_cookies_on_successful_login(self):
        mock_pw_mod = MagicMock()
        mock_pw = MagicMock()
        mock_pw_mod.sync_playwright.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_mod.sync_playwright.return_value.__exit__ = MagicMock(return_value=False)
        mock_context = mock_pw.chromium.launch.return_value.new_context.return_value
        mock_context.cookies.return_value = [
            {"name": "li_at", "value": "AQE_PW"},
            {"name": "JSESSIONID", "value": "ajax:PW"},
        ]
        with (
            patch.dict(
                "sys.modules", {"playwright": MagicMock(), "playwright.sync_api": mock_pw_mod}
            ),
            patch("builtins.print"),
        ):
            result = _try_playwright_login()
        assert result == ("AQE_PW", "ajax:PW")

    def test_returns_none_when_cookies_missing_after_login(self):
        mock_pw_mod = MagicMock()
        mock_pw = MagicMock()
        mock_pw_mod.sync_playwright.return_value.__enter__ = MagicMock(return_value=mock_pw)
        mock_pw_mod.sync_playwright.return_value.__exit__ = MagicMock(return_value=False)
        mock_context = mock_pw.chromium.launch.return_value.new_context.return_value
        mock_context.cookies.return_value = [{"name": "other", "value": "x"}]
        with (
            patch.dict(
                "sys.modules", {"playwright": MagicMock(), "playwright.sync_api": mock_pw_mod}
            ),
            patch("builtins.print"),
        ):
            result = _try_playwright_login()
        assert result is None

    def test_returns_none_on_exception(self):
        mock_pw_mod = MagicMock()
        mock_pw_mod.sync_playwright.return_value.__enter__ = MagicMock(
            side_effect=Exception("browser crashed")
        )
        mock_pw_mod.sync_playwright.return_value.__exit__ = MagicMock(return_value=False)
        with (
            patch.dict(
                "sys.modules", {"playwright": MagicMock(), "playwright.sync_api": mock_pw_mod}
            ),
            patch("builtins.print"),
        ):
            result = _try_playwright_login()
        assert result is None


class TestSetupLinkedin:
    def test_tier1_success(self):
        """browser_cookie3 succeeds → saves cookies, returns True."""
        with (
            patch("builtins.input", side_effect=["chrome"]),
            patch("builtins.print"),
            patch("setup_wizard._try_browser_cookie3", return_value=("AQE", "AJAX")),
            patch("setup_wizard._save_linkedin_cookies", return_value=True) as mock_save,
        ):
            result = _setup_linkedin()
        assert result is True
        mock_save.assert_called_once_with("AQE", "AJAX")

    def test_tier2_success(self):
        """browser_cookie3 fails → playwright succeeds → saves cookies."""
        with (
            patch("builtins.input", side_effect=["chrome", "y"]),
            patch("builtins.print"),
            patch("setup_wizard._try_browser_cookie3", return_value=None),
            patch("setup_wizard._try_playwright_login", return_value=("PW_AQE", "PW_AJAX")),
            patch("setup_wizard._save_linkedin_cookies", return_value=True) as mock_save,
        ):
            result = _setup_linkedin()
        assert result is True
        mock_save.assert_called_once_with("PW_AQE", "PW_AJAX")

    def test_tier3_manual_success(self):
        """Both auto methods fail → manual entry succeeds."""
        with (
            patch("builtins.input", side_effect=["chrome", "n", "MANUAL_LI", "MANUAL_JS"]),
            patch("builtins.print"),
            patch("setup_wizard._try_browser_cookie3", return_value=None),
            patch("setup_wizard._save_linkedin_cookies", return_value=True) as mock_save,
        ):
            result = _setup_linkedin()
        assert result is True
        mock_save.assert_called_once_with("MANUAL_LI", "MANUAL_JS")

    def test_tier3_manual_empty_returns_false(self):
        """Manual entry with empty values returns False."""
        with (
            patch("builtins.input", side_effect=["chrome", "n", "", ""]),
            patch("builtins.print"),
            patch("setup_wizard._try_browser_cookie3", return_value=None),
        ):
            result = _setup_linkedin()
        assert result is False

    def test_tier2_declined_falls_to_manual(self):
        """User declines playwright → falls through to manual entry."""
        with (
            patch("builtins.input", side_effect=["chrome", "n", "LI", "JS"]),
            patch("builtins.print"),
            patch("setup_wizard._try_browser_cookie3", return_value=None),
            patch("setup_wizard._save_linkedin_cookies", return_value=True),
        ):
            result = _setup_linkedin()
        assert result is True

    def test_tier2_playwright_fails_falls_to_manual(self):
        """Playwright returns None → falls through to manual entry."""
        with (
            patch("builtins.input", side_effect=["chrome", "y", "LI", "JS"]),
            patch("builtins.print"),
            patch("setup_wizard._try_browser_cookie3", return_value=None),
            patch("setup_wizard._try_playwright_login", return_value=None),
            patch("setup_wizard._save_linkedin_cookies", return_value=True),
        ):
            result = _setup_linkedin()
        assert result is True
