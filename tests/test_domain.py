"""
Tests for domain.py: the focus is the INVARIANTS of RetrievalResult.__post_init__,
the only logic in the module. Dataclasses without logic are not tested (building
them and reading their fields proves nothing useful).

Rules that __post_init__ enforces:
  1. FLAT with a non-null query_category  -> forbidden
  2. FLAT with fell_back_to_flat=True     -> forbidden
  3. PARA with a null query_category      -> forbidden
And the valid states must build without error, including the diagnostic case
PARA + category + fallback=True.
"""

import pytest

from selfware.context.domain import ParaFolder, RetrievalResult, Strategy


# --- Helper: builds a RetrievalResult with valid defaults and overrides ---
def make_result(**overrides):
    base = {
        "chunks": [],
        "query_category": None,
        "fell_back_to_flat": False,
        "strategy": Strategy.FLAT,
        "k": 5,
        "version": "V1",
    }
    base.update(overrides)
    return RetrievalResult(**base)


# --- VALID states: must build without raising ---


def test_flat_without_category_is_valid():
    r = make_result(
        strategy=Strategy.FLAT, query_category=None, fell_back_to_flat=False
    )
    assert r.strategy == Strategy.FLAT
    assert r.query_category is None


def test_para_with_category_is_valid():
    r = make_result(strategy=Strategy.PARA, query_category=ParaFolder.PROJECTS)
    assert r.query_category == ParaFolder.PROJECTS


def test_para_with_category_and_fallback_is_valid():
    # Key diagnostic case: PARA classified, the filter came back empty and fell
    # back to flat. The predicted category is kept -> a LEGITIMATE combination.
    r = make_result(
        strategy=Strategy.PARA,
        query_category=ParaFolder.AREAS,
        fell_back_to_flat=True,
    )
    assert r.fell_back_to_flat is True
    assert r.query_category == ParaFolder.AREAS


# --- IMPOSSIBLE states: must raise ValueError ---


def test_flat_with_category_is_invalid():
    with pytest.raises(ValueError):
        make_result(strategy=Strategy.FLAT, query_category=ParaFolder.PROJECTS)


def test_flat_with_fallback_is_invalid():
    with pytest.raises(ValueError):
        make_result(strategy=Strategy.FLAT, query_category=None, fell_back_to_flat=True)


def test_para_without_category_is_invalid():
    with pytest.raises(ValueError):
        make_result(strategy=Strategy.PARA, query_category=None)


# --- The enums serialize to their string (str mixin), which persistence needs ---


def test_parafolder_is_str():
    assert ParaFolder.PROJECTS == "projects"
    assert ParaFolder.PROJECTS.value == "projects"


def test_strategy_is_str():
    assert Strategy.FLAT == "flat"
    assert Strategy.PARA == "para"


# --- Conversion to contract C2 (core.schemas.Chunk) ---


def test_chunk_converts_to_contract_c2():
    from datetime import UTC, datetime

    from selfware.context.domain import Chunk, Source
    from selfware.core import schemas

    fecha = datetime(2026, 9, 1, tzinfo=UTC)
    chunk = Chunk(
        chunk_id="c1",
        text="t",
        score=0.8,
        source=Source(
            source_id="msg-1",
            source="gmail",
            chunk_index=0,
            para_folder=ParaFolder.AREAS,
            date=fecha,
        ),
    )
    assert chunk.to_contract() == schemas.Chunk(
        text="t", item_id="msg-1", para_path="areas", ts=fecha, similarity=0.8
    )
