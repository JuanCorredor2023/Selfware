"""A stand-in for the Gmail API client built by `googleapiclient.discovery.build`.

It copies the chained calls `ingest/gmail.py` makes
(`service.users().messages().list(...).execute(num_retries=...)` and friends),
replays canned responses and records every request in the order it was
*executed*, so tests can check ordering (e.g. `getProfile` before listing).

Never touches the network. Every payload a test feeds it must be written by
hand: no real emails in fixtures.
"""

import base64

import httplib2
from googleapiclient.errors import HttpError


def http_error(status):
    """An `HttpError` whose `e.resp.status` is `status`, as the client raises it."""
    return HttpError(httplib2.Response({"status": status}), b"{}")


def b64(text):
    """Gmail-style base64url without padding."""
    return base64.urlsafe_b64encode(text.encode("utf-8")).decode().rstrip("=")


def text_part(text, mime_type="text/plain"):
    return {"mimeType": mime_type, "body": {"size": len(text), "data": b64(text)}}


def make_message(msg_id, text="hello", internal_date="1700000000000", labels=None):
    """A `messages.get(format="full")` response with a single text/plain body."""
    return {
        "id": msg_id,
        "threadId": f"thread-{msg_id}",
        "internalDate": internal_date,
        "labelIds": labels if labels is not None else ["INBOX"],
        "payload": text_part(text),
    }


def added(msg_id, labels=None):
    """One entry of a history record's `messagesAdded` list."""
    return {
        "message": {
            "id": msg_id,
            "threadId": f"thread-{msg_id}",
            "labelIds": labels if labels is not None else ["INBOX"],
        }
    }


class _Request:
    def __init__(self, service, name, kwargs, handler):
        self._service = service
        self._name = name
        self._kwargs = kwargs
        self._handler = handler

    def execute(self, num_retries=0):
        self._service.calls.append((self._name, self._kwargs))
        return self._handler(**self._kwargs)


class _Resource:
    def __init__(self, service, prefix, handlers):
        self._service = service
        self._prefix = prefix
        self._handlers = handlers

    def __getattr__(self, method):
        handler = self._handlers[method]

        def build_request(**kwargs):
            return _Request(self._service, f"{self._prefix}.{method}", kwargs, handler)

        return build_request


class _Users:
    def __init__(self, service):
        self._service = service

    def getProfile(self, **kwargs):
        return _Request(
            self._service, "users.getProfile", kwargs, self._service._get_profile
        )

    def messages(self):
        return _Resource(
            self._service,
            "messages",
            {"list": self._service._list_messages, "get": self._service._get_message},
        )

    def history(self):
        return _Resource(
            self._service, "history", {"list": self._service._list_history}
        )


class FakeGmailService:
    """Canned Gmail API.

    Args:
        profile_history_id: what `getProfile` reports as the current pointer.
        message_pages: `messages.list` responses keyed by the `pageToken` that
            requests them; the first page is keyed by `None`.
        history_pages: same, for `history.list`.
        messages: `messages.get` responses keyed by message id.
        list_error / history_error: raised by every `messages.list` /
            `history.list` call when set.
        get_errors: `HttpError`s raised by `messages.get`, keyed by message id.
    """

    def __init__(
        self,
        profile_history_id="900",
        message_pages=None,
        history_pages=None,
        messages=None,
        list_error=None,
        history_error=None,
        get_errors=None,
    ):
        self.calls = []
        self._profile_history_id = profile_history_id
        self._message_pages = message_pages or {None: {}}
        self._history_pages = history_pages or {None: {"historyId": profile_history_id}}
        self._messages = messages or {}
        self._list_error = list_error
        self._history_error = history_error
        self._get_errors = get_errors or {}

    def users(self):
        return _Users(self)

    def calls_named(self, name):
        return [kwargs for call, kwargs in self.calls if call == name]

    def call_order(self):
        return [call for call, _ in self.calls]

    def _get_profile(self, userId):
        return {"emailAddress": "me@example.com", "historyId": self._profile_history_id}

    def _list_messages(self, userId, pageToken=None, **_):
        if self._list_error:
            raise self._list_error
        return self._message_pages[pageToken]

    def _list_history(self, userId, startHistoryId, pageToken=None, **_):
        if self._history_error:
            raise self._history_error
        return self._history_pages[pageToken]

    def _get_message(self, userId, id, format=None):
        if id in self._get_errors:
            raise self._get_errors[id]
        return self._messages[id]
