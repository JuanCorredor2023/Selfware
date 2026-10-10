from selfware.context.domain import QueryInstruction
from selfware.core.llm import embed


class Embedder:
    def __init__(self, task_description: QueryInstruction = QueryInstruction.RELEVANT_EMAILS):

        self.task_description = task_description

        self.dimensions = 4096 # up to date with core/llm.py quwen3 endpoint

    def embed_query(self, query: str) -> list[float]:

        instruct_query = self._build_instruct_query(query)

        vector, _ = embed([instruct_query])

        return vector[0]
        
    def embed_documents(self, texts: list[str]) -> list[list[float]]:

        vectors, _ = embed(texts)

        return vectors


    def _build_instruct_query(self, query: str):

        instruct_query : str = f"Instruct: {self.task_description.value}\nQuery: {query}"

        return instruct_query


