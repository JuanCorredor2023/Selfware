"""
Tests de retrieve.py — la lógica de H1. Se usan un STORE FALSO y el classifier
configurable, porque aquí lo que se prueba es la LÓGICA DE DECISIÓN (qué rama,
qué campos, cuándo fallback), no Chroma.

Comportamientos:
  - FLAT: query_category=None, sin fallback, no usa el classifier.
  - PARA con resultados: categoría del classifier, sin fallback.
  - PARA con filtrado vacío: fallback True, categoría conservada, chunks del plano.
  - La categoría del resultado SIGUE al classifier (enrutamiento real).
  - k se propaga al store.
"""
import pytest
from selfware.context.retrieve import Retrieve
from selfware.context.classifier import Classifier
from selfware.context.domain import Strategy, ParaFolder, Chunk


class FakeStore:
    """Store falso: devuelve listas fijas y registra con qué k fue llamado."""
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
    classifier = Classifier(classifier_category)
    return Retrieve(store, classifier), store


# --- FLAT ---

def test_flat_categoria_none_sin_fallback():
    r, _ = make_retriever([chunk()], [chunk()], ParaFolder.PROJECTS)
    res = r.retrieve("q", Strategy.FLAT, 5)
    assert res.query_category is None
    assert res.fell_back_to_flat is False
    assert res.strategy == Strategy.FLAT


def test_flat_no_usa_el_classifier():
    # Aunque el classifier esté configurado, FLAT no clasifica -> categoría None
    r, _ = make_retriever([chunk()], [chunk()], ParaFolder.ARCHIVE)
    res = r.retrieve("q", Strategy.FLAT, 5)
    assert res.query_category is None


# --- PARA con resultados ---

def test_para_con_resultados_usa_categoria_del_classifier():
    r, _ = make_retriever([chunk()], [chunk(), chunk()], ParaFolder.AREAS)
    res = r.retrieve("q", Strategy.PARA, 5)
    assert res.query_category == ParaFolder.AREAS
    assert res.fell_back_to_flat is False
    assert len(res.chunks) == 2  # los del filtrado, no los del plano


# --- PARA con fallback ---

def test_para_fallback_cuando_filtrado_vacio():
    # filtrado vacío -> cae a plano, marca fallback, CONSERVA la categoría
    r, _ = make_retriever([chunk(), chunk(), chunk()], [], ParaFolder.RESOURCES)
    res = r.retrieve("q", Strategy.PARA, 5)
    assert res.fell_back_to_flat is True
    assert res.query_category == ParaFolder.RESOURCES  # conservada pese al fallback
    assert len(res.chunks) == 3  # los del plano


# --- Enrutamiento: la categoría sigue al classifier ---

@pytest.mark.parametrize("cat", list(ParaFolder))
def test_enrutamiento_sigue_al_classifier(cat):
    r, _ = make_retriever([chunk()], [chunk()], cat)
    res = r.retrieve("q", Strategy.PARA, 5)
    assert res.query_category == cat


# --- k se propaga al store ---

def test_k_se_propaga_a_flat():
    r, store = make_retriever([chunk()], [chunk()], ParaFolder.PROJECTS)
    r.retrieve("q", Strategy.FLAT, 7)
    assert store.last_flat_k == 7


def test_k_se_propaga_a_filtered():
    r, store = make_retriever([chunk()], [chunk()], ParaFolder.PROJECTS)
    r.retrieve("q", Strategy.PARA, 9)
    assert store.last_filtered_k == 9


def test_para_pasa_parafolder_al_store():
    # el store debe recibir el ParaFolder (enum), no un string
    r, store = make_retriever([chunk()], [chunk()], ParaFolder.AREAS)
    r.retrieve("q", Strategy.PARA, 5)
    assert store.last_filtered_category == ParaFolder.AREAS
    assert isinstance(store.last_filtered_category, ParaFolder)
