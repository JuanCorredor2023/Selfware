"""
core/schemas.py -- the contracts between lanes. Owner: Person 1.

Single source of truth: every lane imports these types from here. It merges
the three drafts that existed before integration (`core/schema.py`,
`core/schemas.py` and `agent/_contracts.py`); see docs/integration_p3.md,
items A1-A5 and C2.

- ContextItem: ingest/ -> context/ (C1)
- Chunk:       context/ -> agent/, eval/, api/ (C2)
- Answer:      agent/ -> api/, eval/ (C3)
- TierCall:    core/llm.py -> observability/ (C4)
- Question:    eval/ (C6)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ContextItem(BaseModel):
    """Contract C1: ingest/ -> context/. One normalized item from a source."""

    id: str
    source: Literal["gmail"]  # more sources will come later
    text: str
    ts: datetime
    hash: str
    para_path: str | None  # None until the PARA classifier runs
    meta: dict


@dataclass
class TierCall:
    """Contract C4: core/llm.py -> observability/. One entry per call to
    Token Factory (Nano or Ultra).

    Mutable on purpose: `observability/cost.py` fills in `cost_usd` (A4)."""

    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float


@dataclass(frozen=True)
class Chunk:
    """A retrieved snippet. Contract C2: produced by `context/` (Person 2).

    Invariant of the list holding it (D9): `retrieve()` returns chunks sorted
    by `similarity` DESCENDING. The first element is the most relevant.

    Attributes:
        text: the snippet text.
        item_id: identifier of the document it came from.
        para_path: the PARA folder the document belongs to.
        ts: date of the original document. A `datetime`, not a string (A2):
            `agent/answer.py` formats it into the prompt. Convert to a string
            only at the HTTP boundary.
        similarity: cosine in [0,1]. HIGHER = MORE RELEVANT (A1, D10). It is
            NOT a distance: receiving a distance here would silently invert
            the confidence signal.
    """

    text: str
    item_id: str
    para_path: str
    ts: datetime
    similarity: float


@dataclass(frozen=True)
class Question:
    """One question from the evaluation set. Contract C6: produced by `eval/`.

    Read from `questions/*.jsonl`, one JSON object per line (D19).

    Attributes:
        id: unique identifier within the set, e.g. `sd-p01`.
        q: the question, exactly as it would be put to the system.
        expected: the correct answer, verified against the email. `None` for
            unanswerable questions: there the right behaviour is to abstain.
        category: the PARA folder where the ANSWER lives (D20.5). `None` for
            unanswerable ones. Must match the string the classifier emits
            (R14, E1), or the PARA filter silently finds nothing.
        evidence: which email the answer came from. `None` for unanswerable.
        answerable: whether the answer exists in the corpus (D21).
        hops: pieces of evidence to combine; 1 = one email (D20.3, D22).
            `None` for unanswerable ones.
        source: `"human"` or `"ai-drafted"` (D27).
        hard_case: whether retrieval is genuinely difficult here (D28).
    """

    id: str
    q: str
    expected: str | None
    category: str | None
    evidence: str | None
    answerable: bool
    hops: int | None
    source: str | None = None
    hard_case: bool = False


@dataclass(frozen=True)
class Answer:
    """The agent's response. Contract C3: produced by `agent/`, consumed by
    `api/` and `eval/`.

    Attributes:
        text: the generated answer.
        confidence: [0,1], from `agent/confidence.py` (D24).
        provenance: the chunks supporting the answer. May be empty (D8).
        used_web: whether Tavily was reached for after abstaining.
        finish_reason: whatever the server returned. Anything other than
            `"stop"` means the answer was cut short (D17, A3).
        tier_calls: one entry per Token Factory call behind this answer (C4).
            Defaults to empty until `agent/answer.py` goes through
            `core/llm.py` (B1, C1).
    """

    text: str
    confidence: float
    provenance: list[Chunk]
    used_web: bool
    finish_reason: str
    tier_calls: list[TierCall] = field(default_factory=list)
