from selfware.context.classifier import FakeClassifier
from selfware.context.domain import Document, ParaFolder
from selfware.context.ingest_classify import classify_documents


class CountingFakeClassifier(FakeClassifier):
    """FakeClassifier que cuenta cuántas veces se llama classify_document,
    para verificar que los ya-clasificados no gatillan llamadas."""

    def __init__(self, category_to_return):
        super().__init__(category_to_return)
        self.document_calls = 0

    def classify_document(self, content):
        self.document_calls += 1
        return super().classify_document(content)


def make_doc(source_id, category):
    return Document(
        source_id=source_id,
        source="email",
        content="contenido de prueba",
        category=category,
        date="2026-01-01T00:00:00Z",
    )


def test_documento_sin_categoria_se_clasifica():
    docs = [make_doc("m1", None)]
    classify_documents(docs, FakeClassifier(ParaFolder.PROJECTS))
    assert docs[0].category == "projects"


def test_documento_con_categoria_queda_intacto():
    docs = [make_doc("m1", "areas")]
    classify_documents(docs, FakeClassifier(ParaFolder.PROJECTS))
    # NO se reclasifica a projects: la categoría previa se respeta
    assert docs[0].category == "areas"


def test_solo_clasifica_los_pendientes():
    docs = [
        make_doc("m1", None),  # pendiente
        make_doc("m2", "areas"),  # ya tiene
        make_doc("m3", None),  # pendiente
    ]
    clf = CountingFakeClassifier(ParaFolder.RESOURCES)
    classify_documents(docs, clf)
    # solo 2 llamadas (m1 y m3), no 3 -- m2 se saltó
    assert clf.document_calls == 2
    assert docs[0].category == "resources"
    assert docs[1].category == "areas"  # intacto
    assert docs[2].category == "resources"


def test_devuelve_la_misma_lista():
    docs = [make_doc("m1", None)]
    result = classify_documents(docs, FakeClassifier(ParaFolder.PROJECTS))
    assert result is docs  # muta y devuelve la misma lista


def test_categoria_es_string_no_enum():
    # category en Document es str (crudo); classify_document devuelve ParaFolder,
    # así que debe guardarse su .value (string), no el enum.
    docs = [make_doc("m1", None)]
    classify_documents(docs, FakeClassifier(ParaFolder.ARCHIVE))
    assert docs[0].category == "archive"
    assert isinstance(docs[0].category, str)
