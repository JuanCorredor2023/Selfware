"""
Tests for store.py: ChromaStore against a REAL Chroma (a temporary collection per
test, through pytest's tmp_path fixture, which creates and cleans an isolated folder).

They use the fake Embedder: its vectors carry no meaning, so relevance (which chunk
is "most similar") is NOT tested, only mechanical behaviour:
  - Idempotence: inserting again does not duplicate.
  - Reclassification (upsert): inserting again with another category updates it.
  - Category filter: search_filtered only returns the requested category.
  - Assembly: Chunks come out with text, a Source with enum and datetime, score in [0,1].
  - Validation: add_documents with an empty list raises.
"""

import hashlib
import random
from datetime import datetime

import pytest

from selfware.context.domain import Document, ParaFolder
from selfware.context.store import ChromaStore


class FakeEmbedder:
    """Fake embedder for tests: deterministic vectors from a hash, no network.
    It has the SAME shape as the real Embedder (embed_documents / embed_query)
    so it can be injected in its place. It applies no real prefixes, because
    its vectors carry no meaning -- it only mimics the shape."""

    def __init__(self, dimensions: int = 4096):
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._to_embedding(text) for text in texts]

    def embed_query(self, query: str) -> list[float]:
        return self._to_embedding(query)

    def _to_embedding(self, text: str) -> list[float]:
        seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16)
        rng = random.Random(seed)
        return [rng.random() for _ in range(self.dimensions)]


def make_store(tmp_path):
    # tmp_path is a pytest fixture: a unique temporary folder per test, so each
    # test runs against a clean, isolated Chroma collection.
    return ChromaStore(embedder=FakeEmbedder(), path=str(tmp_path))


def make_doc(
    source_id, category, content="contenido de prueba", date="2026-01-01T00:00:00Z"
):
    return Document(
        source_id=source_id,
        source="email",
        content=content,
        category=category,
        date=date,
    )


def test_add_documents_empty_raises(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(ValueError):
        store.add_documents([])


def test_insert_count_is_right(tmp_path):
    store = make_store(tmp_path)
    store.add_documents([make_doc("m1", "projects"), make_doc("m2", "areas")])
    assert store.collection.count() == 2


def test_idempotent_no_duplicates(tmp_path):
    store = make_store(tmp_path)
    docs = [make_doc("m1", "projects"), make_doc("m2", "areas")]
    store.add_documents(docs)
    store.add_documents(docs)  # insert the same ones again
    assert store.collection.count() == 2


def test_reclassification_by_upsert(tmp_path):
    store = make_store(tmp_path)
    store.add_documents([make_doc("m1", "projects")])
    # same source_id, another category -> upsert must UPDATE, not duplicate
    store.add_documents([make_doc("m1", "archive")])
    assert store.collection.count() == 1
    got = store.collection.get(include=["metadatas"])
    assert got["metadatas"][0]["category"] == "archive"


def test_category_filter_returns_only_that_category(tmp_path):
    store = make_store(tmp_path)
    store.add_documents(
        [
            make_doc("m1", "projects"),
            make_doc("m2", "areas"),
            make_doc("m3", "projects"),
        ]
    )
    chunks = store.search_filtered("cualquier cosa", ParaFolder.PROJECTS, k=10)
    assert len(chunks) == 2
    assert all(c.source.para_folder == ParaFolder.PROJECTS for c in chunks)


def test_empty_category_filter_returns_empty_list(tmp_path):
    # No RESOURCES inserted -> the filter returns [] (triggers the fallback in retrieve)
    store = make_store(tmp_path)
    store.add_documents([make_doc("m1", "projects")])
    chunks = store.search_filtered("q", ParaFolder.RESOURCES, k=10)
    assert chunks == []


def test_search_flat_respects_k(tmp_path):
    store = make_store(tmp_path)
    store.add_documents([make_doc(f"m{i}", "projects") for i in range(10)])
    chunks = store.search_flat("q", k=3)
    assert len(chunks) == 3


def test_chunk_assembly(tmp_path):
    store = make_store(tmp_path)
    store.add_documents(
        [make_doc("m1", "areas", content="texto exacto", date="2026-03-15T10:30:00Z")]
    )
    chunks = store.search_flat("q", k=1)
    c = chunks[0]
    # original text recovered
    assert c.text == "texto exacto"
    # Source with its enum rebuilt
    assert c.source.para_folder == ParaFolder.AREAS
    assert isinstance(c.source.para_folder, ParaFolder)
    # date rebuilt as an aware datetime
    assert isinstance(c.source.date, datetime)
    assert c.source.date.tzinfo is not None
    # score normalized to [0,1] (cosine: distance [0,2] -> 1-d/2)
    assert -0.01 <= c.score <= 1.01
    # non-empty id
    assert c.chunk_id


def test_distance_to_score_extremes(tmp_path):
    # The formula itself: distance 0 -> score 1 (identical); distance 2 -> score 0 (opposite)
    store = make_store(tmp_path)
    assert store._distance_to_score(0.0) == 1.0
    assert store._distance_to_score(2.0) == 0.0
