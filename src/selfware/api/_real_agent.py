"""
api/_real_agent.py -- Person 4.

Builds the real `answer_question(query, strategy)` for `/ask`. `agent/` never
imports `context/` (architecture rule 1), so the API is where the real
retriever is built and injected into `agent.ask.make_answer_question`.

Only imported when SELFWARE_AGENT=real, so the mock-only setup (and CI) does
not need chromadb or a Token Factory key.

Environment:
    SELFWARE_CHROMA_PATH   folder of the Chroma store (default "chroma_data")
    SELFWARE_CACHE_DIR     folder of the answer cache (default ".cache")

The PARA arm classifies each question with the real context.classifier
(Nemotron Super). Its TierCall is handed to
api/_calls.py, so /ask prices it and /cost counts it.
"""

import os
from collections.abc import Callable
from pathlib import Path

from selfware.agent.answer import make_answerer
from selfware.agent.ask import make_answer_question
from selfware.api._calls import note_tier_call
from selfware.context.classifier import Classifier
from selfware.context.domain import Strategy
from selfware.context.embedder import Embedder
from selfware.context.retrieve import Retrieve
from selfware.context.store import ChromaStore
from selfware.core.schemas import Answer


def build_answer_question() -> Callable[[str, str], Answer]:
    """The Retrieve object is built ONCE per process (F3), not per question."""
    store = ChromaStore(
        Embedder(), path=os.environ.get("SELFWARE_CHROMA_PATH", "chroma_data")
    )
    retriever = Retrieve(store, Classifier(on_tier_call=note_tier_call))

    return make_answer_question(
        retrieve=lambda q, s, k: [
            c.to_contract() for c in retriever.retrieve(q, Strategy(s), k).chunks
        ],
        answer=make_answerer(Path(os.environ.get("SELFWARE_CACHE_DIR", ".cache"))),
    )
