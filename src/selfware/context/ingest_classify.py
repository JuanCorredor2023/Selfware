from selfware.context.classifier import Classifier
from selfware.context.domain import Document


def classify_documents(
    documents: list[Document], classifier: Classifier
) -> list[Document]:
    """
    This is a separate ingestion step, run BEFORE store.add_documents(), which
    keeps the store a pure Chroma adapter (it indexes already-classified docs).
    """
    for doc in documents:
        if doc.category is None:
            doc.category = classifier.classify_document(doc.content).value
    return documents
