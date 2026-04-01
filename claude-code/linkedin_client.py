"""
linkedin_client.py — LinkedIn messaging wrapper for jerbs

Uses the unofficial linkedin-api library (tomquirk/linkedin-api) which
reverse-engineers LinkedIn's Voyager API via session cookies.

Authentication:
  - Primary: Cookies auto-extracted from the user's browser via browser_cookie3
  - Fallback: Playwright interactive login
  - Last resort: Manual cookie entry in the setup wizard

Cookies are saved to ~/.jerbs/linkedin_cookies.json.
"""

import json
import time
from datetime import UTC, datetime, timedelta
from email.utils import formatdate
from pathlib import Path

try:
    from linkedin_api import Linkedin
except ImportError as e:
    raise ImportError(
        "linkedin-api not installed. Run:\n  pip install linkedin-api"
    ) from e

COOKIES_PATH = Path.home() / ".jerbs" / "linkedin_cookies.json"


class LinkedInClient:
    def __init__(self, send_mode: bool = False, lookback_days: int = 7):
        self.send_mode = send_mode
        self.lookback_days = lookback_days
        self.api = self._authenticate()

    def _authenticate(self) -> Linkedin:
        """Load cookies from disk and create a Linkedin API instance."""
        if not COOKIES_PATH.exists():
            raise FileNotFoundError(
                f"LinkedIn cookies not found at {COOKIES_PATH}\n"
                "Run with --setup to configure LinkedIn access."
            )

        with open(COOKIES_PATH) as f:
            cookie_data = json.load(f)

        li_at = cookie_data.get("li_at")
        jsessionid = cookie_data.get("JSESSIONID")
        if not li_at or not jsessionid:
            raise ValueError(
                f"LinkedIn cookies file at {COOKIES_PATH} is missing "
                "'li_at' or 'JSESSIONID'. Re-run --setup to fix."
            )

        from requests.cookies import RequestsCookieJar

        jar = RequestsCookieJar()
        jar.set("li_at", li_at)
        jar.set("JSESSIONID", jsessionid)

        return Linkedin("", "", cookies=jar)

    def search(self, query: str, max_results: int | None = None) -> list[dict]:
        """Fetch recent LinkedIn conversations as message metadata.

        The `query` parameter is accepted for interface compatibility with
        GmailClient but is ignored — LinkedIn has no message search API.
        Conversations are filtered by recency using self.lookback_days.
        """
        try:
            raw = self.api.get_conversations()
        except Exception as e:
            print(f"LinkedIn conversation fetch error: {e}")
            return []

        cutoff = datetime.now(UTC) - timedelta(days=self.lookback_days)
        cutoff_ms = int(cutoff.timestamp() * 1000)

        messages = []
        for conv in raw.get("elements", []):
            last_activity = conv.get("lastActivityAt", 0)
            if last_activity < cutoff_ms:
                continue

            entity_urn = conv.get("entityUrn", "")
            conv_id = entity_urn.replace("urn:li:fs_conversation:", "")
            if not conv_id:
                continue

            # Extract the latest message event as the representative message
            events = conv.get("events", [])
            latest_event = events[0] if events else {}
            event_urn = latest_event.get("entityUrn", conv_id)

            messages.append({"id": event_urn, "threadId": conv_id})

            if max_results and len(messages) >= max_results:
                break

        return messages

    def get_message(self, message_id: str) -> dict:
        """Fetch a conversation and return the latest inbound message normalized
        to the same dict shape as GmailClient.get_message()."""
        # message_id is the event URN; we need the conversation URN to fetch.
        # Try to extract conversation ID — the caller may also pass a threadId.
        # For robustness, accept both event URNs and conversation IDs.
        conv_id = message_id
        if "fs_event" in message_id:
            # Event URN format: urn:li:fs_event:(CONV_ID,EVENT_ID)
            try:
                inner = message_id.split("(")[1].rstrip(")")
                conv_id = inner.split(",")[0]
            except (IndexError, ValueError):
                pass

        try:
            raw = self.api.get_conversation(conv_id)
        except Exception as e:
            print(f"Failed to fetch LinkedIn conversation {conv_id}: {e}")
            return {}

        events = raw.get("elements", [])
        if not events:
            return {}

        # Find the most recent message (events are newest-first)
        event = events[0]
        return self._normalize_event(event, conv_id, message_id)

    def _normalize_event(self, event: dict, conv_id: str, message_id: str) -> dict:
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
        msg_body_data = msg_event.get(
            "com.linkedin.voyager.messaging.event.MessageEvent", {}
        )
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

    def send_reply(self, thread_id: str, body: str, to: str = "", signature: str = ""):
        """Send a reply in an existing LinkedIn conversation.

        Only works if send_mode=True.
        """
        if not self.send_mode:
            raise RuntimeError("send_mode not enabled. Start jerbs with --send to enable.")

        full_body = body
        if signature:
            full_body += f"\n\n{signature}"

        err = self.api.send_message(
            message_body=full_body, conversation_urn_id=thread_id
        )
        if err:
            raise RuntimeError(f"LinkedIn send_message failed for conversation {thread_id}")

    def create_draft(self, thread_id: str, body: str, to: str = "", signature: str = "") -> str:
        """LinkedIn has no draft concept. Returns None with a warning."""
        print("Note: LinkedIn does not support drafts. Reply shown as copy-paste text only.")
        return ""
