import base64
import datetime
import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mailparser_reply import EmailReplyParser

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SECRETS_DIR = Path(os.environ.get("SELFWARE_SECRETS_DIR", Path.home() / ".selfware"))
TOKEN_FILE = SECRETS_DIR / "token.json"
CREDENTIALS_FILE = SECRETS_DIR / "credentials.json"
OUTPUT_FILE = "emails.json"
REPLY_PARSER = EmailReplyParser(languages=["en"])


def get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            # 127.0.0.1, not "localhost": the server is IPv4-only, and browsers may try ::1 first
            creds = flow.run_local_server(host="127.0.0.1", port=8080)
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json())
    return creds


def normalize_body(raw_text):
    replies = REPLY_PARSER.read(text=raw_text).replies
    if not replies:
        return raw_text.strip()
    return replies[0].body.strip()


def decode(data):
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode(
        "utf-8", errors="replace"
    )


def find_text(payload, mime_type):
    if payload.get("mimeType") == mime_type and payload.get("body", {}).get("data"):
        decoded_text = decode(payload["body"]["data"])
        return normalize_body(decoded_text)
    for part in payload.get("parts", []):
        text = find_text(part, mime_type)
        if text:
            return text
    return None


def extract_body(payload):
    return find_text(payload, "text/plain") or find_text(payload, "text/html") or ""


def list_message_ids(service, max_messages=None):
    ids = []
    page_token = None
    while True:
        result = (
            service.users().messages().list(userId="me", pageToken=page_token).execute()
        )
        ids.extend(m["id"] for m in result.get("messages", []))
        page_token = result.get("nextPageToken")
        if not page_token or (max_messages and len(ids) >= max_messages):
            break
    return ids[:max_messages] if max_messages else ids


def fetch_message(service, message_id):
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )
    headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
    ts = datetime.datetime.fromtimestamp(
        int(msg["internalDate"]) / 1000, tz=datetime.UTC
    )
    # Leaving out some parameters to keep API calls minimal while testing
    return {
        "id": msg["id"],
        # "thread_id": msg["threadId"],
        "ts": ts.isoformat(),
        "subject": headers.get("subject", ""),
        # "from": headers.get("from", ""),
        # "to": headers.get("to", ""),
        # "labels": msg.get("labelIds", []),
        # "snippet": msg.get("snippet", ""),
        "body": extract_body(msg["payload"]),
    }


def main(output_file=OUTPUT_FILE, max_messages=None):
    creds = get_credentials()

    try:
        service = build("gmail", "v1", credentials=creds)
        message_ids = list_message_ids(service, max_messages)
        print(f"Fetching {len(message_ids)} messages...")

        messages = []
        for message_id in message_ids:
            try:
                messages.append(fetch_message(service, message_id))
            except HttpError as error:
                print(f"Skipping message {message_id}: {error}")

    except HttpError as error:
        print(f"Failed to retrieve messages: {error}")
        return

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(messages, file, indent=2, ensure_ascii=False)
    print(f"Wrote {len(messages)} messages to {output_file}")


if __name__ == "__main__":
    main()
