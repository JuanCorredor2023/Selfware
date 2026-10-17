"""Fake scorer satisfying `eval.pipeline.ScoreFn`. Deterministic, no network.

**It measures nothing.** Each `(question, arm)` gets a value from a hash, so a
report built on it shows intervals that cross 0 more or less everywhere -- which
is exactly what "no effect" should look like. It stands in for RAGAS until
integration step 7, so `scripts/run_eval.py --fake` can run end to end.

One rule it does copy from the real thing: a row with **no chunks** scores 0.0.
RAGAS context precision/recall over an empty context is 0, and that 0 is what
makes a PARA arm that retrieved nothing show up in the difference (2a,
decision 1).
"""

import hashlib

from selfware.core.schemas import Question
from selfware.eval.harness import Record
from selfware.eval.report import Scores


def _unit(text: str) -> float:
    """A deterministic value in [0, 1) from any string."""
    digest = hashlib.sha256(text.encode()).digest()
    return int.from_bytes(digest[:4], "big") / (1 << 32)


def scores_fake(questions: list[Question], records: list[Record]) -> Scores:
    """One made-up score per row: `(question_id, strategy) -> [0, 1)`.

    `questions` is received to match `ScoreFn` and ignored: the real scorer needs
    the reference answers, this one does not.
    """
    return {
        (r.question_id, r.strategy): (
            0.0 if r.n_chunks == 0 else _unit(f"{r.question_id}||{r.strategy}")
        )
        for r in records
    }
