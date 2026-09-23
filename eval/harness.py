"""Run the question set through both arms and return comparable rows.

This is the module that produces the project's central number: the difference
between the flat index and the PARA-filtered one.

Paired design (D18): **the same question goes through both arms**. That gives far
more statistical power than comparing two independent groups, because the
intrinsic difficulty of each question cancels out in the subtraction. With ~66
questions per category, a 3-point difference cannot be told from noise any other
way.

This module does NOT import `retrieve` or `answer`: it **receives** them (see
`run`). That is how it gets tested end to end with no network and no budget
spent, and the day Person 2's real `retrieve` arrives nothing here has to change
-- the caller changes.

PROVISIONAL IMPORT -- this module imports its contract types from
`agent/_contracts.py`, and a module importing from another module is exactly what
the monolith rule forbids. It is done here because `core/schemas.py` belongs to
Person 1 and does not exist yet, and the alternative -- a second copy of `Chunk`
and `Answer` living in `eval/` -- risks the two definitions drifting apart, which
is the failure family of D10 and R14. At integration both files import from
`core.schemas` and the problem disappears. Tracked in TEMAS_EQUIPO.md.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from agent._contracts import Answer, Chunk, Question

Strategy = Literal["flat", "para"]

#: The two arms, in fixed order. The order is part of reproducibility: two runs
#: of the same set have to produce the rows in the same sequence.
STRATEGIES: tuple[Strategy, ...] = ("flat", "para")

#: Signature of what `context/` produces (Person 2), contract C2.
RetrieveFn = Callable[[str, Strategy, int], list[Chunk]]

#: Signature of what `agent/` produces, contract C3.
AnswerFn = Callable[[str, list[Chunk]], Answer]


@dataclass(frozen=True)
class Record:
    """One result row: one question, one arm.

    Deliberately flat and without the question metadata (`category`,
    `hard_case`, `source`, `hops`). Those live in `Question` and the report joins
    them by `question_id`. Duplicating them here invites the two copies to drift
    apart.

    Attributes:
        question_id: the `id` of the `Question`.
        strategy: `"flat"` or `"para"`. Together with `question_id` it
            identifies the row.
        text: the answer the system gave.
        confidence: [0,1], from `confidence.py` (D24).
        n_chunks: how many chunks this arm retrieved. **Zero is a legitimate
            result**, not an error: by D8 the PARA arm returns an empty list when
            the filter leaves the folder with nothing. Counting those zeros is
            what turns that failure into the finding "PARA retrieves nothing in
            N% of cases".
        finish_reason: whatever the server returned.
        flagged: `True` if `finish_reason != "stop"` (D17). These rows are
            reported separately and do not enter the average unmarked: a
            truncated answer looks reasonable until you read it in full, and it
            contaminates the number silently.
    """

    question_id: str
    strategy: Strategy
    text: str
    confidence: float
    n_chunks: int
    finish_reason: str
    flagged: bool


def load_questions(path: Path) -> list[Question]:
    """Read a JSONL file of questions (D19, contract C6).

    JSONL is one JSON object **per line**, with no brackets wrapping the file. It
    is preferred over a single array because adding a question means writing one
    line at the end, and one corrupt line costs that question instead of the
    whole file.

    The files carry editorial fields that are not in the contract (`note`,
    `pii`). They are ignored: the format can grow, and blowing up over an extra
    field would make something fragile that has no reason to be.

    Args:
        path: path to the `.jsonl`. Blank lines are skipped.

    Returns:
        The questions in the same order as the file. The order matters: it is
        what makes two runs produce the rows in the same sequence.

    Raises:
        ValueError: if an `id` is repeated. Two questions with the same `id` make
            the report join the wrong rows when crossing with the `Record`s, and
            the error would show up as odd numbers, not as an exception.
        KeyError: if a line is missing a required contract field.
    """

    questions = []
    ids = set()

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        dict_line = json.loads(line)
        q_id = dict_line["id"]
        if q_id in ids:
            raise ValueError(f"duplicate id: {q_id}")
        question = Question(
                    id = q_id,
                    q = dict_line["q"],
                    expected = dict_line["expected"],
                    category = dict_line["category"],
                    evidence = dict_line["evidence"],
                    answerable = dict_line["answerable"],
                    hops = dict_line["hops"],
                    source = dict_line.get("source"),
                    hard_case = dict_line.get("hard_case", False))
        questions.append(question)
        ids.add(dict_line["id"])

    return questions


def run(
    questions: list[Question],
    retrieve: RetrieveFn,
    answer: AnswerFn,
    k: int = 5,
) -> list[Record]:
    """Run every question through both arms.

    For each question, and for each arm in `STRATEGIES`: retrieve with that arm,
    answer with those chunks, and write down a row.

    Args:
        questions: the set, in the order it is going to be run.
        retrieve: the retrieval function (C2). It is received, not imported -- so
            the tests can pass a toy one and the real `retrieve` drops in without
            touching this.
        answer: the agent function (C3). It handles its own cache (D16), so this
            module knows nothing about hashes: if a run is interrupted, what was
            already answered is not paid for again.
        k: how many chunks to ask for. **The same value goes to both arms**
            (D11). Choosing a different `k` per strategy stops comparing the
            filter and starts comparing two configurations.

    Returns:
        One row per question per arm, that is `len(questions) * 2`, in
        deterministic order: questions in the order received, arms in the order
        of `STRATEGIES`.

        Questions with `answerable=False` are run too. What changes is not the
        run but the evaluation: for those the criterion is "did it abstain?" and
        not "did it say this text?" (D21). That is `report.py`'s job, not this
        module's.

    OPEN DESIGN QUESTION -- what to do if `answer` raises.
        Today the exception propagates and the run stops. That is the simplest
        thing and it makes the problem impossible to ignore, and the cache makes
        repeating cheap. But over ~130 real calls, one malformed response (for
        example without `</think>`, which triggers `ThinkTagNotFoundError`) would
        bring the whole run down. The alternative, more in line with D8 and D17,
        is to catch it and record the row as `flagged`: a counted failure is a
        result; a failure that stops everything is an obstacle. To be decided
        before the first big run.
    """

    records = []

    for question in questions:
        for strategy in STRATEGIES:
            chunks = retrieve(question.q, strategy, k)
            ans = answer(question.q, chunks)
            record = Record(
                question_id = question.id,
                strategy = strategy,
                text = ans.text,
                confidence = ans.confidence,
                n_chunks = len(chunks),
                finish_reason = ans.finish_reason,
                flagged = ans.finish_reason != "stop"
            )
            records.append(record)

    return records
