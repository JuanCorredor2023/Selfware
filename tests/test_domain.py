"""
Tests de domain.py — el foco son las INVARIANTES de RetrievalResult.__post_init__,
que es la única lógica del módulo. Los dataclasses sin lógica no se testean
(construirlos y leer sus campos no prueba nada útil).

Reglas que el __post_init__ hace cumplir:
  1. FLAT con query_category no nula  -> prohibido
  2. FLAT con fell_back_to_flat=True  -> prohibido
  3. PARA con query_category nula     -> prohibido
Y los estados válidos deben construirse sin error, incluido el caso
diagnóstico PARA + categoría + fallback=True.
"""

import pytest
from selfware.context.domain import RetrievalResult, Strategy, ParaFolder


# --- Helper: construye un RetrievalResult con defaults válidos y overrides ---
def make_result(**overrides):
    base = dict(
        chunks=[],
        query_category=None,
        fell_back_to_flat=False,
        strategy=Strategy.FLAT,
        k=5,
        version="V1",
    )
    base.update(overrides)
    return RetrievalResult(**base)


# --- Estados VÁLIDOS: deben construirse sin lanzar ---


def test_flat_sin_categoria_es_valido():
    r = make_result(
        strategy=Strategy.FLAT, query_category=None, fell_back_to_flat=False
    )
    assert r.strategy == Strategy.FLAT
    assert r.query_category is None


def test_para_con_categoria_es_valido():
    r = make_result(strategy=Strategy.PARA, query_category=ParaFolder.PROJECTS)
    assert r.query_category == ParaFolder.PROJECTS


def test_para_con_categoria_y_fallback_es_valido():
    # Caso diagnóstico clave: PARA clasificó, el filtro quedó vacío y cayó a plano.
    # La categoría predicha se conserva -> combinación LEGÍTIMA, no prohibida.
    r = make_result(
        strategy=Strategy.PARA,
        query_category=ParaFolder.AREAS,
        fell_back_to_flat=True,
    )
    assert r.fell_back_to_flat is True
    assert r.query_category == ParaFolder.AREAS


# --- Estados IMPOSIBLES: deben lanzar ValueError ---


def test_flat_con_categoria_es_invalido():
    with pytest.raises(ValueError):
        make_result(strategy=Strategy.FLAT, query_category=ParaFolder.PROJECTS)


def test_flat_con_fallback_es_invalido():
    with pytest.raises(ValueError):
        make_result(strategy=Strategy.FLAT, query_category=None, fell_back_to_flat=True)


def test_para_sin_categoria_es_invalido():
    with pytest.raises(ValueError):
        make_result(strategy=Strategy.PARA, query_category=None)


# --- Los enums serializan a su string (mixin str) — importa para persistencia ---


def test_parafolder_es_str():
    assert ParaFolder.PROJECTS == "projects"
    assert ParaFolder.PROJECTS.value == "projects"


def test_strategy_es_str():
    assert Strategy.FLAT == "flat"
    assert Strategy.PARA == "para"


# --- Conversión al contrato C2 (core.schemas.Chunk) ---


def test_chunk_se_convierte_al_contrato_c2():
    from datetime import datetime, UTC
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
