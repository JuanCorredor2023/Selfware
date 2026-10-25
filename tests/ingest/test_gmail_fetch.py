"""ingest/gmail.py, fetch side: downloading messages into ContextItems and the
`call_ingest` entry point jobs.py runs on a schedule. No network: `build` and
`get_credentials` are replaced by the fake service."""

from datetime import UTC, datetime

import pytest
from googleapiclient.errors import HttpError

from selfware.core.schemas import ContextItem
from selfware.ingest import gmail
from tests.fakes.gmail_fake import FakeGmailService, added, http_error, make_message


@pytest.fixture
def use_service(monkeypatch):
    """Makes `call_ingest` talk to the given fake instead of Gmail."""

    def install(service):
        monkeypatch.setattr(gmail, "get_credentials", lambda: None)
        monkeypatch.setattr(gmail, "build", lambda *args, **kwargs: service)
        return service

    return install


def test_find_message_by_id_builds_context_item():
    service = FakeGmailService(messages={"m1": make_message("m1", text="Hi Diana")})
    item = gmail.find_message_by_id(service, "m1")
    assert isinstance(item, ContextItem)
    assert item.id == "m1"
    assert item.source == "gmail"
    assert item.text == "Hi Diana"
    (request,) = service.calls_named("messages.get")
    assert request["format"] == "full"


def test_find_message_by_id_converts_internal_date_to_utc():
    service = FakeGmailService(
        messages={"m1": make_message("m1", internal_date="1700000000000")}
    )
    item = gmail.find_message_by_id(service, "m1")
    assert item.ts == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
    assert item.ts.tzinfo is not None


def test_call_ingest_returns_items_and_new_pointer(use_service):
    use_service(
        FakeGmailService(
            profile_history_id="42",
            message_pages={None: {"messages": [{"id": "m1"}, {"id": "m2"}]}},
            messages={"m1": make_message("m1"), "m2": make_message("m2")},
        )
    )
    items, pointer = gmail.call_ingest()
    assert [i.id for i in items] == ["m1", "m2"]
    assert all(isinstance(i, ContextItem) for i in items)
    assert pointer == "42"


def test_call_ingest_passes_pointer_through(use_service):
    service = use_service(FakeGmailService())
    gmail.call_ingest("100")
    (request,) = service.calls_named("history.list")
    assert request["startHistoryId"] == "100"


def test_call_ingest_skips_deleted_message(use_service):
    use_service(
        FakeGmailService(
            message_pages={
                None: {"messages": [{"id": "m1"}, {"id": "gone"}, {"id": "m3"}]}
            },
            messages={"m1": make_message("m1"), "m3": make_message("m3")},
            get_errors={"gone": http_error(404)},
        )
    )
    items, _ = gmail.call_ingest()
    assert [i.id for i in items] == ["m1", "m3"]


@pytest.mark.xfail(
    strict=True,
    reason="call_ingest prints and returns None; the scheduled job must fail",
)
def test_call_ingest_listing_error_raises(use_service):
    use_service(FakeGmailService(list_error=http_error(500)))
    with pytest.raises(HttpError):
        gmail.call_ingest()


def test_call_ingest_no_new_messages(use_service):
    service = use_service(FakeGmailService(history_pages={None: {"historyId": "100"}}))
    items, pointer = gmail.call_ingest("100")
    assert items == []
    assert pointer is not None
    assert not service.calls_named("messages.get")


def test_call_ingest_never_logs_body(use_service, capsys):
    """Workflow logs are readable by anyone with repo access."""
    use_service(
        FakeGmailService(
            history_pages={
                None: {
                    "historyId": "101",
                    "history": [{"messagesAdded": [added("m1"), added("m2")]}],
                }
            },
            messages={"m1": make_message("m1", text="SECRET-BODY-TEXT")},
            get_errors={"m2": http_error(404)},
        )
    )
    gmail.call_ingest("100")
    out = capsys.readouterr()
    assert "SECRET-BODY-TEXT" not in out.out + out.err
