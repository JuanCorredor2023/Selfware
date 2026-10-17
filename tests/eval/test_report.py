"""Tests for `report.py`. Pure arithmetic: no network, no files, no budget.

The scores here are made up on purpose, chosen so the right answer can be
worked out by hand.
"""

import random

import pytest

from selfware.core.schemas import Question
from selfware.eval.harness import Record
from selfware.eval.report import (
    GROUPINGS,
    AbstentionRow,
    BootstrapCI,
    GroupRow,
    OpsRow,
    PairedDiffs,
    Scores,
    _group_ids,
    abstention_table,
    bootstrap_ci,
    is_truncated,
    operational_table,
    paired_differences,
    render_markdown,
    summarize,
)

# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


def rec(
    qid: str,
    strategy: str,
    finish: str = "stop",
    n_chunks: int = 5,
    confidence: float = 0.5,
    fell_back: bool = False,
) -> Record:
    return Record(
        question_id=qid,
        strategy=strategy,
        text="an answer",
        confidence=confidence,
        n_chunks=n_chunks,
        finish_reason=finish,
        flagged=finish != "stop",
        fell_back_to_flat=fell_back,
    )


def pair(
    qid: str, flat_finish="stop", para_finish="stop", para_chunks=5, fell_back=False
):
    return [
        rec(qid, "flat", flat_finish),
        rec(qid, "para", para_finish, n_chunks=para_chunks, fell_back=fell_back),
    ]


# --------------------------------------------------------------------------
# is_truncated
# --------------------------------------------------------------------------


def test_a_normal_row_is_not_truncated():
    assert is_truncated(rec("q1", "flat")) is False


def test_length_is_truncated():
    assert is_truncated(rec("q1", "flat", finish="length")) is True


def test_no_chunks_is_not_truncated():
    """D8: PARA retrieving nothing is PARA failing, not the server cutting."""
    assert is_truncated(rec("q1", "para", finish="no_chunks", n_chunks=0)) is False


# --------------------------------------------------------------------------
# paired_differences
# --------------------------------------------------------------------------


def test_the_difference_is_para_minus_flat():
    records = pair("q1")
    scores = {("q1", "flat"): 0.25, ("q1", "para"): 0.75}

    out = paired_differences(records, scores, ["q1"])

    assert out.diffs == [pytest.approx(0.5)]


def test_it_returns_a_paired_diffs():
    out = paired_differences(pair("q1"), {("q1", "flat"): 0, ("q1", "para"): 0}, ["q1"])

    assert isinstance(out, PairedDiffs)


def test_it_keeps_the_order_of_question_ids():
    records = pair("q1") + pair("q2")
    scores = {
        ("q1", "flat"): 0.0,
        ("q1", "para"): 0.1,
        ("q2", "flat"): 0.0,
        ("q2", "para"): 0.2,
    }

    out = paired_differences(records, scores, ["q2", "q1"])

    assert out.question_ids == ["q2", "q1"]
    assert out.diffs == [pytest.approx(0.2), pytest.approx(0.1)]


def test_only_the_requested_questions_are_used():
    """The per-category table reuses the same records with a narrower id list."""
    records = pair("q1") + pair("q2")
    scores = {
        ("q1", "flat"): 0.0,
        ("q1", "para"): 0.1,
        ("q2", "flat"): 0.0,
        ("q2", "para"): 0.9,
    }

    out = paired_differences(records, scores, ["q1"])

    assert out.question_ids == ["q1"]


@pytest.mark.parametrize("arm", ["flat", "para"])
def test_a_truncated_arm_excludes_the_whole_pair(arm):
    """D17. Either side truncated -> no difference to take."""
    finishes = {"flat_finish": "stop", "para_finish": "stop"}
    finishes[f"{arm}_finish"] = "length"
    records = pair("q1", **finishes) + pair("q2")
    scores = {
        ("q1", "flat"): 0.0,
        ("q1", "para"): 1.0,
        ("q2", "flat"): 0.0,
        ("q2", "para"): 0.3,
    }

    out = paired_differences(records, scores, ["q1", "q2"])

    assert out.excluded == ["q1"]
    assert out.question_ids == ["q2"]
    assert out.diffs == [pytest.approx(0.3)]


def test_an_excluded_question_needs_no_score():
    """RAGAS may not even be run on a truncated answer."""
    records = pair("q1", para_finish="length")

    out = paired_differences(records, {}, ["q1"])

    assert out.excluded == ["q1"]
    assert out.diffs == []


def test_no_chunks_stays_in_the_calculation():
    """D8. This is the case that would make PARA look better if it were hidden:
    PARA retrieved nothing, scored 0, and that 0 must count."""
    records = pair("q1", para_finish="no_chunks", para_chunks=0)
    scores = {("q1", "flat"): 0.8, ("q1", "para"): 0.0}

    out = paired_differences(records, scores, ["q1"])

    assert out.excluded == []
    assert out.diffs == [pytest.approx(-0.8)]


def test_a_missing_arm_raises():
    records = [rec("q1", "flat")]
    scores = {("q1", "flat"): 0.5}

    with pytest.raises(ValueError):
        paired_differences(records, scores, ["q1"])


def test_a_missing_score_raises():
    """A row that ran but has no score means the inputs do not match."""
    scores = {("q1", "flat"): 0.5}

    with pytest.raises(ValueError):
        paired_differences(pair("q1"), scores, ["q1"])


def test_an_id_with_no_records_raises():
    with pytest.raises(ValueError):
        paired_differences(pair("q1"), {}, ["q-does-not-exist"])


# --------------------------------------------------------------------------
# bootstrap_ci
# --------------------------------------------------------------------------

#: Small, mixed differences: the kind of thing a real category produces.
MIXED = [0.3, -0.1, 0.2, 0.0, 0.4, -0.2, 0.1, 0.25, 0.05, -0.05]


def test_it_returns_a_bootstrap_ci():
    assert isinstance(bootstrap_ci(MIXED), BootstrapCI)


def test_the_mean_is_the_plain_mean_of_the_diffs():
    """Not the mean of the bootstrap means: the bootstrap only gives the interval."""
    ci = bootstrap_ci(MIXED)

    assert ci.mean == pytest.approx(sum(MIXED) / len(MIXED))


def test_n_is_the_number_of_diffs():
    assert bootstrap_ci(MIXED).n == len(MIXED)


def test_identical_diffs_collapse_the_interval():
    """Every resample of [0.2, 0.2, ...] has mean 0.2: there is no uncertainty."""
    ci = bootstrap_ci([0.2] * 8)

    assert (ci.mean, ci.low, ci.high) == pytest.approx((0.2, 0.2, 0.2))


def test_a_single_diff_collapses_the_interval():
    ci = bootstrap_ci([0.7])

    assert (ci.low, ci.high) == pytest.approx((0.7, 0.7))


def test_the_mean_lies_inside_the_interval():
    ci = bootstrap_ci(MIXED)

    assert ci.low <= ci.mean <= ci.high


def test_the_interval_has_width_when_the_diffs_vary():
    ci = bootstrap_ci(MIXED)

    assert ci.low < ci.high


def test_all_positive_diffs_give_an_interval_above_zero():
    """PARA better on every question -> the interval must not reach 0."""
    ci = bootstrap_ci([0.1, 0.2, 0.3, 0.15, 0.25, 0.1, 0.2, 0.3])

    assert ci.low > 0


def test_symmetric_diffs_give_an_interval_that_crosses_zero():
    """Half the questions +1, half -1: no effect, and the interval must say so."""
    ci = bootstrap_ci([1.0, -1.0] * 15)

    assert ci.low < 0 < ci.high


def test_the_same_seed_gives_the_same_interval():
    """Reproducibility: two runs of the report must print the same numbers."""
    assert bootstrap_ci(MIXED, seed=7) == bootstrap_ci(MIXED, seed=7)


def test_a_different_seed_gives_a_different_interval():
    """If this fails, the seed is not actually reaching the generator."""
    a = bootstrap_ci(MIXED, seed=1)
    b = bootstrap_ci(MIXED, seed=2)

    assert (a.low, a.high) != (b.low, b.high)


def test_it_does_not_touch_the_global_random_state():
    """It must use its own `random.Random(seed)`. Seeding the global module would
    silently change the random numbers of whoever else uses it."""
    random.seed(123)
    expected = random.random()

    random.seed(123)
    bootstrap_ci(MIXED)
    actual = random.random()

    assert actual == expected


def test_a_higher_level_gives_a_wider_interval():
    narrow = bootstrap_ci(MIXED, level=0.80)
    wide = bootstrap_ci(MIXED, level=0.99)

    assert (wide.high - wide.low) > (narrow.high - narrow.low)


def test_empty_diffs_raise():
    """A category with no usable pairs must show up as such, not as 0.0."""
    with pytest.raises(ValueError):
        bootstrap_ci([])


# --------------------------------------------------------------------------
# Sub-step 2b: _group_ids and summarize
# --------------------------------------------------------------------------


def question(
    qid: str,
    category: str | None = "areas",
    answerable: bool = True,
    hops: int | None = 1,
    source: str | None = "human",
    hard_case: bool = False,
) -> Question:
    return Question(
        id=qid,
        q="a question?",
        expected="an answer" if answerable else None,
        category=category if answerable else None,
        evidence="somewhere" if answerable else None,
        answerable=answerable,
        hops=hops if answerable else None,
        source=source,
        hard_case=hard_case,
    )


def scored(qid: str, flat: float, para: float) -> Scores:
    return {(qid, "flat"): flat, (qid, "para"): para}


def test_groupings_offers_the_protocol_cuts():
    """Section 3 of the protocol: category, hard_case, source, hops; plus global."""
    assert set(GROUPINGS) == {"all", "category", "hard_case", "source", "hops"}


def test_group_ids_groups_and_keeps_question_order():
    qs = [question("q1", "areas"), question("q2", "projects"), question("q3", "areas")]

    out = _group_ids(qs, GROUPINGS["category"])

    assert out == [("areas", ["q1", "q3"]), ("projects", ["q2"])]


def test_group_ids_sorts_groups_by_value():
    qs = [question("q1", hops=3), question("q2", hops=1), question("q3", hops=2)]

    out = _group_ids(qs, GROUPINGS["hops"])

    assert [group for group, _ in out] == [1, 2, 3]


def test_group_ids_puts_none_last_without_crashing():
    """A plain sorted() would raise TypeError comparing None with a string."""
    qs = [question("q1", source=None), question("q2", source="human")]

    out = _group_ids(qs, GROUPINGS["source"])

    assert [group for group, _ in out] == ["human", None]


def test_summarize_returns_group_rows():
    rows = summarize([question("q1")], pair("q1"), scored("q1", 0.2, 0.6), by="all")

    assert all(isinstance(r, GroupRow) for r in rows)


def test_the_all_grouping_gives_one_global_row():
    qs = [question("q1", "areas"), question("q2", "projects")]
    records = pair("q1") + pair("q2")
    scores = scored("q1", 0.2, 0.6) | scored("q2", 0.4, 0.4)

    rows = summarize(qs, records, scores, by="all")

    assert len(rows) == 1
    assert rows[0].group == "all"
    assert rows[0].n_questions == 2


def test_one_row_per_category_in_sorted_order():
    qs = [question("q1", "resources"), question("q2", "areas"), question("q3", "areas")]
    records = pair("q1") + pair("q2") + pair("q3")
    scores = scored("q1", 0, 1) | scored("q2", 0, 1) | scored("q3", 0, 1)

    rows = summarize(qs, records, scores, by="category")

    assert [(r.group, r.n_questions) for r in rows] == [("areas", 2), ("resources", 1)]


def test_unanswerable_questions_are_left_out():
    """D21. They have no records here on purpose: if summarize tried to pair
    them, paired_differences would raise."""
    qs = [question("q1"), question("q-abs", answerable=False)]

    rows = summarize(qs, pair("q1"), scored("q1", 0.2, 0.6), by="all")

    assert rows[0].n_questions == 1


def test_the_arm_means_and_the_difference_add_up():
    """para_mean - flat_mean == ci.mean, or the table contradicts itself."""
    qs = [question("q1"), question("q2")]
    records = pair("q1") + pair("q2")
    scores = scored("q1", 0.2, 0.6) | scored("q2", 0.4, 0.5)

    row = summarize(qs, records, scores, by="all")[0]

    assert row.flat_mean == pytest.approx(0.3)
    assert row.para_mean == pytest.approx(0.55)
    assert row.ci.mean == pytest.approx(row.para_mean - row.flat_mean)


def test_an_excluded_pair_stays_out_of_the_means():
    """q2's scores are extreme on purpose: if they leaked into the means, the
    numbers below would move."""
    qs = [question("q1"), question("q2")]
    records = pair("q1") + pair("q2", para_finish="length")
    scores = scored("q1", 0.2, 0.6) | scored("q2", 0.0, 1.0)

    row = summarize(qs, records, scores, by="all")[0]

    assert row.excluded == ["q2"]
    assert row.n_questions == 2
    assert row.ci.n == 1
    assert (row.flat_mean, row.para_mean) == pytest.approx((0.2, 0.6))


def test_a_group_with_no_usable_pair_is_still_shown():
    """It must appear with ci=None, not vanish and not show a 0.0."""
    qs = [question("q1", "projects"), question("q2", "areas")]
    records = pair("q1", para_finish="length") + pair("q2")
    scores = scored("q2", 0.2, 0.6)

    rows = summarize(qs, records, scores, by="category")
    projects = next(r for r in rows if r.group == "projects")

    assert projects.ci is None
    assert projects.flat_mean is None
    assert projects.para_mean is None
    assert projects.excluded == ["q1"]


def test_the_seed_reaches_the_bootstrap():
    qs = [question(f"q{i}") for i in range(len(MIXED))]
    records = [r for i in range(len(MIXED)) for r in pair(f"q{i}")]
    scores = {}
    for i, d in enumerate(MIXED):
        scores |= scored(f"q{i}", 0.5, 0.5 + d)

    a = summarize(qs, records, scores, by="all", seed=1)[0].ci
    b = summarize(qs, records, scores, by="all", seed=2)[0].ci

    assert (a.low, a.high) != (b.low, b.high)


def test_an_unknown_grouping_raises():
    with pytest.raises(ValueError):
        summarize([question("q1")], pair("q1"), scored("q1", 0, 1), by="color")


# --------------------------------------------------------------------------
# Sub-step 2c: operational_table
# --------------------------------------------------------------------------


def test_operational_returns_one_ops_row_per_arm_in_order():
    rows = operational_table([question("q1")], pair("q1"))

    assert all(isinstance(r, OpsRow) for r in rows)
    assert [r.strategy for r in rows] == ["flat", "para"]


def test_operational_counts_rows_truncated_and_no_chunks_per_arm():
    qs = [question("q1"), question("q2"), question("q3")]
    records = (
        pair("q1")
        + pair("q2", para_finish="length")
        + pair("q3", para_finish="no_chunks", para_chunks=0)
    )

    flat, para = operational_table(qs, records)

    assert (flat.n_rows, flat.n_truncated, flat.n_no_chunks) == (3, 0, 0)
    assert (para.n_rows, para.n_truncated, para.n_no_chunks) == (3, 1, 1)


def test_operational_only_counts_answerable_questions():
    qs = [question("q1"), question("q-abs", answerable=False)]
    records = pair("q1") + pair("q-abs")

    flat, _ = operational_table(qs, records)

    assert flat.n_rows == 1


def test_operational_mean_confidence_skips_truncated_and_no_chunks():
    """Only rows where the model really answered: 0.8 and 0.6 -> 0.7."""
    qs = [question(f"q{i}") for i in range(4)]
    records = [
        rec("q0", "para", confidence=0.8),
        rec("q1", "para", confidence=0.6),
        rec("q2", "para", finish="length", confidence=0.1),
        rec("q3", "para", finish="no_chunks", n_chunks=0, confidence=0.0),
    ]

    _, para = operational_table(qs, records)

    assert para.mean_confidence == pytest.approx(0.7)


def test_operational_mean_confidence_is_none_when_nothing_answered():
    records = [rec("q1", "flat", finish="length"), rec("q1", "para", finish="length")]

    flat, para = operational_table([question("q1")], records)

    assert flat.mean_confidence is None
    assert para.mean_confidence is None


# --------------------------------------------------------------------------
# Sub-step 2c: abstention_table
# --------------------------------------------------------------------------


def test_abstention_returns_one_row_per_arm_with_its_threshold():
    rows = abstention_table([question("q1")], pair("q1"), threshold=0.3)

    assert all(isinstance(r, AbstentionRow) for r in rows)
    assert [r.strategy for r in rows] == ["flat", "para"]
    assert all(r.threshold == 0.3 for r in rows)


def test_abstention_counts_unanswerable_below_the_threshold():
    qs = [question(f"a{i}", answerable=False) for i in range(3)]
    records = [
        rec("a0", "flat", confidence=0.0),
        rec("a1", "flat", confidence=0.2),
        rec("a2", "flat", confidence=0.9),
    ]

    flat, _ = abstention_table(qs, records, threshold=0.3)

    assert (flat.abstained_unanswerable, flat.n_unanswerable) == (2, 3)


def test_abstention_counts_answerable_separately():
    """The price of abstaining: answers the user did not get."""
    qs = [question("q1"), question("q2"), question("a1", answerable=False)]
    records = [
        rec("q1", "para", confidence=0.1),
        rec("q2", "para", confidence=0.9),
        rec("a1", "para", confidence=0.1),
    ]

    _, para = abstention_table(qs, records, threshold=0.3)

    assert (para.abstained_answerable, para.n_answerable) == (1, 2)
    assert (para.abstained_unanswerable, para.n_unanswerable) == (1, 1)


def test_exactly_at_the_threshold_does_not_abstain():
    """Strictly less than: at the threshold it answers."""
    qs = [question("a1", answerable=False)]

    flat, _ = abstention_table(qs, [rec("a1", "flat", confidence=0.3)], threshold=0.3)

    assert flat.abstained_unanswerable == 0


def test_no_chunks_counts_as_abstaining():
    """Confidence 0.0 by construction, so it abstains at any threshold above 0."""
    qs = [question("a1", answerable=False)]
    records = [rec("a1", "para", finish="no_chunks", n_chunks=0, confidence=0.0)]

    _, para = abstention_table(qs, records, threshold=0.05)

    assert (para.abstained_unanswerable, para.n_unanswerable) == (1, 1)


def test_truncated_rows_are_not_counted():
    """D17: whether a cut answer 'stayed quiet' is undecidable."""
    qs = [question("a1", answerable=False), question("a2", answerable=False)]
    records = [
        rec("a1", "flat", finish="length", confidence=0.0),
        rec("a2", "flat", confidence=0.0),
    ]

    flat, _ = abstention_table(qs, records, threshold=0.3)

    assert (flat.abstained_unanswerable, flat.n_unanswerable) == (1, 1)


def test_threshold_zero_means_nobody_abstains():
    qs = [question("a1", answerable=False)]

    flat, _ = abstention_table(qs, [rec("a1", "flat", confidence=0.0)], threshold=0.0)

    assert flat.abstained_unanswerable == 0


def test_rows_of_questions_not_passed_in_are_ignored():
    """D21 keeps the unanswerable questions in their own file. Loading only that
    file with the records of a full run must not count the answerable rows as
    unanswerable: that would turn 1/1 into 1/2 with no error."""
    qs = [question("a1", answerable=False)]
    records = [rec("a1", "flat", confidence=0.0), rec("q1", "flat", confidence=0.9)]

    flat, _ = abstention_table(qs, records, threshold=0.3)

    assert (flat.abstained_unanswerable, flat.n_unanswerable) == (1, 1)
    assert flat.n_answerable == 0


@pytest.mark.parametrize("threshold", [-0.1, 1.5])
def test_a_threshold_outside_0_1_raises(threshold):
    with pytest.raises(ValueError):
        abstention_table([question("q1")], pair("q1"), threshold=threshold)


# --------------------------------------------------------------------------
# Sub-step 2d: render_markdown
# --------------------------------------------------------------------------

OPS = [
    OpsRow(
        "flat",
        n_rows=68,
        n_truncated=0,
        n_no_chunks=0,
        mean_confidence=0.71,
        n_fell_back=0,
    ),
    OpsRow(
        "para",
        n_rows=68,
        n_truncated=2,
        n_no_chunks=5,
        mean_confidence=None,
        n_fell_back=9,
    ),
]

ROWS = [
    GroupRow(
        group="areas",
        n_questions=30,
        excluded=[],
        flat_mean=0.52,
        para_mean=0.61,
        ci=BootstrapCI(mean=0.09, low=0.01, high=0.17, n=30),
        n_para_fell_back=3,
    ),
    GroupRow(
        group="projects",
        n_questions=12,
        excluded=["q1", "q2"],
        flat_mean=None,
        para_mean=None,
        ci=None,
        n_para_fell_back=0,
    ),
    GroupRow(
        group="resources",
        n_questions=26,
        excluded=["q3"],
        flat_mean=0.48,
        para_mean=0.47,
        ci=BootstrapCI(mean=-0.01, low=-0.10, high=0.08, n=25),
        n_para_fell_back=0,
    ),
]

ABSTENTION = [
    AbstentionRow("flat", 0.3, 7, 10, 4, 68),
    AbstentionRow("para", 0.3, 0, 0, 6, 68),
]


def render(**overrides) -> str:
    kwargs = {
        "run": "2026-10-07-fake",
        "metric": "context_precision",
        "k": 5,
        "n_resamples": 10_000,
        "seed": 0,
        "ops": OPS,
        "tables": {"category": ROWS},
        "abstention": ABSTENTION,
    }
    return render_markdown(**(kwargs | overrides))


def test_render_starts_with_the_title_and_ends_with_a_newline():
    md = render()

    assert md.startswith("# Atlas — flat vs PARA\n")
    assert md.endswith("|\n")


def test_render_is_deterministic():
    """Same inputs, same bytes: that is what makes the report reproducible."""
    assert render() == render()


def test_the_warning_shows_up_as_a_quote_only_when_given():
    assert "> ⚠️ fake retriever" in render(warning="fake retriever")
    assert "⚠️" not in render()


def test_the_header_carries_the_run_settings():
    md = render()

    assert "`2026-10-07-fake`" in md
    assert "context_precision" in md
    assert "k=5" in md
    assert "10,000 resamples, seed 0" in md


def test_the_ops_table_formats_two_decimals_and_missing():
    md = render()

    assert "| flat | 68 | 0 | 0 | 0 | 0.71 |" in md
    assert "| para | 68 | 2 | 5 | 9 | — |" in md


def test_a_ci_that_excludes_zero_is_bold():
    assert "| **+0.09** | [+0.01, +0.17] |" in render()


def test_a_ci_that_crosses_zero_is_not_bold():
    assert "| -0.01 | [-0.10, +0.08] |" in render()


def test_a_ci_that_touches_zero_is_not_bold():
    """Strict: an interval that reaches 0 does not let you claim an effect."""
    row = GroupRow("g", 5, [], 0.1, 0.2, BootstrapCI(0.1, 0.0, 0.2, 5), 0)

    assert "**" not in render(tables={"category": [row]}).split("**Bold**")[0]


def test_a_tiny_negative_does_not_render_as_minus_zero():
    row = GroupRow("g", 5, [], 0.5, 0.499, BootstrapCI(-0.001, -0.2, 0.2, 5), 0)

    md = render(tables={"category": [row]})

    assert "-0.00" not in md
    assert "| +0.00 |" in md


def test_a_group_without_pairs_shows_missing_never_zero():
    line = next(x for x in render().splitlines() if x.startswith("| projects"))

    assert line == "| projects | 12 | 2 | — | — | — | — | no usable pairs |"


def test_the_none_group_has_a_readable_label():
    row = GroupRow(None, 1, [], 0.1, 0.2, BootstrapCI(0.1, 0.1, 0.1, 1), 0)

    assert "| (none) |" in render(tables={"source": [row]})


def test_tables_are_rendered_in_the_order_given():
    md = render(tables={"hops": ROWS, "all": ROWS})

    assert md.index("## context_precision by hops") < md.index(
        "## context_precision overall"
    )


def test_abstention_shows_counts_and_rates():
    md = render()

    assert "## Abstention (threshold 0.30)" in md
    assert "| flat | 7/10 (70%) | 4/68 (6%) |" in md


def test_abstention_with_nothing_counted_shows_missing_rate():
    assert "| para | 0/0 (—) | 6/68 (9%) |" in render()


def test_no_abstention_rows_leaves_the_section_out():
    assert "Abstention" not in render(abstention=[])


def test_mixed_thresholds_raise():
    mixed = [ABSTENTION[0], AbstentionRow("para", 0.5, 1, 10, 1, 68)]

    with pytest.raises(ValueError):
        render(abstention=mixed)


# --------------------------------------------------------------------------
# Step 3b (F4): the fallback rate
# --------------------------------------------------------------------------


def test_operational_counts_fallbacks_per_arm():
    qs = [question("q1"), question("q2"), question("q3")]
    records = pair("q1", fell_back=True) + pair("q2", fell_back=True) + pair("q3")

    flat, para = operational_table(qs, records)

    assert flat.n_fell_back == 0
    assert para.n_fell_back == 2


def test_a_fallen_back_row_still_counts_in_the_confidence():
    """It has chunks and an answer: falling back is not failing to answer."""
    qs = [question("q1"), question("q2")]
    records = [
        rec("q1", "para", confidence=0.8, fell_back=True),
        rec("q2", "para", confidence=0.6),
    ]

    _, para = operational_table(qs, records)

    assert para.n_fell_back == 1
    assert para.mean_confidence == pytest.approx(0.7)


def test_summarize_counts_fallbacks_over_the_pairs_in_the_number():
    """q3 fell back but was truncated, so it is not behind the difference and
    must not be counted either: same pairs as the means (2b, decision 3)."""
    qs = [question("q1"), question("q2"), question("q3")]
    records = (
        pair("q1", fell_back=True)
        + pair("q2")
        + pair("q3", para_finish="length", fell_back=True)
    )
    scores = scored("q1", 0.2, 0.3) | scored("q2", 0.2, 0.6)

    row = summarize(qs, records, scores, by="all")[0]

    assert row.ci.n == 2
    assert row.n_para_fell_back == 1


def test_summarize_counts_fallbacks_per_group():
    qs = [question("q1", "areas"), question("q2", "projects")]
    records = pair("q1", fell_back=True) + pair("q2")
    scores = scored("q1", 0.2, 0.3) | scored("q2", 0.2, 0.6)

    rows = summarize(qs, records, scores, by="category")

    assert [(r.group, r.n_para_fell_back) for r in rows] == [
        ("areas", 1),
        ("projects", 0),
    ]


def test_a_group_without_pairs_has_no_fallbacks():
    qs = [question("q1")]
    records = pair("q1", para_finish="length", fell_back=True)

    row = summarize(qs, records, {}, by="all")[0]

    assert row.n_para_fell_back == 0


def test_render_shows_the_fallback_next_to_para():
    line = next(x for x in render().splitlines() if x.startswith("| areas"))

    assert line == (
        "| areas | 30 | 0 | 0.52 | 0.61 | 3/30 (10%) | **+0.09** | [+0.01, +0.17] |"
    )
