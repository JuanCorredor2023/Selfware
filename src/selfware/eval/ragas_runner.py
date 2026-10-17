"""Score the harness rows with RAGAS: context precision or context recall (H1).

This module decides **what** gets judged and turns the judge's numbers into the
`Scores` the report reads. It does **not** call RAGAS itself: the judge is
**received**, like `retrieve` and `answer` everywhere else in `eval/`.

Why, and it is not only for testing. Calling RAGAS for real is blocked twice,
and neither block is in this lane:

- **D2:** `ragas` is not in `pyproject.toml`, so it cannot even be imported.
  This module never imports it, so the suite stays green without it.
- **B4:** RAGAS builds its own LangChain clients pointed at the Token Factory
  URL, which breaks architecture rule 2 (one exit point, `core/llm.py`) until
  the team picks one of B4's options.

The day both land, the real judge -- a function that builds the RAGAS samples,
calls `ragas.evaluate` and returns one float per input -- is written next to
this and passed in. Nothing here changes.

Each call to the judge spends credits, so the rule of this module is: **never
send the judge a row whose score is already known or will not be used.**
"""

from collections.abc import Callable
from dataclasses import dataclass

from selfware.core.schemas import Question
from selfware.eval.harness import Record, Strategy
from selfware.eval.pipeline import ScoreFn
from selfware.eval.report import Scores, is_truncated

#: The two metrics behind H1, mapped to the RAGAS class that computes each one,
#: as verified against Token Factory on 20 Sep (D31). Class *names*, as strings:
#: `ragas` is not imported here. `faithfulness` is not part of H1.
METRICS: dict[str, str] = {
    "context_precision": "LLMContextPrecisionWithReference",
    "context_recall": "LLMContextRecall",
}


@dataclass(frozen=True)
class JudgeInput:
    """One row as RAGAS sees it: the four fields of a `SingleTurnSample`.

    Field names are RAGAS's own on purpose, so building the real sample is a
    1:1 copy. As D31 learned the hard way: in these libraries no field is
    decorative -- what is passed is measured -- so nothing extra goes in.

    Attributes:
        question_id: which question, to key the score. Not sent to RAGAS.
        strategy: which arm, to key the score. Not sent to RAGAS.
        user_input: `Question.q`, the question as asked.
        retrieved_contexts: `Record.contexts`, in retrieval order (precision is
            rank-aware).
        reference: `Question.expected`, the verified answer.
        response: `Record.text`, what the system answered.
    """

    question_id: str
    strategy: Strategy
    user_input: str
    retrieved_contexts: tuple[str, ...]
    reference: str
    response: str


#: What the real judge will be: all the inputs of a run in, one score per input
#: out, **same order**. One call per metric, not one per row: RAGAS `evaluate`
#: takes a whole dataset, and batching is cheaper than 136 round trips.
JudgeFn = Callable[[list[JudgeInput]], list[float]]


def to_judge_inputs(
    questions: list[Question], records: list[Record]
) -> tuple[list[JudgeInput], Scores]:
    """Decide, row by row, what goes to the judge and what is already known.

    The table of step 7, decision 3:

    | Row                                  | What happens                       |
    |--------------------------------------|------------------------------------|
    | Its question is not in `questions`   | Ignored                            |
    | Unanswerable (`answerable=False`)    | Ignored: no `reference`, and out   |
    |                                      | of precision/recall (D21)          |
    | Truncated (`is_truncated`)           | Ignored: `paired_differences`      |
    |                                      | excludes it anyway                 |
    | No chunks (`n_chunks == 0`)          | **0.0, without calling the judge** |
    | Anything else                        | A `JudgeInput`                     |

    "Ignored" means the row gets **no score at all**, not a 0: a 0 would enter
    the difference as if the arm had failed. Truncated rows are excluded by
    `paired_differences` without needing a score (2a), and unanswerable ones
    never reach `summarize`.

    The no-chunks 0.0 is not a shortcut: context precision and recall over an
    empty context are 0 by definition, and that 0 is what makes a PARA arm that
    retrieved nothing count against it (2a, decision 1). Paying the judge to
    say so would be paying to learn nothing.

    Args:
        questions: the full set; tells which rows are answerable and gives
            `q` and `expected`.
        records: the harness output.

    Returns:
        `(inputs, known)`: the `JudgeInput`s **in the order of `records`**, and
        the scores already decided (the no-chunks zeros), keyed like `Scores`.
    """
    questions_by_id = {q.id: q for q in questions if q.answerable}
    known = {}
    inputs = []
    for r in records:
        if r.question_id not in questions_by_id or is_truncated(r):
            continue
        if r.n_chunks == 0:
            known[(r.question_id, r.strategy)] = 0.0
            continue

        inputs.append(
            JudgeInput(
                question_id=r.question_id,
                strategy=r.strategy,
                user_input=questions_by_id[r.question_id].q,
                retrieved_contexts=r.contexts,
                reference=questions_by_id[r.question_id].expected,
                response=r.text,
            )
        )

    return inputs, known


def make_ragas_scorer(metric: str, judge: JudgeFn) -> ScoreFn:
    """Return the `ScoreFn` `evaluate` expects, backed by `judge`.

    The returned function: `to_judge_inputs` -> **one** call to `judge` with
    every input (or none at all, if there is nothing to judge) -> checks what
    came back -> merges it with the already-known zeros.

    It refuses a judge answer it cannot trust, loudly, rather than let a bad
    number into the report:

    - a different number of scores than inputs: the pairing by position would
      put every score on the wrong row;
    - a score that is NaN or outside [0, 1]. RAGAS returns NaN when it cannot
      parse the judge model's output; a NaN that reached `fmean` would print
      `nan` across a whole table. Retrying those rows is a decision for the
      real judge (integration step 11), not something to paper over here.

    Args:
        metric: a key of `METRICS`. It is checked here, when the scorer is
            built, so a typo fails before any credit is spent.
        judge: see `JudgeFn`.

    Raises:
        ValueError: here, for an unknown `metric`; when scoring, for a judge
            answer as described above.
    """
    if metric not in METRICS:
        raise ValueError(f"unknown metric {metric!r}; expected one of {list(METRICS)}")

    def score(questions: list[Question], records: list[Record]) -> Scores:
        inputs, known = to_judge_inputs(questions, records)
        if not inputs:
            return known

        values = judge(inputs)
        if len(values) != len(inputs):
            raise ValueError(
                f"the judge returned {len(values)} scores for {len(inputs)} inputs"
            )

        bad = [
            (i.question_id, i.strategy, v)
            for i, v in zip(inputs, values, strict=True)
            if not 0.0 <= v <= 1.0  # also False for NaN
        ]
        if bad:
            raise ValueError(f"the judge returned scores outside [0, 1]: {bad}")

        judged = {
            (i.question_id, i.strategy): v for i, v in zip(inputs, values, strict=True)
        }
        return known | judged

    return score
