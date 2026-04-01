"""
LinkedIn MCP Server — Exposes LinkedIn messaging via MCP tools.

Wraps the unofficial linkedin-api library using cookies stored at
~/.jerbs/linkedin_cookies.json. Reuses the same message normalization
logic as claude-code/linkedin_client.py.
"""

import json
import os
from datetime import UTC, datetime, timedelta
from email.utils import formatdate
from pathlib import Path

from linkedin_api import Linkedin
from mcp.server.fastmcp import FastMCP
from requests.cookies import RequestsCookieJar

COOKIES_PATH = Path.home() / ".jerbs" / "linkedin_cookies.json"

mcp = FastMCP("linkedin")


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


def _get_api() -> Linkedin:
    """Load cookies from disk and return an authenticated Linkedin instance."""
    if not COOKIES_PATH.exists():
        raise FileNotFoundError(
            f"LinkedIn cookies not found at {COOKIES_PATH}\n"
            "Run the jerbs setup wizard to configure LinkedIn access."
        )

    with open(COOKIES_PATH) as f:
        cookie_data = json.load(f)

    li_at = cookie_data.get("li_at")
    jsessionid = cookie_data.get("JSESSIONID")
    if not li_at or not jsessionid:
        raise ValueError(
            f"LinkedIn cookies file at {COOKIES_PATH} is missing "
            "'li_at' or 'JSESSIONID'. Re-run setup to fix."
        )

    jar = RequestsCookieJar()
    jar.set("li_at", li_at)
    jar.set("JSESSIONID", jsessionid)

    return Linkedin("", "", cookies=jar)


# Lazy singleton so we only authenticate once per server lifetime.
_api_instance: Linkedin | None = None


def _api() -> Linkedin:
    global _api_instance
    if _api_instance is None:
        _api_instance = _get_api()
    return _api_instance


# ---------------------------------------------------------------------------
# Normalization (mirrors linkedin_client.py _normalize_event)
# ---------------------------------------------------------------------------


def _normalize_event(event: dict, conv_id: str, message_id: str) -> dict:
    """Convert a LinkedIn message event to the standard jerbs message dict."""
    # Extract sender info from miniProfile
    from_data = event.get("from", {})
    mini = from_data.get("com.linkedin.voyager.messaging.MessagingMember", {})
    mini_profile = mini.get("miniProfile", {})
    first = mini_profile.get("firstName", "")
    last = mini_profile.get("lastName", "")
    sender_name = f"{first} {last}".strip() or "Unknown"

    # Extract message body
    msg_event = event.get("eventContent", {})
    msg_body_data = msg_event.get("com.linkedin.voyager.messaging.event.MessageEvent", {})
    body = msg_body_data.get("attributedBody", {}).get("text", "")

    # Synthesize a pseudo-subject from sender + first line
    first_line = body.split("\n")[0][:80] if body else ""
    subject = f"{sender_name} -- {first_line}" if first_line else sender_name

    # Convert epoch ms to RFC 2822 date string
    created_ms = event.get("createdAt", 0)
    if created_ms:
        created_dt = datetime.fromtimestamp(created_ms / 1000, tz=UTC)
        date_str = formatdate(timeval=created_dt.timestamp(), localtime=False, usegmt=True)
    else:
        date_str = ""

    return {
        "id": message_id,
        "threadId": conv_id,
        "subject": subject,
        "from": sender_name,
        "to": "",
        "date": date_str,
        "snippet": body[:200],
        "body": body[:2000],
    }


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def linkedin_search_messages(
    lookback_days: int = 7,
    max_results: int | None = None,
) -> list[dict]:
    """Fetch recent LinkedIn conversations as message metadata dicts.

    Each dict contains 'id' (event URN) and 'threadId' (conversation ID).
    Conversations are filtered to those with activity in the last
    `lookback_days` days.
    """
    api = _api()
    raw = api.get_conversations()

    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    cutoff_ms = int(cutoff.timestamp() * 1000)

    messages: list[dict] = []
    for conv in raw.get("elements", []):
        last_activity = conv.get("lastActivityAt", 0)
        if last_activity < cutoff_ms:
            continue

        entity_urn = conv.get("entityUrn", "")
        conv_id = entity_urn.replace("urn:li:fs_conversation:", "")
        if not conv_id:
            continue

        events = conv.get("events", [])
        latest_event = events[0] if events else {}
        event_urn = latest_event.get("entityUrn", conv_id)

        messages.append({"id": event_urn, "threadId": conv_id})

        if max_results and len(messages) >= max_results:
            break

    return messages


@mcp.tool()
def linkedin_read_message(message_id: str) -> dict:
    """Read a specific LinkedIn message/conversation.

    Accepts an event URN or a conversation ID. Returns a normalized message
    dict with keys: id, threadId, subject, from, to, date, body, snippet.
    """
    api = _api()

    # Resolve conversation ID from event URN if needed
    conv_id = message_id
    if "fs_event" in message_id:
        try:
            inner = message_id.split("(")[1].rstrip(")")
            conv_id = inner.split(",")[0]
        except (IndexError, ValueError):
            pass

    raw = api.get_conversation(conv_id)
    events = raw.get("elements", [])
    if not events:
        return {}

    event = events[0]
    return _normalize_event(event, conv_id, message_id)


@mcp.tool()
def linkedin_read_conversation(conversation_id: str) -> list[dict]:
    """Read all messages in a LinkedIn conversation thread.

    Returns a list of normalized message dicts, one per message in the
    thread (newest first).
    """
    api = _api()
    raw = api.get_conversation(conversation_id)
    events = raw.get("elements", [])

    results: list[dict] = []
    for event in events:
        event_urn = event.get("entityUrn", "")
        results.append(_normalize_event(event, conversation_id, event_urn))

    return results


@mcp.tool()
def linkedin_send_message(conversation_id: str, message_body: str) -> dict:
    """Send a reply in an existing LinkedIn conversation.

    Requires the LINKEDIN_SEND_ENABLED environment variable to be set to
    a truthy value (e.g. '1', 'true', 'yes').

    Returns {"status": "sent"} on success.
    """
    enabled = os.environ.get("LINKEDIN_SEND_ENABLED", "").lower()
    if enabled not in ("1", "true", "yes"):
        return {
            "status": "blocked",
            "error": (
                "Sending is disabled. Set the LINKEDIN_SEND_ENABLED "
                "environment variable to '1' to enable."
            ),
        }

    api = _api()
    err = api.send_message(message_body=message_body, conversation_urn_id=conversation_id)
    if err:
        return {
            "status": "error",
            "error": f"send_message failed for conversation {conversation_id}",
        }

    return {"status": "sent"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
