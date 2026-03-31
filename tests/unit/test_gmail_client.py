"""
Unit tests for gmail_client.py — Gmail API wrapper.

Google API libraries are already stubbed as MagicMocks via conftest.py.
"""

import base64
import importlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "claude-code"))

import gmail_client
from gmail_client import SCOPES_READONLY, SCOPES_SEND, GmailClient


def make_client(send_mode: bool = False) -> GmailClient:
    """Create a GmailClient with _authenticate mocked out."""
    with patch.object(GmailClient, "_authenticate", return_value=MagicMock()):
        return GmailClient(send_mode=send_mode)


def b64(text: str) -> str:
    """URL-safe base64-encode a string."""
    return base64.urlsafe_b64encode(text.encode()).decode()


# ---------------------------------------------------------------------------
# Import error handler (lines 28–29)
# ---------------------------------------------------------------------------


class TestImportError:
    def test_raises_helpful_message_when_google_libs_missing(self):
        null_mods = {k: None for k in sys.modules if k.startswith("google") or "googleapi" in k}
        with patch.dict(sys.modules, null_mods):
            with pytest.raises(ImportError, match="Google API libraries not installed"):
                importlib.reload(gmail_client)
        importlib.reload(gmail_client)  # restore to working state


# ---------------------------------------------------------------------------
# __init__ / scopes (lines 46–48)
# ---------------------------------------------------------------------------


class TestInit:
    def test_readonly_scopes_by_default(self):
        c = make_client(send_mode=False)
        assert c.send_mode is False
        assert c.scopes == SCOPES_READONLY

    def test_send_scopes_when_send_mode_true(self):
        c = make_client(send_mode=True)
        assert c.send_mode is True
        assert c.scopes == SCOPES_SEND


# ---------------------------------------------------------------------------
# _authenticate (lines 51–71)
# ---------------------------------------------------------------------------


class TestAuthenticate:
    def test_valid_cached_token_skips_refresh(self, tmp_path):
        token = tmp_path / "token.json"
        token.write_text('{"token": "cached"}')

        mock_creds = MagicMock()
        mock_creds.valid = True

        with (
            patch("gmail_client.TOKEN_PATH", token),
            patch("gmail_client.Credentials") as MockCreds,
            patch("gmail_client.build") as mock_build,
        ):
            MockCreds.from_authorized_user_file.return_value = mock_creds
            GmailClient()
            mock_build.assert_called_once_with("gmail", "v1", credentials=mock_creds)

    def test_expired_token_with_refresh_token_calls_refresh(self, tmp_path):
        token = tmp_path / "token.json"
        token.write_text('{"token": "old"}')

        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "rt"

        with (
            patch("gmail_client.TOKEN_PATH", token),
            patch("gmail_client.Credentials") as MockCreds,
            patch("gmail_client.Request"),
            patch("gmail_client.build"),
            patch("builtins.open", mock_open()),
        ):
            MockCreds.from_authorized_user_file.return_value = mock_creds
            GmailClient()
            mock_creds.refresh.assert_called_once()

    def test_missing_credentials_file_raises(self, tmp_path):
        no_token = tmp_path / "token.json"
        no_creds = tmp_path / "credentials.json"

        with (
            patch("gmail_client.TOKEN_PATH", no_token),
            patch("gmail_client.CREDENTIALS_PATH", no_creds),
        ):
            with pytest.raises(FileNotFoundError, match="Gmail credentials not found"):
                GmailClient()

    def test_new_oauth_flow_when_no_cached_token(self, tmp_path):
        no_token = tmp_path / "token.json"
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("{}")

        mock_creds = MagicMock()
        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = mock_creds

        with (
            patch("gmail_client.TOKEN_PATH", no_token),
            patch("gmail_client.CREDENTIALS_PATH", creds_file),
            patch("gmail_client.InstalledAppFlow") as MockFlow,
            patch("gmail_client.build"),
            patch("builtins.open", mock_open()),
        ):
            MockFlow.from_client_secrets_file.return_value = mock_flow
            GmailClient()
            mock_flow.run_local_server.assert_called_once_with(port=0)


# ---------------------------------------------------------------------------
# search (lines 75–100)
# ---------------------------------------------------------------------------


class TestSearch:
    def test_returns_messages(self):
        c = make_client()
        c.service.users().messages().list().execute.return_value = {
            "messages": [{"id": "m1"}, {"id": "m2"}]
        }
        results = c.search("subject:hiring")
        assert len(results) == 2

    def test_no_messages_returns_empty(self):
        c = make_client()
        c.service.users().messages().list().execute.return_value = {}
        results = c.search("q")
        assert results == []

    def test_max_results_limits_count(self):
        c = make_client()
        c.service.users().messages().list().execute.return_value = {
            "messages": [{"id": f"m{i}"} for i in range(10)]
        }
        results = c.search("q", max_results=3)
        assert len(results) == 3

    def test_max_results_none_omits_maxResults_kwarg(self):
        c = make_client()
        execute_mock = c.service.users().messages().list().execute
        execute_mock.return_value = {"messages": [{"id": "m1"}]}
        c.search("q", max_results=None)
        # No exception = no maxResults limit applied
        assert execute_mock.called

    def test_pagination_follows_next_page_token(self):
        c = make_client()
        responses = [
            {"messages": [{"id": "m1"}], "nextPageToken": "tok"},
            {"messages": [{"id": "m2"}]},
        ]
        c.service.users().messages().list().execute.side_effect = responses
        results = c.search("q")
        assert len(results) == 2

    def test_http_error_returns_empty_list(self):
        c = make_client()
        with patch("gmail_client.HttpError", Exception):
            c.service.users().messages().list().execute.side_effect = Exception("403 Forbidden")
            results = c.search("q")
        assert results == []


# ---------------------------------------------------------------------------
# get_message (lines 104–114)
# ---------------------------------------------------------------------------


class TestGetMessage:
    def test_returns_parsed_message(self):
        c = make_client()
        raw_msg = {
            "id": "m1",
            "threadId": "t1",
            "snippet": "Snip",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test"},
                    {"name": "From", "value": "r@co.com"},
                    {"name": "To", "value": "me@me.com"},
                    {"name": "Date", "value": "Mon, 28 Mar 2026"},
                ],
                "body": {"data": b64("Hello world")},
            },
        }
        c.service.users().messages().get().execute.return_value = raw_msg
        result = c.get_message("m1")
        assert result["id"] == "m1"
        assert result["subject"] == "Test"

    def test_http_error_returns_empty_dict(self):
        c = make_client()
        with patch("gmail_client.HttpError", Exception):
            c.service.users().messages().get().execute.side_effect = Exception("404")
            result = c.get_message("missing")
        assert result == {}


# ---------------------------------------------------------------------------
# _parse_message (lines 117–128)
# ---------------------------------------------------------------------------


class TestParseMessage:
    def test_extracts_headers_and_body(self):
        c = make_client()
        msg = {
            "id": "m1",
            "threadId": "t1",
            "snippet": "Preview",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Hello"},
                    {"name": "From", "value": "a@b.com"},
                    {"name": "To", "value": "me@x.com"},
                    {"name": "Date", "value": "2026-03-28"},
                ],
                "body": {"data": b64("Body content")},
            },
        }
        result = c._parse_message(msg)
        assert result["subject"] == "Hello"
        assert result["from"] == "a@b.com"
        assert result["to"] == "me@x.com"
        assert "Body content" in result["body"]

    def test_body_truncated_at_2000_chars(self):
        c = make_client()
        long_body = "x" * 3000
        msg = {
            "id": "m1",
            "threadId": "",
            "snippet": "",
            "payload": {
                "headers": [],
                "body": {"data": b64(long_body)},
            },
        }
        result = c._parse_message(msg)
        assert len(result["body"]) == 2000

    def test_missing_headers_use_empty_defaults(self):
        c = make_client()
        msg = {"id": "m1", "threadId": "", "snippet": "", "payload": {"headers": [], "body": {}}}
        result = c._parse_message(msg)
        assert result["subject"] == ""
        assert result["from"] == ""


# ---------------------------------------------------------------------------
# _extract_body (lines 131–144)
# ---------------------------------------------------------------------------


class TestExtractBody:
    def test_direct_body_data(self):
        c = make_client()
        payload = {"body": {"data": b64("Hello world")}}
        assert c._extract_body(payload) == "Hello world"

    def test_text_plain_part(self):
        c = make_client()
        payload = {
            "body": {},
            "parts": [{"mimeType": "text/plain", "body": {"data": b64("Plain text")}}],
        }
        assert c._extract_body(payload) == "Plain text"

    def test_html_part_skipped_in_favour_of_text_plain(self):
        c = make_client()
        payload = {
            "body": {},
            "parts": [
                {"mimeType": "text/html", "body": {"data": b64("<b>html</b>")}},
                {"mimeType": "text/plain", "body": {"data": b64("plain")}},
            ],
        }
        assert c._extract_body(payload) == "plain"

    def test_recursive_parts(self):
        c = make_client()
        payload = {
            "body": {},
            "parts": [
                {
                    "mimeType": "multipart/alternative",
                    "body": {},
                    "parts": [{"mimeType": "text/plain", "body": {"data": b64("Nested plain")}}],
                }
            ],
        }
        assert c._extract_body(payload) == "Nested plain"

    def test_fallback_to_snippet(self):
        c = make_client()
        payload = {"body": {}, "parts": [], "snippet": "Snippet text"}
        assert c._extract_body(payload) == "Snippet text"

    def test_empty_payload_returns_empty_string(self):
        c = make_client()
        assert c._extract_body({}) == ""


# ---------------------------------------------------------------------------
# send_reply (lines 148–161)
# ---------------------------------------------------------------------------


class TestSendReply:
    def test_raises_when_send_mode_disabled(self):
        c = make_client(send_mode=False)
        with pytest.raises(RuntimeError, match="send_mode not enabled"):
            c.send_reply("thread1", "Hi there")

    def test_sends_message_when_send_mode_enabled(self):
        c = make_client(send_mode=True)
        c.send_reply("thread1", "Hi there")
        c.service.users().messages().send().execute.assert_called()

    def test_appends_signature_to_body(self):
        c = make_client(send_mode=True)
        c.send_reply("thread1", "Body", signature="Alex")
        # Verify send was called (signature appended without error)
        c.service.users().messages().send().execute.assert_called()

    def test_no_signature_still_sends(self):
        c = make_client(send_mode=True)
        c.send_reply("thread1", "Body only", to="r@co.com")
        c.service.users().messages().send().execute.assert_called()


# ---------------------------------------------------------------------------
# create_draft (lines 165–180)
# ---------------------------------------------------------------------------


class TestCreateDraft:
    def test_creates_draft_and_returns_id(self):
        c = make_client()
        c.service.users().drafts().create().execute.return_value = {"id": "draft001"}
        draft_id = c.create_draft("thread1", "Draft body")
        assert draft_id == "draft001"

    def test_draft_with_to_header(self):
        c = make_client()
        c.service.users().drafts().create().execute.return_value = {"id": "d2"}
        draft_id = c.create_draft("thread1", "Body", to="recruiter@co.com")
        assert draft_id == "d2"

    def test_draft_with_signature_appended(self):
        c = make_client()
        c.service.users().drafts().create().execute.return_value = {"id": "d3"}
        draft_id = c.create_draft("thread1", "Body", signature="Alex Rivera")
        assert draft_id == "d3"
