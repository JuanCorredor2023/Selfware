"""ingest/jobs.py: one scheduled run (GitHub Actions) = read pointer -> fetch new
emails -> upsert into the index -> save pointer.

Every test here imports jobs.py through `jobs_module`, which first swaps
ChromaStore, Embedder and call_ingest for mocks, so a regression back to
import-time side effects can't start OAuth or spend Nebius credits.

The contract jobs.py exposes:

    main(store, state, classifier=None) -> None
        store: anything with add_documents(list[Document])
        state: anything with load() -> str | None and save(history_id)
    to_document(item: ContextItem) -> Document
"""

import hashlib
import importlib
import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from selfware.context import embedder as embedder_module
from selfware.context import store as store_module
from selfware.context.domain import Document
from selfware.context.store import ChromaStore
from selfware.core.schemas import ContextItem
from selfware.ingest import gmail


def make_item(msg_id, text="hello", category="resources"):
    return ContextItem(
        id=msg_id,
        source="gmail",
        text=text,
        category=category,
        ts=datetime(2026, 10, 1, tzinfo=UTC),
    )


class FakeState:
    def __init__(self, history_id=None, events=None):
        self.history_id = history_id
        self.saved = None
        self.events = events if events is not None else []

    def load(self):
        return self.history_id

    def save(self, history_id):
        self.events.append("save")
        self.saved = history_id


class FakeStore:
    """Behaves like ChromaStore.add_documents, including raising on []."""

    def __init__(self, events=None, fail=None):
        self.added = []
        self.events = events if events is not None else []
        self._fail = fail

    def add_documents(self, documents):
        if not documents:
            raise ValueError("Documents is empty")
        if self._fail:
            raise self._fail
        self.events.append("add")
        self.added.extend(documents)


class SmallEmbedder:
    """Deterministic 8-dim vectors, no network."""

    def embed_documents(self, texts):
        return [self._vector(t) for t in texts]

    def embed_query(self, query):
        return self._vector(query)

    def _vector(self, text):
        digest = hashlib.sha256(text.encode()).digest()
        return [b / 255 for b in digest[:8]]


@pytest.fixture
def ingest_result(monkeypatch):
    """What the patched gmail.call_ingest returns; tests may overwrite it."""
    call_ingest = MagicMock(return_value=([], "1"))
    monkeypatch.setattr(gmail, "call_ingest", call_ingest)
    return call_ingest


@pytest.fixture
def jobs_module(monkeypatch, ingest_result):
    chroma = MagicMock(name="ChromaStore")
    embedder = MagicMock(name="Embedder")
    monkeypatch.setattr(store_module, "ChromaStore", chroma)
    monkeypatch.setattr(embedder_module, "Embedder", embedder)
    sys.modules.pop("selfware.ingest.jobs", None)

    module = importlib.import_module("selfware.ingest.jobs")
    module.test_mocks = {"ChromaStore": chroma, "Embedder": embedder}
    yield module

    sys.modules.pop("selfware.ingest.jobs", None)


def test_importing_jobs_has_no_side_effects(jobs_module, ingest_result):
    assert not ingest_result.called
    assert not jobs_module.test_mocks["ChromaStore"].called
    assert not jobs_module.test_mocks["Embedder"].called


def test_main_converts_context_items_to_documents(jobs_module, ingest_result):
    ingest_result.return_value = ([make_item("m1", "Hi"), make_item("m2", "Yo")], "7")
    store = FakeStore()

    jobs_module.main(store=store, state=FakeState("5"))

    assert all(isinstance(d, Document) for d in store.added)
    assert [(d.source_id, d.source, d.content, d.category) for d in store.added] == [
        ("m1", "gmail", "Hi", "resources"),
        ("m2", "gmail", "Yo", "resources"),
    ]
    assert datetime.fromisoformat(store.added[0].date) == datetime(
        2026, 10, 1, tzinfo=UTC
    )


def test_main_with_no_new_emails_does_not_crash(jobs_module, ingest_result):
    """A quiet hour is the normal case; add_documents([]) raises."""
    ingest_result.return_value = ([], "8")
    store, state = FakeStore(), FakeState("5")

    jobs_module.main(store=store, state=state)

    assert store.added == []
    assert state.saved == "8"


def test_main_saves_pointer_after_indexing(jobs_module, ingest_result):
    ingest_result.return_value = ([make_item("m1")], "9")
    events = []

    jobs_module.main(store=FakeStore(events), state=FakeState("5", events))

    assert events == ["add", "save"]


def test_main_does_not_save_pointer_if_indexing_fails(jobs_module, ingest_result):
    """Otherwise the next run starts after emails that never reached the index."""
    ingest_result.return_value = ([make_item("m1")], "9")
    state = FakeState("5")

    with pytest.raises(RuntimeError):
        jobs_module.main(store=FakeStore(fail=RuntimeError("chroma down")), state=state)

    assert state.saved is None


def test_main_first_run_without_state(jobs_module, ingest_result):
    jobs_module.main(store=FakeStore(), state=FakeState(None))
    ingest_result.assert_called_once_with(None)


def test_main_passes_stored_pointer(jobs_module, ingest_result):
    jobs_module.main(store=FakeStore(), state=FakeState("5"))
    ingest_result.assert_called_once_with("5")


def test_rerun_same_emails_is_idempotent(jobs_module, ingest_result, tmp_path):
    """Retries after a failed run re-read the same emails; the index must not
    grow. Uses real Chroma in tmp_path with a local embedder."""
    ingest_result.return_value = ([make_item("m1"), make_item("m2")], "9")
    store = ChromaStore(embedder=SmallEmbedder(), path=str(tmp_path))

    jobs_module.main(store=store, state=FakeState("5"))
    jobs_module.main(store=store, state=FakeState("5"))

    assert store.collection.count() == 2
