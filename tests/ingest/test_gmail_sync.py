"""ingest/gmail.py, listing side: which message ids a scheduled run must fetch
and which history pointer it hands back for the next run.

Tests marked xfail(strict=True) describe known bugs. When the fix lands they
start passing, strict mode turns that into a failure, and the marker must go.
"""

import pytest
from googleapiclient.errors import HttpError

from selfware.ingest import gmail
from tests.fakes.gmail_fake import FakeGmailService, added, http_error


def ids_page(ids, next_token=None):
    page = {"messages": [{"id": i, "threadId": f"thread-{i}"} for i in ids]}
    if next_token:
        page["nextPageToken"] = next_token
    return page


def history_page(*records, history_id="150", next_token=None):
    page = {"history": list(records), "historyId": history_id}
    if next_token:
        page["nextPageToken"] = next_token
    return page


# --------------------------------------------------------------------------
# Full sync
# --------------------------------------------------------------------------


def test_get_all_messages_follows_all_pages():
    service = FakeGmailService(
        message_pages={
            None: ids_page(["m1", "m2"], "p2"),
            "p2": ids_page(["m3"], "p3"),
            "p3": ids_page(["m4"]),
        }
    )
    ids, _ = gmail.get_all_messages(service)
    assert ids == ["m1", "m2", "m3", "m4"]
    assert len(service.calls_named("messages.list")) == 3


def test_get_all_messages_empty_mailbox():
    service = FakeGmailService(profile_history_id="42", message_pages={None: {}})
    assert gmail.get_all_messages(service) == ([], "42")


def test_get_all_messages_takes_pointer_before_listing():
    """An email arriving mid-listing must be picked up by the next history
    read, so the pointer has to predate the first page."""
    service = FakeGmailService(message_pages={None: ids_page(["m1"])})
    gmail.get_all_messages(service)
    order = service.call_order()
    assert order.index("users.getProfile") < order.index("messages.list")


def test_get_all_messages_dedupes_ids():
    service = FakeGmailService(
        message_pages={None: ids_page(["m1", "m2"], "p2"), "p2": ids_page(["m2"])}
    )
    ids, _ = gmail.get_all_messages(service)
    assert ids == ["m1", "m2"]


# --------------------------------------------------------------------------
# Incremental sync (history)
# --------------------------------------------------------------------------


def test_get_added_messages_collects_ids_across_pages():
    service = FakeGmailService(
        history_pages={
            None: history_page({"messagesAdded": [added("m1")]}, next_token="h2"),
            "h2": history_page({"messagesAdded": [added("m2")]}),
        }
    )
    ids, _ = gmail.get_added_messages(service, "100")
    assert ids == ["m1", "m2"]
    assert [c["pageToken"] for c in service.calls_named("history.list")] == [None, "h2"]


def test_get_added_messages_ignores_records_without_messages_added():
    service = FakeGmailService(
        history_pages={
            None: history_page(
                {"id": "101", "messages": [{"id": "m0"}]},
                {"id": "102", "messagesAdded": [added("m1")]},
            )
        }
    )
    ids, _ = gmail.get_added_messages(service, "100")
    assert ids == ["m1"]


def test_get_added_messages_dedupes_ids():
    service = FakeGmailService(
        history_pages={
            None: history_page(
                {"messagesAdded": [added("m1")]},
                {"messagesAdded": [added("m1"), added("m2")]},
            )
        }
    )
    ids, _ = gmail.get_added_messages(service, "100")
    assert ids == ["m1", "m2"]


def test_get_added_messages_requests_only_message_added():
    service = FakeGmailService()
    gmail.get_added_messages(service, "100")
    (request,) = service.calls_named("history.list")
    assert request["historyTypes"] == ["messageAdded"]
    assert request["startHistoryId"] == "100"


def test_get_added_messages_returns_pointer_from_history_response():
    service = FakeGmailService(
        profile_history_id="999",
        history_pages={
            None: history_page({"messagesAdded": [added("m1")]}, history_id="150")
        },
    )
    _, pointer = gmail.get_added_messages(service, "100")
    assert pointer == "150"


def test_get_added_messages_no_changes():
    service = FakeGmailService(history_pages={None: {"historyId": "100"}})
    ids, pointer = gmail.get_added_messages(service, "100")
    assert ids == []
    assert pointer is not None


def test_get_added_messages_skips_drafts_spam_trash():
    service = FakeGmailService(
        history_pages={
            None: history_page(
                {
                    "messagesAdded": [
                        added("inbox"),
                        added("draft", ["DRAFT"]),
                        added("spam", ["SPAM"]),
                        added("trash", ["TRASH"]),
                    ]
                }
            )
        }
    )
    ids, _ = gmail.get_added_messages(service, "100")
    assert ids == ["inbox"]


# --------------------------------------------------------------------------
# Choosing between them
# --------------------------------------------------------------------------


def test_get_messages_without_pointer_does_full_sync():
    service = FakeGmailService(
        profile_history_id="42", message_pages={None: ids_page(["m1"])}
    )
    assert gmail.get_messages(service, None) == (["m1"], "42")
    assert not service.calls_named("history.list")


def test_get_messages_with_pointer_does_incremental():
    service = FakeGmailService(
        history_pages={None: history_page({"messagesAdded": [added("m1")]})}
    )
    ids, _ = gmail.get_messages(service, "100")
    assert ids == ["m1"]
    assert not service.calls_named("messages.list")


def test_get_messages_expired_pointer_falls_back():
    service = FakeGmailService(
        profile_history_id="42",
        history_error=http_error(404),
        message_pages={None: ids_page(["m1", "m2"])},
    )
    assert gmail.get_messages(service, "1") == (["m1", "m2"], "42")


@pytest.mark.parametrize("status", [401, 500])
def test_get_messages_other_http_error_propagates(status):
    service = FakeGmailService(history_error=http_error(status))
    with pytest.raises(HttpError):
        gmail.get_messages(service, "100")
    assert not service.calls_named("messages.list")
