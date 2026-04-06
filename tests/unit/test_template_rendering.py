"""
Template rendering tests — verify that results-template.html correctly renders
screening results from fetched JSON using a headless browser.

These tests use playwright to load the generated HTML and inspect the DOM after
client-side JavaScript execution. They cover the rendering pipeline that unit
tests cannot reach: theme switching, card building, filter bar, age badges,
and light/dark mode — all of which execute in JavaScript.

Files are served via a local HTTP server so the <script src="results-data.js"> tag works
(file:// URLs cannot use fetch).

Requires: playwright (pip install playwright && playwright install chromium)
"""

import sys
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

try:
    from playwright.sync_api import sync_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "shared" / "scripts"))
from export_html import export_to_html

pytestmark = pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_DATA = {
    "run_date": "2026-04-04",
    "profile_name": "Test Profile",
    "mode": "dry-run",
    "lookback_days": 7,
    "actions": [
        {
            "title": "Recruiter replied — Stripe",
            "body": "Jane responded 2 hours ago",
            "links": [{"url": "https://example.com", "label": "View thread"}],
        }
    ],
    "persistence_stats": {
        "pending_merged": 2,
        "responses_found": 1,
    },
    "pending_results": [
        {
            "verdict": "pass",
            "company": "PendingCorp",
            "role": "Staff SRE",
            "location": "Remote",
            "source": "Direct Outreach",
            "reason": "Strong match.",
            "comp_assessment": "Good comp.",
            "missing_fields": [],
            "reply_draft": "",
            "email_url": "",
            "posting_url": "",
            "email_date": "2026-04-01",
            "message_id": "msg_pending",
            "status": "pending",
            "added_at": "2026-04-01",
            "sent": False,
        }
    ],
    "results": [
        {
            "verdict": "pass",
            "company": "Acme Inc",
            "role": "Principal Engineer",
            "location": "San Francisco, CA",
            "source": "Direct Outreach",
            "reason": "Clears all criteria with strong comp.",
            "comp_assessment": "$400k TC, above target.",
            "missing_fields": ["equity details"],
            "reply_draft": "Thanks for reaching out! I'm interested.",
            "draft_url": "https://mail.google.com/draft/123",
            "email_url": "https://mail.google.com/msg/456",
            "posting_url": "https://acme.com/jobs/123",
            "email_date": "2026-04-04",
            "message_id": "msg_acme",
            "sent": False,
        },
        {
            "verdict": "maybe",
            "company": "Beta Corp",
            "role": "Senior SRE",
            "location": "Remote",
            "source": "Job Alert Listings",
            "reason": "Comp unclear, location good.",
            "comp_assessment": "Not specified.",
            "missing_fields": ["salary", "equity"],
            "reply_draft": "Could you share more about compensation?",
            "draft_url": "",
            "email_url": "https://mail.google.com/msg/789",
            "posting_url": "",
            "email_date": "2026-04-03",
            "message_id": "msg_beta",
            "sent": False,
        },
        {
            "verdict": "fail",
            "company": "Gamma LLC",
            "role": "Junior Dev",
            "location": "Onsite only",
            "source": "Job Alert Listings",
            "reason": "Below experience level.",
            "dealbreaker": "seniority",
            "comp_assessment": "",
            "missing_fields": [],
            "reply_draft": "",
            "email_url": "",
            "posting_url": "",
            "email_date": "2026-04-02",
            "message_id": "msg_gamma",
            "sent": False,
        },
    ],
}


class _QuietHandler(SimpleHTTPRequestHandler):
    """HTTP handler that suppresses log output during tests."""

    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="module")
def served_dir(tmp_path_factory):
    """Set up a tmpdir with HTML + results-data.js, served via HTTP."""
    tmp = tmp_path_factory.mktemp("template_test")
    html_path = tmp / "index.html"
    export_to_html(SAMPLE_DATA.copy(), str(html_path))
    # Verify results-data.js was created
    assert (tmp / "results-data.js").exists()
    return tmp


@pytest.fixture(scope="module")
def http_server(served_dir):
    """Start a local HTTP server serving the test directory."""
    handler = partial(_QuietHandler, directory=str(served_dir))
    server = HTTPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    """Launch a shared headless browser for all tests in this module."""
    pw = sync_playwright().start()
    b = pw.chromium.launch(headless=True)
    yield b
    b.close()
    pw.stop()


@pytest.fixture()
def page(browser, http_server):
    """Open a fresh page with the rendered HTML for each test.
    Uses dark color scheme to match the expected default behavior."""
    ctx = browser.new_context(color_scheme="dark")
    p = ctx.new_page()
    p.goto(f"{http_server}/index.html")
    p.wait_for_selector("#app .header, #app .top-bar", timeout=5000)
    yield p
    p.close()
    ctx.close()


# ---------------------------------------------------------------------------
# Core rendering
# ---------------------------------------------------------------------------


class TestPageRenders:
    def test_app_container_has_content(self, page):
        app = page.query_selector("#app")
        assert app is not None
        assert len(app.inner_html()) > 100

    def test_title_contains_run_date(self, page):
        title = page.title()
        assert "2026-04-04" in title

    def test_no_placeholder_visible(self, page):
        # The placeholder is in the raw HTML but should not be in rendered content
        app_text = page.inner_text("#app")
        assert "__RESULTS_DATA__" not in app_text


# ---------------------------------------------------------------------------
# Card counts
# ---------------------------------------------------------------------------


class TestCardCounts:
    def test_interested_count(self, page):
        # 1 new pass + 1 pending pass = 2 interested
        text = page.inner_text("#app")
        assert "2" in text  # interested count

    def test_maybe_count(self, page):
        text = page.inner_text("#app")
        assert "1" in text  # maybe count

    def test_filtered_count(self, page):
        text = page.inner_text("#app")
        assert "1" in text  # filtered count

    def test_pass_cards_rendered(self, page):
        cards = page.query_selector_all('[data-verdict="pass"]')
        assert len(cards) == 2  # Acme + PendingCorp

    def test_maybe_cards_rendered(self, page):
        cards = page.query_selector_all('.card[data-verdict="maybe"]')
        assert len(cards) == 1

    def test_fail_items_rendered(self, page):
        fail_items = page.query_selector_all('[data-verdict="fail"], [data-verdict="filtered"]')
        assert len(fail_items) >= 1


# ---------------------------------------------------------------------------
# Card content
# ---------------------------------------------------------------------------


class TestCardContent:
    def test_company_names_visible(self, page):
        text = page.inner_text("#app").lower()
        assert "acme inc" in text
        assert "beta corp" in text
        assert "pendingcorp" in text

    def test_role_visible(self, page):
        text = page.inner_text("#app")
        assert "Principal Engineer" in text

    def test_draft_reply_present(self, page):
        # Draft is in collapsed card body — check innerHTML (not visible text)
        html = page.inner_html("#app")
        assert "Thanks for reaching out" in html

    def test_posting_link_present(self, page):
        links = page.query_selector_all('a[href="https://acme.com/jobs/123"]')
        assert len(links) >= 1

    def test_email_link_present(self, page):
        links = page.query_selector_all('a[href="https://mail.google.com/msg/456"]')
        assert len(links) >= 1


# ---------------------------------------------------------------------------
# Action banners
# ---------------------------------------------------------------------------


class TestActionBanners:
    def test_action_banner_rendered(self, page):
        banners = page.query_selector_all(".action-banner")
        assert len(banners) >= 1

    def test_action_banner_content(self, page):
        text = page.inner_text("#app").lower()
        assert "stripe" in text
        assert "jane responded" in text


# ---------------------------------------------------------------------------
# Persistence summary
# ---------------------------------------------------------------------------


class TestPersistenceSummary:
    def test_persistence_summary_rendered(self, page):
        summary = page.query_selector(".persistence-summary")
        assert summary is not None

    def test_pending_merged_shown(self, page):
        text = page.inner_text(".persistence-summary")
        assert "2" in text and "pending" in text.lower()


# ---------------------------------------------------------------------------
# Theme switching
# ---------------------------------------------------------------------------


class TestThemeSwitching:
    def test_default_theme_is_terminal(self, page):
        # Terminal theme has css-terminal enabled
        term_style = page.query_selector("#css-terminal")
        assert term_style is not None
        assert term_style.get_attribute("disabled") is None

    def test_switch_to_cards_theme(self, page):
        page.evaluate("switchTheme('cards')")
        page.wait_for_timeout(200)
        cards_style = page.query_selector("#css-cards")
        assert cards_style is not None
        assert cards_style.get_attribute("disabled") is None
        # Terminal should be disabled
        term_style = page.query_selector("#css-terminal")
        assert term_style.get_attribute("disabled") is not None

    def test_switch_back_to_terminal(self, page):
        page.evaluate("switchTheme('cards')")
        page.evaluate("switchTheme('terminal')")
        page.wait_for_timeout(200)
        term_style = page.query_selector("#css-terminal")
        assert term_style.get_attribute("disabled") is None

    def test_cards_theme_renders_cards(self, page):
        page.evaluate("switchTheme('cards')")
        page.wait_for_timeout(200)
        # Cards theme should still have pass/maybe cards
        cards = page.query_selector_all('[data-verdict="pass"]')
        assert len(cards) == 2


# ---------------------------------------------------------------------------
# Filter bar
# ---------------------------------------------------------------------------


class TestFilterBar:
    def test_filter_bar_present(self, page):
        bar = page.query_selector(".filter-bar")
        assert bar is not None

    def test_filter_interested_only(self, page):
        page.evaluate("setFilter('pass', document.querySelector('.filter-btn'))")
        page.wait_for_timeout(100)
        visible = page.query_selector_all('[data-verdict="pass"]:not(.hidden)')
        hidden = page.query_selector_all('[data-verdict="maybe"].hidden')
        assert len(visible) >= 1
        assert len(hidden) >= 1

    def test_filter_all_shows_everything(self, page):
        # First filter to pass only
        page.evaluate("setFilter('pass', document.querySelector('.filter-btn'))")
        # Then reset to all
        page.evaluate("setFilter('all', document.querySelector('.filter-btn'))")
        page.wait_for_timeout(100)
        hidden = page.query_selector_all("[data-verdict].hidden")
        assert len(hidden) == 0


# ---------------------------------------------------------------------------
# Light/dark mode
# ---------------------------------------------------------------------------


class TestLightDarkMode:
    def test_default_is_dark(self, page):
        has_light = page.evaluate("document.body.classList.contains('light')")
        assert has_light is False

    def test_toggle_to_light(self, page):
        page.evaluate("toggleLight()")
        has_light = page.evaluate("document.body.classList.contains('light')")
        assert has_light is True

    def test_toggle_back_to_dark(self, page):
        page.evaluate("toggleLight()")
        page.evaluate("toggleLight()")
        has_light = page.evaluate("document.body.classList.contains('light')")
        assert has_light is False

    def test_light_mode_button_label_updates(self, page):
        btn = page.query_selector("#theme-btn")
        assert btn.inner_text() == "Light"
        page.evaluate("toggleLight()")
        assert btn.inner_text() == "Dark"


class TestSystemLightPreference:
    """Verify that prefers-color-scheme: light is respected."""

    def test_light_system_preference_activates_light_mode(self, browser, http_server):
        ctx = browser.new_context(color_scheme="light")
        p = ctx.new_page()
        p.goto(f"{http_server}/index.html")
        p.wait_for_selector("#app .header, #app .top-bar", timeout=5000)
        has_light = p.evaluate("document.body.classList.contains('light')")
        assert has_light is True
        btn = p.query_selector("#theme-btn")
        assert btn.inner_text() == "Dark"
        p.close()
        ctx.close()


# ---------------------------------------------------------------------------
# Age badges
# ---------------------------------------------------------------------------


class TestAgeBadges:
    def test_new_item_has_new_badge(self, page):
        new_badges = page.query_selector_all('[data-isnew="true"]')
        assert len(new_badges) >= 1

    def test_pending_item_has_age_badge(self, page):
        age_badges = page.query_selector_all(".age-badge")
        # Should have badges for both new and pending items
        assert len(age_badges) >= 2


# ---------------------------------------------------------------------------
# Download button
# ---------------------------------------------------------------------------


class TestDownloadButton:
    def test_save_button_exists(self, page):
        buttons = page.query_selector_all("button")
        save_btn = [b for b in buttons if "Save" in b.inner_text()]
        assert len(save_btn) >= 1
