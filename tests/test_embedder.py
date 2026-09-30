"""
Tests de embedder.py — el Embedder falso determinista.
Se validan sus PROPIEDADES, no su semántica (los vectores no tienen sentido
semántico, así que no se prueba relevancia — eso es del embedder real).

Propiedades:
  - Forma batch: N textos -> N vectores, en orden.
  - Dimensión fija: todos los vectores de self.dimensions.
  - Determinismo: mismo texto -> mismo vector, incluso entre instancias.
  - Aislamiento: no contamina el generador random global.
"""

import random
from selfware.context.embedder import Embedder


def test_forma_batch_conserva_cantidad_y_orden():
    emb = Embedder()
    textos = ["uno", "dos", "tres"]
    vecs = emb.embed(textos)
    assert len(vecs) == len(textos)
    # el orden se conserva: reembeber un solo texto da el mismo vector que su posición
    assert emb.embed(["dos"])[0] == vecs[1]


def test_dimension_fija():
    emb = Embedder()
    vecs = emb.embed(["a", "bb", "ccc largo con muchas palabras distintas"])
    assert all(len(v) == emb.dimensions for v in vecs)


def test_determinismo_misma_instancia():
    emb = Embedder()
    a = emb.embed(["texto idéntico"])[0]
    b = emb.embed(["texto idéntico"])[0]
    assert a == b


def test_determinismo_entre_instancias():
    # El determinismo vive en el algoritmo (hash), no en el estado del objeto.
    a = Embedder().embed(["texto idéntico"])[0]
    b = Embedder().embed(["texto idéntico"])[0]
    assert a == b


def test_textos_distintos_dan_vectores_distintos():
    emb = Embedder()
    assert emb.embed(["texto A"])[0] != emb.embed(["texto B"])[0]


def test_no_contamina_random_global():
    # Sembrar el global, embeber, y confirmar que la secuencia global no cambió:
    # el Embedder usa una instancia local random.Random, no el módulo global.
    r = random.Random()
    random.seed(12345)
    esperado = random.random()

    random.seed(12345)
    Embedder().embed(["algo", "otra cosa"])  # no debe tocar el estado global
    obtenido = random.random()

    assert esperado == obtenido


def test_lista_vacia_devuelve_lista_vacia():
    assert Embedder().embed([]) == []
