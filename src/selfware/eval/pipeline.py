"""One call from a question set to the finished Markdown report.

This module composes, in order, everything `eval/` already has:

    harness.run -> score -> operational_table / summarize x5 / abstention_table
                -> render_markdown

It is the piece behind the plan's "reproducible with one command" (Person 3's
definition of done). The command itself is `scripts/run_eval.py`, which only
reads arguments, picks the pieces (fake today, real from integration step 11)
and writes the file.

Same pattern as the harness and the report: `retrieve`, `answer` and `score`
are **received**, never imported. This module does not know whether it is
running against `retrieve_fake` or Person 2's Chroma, against Ultra or a toy
agent, against RAGAS or made-up scores -- the caller decides. That is how it is
tested with no network and no budget, and why it does not break architecture
rule 1: the wiring of `agent/` with `context/` happens in `scripts/`, which is
not a module of the monolith (option 3 of integration item C1).

It reads no files and writes none: it returns the report as a string.
"""

from collections.abc import Callable

from selfware.core.schemas import Question
from selfware.eval.harness import AnswerFn, Record, RetrieveFn
from selfware.eval.harness import run as run_harness
from selfware.eval.report import (
    GROUPINGS,
    Scores,
    abstention_table,
    operational_table,
    render_markdown,
    summarize,
)

#: Signature of what scores the rows: RAGAS from integration step 7, made-up
#: values today. It receives the questions too because a real metric needs the
#: reference answer (`expected`), which lives in `Question`, not in `Record`.
#:
#: KNOWN GAP for step 7: RAGAS also needs the **text of the retrieved chunks**
#: of each row (its "contexts"), and `Record` keeps only how many there were
#: (`n_chunks`). Fake scores do not need them; the real scorer will.
ScoreFn = Callable[[list[Question], list[Record]], Scores]


def evaluate(
    questions: list[Question],
    retrieve: RetrieveFn,
    answer: AnswerFn,
    score: ScoreFn,
    *,
    run: str,
    metric: str,
    threshold: float,
    k: int = 5,
    n_resamples: int = 10_000,
    seed: int = 0,
    warning: str | None = None,
) -> str:
    """Run the whole evaluation and return the report as Markdown.

    In this order:

    1. `harness.run(questions, retrieve, answer, k=k)` -> the rows.
    2. `score(questions, records)` -> one metric per row.
    3. `operational_table(questions, records)`.
    4. `summarize(...)` once per cut in `GROUPINGS`, **in `GROUPINGS` order**
       (`all`, `category`, `hard_case`, `source`, `hops`), with the same
       `n_resamples` and `seed` for every cut: the whole report reproducible.
    5. `abstention_table(questions, records, threshold)`.
    6. `render_markdown(...)` with all of the above.

    Everything after `score` is keyword-only, like `render_markdown`: three
    strings and four numbers are too easy to pass in the wrong order.

    Args:
        questions: answerable and unanswerable together. Each table picks the
            ones it needs (D21): the per-group tables only the answerable,
            the abstention table both.
        retrieve: contract C2, returning a `Retrieved`.
        answer: contract C3.
        score: see `ScoreFn`.
        run: label of the run, shown in the header.
        metric: name of the metric `score` produces, shown in the headings.
        threshold: for the abstention table (D13). No default, on purpose.
        k: chunks per query, the same in both arms (D11).
        n_resamples: bootstrap resamples (D18).
        seed: bootstrap seed.
        warning: passed to `render_markdown`. The CLI sets it automatically
            for fake runs.

    Returns:
        The report, exactly as `render_markdown` returns it.
    """
    records = run_harness(questions=questions, retrieve=retrieve, answer=answer, k=k)
    scores = score(questions, records)
    operational_rows = operational_table(questions=questions, records=records)

    cuts = {
        group: summarize(
            questions=questions,
            records=records,
            scores=scores,
            by=group,
            n_resamples=n_resamples,
            seed=seed,
        )
        for group in GROUPINGS
    }

    abstention_rows = abstention_table(
        questions=questions, records=records, threshold=threshold
    )

    render_markdown_text = render_markdown(
        run=run,
        metric=metric,
        k=k,
        n_resamples=n_resamples,
        seed=seed,
        ops=operational_rows,
        tables=cuts,
        abstention=abstention_rows,
        warning=warning,
    )

    return render_markdown_text
