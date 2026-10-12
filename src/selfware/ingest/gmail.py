import datetime
import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from selfware.core.schemas import ContextItem
from selfware.ingest.normalize import extract_body

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SECRETS_DIR = Path(os.environ.get("SELFWARE_SECRETS_DIR", Path.home() / ".selfware"))
TOKEN_FILE = SECRETS_DIR / "token.json"
CREDENTIALS_FILE = SECRETS_DIR / "credentials.json"
OUTPUT_FILE = "emails.json"


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
            creds = flow.run_local_server(host="127.0.0.1", port=8080)
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(creds.to_json())
    return creds


def get_all_messages(service):
    gmail_api = service.users().messages()
    msg_list = []
    page_token = None
    while True:
        gmail_api.list(userId="me", pageToken=page_token).execute()
        msg_list.append()


def get_new_messages(service, since_date=None):
    try: 
        history_id = service.users().getProfile(userId="me").execute().get("historyId", [])
        new_messages = (
            service.users().history().list(userId="me", startHistoryId=history_id, historyTypes=["messageAdded"]).execute()
        )

        new_messages_list = []
        for record in new_messages.get("history", []):
            for msg in record.get("messagesAdded", []):
                msg_id = msg["message"]["id"]
                new_messages_list.append(msg_id)
        return new_messages_list
    except HttpError as e: 
        if e.resp.status == 404:
            return get_all_messages(service)
        else: 
            print(f"Could not fetch messages : {e}")



def get_messages_by_ids(service, message_ids):
    gmail_api = service.users.messages()
    mails = []
    for msg_id in message_ids:
        msg = gmail_api.get(userId="me", id=msg_id, format="full").execute()
        ts = datetime.datetime.fromtimestamp(
            int(msg["internalDate"]) / 1000, tz=datetime.UTC
        )
        mails.append(
            {
                "id": msg["id"],
                "ts": ts.isoformat(),
                "body": extract_body(msg["payload"]),
            }
        )


def fetch_message(service, msg_id):
    msg = service.users.messages().get(userId="me", id=msg_id, format="full").execute()
    ts = datetime.datetime.fromtimestamp(
        int(msg["internalDate"]) / 1000, tz=datetime.UTC
    )
    return ContextItem(msg["id"], "gmail", extract_body(msg["payload"]), ts.isoformat())


def call_ingest(output_file=OUTPUT_FILE):
    creds = get_credentials()

    try:
        service = build("gmail", "v1", credentials=creds)
        message_ids = get_new_messages(service)
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