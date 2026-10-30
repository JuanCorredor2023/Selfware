from selfware.context.classifier import FakeClassifier
from selfware.context.domain import Document, ParaFolder
from selfware.context.ingest_classify import classify_documents


class CountingFakeClassifier(FakeClassifier):
    """FakeClassifier that counts the calls to classify_document, to check that
    already-classified documents trigger no call."""

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


def test_document_without_category_is_classified():
    docs = [make_doc("m1", None)]
    classify_documents(docs, FakeClassifier(ParaFolder.PROJECTS))
    assert docs[0].category == "projects"


def test_document_with_category_is_left_alone():
    docs = [make_doc("m1", "areas")]
    classify_documents(docs, FakeClassifier(ParaFolder.PROJECTS))
    # NOT reclassified as projects: the existing category is kept
    assert docs[0].category == "areas"


def test_only_classifies_the_pending_ones():
    docs = [
        make_doc("m1", None),  # pending
        make_doc("m2", "areas"),  # already has one
        make_doc("m3", None),  # pending
    ]
    clf = CountingFakeClassifier(ParaFolder.RESOURCES)
    classify_documents(docs, clf)
    # only 2 calls (m1 and m3), not 3 -- m2 was skipped
    assert clf.document_calls == 2
    assert docs[0].category == "resources"
    assert docs[1].category == "areas"  # untouched
    assert docs[2].category == "resources"


def test_returns_the_same_list():
    docs = [make_doc("m1", None)]
    result = classify_documents(docs, FakeClassifier(ParaFolder.PROJECTS))
    assert result is docs  # mutates and returns the same list


def test_category_is_a_string_not_an_enum():
    # Document.category is a raw str; classify_document returns a ParaFolder,
    # so its .value (a string) must be stored, not the enum.
    docs = [make_doc("m1", None)]
    classify_documents(docs, FakeClassifier(ParaFolder.ARCHIVE))
    assert docs[0].category == "archive"
    assert isinstance(docs[0].category, str)
