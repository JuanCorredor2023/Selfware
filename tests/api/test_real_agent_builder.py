"""api/_real_agent.py builds ONE retriever and hands it to the agent."""

import pytest

pytest.importorskip("chromadb")  # the builder imports context/, which needs it

from selfware.api import _real_agent


def test_builder_creates_the_retriever_once_and_uses_env_paths(monkeypatch, tmp_path):
    built = {"store": 0}

    class FakeStore:
        def __init__(self, embedder, path):
            built["store"] += 1
            built["path"] = path

    class FakeRetrieve:
        def __init__(self, store, classifier):
            self.store, self.classifier = store, classifier

    seen = {}

    def fake_make_answer_question(retrieve, answer):
        seen["retrieve"], seen["answer"] = retrieve, answer
        return "answer_question"

    monkeypatch.setenv("SELFWARE_CHROMA_PATH", str(tmp_path / "chroma"))
    monkeypatch.setattr(_real_agent, "ChromaStore", FakeStore)
    monkeypatch.setattr(_real_agent, "Retrieve", FakeRetrieve)
    monkeypatch.setattr(_real_agent, "make_answer_question", fake_make_answer_question)
    monkeypatch.setattr(_real_agent, "make_answerer", lambda cache_dir: "answerer")

    assert _real_agent.build_answer_question() == "answer_question"
    assert built["store"] == 1
    assert built["path"] == str(tmp_path / "chroma")
    assert seen["answer"] == "answerer"
