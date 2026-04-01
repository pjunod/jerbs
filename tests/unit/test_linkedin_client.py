"""
Unit tests for linkedin_client.py — LinkedIn messaging wrapper.

linkedin-api is stubbed as a MagicMock via conftest.py.
"""

import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "claude-code"))

import linkedin_client
from linkedin_client import COOKIES_PATH, LinkedInClient


def make_client(send_mode: bool = False, lookback_days: int = 7) -> LinkedInClient:
    """Create a LinkedInClient with _authenticate mocked out."""
    with patch.object(LinkedInClient, "_authenticate", return_value=MagicMock()):
        return LinkedInClient(send_mode=send_mode, lookback_days=lookback_days)


def _epoch_ms(days_ago: int = 0) -> int:
    """Return epoch milliseconds for `days_ago` days before now."""
    dt = datetime.now(UTC) - timedelta(days=days_ago)
    return int(dt.timestamp() * 1000)


def _make_conversation(conv_id: str, days_ago: int = 0, sender: str = "Jane Doe",
                       body: str = "Hi, I have a great role for you") -> dict:
    """Build a synthetic LinkedIn conversation element."""
    event_urn = f"urn:li:fs_event:({conv_id},1234)"
    return {
        "entityUrn": f"urn:li:fs_conversation:{conv_id}",
        "lastActivityAt": _epoch_ms(days_ago),
        "read": False,
        "events": [
            {
                "entityUrn": event_urn,
                "createdAt": _epoch_ms(days_ago),
                "from": {
                    "com.linkedin.voyager.messaging.MessagingMember": {
                        "miniProfile": {
                            "firstName": sender.split()[0],
                            "lastName": sender.split()[-1] if " " in sender else "",
                        }
                    }
                },
                "eventContent": {
                    "com.linkedin.voyager.messaging.event.MessageEvent": {
                        "attributedBody": {"text": body}
                    }
                },
            }
        ],
    }


def _make_conversation_events(conv_id: str, days_ago: int = 0, sender: str = "Jane Doe",
                              body: str = "Hi, I have a great role for you") -> dict:
    """Build the response from get_conversation() (message events)."""
    return {
        "elements": [
            {
                "entityUrn": f"urn:li:fs_event:({conv_id},1234)",
                "createdAt": _epoch_ms(days_ago),
                "from": {
                    "com.linkedin.voyager.messaging.MessagingMember": {
                        "miniProfile": {
                            "firstName": sender.split()[0],
                            "lastName": sender.split()[-1] if " " in sender else "",
                        }
                    }
                },
                "eventContent": {
                    "com.linkedin.voyager.messaging.event.MessageEvent": {
                        "attributedBody": {"text": body}
                    }
                },
            }
        ]
    }


# ---------------------------------------------------------------------------
# __init__ / send_mode
# ---------------------------------------------------------------------------


class TestInit:
    def test_readonly_by_default(self):
        c = make_client(send_mode=False)
        assert c.send_mode is False

    def test_send_mode_when_true(self):
        c = make_client(send_mode=True)
        assert c.send_mode is True

    def test_lookback_days_stored(self):
        c = make_client(lookback_days=3)
        assert c.lookback_days == 3


# ---------------------------------------------------------------------------
# _authenticate
# ---------------------------------------------------------------------------


class TestAuthenticate:
    def test_missing_cookies_file_raises(self, tmp_path):
        missing = tmp_path / "no_cookies.json"
        with patch("linkedin_client.COOKIES_PATH", missing):
            with pytest.raises(FileNotFoundError, match="LinkedIn cookies not found"):
                LinkedInClient()

    def test_empty_li_at_raises(self, tmp_path):
        cookies_file = tmp_path / "cookies.json"
        cookies_file.write_text(json.dumps({"li_at": "", "JSESSIONID": "ajax:123"}))
        with patch("linkedin_client.COOKIES_PATH", cookies_file):
            with pytest.raises(ValueError, match="missing"):
                LinkedInClient()

    def test_missing_jsessionid_raises(self, tmp_path):
        cookies_file = tmp_path / "cookies.json"
        cookies_file.write_text(json.dumps({"li_at": "AQE123"}))
        with patch("linkedin_client.COOKIES_PATH", cookies_file):
            with pytest.raises(ValueError, match="missing"):
                LinkedInClient()

    def test_valid_cookies_creates_api(self, tmp_path):
        cookies_file = tmp_path / "cookies.json"
        cookies_file.write_text(json.dumps({"li_at": "AQE123", "JSESSIONID": "ajax:456"}))
        with (
            patch("linkedin_client.COOKIES_PATH", cookies_file),
            patch("linkedin_client.Linkedin") as MockLinkedin,
        ):
            client = LinkedInClient()
            MockLinkedin.assert_called_once()
            assert client.api == MockLinkedin.return_value


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_returns_recent_conversations(self):
        c = make_client(lookback_days=7)
        c.api.get_conversations.return_value = {
            "elements": [
                _make_conversation("conv1", days_ago=1),
                _make_conversation("conv2", days_ago=3),
            ]
        }
        results = c.search("")
        assert len(results) == 2
        assert results[0]["threadId"] == "conv1"
        assert results[1]["threadId"] == "conv2"

    def test_filters_old_conversations(self):
        c = make_client(lookback_days=2)
        c.api.get_conversations.return_value = {
            "elements": [
                _make_conversation("recent", days_ago=1),
                _make_conversation("old", days_ago=5),
            ]
        }
        results = c.search("")
        assert len(results) == 1
        assert results[0]["threadId"] == "recent"

    def test_max_results_limits_count(self):
        c = make_client(lookback_days=30)
        c.api.get_conversations.return_value = {
            "elements": [
                _make_conversation(f"conv{i}", days_ago=i) for i in range(10)
            ]
        }
        results = c.search("", max_results=3)
        assert len(results) == 3

    def test_empty_response_returns_empty(self):
        c = make_client()
        c.api.get_conversations.return_value = {"elements": []}
        assert c.search("") == []

    def test_api_error_returns_empty(self):
        c = make_client()
        c.api.get_conversations.side_effect = Exception("401 Unauthorized")
        assert c.search("") == []

    def test_query_param_ignored(self):
        c = make_client(lookback_days=7)
        c.api.get_conversations.return_value = {
            "elements": [_make_conversation("conv1", days_ago=1)]
        }
        # query is accepted but ignored
        results = c.search("subject:hiring newer_than:1d")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# get_message
# ---------------------------------------------------------------------------


class TestGetMessage:
    def test_returns_normalized_dict(self):
        c = make_client()
        c.api.get_conversation.return_value = _make_conversation_events(
            "conv1", days_ago=0, sender="Jane Recruiter", body="Hi, great role at Acme Corp"
        )
        event_urn = "urn:li:fs_event:(conv1,1234)"
        result = c.get_message(event_urn)
        assert result["id"] == event_urn
        assert result["threadId"] == "conv1"
        assert result["from"] == "Jane Recruiter"
        assert "great role at Acme Corp" in result["body"]
        assert result["subject"].startswith("Jane Recruiter")

    def test_accepts_plain_conversation_id(self):
        c = make_client()
        c.api.get_conversation.return_value = _make_conversation_events(
            "conv1", body="Hello"
        )
        result = c.get_message("conv1")
        assert result["threadId"] == "conv1"
        c.api.get_conversation.assert_called_with("conv1")

    def test_api_error_returns_empty_dict(self):
        c = make_client()
        c.api.get_conversation.side_effect = Exception("404")
        assert c.get_message("conv1") == {}

    def test_empty_events_returns_empty_dict(self):
        c = make_client()
        c.api.get_conversation.return_value = {"elements": []}
        assert c.get_message("conv1") == {}

    def test_body_truncated_at_2000_chars(self):
        c = make_client()
        long_body = "x" * 3000
        c.api.get_conversation.return_value = _make_conversation_events(
            "conv1", body=long_body
        )
        result = c.get_message("conv1")
        assert len(result["body"]) == 2000

    def test_snippet_truncated_at_200_chars(self):
        c = make_client()
        long_body = "y" * 500
        c.api.get_conversation.return_value = _make_conversation_events(
            "conv1", body=long_body
        )
        result = c.get_message("conv1")
        assert len(result["snippet"]) == 200


# ---------------------------------------------------------------------------
# _normalize_event
# ---------------------------------------------------------------------------


class TestNormalizeEvent:
    def test_synthesizes_subject_from_sender_and_body(self):
        c = make_client()
        event = _make_conversation_events("conv1", sender="Alice Smith",
                                          body="Exciting opportunity at TechCo")["elements"][0]
        result = c._normalize_event(event, "conv1", "msg1")
        assert result["subject"] == "Alice Smith -- Exciting opportunity at TechCo"

    def test_subject_truncates_first_line_at_80_chars(self):
        c = make_client()
        long_first_line = "A" * 120
        event = _make_conversation_events("conv1", body=long_first_line)["elements"][0]
        result = c._normalize_event(event, "conv1", "msg1")
        # "Jane Doe -- " + 80 chars
        first_line_part = result["subject"].split(" -- ", 1)[1]
        assert len(first_line_part) == 80

    def test_subject_falls_back_to_sender_only_when_no_body(self):
        c = make_client()
        event = _make_conversation_events("conv1", sender="Bob Jones", body="")["elements"][0]
        result = c._normalize_event(event, "conv1", "msg1")
        assert result["subject"] == "Bob Jones"

    def test_unknown_sender_when_no_profile(self):
        c = make_client()
        event = {
            "entityUrn": "urn:li:fs_event:(conv1,1)",
            "createdAt": _epoch_ms(0),
            "from": {},
            "eventContent": {
                "com.linkedin.voyager.messaging.event.MessageEvent": {
                    "attributedBody": {"text": "Hello"}
                }
            },
        }
        result = c._normalize_event(event, "conv1", "msg1")
        assert result["from"] == "Unknown"

    def test_date_is_rfc2822_format(self):
        c = make_client()
        event = _make_conversation_events("conv1", days_ago=0)["elements"][0]
        result = c._normalize_event(event, "conv1", "msg1")
        assert "GMT" in result["date"] or result["date"] == ""


# ---------------------------------------------------------------------------
# send_reply
# ---------------------------------------------------------------------------


class TestSendReply:
    def test_raises_when_send_mode_disabled(self):
        c = make_client(send_mode=False)
        with pytest.raises(RuntimeError, match="send_mode not enabled"):
            c.send_reply("conv1", "Thanks for reaching out!")

    def test_sends_message_when_send_mode_enabled(self):
        c = make_client(send_mode=True)
        c.api.send_message.return_value = False  # False = success
        c.send_reply("conv1", "Thanks!")
        c.api.send_message.assert_called_once_with(
            message_body="Thanks!", conversation_urn_id="conv1"
        )

    def test_appends_signature(self):
        c = make_client(send_mode=True)
        c.api.send_message.return_value = False
        c.send_reply("conv1", "Body", signature="Alex")
        call_args = c.api.send_message.call_args
        assert "Alex" in call_args.kwargs["message_body"]

    def test_raises_on_api_error(self):
        c = make_client(send_mode=True)
        c.api.send_message.return_value = True  # True = error
        with pytest.raises(RuntimeError, match="send_message failed"):
            c.send_reply("conv1", "Hi")


# ---------------------------------------------------------------------------
# create_draft
# ---------------------------------------------------------------------------


class TestCreateDraft:
    def test_returns_empty_string(self):
        c = make_client()
        result = c.create_draft("conv1", "Draft body")
        assert result == ""
