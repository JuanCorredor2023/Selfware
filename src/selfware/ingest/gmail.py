import datetime
import json
import logging
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
# Messages in these folders are never indexed. The full listing already leaves
# out spam and trash, but history reports every added message.
SKIPPED_LABELS = {"DRAFT", "SPAM", "TRASH"}

logger = logging.getLogger(__name__)


def get_credentials():
    token_json = os.environ.get("GMAIL_TOKEN_JSON")
    if token_json:
        # Scheduled job: no browser to log in with, so a revoked or invalid
        # token must fail the run instead of falling back to the local flow.
        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
        if not creds.valid:
            creds.refresh(Request())
        return creds

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
    next_start_id = (
        service.users().getProfile(userId="me").execute(num_retries=3).get("historyId")
    )
    while True:
        result = (
            service.users()
            .messages()
            .list(userId="me", pageToken=page_token)
            .execute(num_retries=3)
        )
        ids.extend(m["id"] for m in result.get("messages", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            return list(dict.fromkeys(ids)), next_start_id


def get_added_messages(service, start_history_id):
    ids = []
    page_token = None
    next_start_id = start_history_id
    while True:
        new_messages = (
            service.users()
            .history()
            .list(
                userId="me",
                startHistoryId=start_history_id,
                historyTypes=["messageAdded"],
                pageToken=page_token,
            )
            .execute(num_retries=3)
        )

        for record in new_messages.get("history", []):
            for msg in record.get("messagesAdded", []):
                if SKIPPED_LABELS.isdisjoint(msg["message"].get("labelIds", [])):
                    ids.append(msg["message"]["id"])
        # The pointer comes from the response itself: asking getProfile later
        # would skip any mail that arrived in between.
        next_start_id = new_messages.get("historyId", next_start_id)
        page_token = new_messages.get("nextPageToken")
        if not page_token:
            return list(dict.fromkeys(ids)), next_start_id


def get_messages(service, last_history_id=None):
    if last_history_id:
        try:
            return get_added_messages(service, last_history_id)
        except HttpError as e:
            if e.resp.status != 404:
                raise
            # Gmail only keeps history for a limited time; start over.
            logger.warning("History pointer has expired, running a full sync")
    return get_all_messages(service)


def find_message_by_id(service, msg_id):
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=msg_id, format="full")
        .execute(num_retries=3)
    )
    ts = datetime.datetime.fromtimestamp(
        int(msg["internalDate"]) / 1000, tz=datetime.UTC
    )
    return ContextItem(
        id=msg["id"],
        source="gmail",
        text=extract_body(msg["payload"]),
        ts=ts.isoformat(),
    )


def call_ingest(last_history_id=None):
    """Fetches the messages added since `last_history_id` (all of them when
    it is None) and returns them with the pointer for the next run.

    Any error other than a message deleted mid-run propagates: the job must
    fail, so the pointer is not advanced past emails that were never read.
    Never logs message contents."""
    service = build("gmail", "v1", credentials=get_credentials())
    message_ids, next_history_id = get_messages(service, last_history_id)
    logger.info("Fetching %d messages", len(message_ids))

    messages = []
    for message_id in message_ids:
        try:
            messages.append(find_message_by_id(service, message_id))
        except HttpError as error:
            if error.resp.status != 404:
                raise
            logger.info("Skipping message %s: deleted", message_id)
    return messages, next_history_id
