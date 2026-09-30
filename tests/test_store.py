"""
Tests de store.py — ChromaStore contra Chroma REAL (colección temporal por test,
vía la fixture tmp_path de pytest, que crea y limpia un directorio aislado).

Se usa el Embedder falso: los vectores no tienen sentido semántico, así que NO se
prueba relevancia (qué chunk es "más parecido"), solo comportamiento mecánico:
  - Idempotencia: reinsertar no duplica.
  - Reclasificación (upsert): reinsertar con otra categoría actualiza.
  - Filtro por categoría: search_filtered solo devuelve la categoría pedida.
  - Ensamblado: los Chunk salen con texto, Source con enum y datetime, score en [0,1].
  - Validación: add_documents vacío lanza.
"""
import pytest
from selfware.context.store import ChromaStore
from selfware.context.embedder import Embedder
from selfware.context.domain import Document, ParaFolder
from datetime import datetime


def make_store(tmp_path):
    # tmp_path es una fixture de pytest: un directorio temporal único por test.
    # Así cada test corre contra una colección Chroma limpia y aislada.
    return ChromaStore(embedder=Embedder(), path=str(tmp_path))


def make_doc(source_id, category, content="contenido de prueba", date="2026-01-01T00:00:00Z"):
    return Document(
        source_id=source_id,
        source="email",
        content=content,
        category=category,
        date=date,
    )


def test_add_documents_vacio_lanza(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(ValueError):
        store.add_documents([])


def test_insercion_cuenta_correcta(tmp_path):
    store = make_store(tmp_path)
    store.add_documents([make_doc("m1", "projects"), make_doc("m2", "areas")])
    assert store.collection.count() == 2


def test_idempotencia_no_duplica(tmp_path):
    store = make_store(tmp_path)
    docs = [make_doc("m1", "projects"), make_doc("m2", "areas")]
    store.add_documents(docs)
    store.add_documents(docs)  # reinsertar los mismos
    assert store.collection.count() == 2


def test_reclasificacion_por_upsert(tmp_path):
    store = make_store(tmp_path)
    store.add_documents([make_doc("m1", "projects")])
    # mismo source_id, categoría distinta -> upsert debe ACTUALIZAR, no duplicar
    store.add_documents([make_doc("m1", "archive")])
    assert store.collection.count() == 1
    got = store.collection.get(include=["metadatas"])
    assert got["metadatas"][0]["category"] == "archive"


def test_filtro_por_categoria_solo_devuelve_esa(tmp_path):
    store = make_store(tmp_path)
    store.add_documents([
        make_doc("m1", "projects"),
        make_doc("m2", "areas"),
        make_doc("m3", "projects"),
    ])
    chunks = store.search_filtered("cualquier cosa", ParaFolder.PROJECTS, k=10)
    assert len(chunks) == 2
    assert all(c.source.para_folder == ParaFolder.PROJECTS for c in chunks)


def test_filtro_categoria_vacia_devuelve_lista_vacia(tmp_path):
    # Ninguna categoría RESOURCES insertada -> filtro devuelve [] (dispara el fallback en retrieve)
    store = make_store(tmp_path)
    store.add_documents([make_doc("m1", "projects")])
    chunks = store.search_filtered("q", ParaFolder.RESOURCES, k=10)
    assert chunks == []


def test_search_flat_respeta_k(tmp_path):
    store = make_store(tmp_path)
    store.add_documents([make_doc(f"m{i}", "projects") for i in range(10)])
    chunks = store.search_flat("q", k=3)
    assert len(chunks) == 3


def test_ensamblado_del_chunk(tmp_path):
    store = make_store(tmp_path)
    store.add_documents([make_doc("m1", "areas", content="texto exacto", date="2026-03-15T10:30:00Z")])
    chunks = store.search_flat("q", k=1)
    c = chunks[0]
    # texto original recuperado
    assert c.text == "texto exacto"
    # Source con enum reconstruido
    assert c.source.para_folder == ParaFolder.AREAS
    assert isinstance(c.source.para_folder, ParaFolder)
    # fecha reconstruida a datetime aware
    assert isinstance(c.source.date, datetime)
    assert c.source.date.tzinfo is not None
    # score normalizado en rango [0,1] (coseno: distancia [0,2] -> 1-d/2)
    assert -0.01 <= c.score <= 1.01
    # id no vacío
    assert c.chunk_id


def test_distance_to_score_extremos(tmp_path):
    # Prueba directa de la fórmula: distancia 0 -> score 1 (idéntico); distancia 2 -> score 0 (opuesto)
    store = make_store(tmp_path)
    assert store._distance_to_score(0.0) == 1.0
    assert store._distance_to_score(2.0) == 0.0
