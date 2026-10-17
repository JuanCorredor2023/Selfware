"""Turn the harness rows into the project's number: PARA minus flat, with a CI.

`harness.run()` produces one `Record` per question per arm. This module pairs
the two arms of each question, takes the difference of a metric, and puts a
95% confidence interval around the mean difference by paired bootstrap (D18).

This module does NOT compute metrics: it **receives** them as `Scores`. Today
the tests pass made-up values; the day `ragas_runner.py` exists it passes
context precision or recall, one metric at a time, and nothing here changes.
Same trick as the harness receiving `retrieve` and `answer`.

Sign convention, used everywhere in this module: **difference = PARA - flat**.
Positive means PARA scored higher.

Standard library only (`random`, `statistics`). `numpy` happens to be installed
because `chromadb` pulls it in, but leaning on a borrowed dependency is fragile:
the day `context/` drops it, the report would break for no reason of its own.
"""

import random
import statistics
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass

from selfware.core.schemas import Question
from selfware.eval.harness import STRATEGIES, Record, Strategy

#: Value of ONE metric per row: `(question_id, strategy) -> score`. For context
#: precision / recall the score is in [0,1], but nothing here assumes a range.
Scores = dict[tuple[str, Strategy], float]


@dataclass(frozen=True)
class PairedDiffs:
    """The per-question differences of one metric, ready for `bootstrap_ci`.

    Attributes:
        question_ids: the questions that made it into `diffs`, in the order
            received. `question_ids[i]` is the question behind `diffs[i]`.
        diffs: `score(para) - score(flat)` for each of those questions.
        excluded: questions left out because an arm was **truncated** (D17).
            Reported next to the number, never dropped silently: if this list
            is long, the right move is raising `max_tokens` and re-running,
            not trusting the mean of what survived.
    """

    question_ids: list[str]
    diffs: list[float]
    excluded: list[str]


@dataclass(frozen=True)
class BootstrapCI:
    """A mean difference with its confidence interval.

    Attributes:
        mean: the plain mean of the observed differences -- NOT the mean of the
            bootstrap means. The bootstrap only gives the interval.
        low: lower bound of the interval.
        high: upper bound of the interval.
        n: how many differences went in. An interval over 4 questions and one
            over 60 can look alike; `n` is what tells them apart.
    """

    mean: float
    low: float
    high: float
    n: int


def is_truncated(record: Record) -> bool:
    """Whether a row was cut short by the server, as opposed to having no chunks.

    Both cases are `flagged` (`finish_reason != "stop"`), and they mean opposite
    things for the report:

    - **Truncated** (e.g. `"length"`): the answer was cut mid-way. It looks
      reasonable until read in full, so it stays out of the mean (D17).
    - **No chunks** (D8): the PARA filter left the folder empty and the model
      was not even called. That is **PARA failing**, and it is precisely the
      kind of failure the experiment exists to count. Excluding it would hide
      PARA's worst case and make it look better than it is.

    They are told apart by `n_chunks`, as `agent/answer.py` documents for
    `NO_CHUNKS`: zero chunks is missing retrieval, not truncation. This avoids
    importing `NO_CHUNKS` from `agent/` (architecture rule 1).
    """
    return record.flagged and record.n_chunks > 0


def paired_differences(
    records: list[Record],
    scores: Scores,
    question_ids: Iterable[str],
) -> PairedDiffs:
    """Pair the two arms of each question and subtract: PARA - flat.

    Args:
        records: the harness output. May contain more questions than
            `question_ids`; only those asked for are used. That is how the
            per-category table works: same records, a different list of ids.
        scores: the metric value per row. Rows of an **excluded** question do
            not need a score (RAGAS might not even be run on a truncated
            answer). Every other row does.
        question_ids: which questions to pair, in the order the result should
            follow.

    Returns:
        A `PairedDiffs`. A question goes to `excluded` if **either** of its two
        arms `is_truncated`. The whole pair goes, not just the bad row: the
        design is paired, and without one side there is no difference to take.

    Raises:
        ValueError: if a question in `question_ids` is missing the record of one
            of its arms, or a non-excluded row has no score. Both mean the
            inputs do not match each other, and computing on anyway would give
            a wrong number with no error -- the worst kind.
    """

    search = {}
    valid = []
    diffs = []
    excluded = []
    for record in records:
        search[(record.question_id, record.strategy)] = record

    for qid in question_ids:
        if (qid, "para") not in search or (qid, "flat") not in search:
            raise ValueError("One of the strategies wasn't responded")
        if is_truncated(search[(qid, "para")]) or is_truncated(search[(qid, "flat")]):
            excluded.append(qid)
            continue
        if (qid, "para") not in scores or (qid, "flat") not in scores:
            raise ValueError("One of the strategies doesn't have a score")
        diff = scores[(qid, "para")] - scores[(qid, "flat")]
        valid.append(qid)
        diffs.append(diff)

    return PairedDiffs(
        question_ids=valid,
        diffs=diffs,
        excluded=excluded,
    )


def bootstrap_ci(
    diffs: list[float],
    n_resamples: int = 10_000,
    seed: int = 0,
    level: float = 0.95,
) -> BootstrapCI:
    """Confidence interval for the mean difference, by bootstrap (D18).

    The procedure, which is the whole idea:

    1. Draw `len(diffs)` values from `diffs` **at random, with replacement**:
       some repeat, some do not appear. That is one "resample".
    2. Take the mean of that resample.
    3. Repeat `n_resamples` times. You now have `n_resamples` means that
       "could have come out" with a different draw of questions.
    4. Sort them. The interval goes from the `(1 - level) / 2` quantile to the
       `1 - (1 - level) / 2` quantile -- for 95%, from 2.5% to 97.5%.

    Quantile, defined here so there is no ambiguity: on the sorted list of
    means, the `q` quantile is the element at index
    `round(q * (n_resamples - 1))`.

    It is **paired** because what gets resampled are per-question differences,
    not loose scores: each question's own difficulty cancels in the subtraction.

    Reproducibility: the random draws come from `random.Random(seed)`, a
    generator of our own, **never** from the global `random` module. Two runs
    with the same seed give the same interval, and calling this function does
    not disturb anybody else's random numbers.

    Args:
        diffs: per-question differences, from `paired_differences`.
        n_resamples: 10,000 by D18.
        seed: fixed, so the report is reproducible.
        level: confidence level, in (0, 1).

    Returns:
        A `BootstrapCI`. If the interval crosses 0, the data does not let you
        claim PARA helps (or hurts) in that group.

    Raises:
        ValueError: if `diffs` is empty. There is no interval around nothing,
            and a category with no usable pairs has to show up as such in the
            report, not as a 0.0.
    """

    if not diffs:
        raise ValueError(
            "the differences are empty so there is no information to check"
        )

    means = []
    rng = random.Random(seed)

    for _ in range(n_resamples):
        samples = rng.choices(diffs, k=len(diffs))
        mean = statistics.fmean(samples)
        means.append(mean)

    means.sort()
    low_idx = round((1 - level) / 2 * (n_resamples - 1))
    high_idx = round((1 - (1 - level) / 2) * (n_resamples - 1))

    return BootstrapCI(
        mean=statistics.fmean(diffs),
        low=means[low_idx],
        high=means[high_idx],
        n=len(diffs),
    )


# --------------------------------------------------------------------------
# Sub-step 2b: one table row per group
# --------------------------------------------------------------------------

#: How to read the group out of a question, per report cut (section 3 of the
#: protocol: category, `hard_case`, `source`, `hops`). `"all"` puts every
#: question in one group: that is the global row.
#:
#: `hops` stands in for `docs_needed` (D36) until that field is in `Question`:
#: the `hops: 2` bucket still mixes reachable and impossible-with-k questions.
GROUPINGS: dict[str, Callable[[Question], Hashable]] = {
    "all": lambda q: "all",
    "category": lambda q: q.category,  # D20.5
    "hard_case": lambda q: q.hard_case,  # D28
    "source": lambda q: q.source,  # D27
    "hops": lambda q: q.hops,  # D22, D35
}


@dataclass(frozen=True)
class GroupRow:
    """One row of a per-group table.

    Attributes:
        group: the value of the group -- `"area"`, `True`, `2`, `None`...
        n_questions: answerable questions in the group, **excluded ones
            included**. Next to `ci.n` it tells how many were lost to D17.
        excluded: ids left out because an arm was truncated (D17).
        flat_mean: mean flat score over the pairs that made it in, or `None`
            if none did.
        para_mean: same, for PARA. Computed over the **same pairs** as the
            difference, so `para_mean - flat_mean == ci.mean` and the table
            adds up when someone subtracts the columns by hand.
        ci: the paired bootstrap interval of PARA - flat, or `None` when the
            group has no usable pair. The row is still there: a group that
            vanished from the table would hide that it ran out of data.
        n_para_fell_back: of the pairs behind `ci` (the same `ci.n`
            questions), how many had the PARA arm fall back to flat (F4).
            Counted over the same pairs as the difference, like the means. A
            difference near 0 with most of its pairs fallen back does not say
            "PARA does not help": it says "PARA barely ran" -- a finding about
            the classifier, not about H1. 0 when the group has no usable pair.
    """

    group: Hashable
    n_questions: int
    excluded: list[str]
    flat_mean: float | None
    para_mean: float | None
    ci: BootstrapCI | None
    n_para_fell_back: int


def _group_ids(
    questions: Iterable[Question], key: Callable[[Question], Hashable]
) -> list[tuple[Hashable, list[str]]]:
    """Group question ids by `key`, groups sorted by value with `None` last.

    Inside each group the ids keep the order of `questions`, so the report is
    reproducible run after run.

    The trap this avoids. A plain `sorted()` over the group values blows up
    with `TypeError` the moment one of them is `None` (`source` can be): Python
    refuses to compare `None < "human"`. Sorting by the pair
    `(value is None, value)` instead puts every non-`None` first (`False <
    True`), and since the values are unique there is at most one `None` group,
    so `None` never actually gets compared with anything.

    Returns:
        A list of `(group value, [question ids])`.
    """
    groups: dict[Hashable, list[str]] = {}
    for q in questions:
        groups.setdefault(key(q), []).append(q.id)

    return sorted(groups.items(), key=lambda item: (item[0] is None, item[0]))


def summarize(
    questions: list[Question],
    records: list[Record],
    scores: Scores,
    by: str = "category",
    n_resamples: int = 10_000,
    seed: int = 0,
) -> list[GroupRow]:
    """One `GroupRow` per group: PARA - flat with its interval, per group.

    Args:
        questions: the full set. Only **answerable** ones are used: the
            unanswerable ones measure whether the system knows to stay quiet,
            not retrieval (D21), and go to the abstention table instead.
        records: the harness output.
        scores: ONE metric per row (see `Scores`).
        by: which cut, a key of `GROUPINGS`.
        n_resamples: passed on to `bootstrap_ci`.
        seed: passed on to `bootstrap_ci`. The same seed for every group, so
            the whole table is reproducible.

    Returns:
        The rows, in the order `_group_ids` gives.

    Raises:
        ValueError: if `by` is not in `GROUPINGS`, or if `paired_differences`
            finds records or scores that do not match the questions.
    """
    if by not in GROUPINGS:
        raise ValueError(f"unknown grouping {by!r}; expected one of {list(GROUPINGS)}")

    answerable_questions = []
    rows = []

    for q in questions:
        if q.answerable:
            answerable_questions.append(q)

    groups = _group_ids(answerable_questions, GROUPINGS[by])

    for group, ids in groups:
        paired = paired_differences(records=records, scores=scores, question_ids=ids)
        if not paired.diffs:
            rows.append(
                GroupRow(
                    group=group,
                    n_questions=len(ids),
                    excluded=paired.excluded,
                    flat_mean=None,
                    para_mean=None,
                    ci=None,
                    n_para_fell_back=0,
                )
            )
            continue
        ci = bootstrap_ci(diffs=paired.diffs, n_resamples=n_resamples, seed=seed)
        flat_scores = []
        para_scores = []

        paired_ids = set()

        for qid in paired.question_ids:
            para_scores.append(scores[(qid, "para")])
            flat_scores.append(scores[(qid, "flat")])
            paired_ids.add(qid)

        n_para_fell_back = 0

        for r in records:
            if (
                r.question_id in paired_ids
                and r.strategy == "para"
                and r.fell_back_to_flat
            ):
                n_para_fell_back += 1

        rows.append(
            GroupRow(
                group=group,
                n_questions=len(ids),
                excluded=paired.excluded,
                flat_mean=statistics.fmean(flat_scores),
                para_mean=statistics.fmean(para_scores),
                ci=ci,
                n_para_fell_back=n_para_fell_back,
            )
        )

    return rows


# --------------------------------------------------------------------------
# Sub-step 2c: operational and abstention tables
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class OpsRow:
    """How one arm behaved mechanically, before looking at any metric.

    If this table looks wrong, the RAGAS table is not worth reading yet.

    Attributes:
        strategy: `"flat"` or `"para"`.
        n_rows: rows of this arm over the answerable questions.
        n_truncated: rows cut short by the server (`is_truncated`, D17).
        n_no_chunks: rows where retrieval returned nothing (D8). With the real
            `retrieve()` this stays near 0 for PARA, because an empty filter
            falls back to flat; the PARA failure shows up as the fallback rate
            instead (integration step 3, F4). It still catches an empty index.
        mean_confidence: mean `confidence` over the rows where the model really
            answered -- neither truncated nor without chunks -- or `None` if
            there is none. No-chunks rows are 0.0 by construction, not because
            the model doubted, so averaging them in would mix two things.
        n_fell_back: rows where the PARA arm fell back to flat (F4). Always 0
            for flat. Independent of the other counts: a fallen-back row still
            has chunks and an answer, so it is also counted in the confidence.
    """

    strategy: Strategy
    n_rows: int
    n_truncated: int
    n_no_chunks: int
    mean_confidence: float | None
    n_fell_back: int


def operational_table(questions: list[Question], records: list[Record]) -> list[OpsRow]:
    """One `OpsRow` per arm, in the order of `STRATEGIES`.

    Only rows of **answerable** questions are counted, so this table describes
    the same rows as the RAGAS table. With the unanswerable ones in, correct
    abstentions would drag `mean_confidence` down and read as a problem.

    Args:
        questions: the full set; used to know which ids are answerable.
        records: the harness output. Rows of ids not in `questions` are ignored.

    Returns:
        `[OpsRow for "flat", OpsRow for "para"]`.
    """
    answerable_ids = set()

    for q in questions:
        if q.answerable:
            answerable_ids.add(q.id)

    ops_rows = []

    for strategy in STRATEGIES:
        rows = [
            r
            for r in records
            if r.strategy == strategy and r.question_id in answerable_ids
        ]

        rows_confidence = []
        n_truncated = 0
        n_no_chunks = 0

        n_fell_back = 0

        for r in rows:
            if r.fell_back_to_flat:
                n_fell_back += 1
            if not is_truncated(r) and r.n_chunks > 0:
                rows_confidence.append(r.confidence)
            elif is_truncated(r):
                n_truncated += 1
            else:
                n_no_chunks += 1

        mean = None
        if rows_confidence:
            mean = statistics.fmean(rows_confidence)

        ops_rows.append(
            OpsRow(
                strategy=strategy,
                n_rows=len(rows),
                n_truncated=n_truncated,
                n_no_chunks=n_no_chunks,
                mean_confidence=mean,
                n_fell_back=n_fell_back,
            )
        )

    return ops_rows


@dataclass(frozen=True)
class AbstentionRow:
    """Whether one arm knows when to stay quiet, at one threshold (D13, D21).

    The two pairs of counts pull in opposite directions, like precision and
    recall: a system that always abstains scores 10/10 on the first and is
    useless. The second pair is the price of abstaining.

    Counts, not just rates: with 10 unanswerable questions each one moves the
    rate by 10 points, and "70%" alone sounds more solid than "7/10".

    Attributes:
        strategy: `"flat"` or `"para"`.
        threshold: the threshold this row was computed at.
        abstained_unanswerable: unanswerable questions where it abstained.
            Higher is better.
        n_unanswerable: unanswerable rows counted (truncated ones excluded).
        abstained_answerable: answerable questions where it abstained anyway.
            Lower is better: each one is an answer the user did not get.
        n_answerable: answerable rows counted (truncated ones excluded).
    """

    strategy: Strategy
    threshold: float
    abstained_unanswerable: int
    n_unanswerable: int
    abstained_answerable: int
    n_answerable: int


def abstention_table(
    questions: list[Question], records: list[Record], threshold: float
) -> list[AbstentionRow]:
    """One `AbstentionRow` per arm, in the order of `STRATEGIES`.

    A row abstains when `confidence < threshold` (D13: the decision is a
    comparison in Python, not the model choosing). Strictly less: a row exactly
    at the threshold answers. The sentinel (R18) and no-chunks rows have
    confidence 0.0, so they abstain at any threshold above 0.

    **Truncated rows are not counted** on either side: their confidence comes
    from an answer cut mid-way, so whether it "stayed quiet" is undecidable
    (D17). They drop out of the `n`s.

    Calibrating the threshold (week 4) is calling this at 0.1, 0.2, 0.3... and
    choosing where the two columns balance. That is why `threshold` has **no
    default**: any number today would be made up, and making the caller write
    it keeps that choice visible.

    Args:
        questions: the full set; tells which ids are answerable and which are
            not. Only `answerable is False` makes a row unanswerable: "not
            answerable" is NOT the same as "not in the answerable set".
        records: the harness output. Rows of ids not in `questions` are
            ignored -- D21 keeps the unanswerable questions in their own file,
            so a caller may well pass only that file with a full run's records.
        threshold: in [0, 1], the same range as `confidence`.

    Raises:
        ValueError: if `threshold` is outside [0, 1]. Above 1 everything
            abstains and below 0 nothing does: both are typos, not choices.
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"threshold must be in [0, 1], got {threshold}")

    answerable_ids = set()
    unanswerable_ids = set()

    for q in questions:
        if q.answerable:
            answerable_ids.add(q.id)
        else:
            unanswerable_ids.add(q.id)

    abs_rows = []

    for strategy in STRATEGIES:
        rows_answerable = []
        rows_unanswerable = []

        for r in records:
            if r.strategy == strategy:
                if is_truncated(r):
                    continue
                if r.question_id in answerable_ids:
                    rows_answerable.append(r)
                elif r.question_id in unanswerable_ids:
                    rows_unanswerable.append(r)

        abstained_unanswerable = 0
        abstained_answerable = 0

        for r in rows_answerable:
            if r.confidence < threshold:
                abstained_answerable += 1

        for r in rows_unanswerable:
            if r.confidence < threshold:
                abstained_unanswerable += 1

        abs_rows.append(
            AbstentionRow(
                strategy=strategy,
                threshold=threshold,
                abstained_unanswerable=abstained_unanswerable,
                n_unanswerable=len(rows_unanswerable),
                abstained_answerable=abstained_answerable,
                n_answerable=len(rows_answerable),
            )
        )

    return abs_rows


# --------------------------------------------------------------------------
# Sub-step 2d: render the tables as Markdown
# --------------------------------------------------------------------------

#: What the numeric cells show when there is no number. Never "0.00": a group
#: without data and a group with no effect must not look alike (2b, decision 2).
MISSING = "—"


def _fmt_score(value: float | None) -> str:
    """A score or a mean, two decimals: `0.52`. `None` -> `MISSING`."""
    return MISSING if value is None else f"{value:.2f}"


def _fmt_signed(value: float) -> str:
    """A difference, two decimals and always signed: `+0.09`, `-0.01`.

    Rounding first and adding `0.0` turns a tiny negative such as `-0.001`
    into `+0.00` instead of `-0.00`: Python keeps the sign of a negative zero,
    and "-0.00" would read as "PARA slightly worse" when it means "no
    difference at this precision".
    """
    return f"{round(value, 2) + 0.0:+.2f}"


def _fmt_count(k: int, n: int) -> str:
    """`7/10 (70%)`. The count goes first: with n=10, each question moves the
    rate by 10 points (2c, decision 4). `0/0 (—)` when nothing was counted."""
    rate = MISSING if n == 0 else f"{k / n:.0%}"
    return f"{k}/{n} ({rate})"


def _fmt_group(group: Hashable) -> str:
    """The group label. `None` (e.g. a question without `source`) -> `(none)`,
    so the cell is never empty and never says "None" like a Python leak."""
    return "(none)" if group is None else str(group)


def _excludes_zero(ci: BootstrapCI) -> bool:
    """Whether the whole interval is on one side of 0. Strict: an interval that
    touches 0 does not let you claim an effect."""
    return ci.low > 0 or ci.high < 0


def _ops_section(ops: list[OpsRow]) -> list[str]:
    lines = [
        "## Operational, by arm (answerable questions)",
        "",
        "| arm | rows | truncated | no chunks | fell back | mean confidence |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in ops:
        lines.append(
            f"| {row.strategy} | {row.n_rows} | {row.n_truncated} "
            f"| {row.n_no_chunks} | {row.n_fell_back} "
            f"| {_fmt_score(row.mean_confidence)} |"
        )
    return lines


def _group_section(metric: str, cut: str, rows: list[GroupRow]) -> list[str]:
    title = "overall" if cut == "all" else f"by {cut}"
    lines = [
        f"## {metric} {title}",
        "",
        "| group | n | excl. | flat | PARA | PARA fell back | PARA − flat | 95% CI |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        if row.ci is None:
            diff, interval, fell_back = MISSING, "no usable pairs", MISSING
        else:
            fell_back = _fmt_count(row.n_para_fell_back, row.ci.n)
            diff = _fmt_signed(row.ci.mean)
            if _excludes_zero(row.ci):
                diff = f"**{diff}**"
            low, high = _fmt_signed(row.ci.low), _fmt_signed(row.ci.high)
            interval = f"[{low}, {high}]"
        lines.append(
            f"| {_fmt_group(row.group)} | {row.n_questions} | {len(row.excluded)} "
            f"| {_fmt_score(row.flat_mean)} | {_fmt_score(row.para_mean)} "
            f"| {fell_back} | {diff} | {interval} |"
        )
    return lines


def _abstention_section(rows: list[AbstentionRow]) -> list[str]:
    thresholds = {row.threshold for row in rows}
    if len(thresholds) != 1:
        raise ValueError(
            f"one abstention table per threshold; got {sorted(thresholds)}"
        )
    lines = [
        f"## Abstention (threshold {rows[0].threshold:.2f})",
        "",
        "| arm | unanswerable: abstained ↑ | answerable: abstained ↓ |",
        "|---|---:|---:|",
    ]
    for row in rows:
        unanswerable = _fmt_count(row.abstained_unanswerable, row.n_unanswerable)
        answerable = _fmt_count(row.abstained_answerable, row.n_answerable)
        lines.append(f"| {row.strategy} | {unanswerable} | {answerable} |")
    return lines


def render_markdown(
    *,
    run: str,
    metric: str,
    k: int,
    n_resamples: int,
    seed: int,
    ops: list[OpsRow],
    tables: dict[str, list[GroupRow]],
    abstention: list[AbstentionRow],
    warning: str | None = None,
) -> str:
    """The whole report as one Markdown string. Formatting only.

    It receives tables already computed by `operational_table`, `summarize`
    and `abstention_table`, and computes nothing, reads nothing and writes
    nothing. That keeps it trivially testable and makes the output a pure
    function of the inputs: same inputs, same bytes. That is also why there is
    no timestamp generated in here -- the caller puts whatever identifies the
    run in `run`.

    In English on purpose: the hackathon checklist (plan, section 8) requires
    everything in English, and this is what goes into the video and the README.

    Everything is keyword-only: nine arguments, several of them `int`, are too
    easy to pass in the wrong order.

    Args:
        run: a label for the run, e.g. `2026-10-07-fake`.
        metric: the name of the metric behind `tables`, e.g.
            `context_precision`. One report per metric.
        k: chunks per query, the same in both arms (D11).
        n_resamples: the bootstrap resamples used for every interval.
        seed: the bootstrap seed used for every interval.
        ops: from `operational_table`.
        tables: cut name -> rows, from `summarize(..., by=cut)`. Rendered in
            the dict's order, so the caller decides which cut goes first.
        abstention: from `abstention_table`, all at the same threshold. Empty
            -> the section is left out (e.g. no unanswerable set loaded).
        warning: shown first, as a quote, when the data cannot be read as a
            result -- today, any run against `retrieve_fake` or the fake
            embedder. A number without that warning can end up on a slide.

    Raises:
        ValueError: if `abstention` mixes thresholds.
    """
    lines = ["# Atlas — flat vs PARA", ""]

    if warning:
        lines += [f"> ⚠️ {warning}", ""]

    header = (
        f"Run: `{run}` · metric: {metric} · k={k} · "
        f"bootstrap {n_resamples:,} resamples, seed {seed}"
    )
    lines += [header, ""]

    lines += _ops_section(ops) + [""]

    for cut, rows in tables.items():
        lines += _group_section(metric, cut, rows) + [""]
    if tables:
        lines += ["**Bold**: the 95% CI excludes 0.", ""]

    if abstention:
        lines += _abstention_section(abstention) + [""]

    return "\n".join(lines).rstrip("\n") + "\n"
