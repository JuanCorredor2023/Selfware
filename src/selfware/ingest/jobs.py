import json
import logging
import os
from pathlib import Path

import selfware.ingest.gmail as gmail_ingest
from selfware.context.classifier import Classifier
from selfware.context.domain import Document
from selfware.context.ingest_classify import classify_documents
from selfware.core.schemas import ContextItem

CHROMA_PATH = os.environ.get("SELFWARE_CHROMA_PATH", "chroma_data")
# Lives next to the index: the pointer only means something for that index.
STATE_FILE = Path(
    os.environ.get("SELFWARE_STATE_FILE", Path(CHROMA_PATH) / "ingest_state.json")
)


class FileState:
    """Keeps the Gmail historyId between runs."""

    def __init__(self, path=STATE_FILE):
        self.path = Path(path)

    def load(self):
        if not self.path.exists():
            return None  # first run -> full sync
        return json.loads(self.path.read_text(encoding="utf-8")).get("history_id")

    def save(self, history_id):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"history_id": history_id}), encoding="utf-8")
        tmp.replace(self.path)


def to_document(item: ContextItem) -> Document:
    # Bridge until ContextItem and Document are unified in core/schemas.py.
    return Document(
        source_id=item.id,
        source=item.source,
        content=item.text,
        category=item.category,
        date=item.ts.isoformat(),
    )


def main(store, state, classifier=None):
    """One scheduled run: read pointer -> fetch new emails -> classify ->
    index -> save pointer.

    The pointer is saved only after indexing succeeds, so a failed run fetches
    the same emails again next time; the store's ids make that idempotent."""
    messages, next_history_id = gmail_ingest.call_ingest(state.load())
    if messages:  # add_documents([]) raises, and a quiet run is the normal case
        documents = [to_document(m) for m in messages]
        classify_documents(documents, classifier or Classifier())
        store.add_documents(documents)
    state.save(next_history_id)


if __name__ == "__main__":
    from selfware.context.embedder import Embedder
    from selfware.context.store import ChromaStore

    logging.basicConfig(level=logging.INFO)
    main(store=ChromaStore(embedder=Embedder(), path=CHROMA_PATH), state=FileState())
