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
    ids = []
    page_token = None
    while True:
        result = (
            service.users().messages().list(userId="me", pageToken=page_token).execute()
        )
        ids.extend(m["id"] for m in result.get("messages", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            next_start_id = service.users().getProfile(userId="me").execute()["historyId"]
            return list(dict.fromkeys(ids)), next_start_id

def get_added_messages(service, start_history_id):
    ids = []
    page_token = None
    while True: 
        new_messages = (
            service.users().history().list(userId="me", 
                                        startHistoryId=start_history_id, 
                                        historyTypes=["messageAdded"], 
                                        pageToke=page_token)
                                        .execute()
        )

        for record in new_messages.get("history", []):
            for msg in record.get("messagesAdded", []):
                msg_id = msg["message"]["id"]
                ids.append(msg_id)
        page_token = new_messages.get("nextPageToken") 
        if not page_token:
            next_start_id = service.users().getProfile(userId="me").execute()["historyId"]
            return list(dict.fromkeys(ids)), next_start_id

def get_messages(service, last_history_id=None):
    if last_history_id:
        try: 
            return get_added_messages(service, last_history_id)
        except HttpError as e:
            if e.resp.status == 404:
                print("Identifier \'last_history_id\' has expired")
    else:
        return get_all_messages(service)

           

def fetch_message(service, msg_id):
    msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
    ts = datetime.datetime.fromtimestamp(
        int(msg["internalDate"]) / 1000, tz=datetime.UTC
    )
    return ContextItem(id=msg["id"], 
                       source="gmail", 
                       text=extract_body(msg["payload"]), 
                       ts=ts.isoformat())

def call_ingest():
    creds = get_credentials()

    try:
        service = build("gmail", "v1", credentials=creds)
        message_ids, nextHistoryId = get_messages(service)
        print(f"Fetching {len(message_ids)} messages...")

        messages = []
        for message_id in message_ids:
            try:
                messages.append(fetch_message(service, message_id))
            except HttpError as error:
                print(f"Skipping message {message_id}: {error}")
        return message_ids, nextHistoryId

    except HttpError as error:
        print(f"Failed to retrieve messages: {error}")
        return

    # with open(output_file, "w", encoding="utf-8") as file:
    #     json.dump(messages, file, indent=2, ensure_ascii=False)
    # print(f"Wrote {len(messages)} messages to {output_file}")