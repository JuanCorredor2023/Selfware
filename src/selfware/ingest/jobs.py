import json
import os
from pathlib import Path

import selfware.ingest.gmail as gmail_ingest
from selfware.context.embedder import Embedder
from selfware.context.ingest_classify import classify_documents
from selfware.context.store import ChromaStore

STATE_FILE = Path(
    os.environ.get("SELFWARE_STATE_FILE", "chroma_data/ingest_state.json")
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


def updateHistoryId():
    db_instance = ChromaStore(embedder=Embedder(), path="chroma_data")
    state = FileState()
    lastHistoryId = state.load()

    messages, nextHistoryId = gmail_ingest.call_ingest(lastHistoryId)
    if messages:
        classified_messages = classify_documents(messages)
        db_instance.add_documents(classified_messages)
        state.save(nextHistoryId)


if __name__ == "__main__":
    updateHistoryId()
