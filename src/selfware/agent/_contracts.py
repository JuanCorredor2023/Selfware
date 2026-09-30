# PROVISIONAL: replace with "from core.schemas import ..." at integration time.
"""Types this module needs from `core/`, copied here so `agent/` and `eval/`
can be built and tested before `core/schemas.py` is signed.

The real owner of these contracts is Person 1. Nothing here is a decision: it
is a local copy so the branch runs on its own. At integration time this file
is deleted and every import of it points at `core.schemas` instead.

Two known disagreements with the draft `core/schemas.py` currently living on
`origin/feature/setup-producto-observabilidad`. Both are open questions for
Person 1, written up in TEMAS_EQUIPO.md:

1. `Chunk.similarity` vs the draft's `Chunk.score` (D10). See the field docs.
2. `Chunk.ts` is a `datetime` here and a `str` in the draft. `build_prompt()`
   calls `.strftime()` on it, so a `str` raises AttributeError on the first
   real call.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TierCall:
    """Contract C4: core/llm.py -> observability/. One entry per call to
    Token Factory (Nano or Ultra)."""

    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float


@dataclass(frozen=True)
class Chunk:
    """A retrieved snippet. Contract C2: produced by `context/` (Person 2).

    Invariant of the list holding it (D9): `retrieve()` returns chunks sorted
    by `similarity` DESCENDING. The first element is the most relevant. That
    order is information produced by the retriever, not presentation.

    `frozen=True` makes it immutable: a consumer cannot accidentally modify a
    chunk another module is still going to read.

    Attributes:
        text: the snippet text.
        item_id: identifier of the document it came from.
        para_path: the PARA folder the document belongs to.
        ts: date of the original document.
        similarity: cosine in [0,1]. HIGHER = MORE RELEVANT (D10).
            It is NOT a distance. The field is called `similarity` and not
            `score` precisely because the real risk is receiving a distance:
            the confidence signal would be inverted -- the system confident
            exactly where it should doubt -- without raising any error.
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
            unanswerable questions: there the right behaviour is to abstain, not
            a piece of text.
        category: the PARA folder where the ANSWER lives, not the topic of the
            question (D20.5). `None` for unanswerable ones. Watch out for R14:
            this string has to be exactly the one the Person 1 classifier emits,
            or the PARA filter finds nothing and the system abstains on
            everything without raising.
        evidence: which email the answer came from. It forces you to find it
            BEFORE writing the question; without it you write unanswerable
            questions by accident. `None` for unanswerable ones.
        answerable: whether the answer exists in the corpus. The `False` ones
            live in a separate file (D21) and are evaluated differently: the
            criterion is "did it abstain?", not "did it say this text?".
        hops: how many pieces of evidence have to be combined. 1 = it is in one
            email; 2 = you have to compare, count, sort or add up (D20.3, D22).
            `None` for unanswerable ones.
        source: `"human"` or `"ai-drafted"` (D27). It allows checking that the
            flat-vs-PARA difference holds within each group, and is not an
            artefact of AI questions inheriting the vocabulary of the email.
        hard_case: whether this is a case where retrieval is genuinely difficult
            (D28). Reported as a separate subset from the global average.
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
        confidence: [0,1], from `confidence.py` (D24). `abstain.py` compares it
            against a threshold, in Python code -- the model never decides (D13).
        provenance: the chunks supporting the answer. May come back empty: by D8
            the PARA arm returns `[]` when the filter leaves the folder with
            nothing, and that is a legitimate result that ends in abstention.
        used_web: whether Tavily was reached for after abstaining.
        finish_reason: whatever the server returned. Anything other than
            `"stop"` means the answer was cut short, and it is reported
            separately (D17). A truncated answer evaluated as a normal one
            silently contaminates the number.
        tier_calls: one entry per Token Factory call behind this answer (C4).

    EXTENSION TO C3 -- `finish_reason` is not in the contract as written in
        P3.md; it was added here on 20 Sep because D17 depends on it. Person 1
        still has to sign it off (P1.3 in TEMAS_EQUIPO.md), and Person 4 has to
        stop discarding the field in `core.llm.call()` (P4.2) or nothing
        downstream of `core/` can ever populate it.

    PROVISIONAL -- `tier_calls` defaults to empty.
        `agent/answer.py` calls the SDK client directly instead of going through
        `core/llm.py`, and `TierCall` is built inside `core/llm.py`. So today
        there is nothing for the agent to put here. The default keeps the field
        in the contract, visible, instead of pretending it does not exist. It
        stops being a default once P4.5 is resolved.
    """

    text: str
    confidence: float
    provenance: list[Chunk]
    used_web: bool
    finish_reason: str
    tier_calls: list[TierCall] = field(default_factory=list)
