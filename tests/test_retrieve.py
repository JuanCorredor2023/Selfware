"""
Tests for retrieve.py: the H1 logic. They use a FAKE STORE and a configurable
classifier, because what is tested here is the DECISION LOGIC (which branch,
which fields, when to fall back), not Chroma.

Behaviours:
  - FLAT: query_category=None, no fallback, does not use the classifier.
  - PARA with results: the classifier's category, no fallback.
  - PARA with an empty filtered search: fallback True, category kept, flat chunks.
  - The result's category FOLLOWS the classifier (real routing).
  - k is passed on to the store.
"""

import pytest

from selfware.context.classifier import FakeClassifier
from selfware.context.domain import Chunk, ParaFolder, Strategy
from selfware.context.retrieve import Retrieve


class FakeStore:
    """Fake store: returns fixed lists and records the k it was called with."""

    def __init__(self, flat_result, filtered_result):
        self._flat = flat_result
        self._filtered = filtered_result
        self.last_flat_k = None
        self.last_filtered_k = None
        self.last_filtered_category = None

    def search_flat(self, query, k):
        self.last_flat_k = k
        return self._flat

    def search_filtered(self, query, category, k):
        self.last_filtered_k = k
        self.last_filtered_category = category
        return self._filtered


def chunk():
    return Chunk(chunk_id="x", text="t", score=0.9, source=None)


def make_retriever(flat_result, filtered_result, classifier_category):
    store = FakeStore(flat_result, filtered_result)
    classifier = FakeClassifier(classifier_category)
    return Retrieve(store, classifier), store


# --- FLAT ---


def test_flat_category_none_no_fallback():
    r, _ = make_retriever([chunk()], [chunk()], ParaFolder.PROJECTS)
    res = r.retrieve("q", Strategy.FLAT, 5)
    assert res.query_category is None
    assert res.fell_back_to_flat is False
    assert res.strategy == Strategy.FLAT


def test_flat_does_not_use_the_classifier():
    # Even with a classifier configured, FLAT does not classify -> category None
    r, _ = make_retriever([chunk()], [chunk()], ParaFolder.ARCHIVE)
    res = r.retrieve("q", Strategy.FLAT, 5)
    assert res.query_category is None


# --- PARA with results ---


def test_para_with_results_uses_the_classifier_category():
    r, _ = make_retriever([chunk()], [chunk(), chunk()], ParaFolder.AREAS)
    res = r.retrieve("q", Strategy.PARA, 5)
    assert res.query_category == ParaFolder.AREAS
    assert res.fell_back_to_flat is False
    assert len(res.chunks) == 2  # the filtered ones, not the flat ones


# --- PARA with fallback ---


def test_para_falls_back_when_filtered_is_empty():
    # empty filtered search -> falls back to flat, flags it, KEEPS the category
    r, _ = make_retriever([chunk(), chunk(), chunk()], [], ParaFolder.RESOURCES)
    res = r.retrieve("q", Strategy.PARA, 5)
    assert res.fell_back_to_flat is True
    assert res.query_category == ParaFolder.RESOURCES  # kept despite the fallback
    assert len(res.chunks) == 3  # the flat ones


# --- Routing: the category follows the classifier ---


@pytest.mark.parametrize("cat", list(ParaFolder))
def test_routing_follows_the_classifier(cat):
    r, _ = make_retriever([chunk()], [chunk()], cat)
    res = r.retrieve("q", Strategy.PARA, 5)
    assert res.query_category == cat


# --- k is passed on to the store ---


def test_k_is_passed_to_flat():
    r, store = make_retriever([chunk()], [chunk()], ParaFolder.PROJECTS)
    r.retrieve("q", Strategy.FLAT, 7)
    assert store.last_flat_k == 7


def test_k_is_passed_to_filtered():
    r, store = make_retriever([chunk()], [chunk()], ParaFolder.PROJECTS)
    r.retrieve("q", Strategy.PARA, 9)
    assert store.last_filtered_k == 9


def test_para_passes_a_parafolder_to_the_store():
    # the store must receive the ParaFolder (enum), not a string
    r, store = make_retriever([chunk()], [chunk()], ParaFolder.AREAS)
    r.retrieve("q", Strategy.PARA, 5)
    assert store.last_filtered_category == ParaFolder.AREAS
    assert isinstance(store.last_filtered_category, ParaFolder)
