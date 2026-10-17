"""Fake agent satisfying contract C3. Deterministic, no network, no budget.

**It answers nothing.** The text is always `"FAKE answer"` and the confidence
comes from a hash, so nobody can mistake a report built on it for a result. It
exists so `scripts/run_eval.py --fake` can run the whole pipeline end to end.

What it does reproduce is the *shape* of `agent/answer.py`, which is what the
report needs to exercise every column:

- zero chunks -> the model is not "called": `confidence=0.0`,
  `finish_reason="no_chunks"` (same as `NO_CHUNKS`);
- about 1 in 20 answers comes back truncated (`finish_reason="length"`), so the
  truncated and excluded columns are not always 0;
- the rest: `finish_reason="stop"` with a confidence in [0, 1).

Same hashing as `retrieve_fake` (sha256, first 4 bytes, big-endian, over 2**32)
and for the same reason: `random` has global state; a hash depends on nothing.
"""

import hashlib

from selfware.core.schemas import Answer, Chunk

#: Text of every fake answer. Shouting on purpose.
FAKE_TEXT = "FAKE answer"

#: Fraction of answers that come back truncated. Small, like a healthy run.
TRUNCATED_RATE = 0.05


def _unit(text: str) -> float:
    """A deterministic value in [0, 1) from any string."""
    digest = hashlib.sha256(text.encode()).digest()
    return int.from_bytes(digest[:4], "big") / (1 << 32)


def answer_fake(question: str, chunks: list[Chunk]) -> Answer:
    """`(question, chunks) -> Answer`, like the function `make_answerer` returns.

    The hash covers the question **and** the ids of the chunks, so the two arms
    of the same question (which retrieve different chunks) get different
    confidences, as they would with the real agent.
    """
    if not chunks:
        return Answer(
            text="",
            confidence=0.0,
            provenance=[],
            used_web=False,
            finish_reason="no_chunks",
        )

    key = question + "||" + "|".join(c.item_id for c in chunks)
    truncated = _unit("finish||" + key) < TRUNCATED_RATE

    return Answer(
        text=FAKE_TEXT,
        confidence=_unit("confidence||" + key),
        provenance=list(chunks),
        used_web=False,
        finish_reason="length" if truncated else "stop",
    )
