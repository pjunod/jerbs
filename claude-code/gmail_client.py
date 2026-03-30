"""
gmail_client.py — Gmail API wrapper for jerbs

Uses Google's official API with OAuth2. On first run, opens a browser for
authorization and saves credentials to ~/.jerbs/gmail_token.json.

Required Google API scopes:
  - https://www.googleapis.com/auth/gmail.readonly  (default)
  - https://www.googleapis.com/auth/gmail.send      (only if --send mode)

Setup:
  1. Go to https://console.cloud.google.com/
  2. Create a project, enable the Gmail API
  3. Create OAuth2 credentials (Desktop app)
  4. Download credentials.json → place at ~/.jerbs/credentials.json
"""

import base64
from email.mime.text import MIMEText
from pathlib import Path

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError as e:
    raise ImportError(
        "Google API libraries not installed. Run:\n"
        "  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
    ) from e

CREDENTIALS_PATH = Path.home() / ".jerbs" / "credentials.json"
TOKEN_PATH = Path.home() / ".jerbs" / "gmail_token.json"

SCOPES_READONLY = ["https://www.googleapis.com/auth/gmail.readonly"]
SCOPES_SEND = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


class GmailClient:
    def __init__(self, send_mode: bool = False):
        self.send_mode = send_mode
        self.scopes = SCOPES_SEND if send_mode else SCOPES_READONLY
        self.service = self._authenticate()

    def _authenticate(self):
        creds = None
        if TOKEN_PATH.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), self.scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not CREDENTIALS_PATH.exists():
                    raise FileNotFoundError(
                        f"Gmail credentials not found at {CREDENTIALS_PATH}\n"
                        "See claude-code/README.md for setup instructions."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), self.scopes)
                creds = flow.run_local_server(port=0)

            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(TOKEN_PATH, "w") as f:
                f.write(creds.to_json())

        return build("gmail", "v1", credentials=creds)

    def search(self, query: str, max_results: int = None) -> list[dict]:
        """Search Gmail and return list of message metadata."""
        messages = []
        kwargs = {"userId": "me", "q": query}
        if max_results:
            kwargs["maxResults"] = min(max_results, 500)

        try:
            response = self.service.users().messages().list(**kwargs).execute()
            messages.extend(response.get("messages", []))

            while "nextPageToken" in response and (
                max_results is None or len(messages) < max_results
            ):
                response = (
                    self.service.users()
                    .messages()
                    .list(**kwargs, pageToken=response["nextPageToken"])
                    .execute()
                )
                messages.extend(response.get("messages", []))

            if max_results:
                messages = messages[:max_results]
        except HttpError as e:
            print(f"Gmail search error: {e}")

        return messages

    def get_message(self, message_id: str) -> dict:
        """Fetch full message content."""
        try:
            msg = (
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )
            return self._parse_message(msg)
        except HttpError as e:
            print(f"Failed to fetch message {message_id}: {e}")
            return {}

    def _parse_message(self, msg: dict) -> dict:
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        body = self._extract_body(msg.get("payload", {}))
        return {
            "id": msg["id"],
            "threadId": msg.get("threadId", ""),
            "subject": headers.get("Subject", ""),
            "from": headers.get("From", ""),
            "to": headers.get("To", ""),
            "date": headers.get("Date", ""),
            "snippet": msg.get("snippet", ""),
            "body": body[:2000],
        }

    def _extract_body(self, payload: dict) -> str:
        if payload.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode(
                "utf-8", errors="ignore"
            )
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                return base64.urlsafe_b64decode(part["body"]["data"]).decode(
                    "utf-8", errors="ignore"
                )
        for part in payload.get("parts", []):
            result = self._extract_body(part)
            if result:
                return result
        return payload.get("snippet", "")

    def send_reply(self, thread_id: str, body: str, to: str = "", signature: str = ""):
        """Send a reply email. Only works if send_mode=True."""
        if not self.send_mode:
            raise RuntimeError("send_mode not enabled. Start jerbs with --send to enable.")

        full_body = body
        if signature:
            full_body += f"\n\n{signature}"

        message = MIMEText(full_body)
        message["threadId"] = thread_id
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        self.service.users().messages().send(
            userId="me", body={"raw": raw, "threadId": thread_id}
        ).execute()

    def create_draft(self, thread_id: str, body: str, to: str = "", signature: str = "") -> str:
        """Create a draft reply. Returns draft ID."""
        full_body = body
        if signature:
            full_body += f"\n\n{signature}"

        message = MIMEText(full_body)
        if to:
            message["To"] = to
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        draft = (
            self.service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw, "threadId": thread_id}})
            .execute()
        )
        return draft["id"]
