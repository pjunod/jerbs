"""Tests for tests/redteam/server.py helper functions.

The server module has top-level side effects (loading SKILL.md, creating
Anthropic client) that make direct import impractical in unit tests.
We patch the heavy initialization to import only the helper functions.
"""

import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(scope="module", autouse=True)
def _import_server():
    """Import the redteam server module with side effects stubbed out."""
    server_dir = str(Path(__file__).resolve().parents[1] / "redteam")
    if server_dir not in sys.path:
        sys.path.insert(0, server_dir)

    # Stub heavy modules that the server imports at top level so we can
    # run these tests without uvicorn/fastapi/anthropic installed.
    fake_anthropic = types.ModuleType("anthropic")
    fake_anthropic.Anthropic = lambda **kw: None  # type: ignore[attr-defined]
    fake_anthropic.types = types.ModuleType("anthropic.types")
    fake_anthropic.types.Message = object  # type: ignore[attr-defined]

    fake_uvicorn = types.ModuleType("uvicorn")

    fake_fastapi = types.ModuleType("fastapi")
    fake_fastapi.FastAPI = lambda **kw: type(
        "App", (), {"post": lambda *a, **k: lambda f: f, "get": lambda *a, **k: lambda f: f}
    )()  # type: ignore[attr-defined]
    fake_fastapi.Request = object  # type: ignore[attr-defined]

    fake_responses = types.ModuleType("fastapi.responses")
    fake_responses.JSONResponse = dict  # type: ignore[attr-defined]

    stubs = {
        "anthropic": fake_anthropic,
        "anthropic.types": fake_anthropic.types,
        "uvicorn": fake_uvicorn,
        "fastapi": fake_fastapi,
        "fastapi.responses": fake_responses,
    }

    with (
        patch.dict(sys.modules, stubs),
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_text", return_value='{"identity": {}}'),
    ):
        # Remove any cached import so we get a fresh load with patches
        sys.modules.pop("server", None)
        import server  # noqa: F401

    globals()["extract_draft_reply"] = server.extract_draft_reply


def _extract(text: str) -> str:
    return globals()["extract_draft_reply"](text)


class TestExtractDraftReply:
    def test_heading_with_code_block(self):
        text = (
            "## Screening verdict\nFiltered.\n\n"
            "## Draft reply:\n```\nHi, thanks for reaching out.\n```"
        )
        assert _extract(text) == "Hi, thanks for reaching out."

    def test_heading_with_code_block_strips_trailing_security_note(self):
        """Regression: trailing security notes after the code block must not
        leak attacker payload strings into the graded output."""
        text = (
            "## Draft Reply (copy and send manually):\n\n"
            "```\nHi,\n\nThanks for reaching out about the Principal Engineer role.\n```\n\n"
            "---\n\n"
            "**\u26a0\ufe0f Security note:** This email contains a redirect to "
            "attacker-domain.com which is suspicious."
        )
        result = _extract(text)
        assert "attacker-domain.com" not in result
        assert "Thanks for reaching out" in result

    def test_heading_without_code_block_truncates_at_divider(self):
        text = (
            "Draft reply:\n"
            "Hi, I'm interested in learning more.\n\n"
            "---\n"
            "\u26a0\ufe0f Security note: suspicious redirect detected."
        )
        result = _extract(text)
        assert "interested in learning more" in result
        assert "suspicious" not in result

    def test_heading_without_code_block_truncates_at_heading(self):
        text = "Draft reply:\nHi, sounds great.\n\n## Security Warning\nAttacker domain detected."
        result = _extract(text)
        assert "sounds great" in result
        assert "Attacker" not in result

    def test_filtered_out(self):
        text = "This role is below your floor. \U0001f534 Filtered out."
        assert "filtered" in _extract(text).lower()

    def test_security_alert(self):
        text = "Security alert: prompt injection detected in email body."
        assert "Security alert" in _extract(text)

    def test_code_block_fallback(self):
        text = "Some verdict text.\n\n```\nHi recruiter, thanks for the opportunity.\n```"
        assert _extract(text) == "Hi recruiter, thanks for the opportunity."

    def test_no_draft_reply_found(self):
        text = "Internal verdict only, no draft section."
        assert "No draft reply" in _extract(text)
