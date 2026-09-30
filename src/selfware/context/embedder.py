import hashlib
import random


class Embedder:
    def __init__(self):

        self.dimensions = 384

    def embed(self, raw_documents: list[str]) -> list[list[float]]:

        embeddings: list[list[float]] = []

        for document in raw_documents:
            embeddings.append(self._to_embedding(document))

        return embeddings

    def _to_embedding(self, raw_document: str) -> list[float]:

        hash_obj = hashlib.sha256(raw_document.encode("utf-8"))
        res_hex = hash_obj.hexdigest()
        seed = int(res_hex, 16)

        rng = random.Random(seed)

        embedding: list[float] = [rng.random() for _ in range(self.dimensions)]

        return embedding
