"""Choose the abstention threshold against the report (week 4, D13).

`agent/abstain.py` abstains when `confidence < threshold`, and the threshold is
received, never defaulted: any number written today would be made up.
Calibrating is replacing that made-up number with one chosen by an explicit
criterion, on the evaluation's own rows:

1. `sweep`: the abstention table at many thresholds (0.00 to 1.00 by 0.05).
2. `choose_threshold`: the criterion of step 8, decision 2 -- the threshold
   that abstains most on unanswerable questions without going over a maximum
   cost on answerable ones; ties go to the lowest.
3. `render_sweep`: the table and the choice as Markdown, for the report.

It lives in `eval/` and not next to the rule in `agent/abstain.py` because it
needs `abstention_table`, and `agent/` cannot import `eval/` (rule 1). A test in
`tests/agent/test_abstain.py` keeps the two copies of the rule in agreement.

A real threshold needs real rows (integration step 12). Until then this runs on
fakes, which only proves the machinery: a threshold chosen on `answer_fake`'s
hashed confidences means nothing.
"""

from selfware.core.schemas import Question
from selfware.eval.harness import Record, Strategy
from selfware.eval.report import AbstentionRow, _fmt_count, abstention_table

#: The thresholds tried by default: 0.00, 0.05, ..., 1.00 (21 values). Rounded,
#: because `0.05 * 3` is `0.15000000000000002` in floating point, and that would
#: print badly and compare badly.
DEFAULT_THRESHOLDS: tuple[float, ...] = tuple(round(i * 0.05, 2) for i in range(21))

#: The abstention table at each threshold: threshold -> `[flat row, para row]`.
Sweep = dict[float, list[AbstentionRow]]


def sweep(
    questions: list[Question],
    records: list[Record],
    thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS,
) -> Sweep:
    """`abstention_table` at every threshold, in the order given.

    The `n`s are the same at every threshold -- which rows are counted depends
    on truncation, not on the threshold -- so the rows can be compared by their
    counts directly.

    Raises:
        ValueError: if `thresholds` is empty, or one of them is outside [0, 1]
            (from `abstention_table`).
    """
    if not thresholds:
        raise ValueError("at least one threshold is needed")
    return {t: abstention_table(questions, records, t) for t in thresholds}


def choose_threshold(swept: Sweep, arm: Strategy, max_cost: float) -> float | None:
    """The threshold that abstains most where it should, within a cost budget.

    For each threshold, take the row of `arm` and compute:

        benefit = abstained_unanswerable / n_unanswerable   (higher is better)
        cost    = abstained_answerable   / n_answerable     (lower is better)

    Among the thresholds whose `cost <= max_cost` (the budget is inclusive),
    return the one with the **highest benefit**; if several tie, the **lowest**
    threshold -- it silences the fewest good answers for the same benefit.

    Args:
        swept: from `sweep`.
        arm: `"para"` to calibrate what `/ask` uses by default (decision 3);
            `"flat"` is there to compare.
        max_cost: in [0, 1]: the fraction of answerable questions you accept
            to leave unanswered. **No default**: it is a product decision, not
            a technical one. 0.10 reads "I accept staying quiet on 1 in 10
            questions that did have an answer".

    Returns:
        The chosen threshold, or `None` when no threshold fits the budget. With
        0.0 in the sweep that cannot happen -- nothing is below 0, so its cost
        is 0 -- but a sweep without it can.

    Raises:
        ValueError: if `max_cost` is outside [0, 1], or the rows of `arm` have
            no answerable or no unanswerable questions: with either `n` at 0
            the criterion divides by zero and calibrating means nothing.
    """
    if not 0.0 <= max_cost <= 1.0:
        raise ValueError(f"max_cost must be in [0, 1], got {max_cost}")

    rows: dict[float, AbstentionRow] = {
        t: next(r for r in table if r.strategy == arm) for t, table in swept.items()
    }
    if any(r.n_answerable == 0 or r.n_unanswerable == 0 for r in rows.values()):
        raise ValueError(
            f"cannot calibrate {arm!r}: it needs answerable AND unanswerable rows"
        )

    sorted_rows = sorted(rows.items())

    best_benefit = 0.0
    best_threshold = None

    for threshold, row in sorted_rows:
        benefit = row.abstained_unanswerable / row.n_unanswerable
        cost = row.abstained_answerable / row.n_answerable
        if cost > max_cost:
            continue
        if best_threshold is None or best_benefit < benefit:
            best_benefit = benefit
            best_threshold = threshold

    return best_threshold


def render_sweep(
    swept: Sweep, *, arm: Strategy, max_cost: float, chosen: float | None
) -> str:
    """The sweep as a Markdown section, with the chosen threshold marked.

    One row per threshold, both arms side by side as `k/n (%)`, the chosen row
    in bold with an arrow. The criterion is printed above the table: a
    threshold shown without the rule that picked it cannot be checked.
    """
    lines = [
        "## Abstention threshold sweep",
        "",
        (
            f"Criterion: the most abstentions on unanswerable questions for "
            f"**{arm}**, with at most {max_cost:.0%} of answerable questions left "
            "unanswered; ties go to the lowest threshold."
        ),
        "",
    ]
    if chosen is None:
        lines += ["**No threshold fits the budget.**", ""]
    else:
        lines += [f"**Chosen threshold: {chosen:.2f}**", ""]

    lines += [
        (
            "| threshold | flat: unanswerable ↑ | flat: answerable ↓ "
            "| para: unanswerable ↑ | para: answerable ↓ |"
        ),
        "|---:|---:|---:|---:|---:|",
    ]
    for t, table in swept.items():
        by_arm = {r.strategy: r for r in table}
        cells = []
        for s in ("flat", "para"):
            r = by_arm[s]
            cells += [
                _fmt_count(r.abstained_unanswerable, r.n_unanswerable),
                _fmt_count(r.abstained_answerable, r.n_answerable),
            ]
        label = f"**{t:.2f} ←**" if t == chosen else f"{t:.2f}"
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    return "\n".join(lines) + "\n"
