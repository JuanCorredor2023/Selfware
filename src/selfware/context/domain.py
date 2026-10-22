from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from selfware.core import schemas


# -- Definition of what is PARA
class ParaFolder(str, Enum):
    PROJECTS = "projects"
    AREAS = "areas"
    RESOURCES = "resources"
    ARCHIVE = "archive"


class Strategy(str, Enum):
    FLAT = "flat"
    PARA = "para"


class QueryInstruction(str, Enum):
    RELEVANT_EMAILS = (
        "Given a search query, retrieve relevant emails that answer the query"
    )


@dataclass
class Source:
    source_id: str
    source: str
    chunk_index: int
    para_folder: ParaFolder
    date: datetime


@dataclass
class Chunk:
    chunk_id: str
    text: str
    score: float
    source: Source

    def to_contract(self) -> schemas.Chunk:
        # Contract C2 for agent/, eval/ and api/. `score` is already a
        # similarity in [0,1] (store.py maps cosine distance d to 1 - d/2).
        return schemas.Chunk(
            text=self.text,
            item_id=self.source.source_id,
            para_path=self.source.para_folder.value,
            ts=self.source.date,
            similarity=self.score,
        )


@dataclass
class Document:
    source_id: str
    source: str
    content: str
    category: str | None
    date: str


@dataclass
class RetrievalResult:
    chunks: list[Chunk]
    query_category: ParaFolder | None
    fell_back_to_flat: bool
    strategy: Strategy
    k: int
    version: str

    def __post_init__(self) -> None:

        if self.strategy == Strategy.FLAT and self.query_category is not None:
            raise ValueError("Flat strategy does not classify.")

        if self.strategy == Strategy.FLAT and self.fell_back_to_flat:
            raise ValueError("Flat was already selected, so no fell_back to it.")

        if self.strategy == Strategy.PARA and self.query_category is None:
            raise ValueError("PARA always classifies.")
