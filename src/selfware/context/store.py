import hashlib
from datetime import datetime
from typing import Any

from chromadb import PersistentClient, QueryResult

from .domain import Chunk, Document, ParaFolder, Source
from .embedder import Embedder


class ChromaStore:
    def __init__(self, embedder: Embedder, path: str = "chroma_data"):
        self.path = path
        self.client = PersistentClient(path=self.path)
        self.collection_name = "collection_v1"
        self.embedder = embedder

        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=None,
            configuration={"hnsw": {"space": "cosine"}},
        )

    def add_documents(self, documents: list[Document]) -> None:

        if not documents:
            raise ValueError("Documents is empty")

        ids: list[str] = []

        raw_texts = self._isolate_texts(documents)
        embeddings = self.embedder.embed(raw_texts)

        metadatas: list[dict[str, str]] = []

        for i in range(len(documents)):
            document: Document = documents[i]

            chunk_index = 0

            curr_id = self._create_id(document.source_id, document.source, chunk_index)

            ids.append(curr_id)

            metadatas.append(
                {
                    "source_id": document.source_id,
                    "source": document.source,
                    "chunk_index": chunk_index,
                    "category": document.category,
                    "date": document.date,
                }
            )

        self._add_data(ids, embeddings, raw_texts, metadatas)

    def _create_id(self, source_id: str, source: str, chunk_index: int) -> str:

        to_hash: str = source_id + source + str(chunk_index)
        hash_obj = hashlib.sha256(to_hash.encode("utf-8"))
        res_hex = hash_obj.hexdigest()

        return res_hex

    def _add_data(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, str]],
    ) -> None:

        self.collection.upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )

    def _isolate_texts(self, documents: list[Document]) -> list[str]:

        raw_texts: list[str] = []

        for document in documents:
            raw_texts.append(document.content)

        return raw_texts

    def _to_para_folder(self, category: str) -> ParaFolder:

        return ParaFolder(category)

    def _to_datetime(self, isostring: str) -> datetime:

        return datetime.fromisoformat(isostring)

    def _build_source(self, row: dict[str, Any] | None) -> Source:

        curr_source: Source = Source(
            source_id=row["source_id"],
            source=row["source"],
            chunk_index=row["chunk_index"],
            para_folder=self._to_para_folder(row["category"]),
            date=self._to_datetime(row["date"]),
        )

        return curr_source

    def _build_source_list(
        self, metadatas: list[dict[str, Any] | None] | None
    ) -> list[Source]:

        source_list: list[Source] = []

        for row in metadatas:
            curr_source: Source = self._build_source(row)

            source_list.append(curr_source)

        return source_list

    def _distance_to_score(self, distance: float) -> float:

        score = 1 - (distance / 2)

        return score

    def _build_chunk(
        self, document: str, row: Source, curr_id: str, distance: float
    ) -> Chunk:

        chunk: Chunk = Chunk(
            chunk_id=curr_id,
            text=document,
            score=self._distance_to_score(distance),
            source=row,
        )

        return chunk

    def _build_chunk_list(
        self,
        documents: list[str | None] | None,
        source_list: list[Source],
        ids_list: list[str],
        distance_list: list[float | None] | None,
    ) -> list[Chunk]:

        chunk_list: list[str] = []

        for i in range(len(documents)):
            curr_id: str = ids_list[i]
            document: str = documents[i]
            distance: float = distance_list[i]
            row: Source = source_list[i]

            chunk: Chunk = self._build_chunk(document, row, curr_id, distance)

            chunk_list.append(chunk)

        return chunk_list

    def search_flat(self, query: str, k: int) -> list[Chunk]:

        queries: list[str] = [query]

        query_embedding: list[float] = self.embedder.embed(queries)[0]

        search_results: QueryResult = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )

        ids_list: list[str] = search_results["ids"][0]
        documents: list[str | None] | None = search_results["documents"][0]
        distance_list: list[float | None] | None = search_results["distances"][0]
        metadatas: list[dict[str, Any] | None] | None = search_results["metadatas"][0]

        source_list: list[Source] = self._build_source_list(metadatas)
        chunk_list: list[Chunk] = self._build_chunk_list(
            documents, source_list, ids_list, distance_list
        )

        return chunk_list

    def search_filtered(self, query: str, category: ParaFolder, k: int) -> list[Chunk]:

        queries: list[str] = [query]

        query_embedding: list[float] = self.embedder.embed(queries)[0]

        search_results: QueryResult = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where={"category": category.value},
            include=["documents", "metadatas", "distances"],
        )

        ids_list: list[str] = search_results["ids"][0]
        documents: list[str | None] | None = search_results["documents"][0]
        distance_list: list[float | None] | None = search_results["distances"][0]
        metadatas: list[dict[str, Any] | None] | None = search_results["metadatas"][0]

        source_list: list[Source] = self._build_source_list(metadatas)
        chunk_list: list[Chunk] = self._build_chunk_list(
            documents, source_list, ids_list, distance_list
        )

        return chunk_list
