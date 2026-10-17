"""Tests for `eval/calibrate.py`. No network, no budget.

The `choose_threshold` tests build the sweep by hand from `AbstentionRow`s, so
every benefit and cost can be worked out on paper.
"""

import pytest

from selfware.core.schemas import Question
from selfware.eval.calibrate import (
    DEFAULT_THRESHOLDS,
    choose_threshold,
    render_sweep,
    sweep,
)
from selfware.eval.harness import Record
from selfware.eval.report import AbstentionRow, abstention_table

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def row(arm: str, t: float, good: int, n_good: int, bad: int, n_bad: int):
    """`good`: abstained on unanswerable (benefit); `bad`: on answerable (cost)."""
    return AbstentionRow(arm, t, good, n_good, bad, n_bad)


def para_only(*entries) -> dict:
    """A sweep where flat mirrors para; entries are (t, good, bad) over 10/10."""
    return {
        t: [row("flat", t, good, 10, bad, 10), row("para", t, good, 10, bad, 10)]
        for t, good, bad in entries
    }


# --------------------------------------------------------------------------
# sweep
# --------------------------------------------------------------------------


def test_the_default_thresholds_go_from_0_to_1_by_005():
    assert len(DEFAULT_THRESHOLDS) == 21
    assert DEFAULT_THRESHOLDS[0] == 0.0
    assert DEFAULT_THRESHOLDS[-1] == 1.0
    assert DEFAULT_THRESHOLDS[3] == 0.15  # not 0.15000000000000002


def test_sweep_is_the_abstention_table_at_each_threshold():
    questions = [Question("a1", "?", None, None, None, False, None)]
    records = [Record("a1", "flat", "t", 0.4, 5, "stop", False)]

    swept = sweep(questions, records, thresholds=(0.3, 0.5))

    assert list(swept) == [0.3, 0.5]
    assert swept[0.5] == abstention_table(questions, records, 0.5)


def test_an_empty_list_of_thresholds_raises():
    with pytest.raises(ValueError):
        sweep([], [], thresholds=())


# --------------------------------------------------------------------------
# choose_threshold
# --------------------------------------------------------------------------


def test_it_picks_the_highest_benefit_within_the_budget():
    """0.6 abstains most (9/10) but costs 30%; with a 20% budget, 0.4 wins."""
    swept = para_only((0.2, 4, 0), (0.4, 7, 2), (0.6, 9, 3))

    assert choose_threshold(swept, "para", max_cost=0.20) == 0.4


def test_the_budget_is_inclusive():
    """A cost exactly at `max_cost` fits."""
    swept = para_only((0.2, 4, 0), (0.4, 7, 2))

    assert choose_threshold(swept, "para", max_cost=0.20) == 0.4


def test_a_tie_goes_to_the_lowest_threshold():
    """Same benefit: the lower threshold silences no more good answers."""
    swept = para_only((0.3, 7, 1), (0.5, 7, 1), (0.7, 7, 1))

    assert choose_threshold(swept, "para", max_cost=0.5) == 0.3


def test_the_tie_rule_does_not_depend_on_the_sweep_order():
    swept = para_only((0.7, 7, 1), (0.3, 7, 1), (0.5, 7, 1))

    assert choose_threshold(swept, "para", max_cost=0.5) == 0.3


def test_none_when_no_threshold_fits_the_budget():
    swept = para_only((0.4, 7, 2), (0.6, 9, 3))

    assert choose_threshold(swept, "para", max_cost=0.10) is None


def test_with_zero_in_the_sweep_something_always_fits():
    """Nothing is below 0, so threshold 0.0 always costs 0."""
    swept = para_only((0.0, 0, 0), (0.5, 8, 4))

    assert choose_threshold(swept, "para", max_cost=0.0) == 0.0


def test_it_calibrates_the_arm_it_is_asked_for():
    swept = {
        0.2: [row("flat", 0.2, 3, 10, 0, 10), row("para", 0.2, 5, 10, 0, 10)],
        0.5: [row("flat", 0.5, 8, 10, 1, 10), row("para", 0.5, 6, 10, 4, 10)],
    }

    assert choose_threshold(swept, "flat", max_cost=0.15) == 0.5
    assert choose_threshold(swept, "para", max_cost=0.15) == 0.2


@pytest.mark.parametrize("max_cost", [-0.1, 1.5])
def test_a_max_cost_outside_0_1_raises(max_cost):
    with pytest.raises(ValueError):
        choose_threshold(para_only((0.2, 4, 0)), "para", max_cost=max_cost)


def test_no_unanswerable_rows_means_no_calibration():
    swept = {0.2: [row("flat", 0.2, 0, 0, 0, 10), row("para", 0.2, 0, 0, 0, 10)]}

    with pytest.raises(ValueError):
        choose_threshold(swept, "para", max_cost=0.1)


def test_end_to_end_from_rows():
    """From harness-like rows to a threshold: confidences 0.1/0.2/0.6 on three
    unanswerable rows, 0.25/0.9 on two answerable ones. At 0.3 it abstains on
    2/3 unanswerable for 1/2 answerable; at 0.25, 2/3 for 0/2 -> 0.25 wins with
    a budget of 0."""
    questions = [
        Question(f"a{i}", "?", None, None, None, False, None) for i in range(3)
    ]
    questions += [Question(f"q{i}", "?", "x", "areas", "e", True, 1) for i in range(2)]
    conf = {"a0": 0.1, "a1": 0.2, "a2": 0.6, "q0": 0.25, "q1": 0.9}
    records = [
        Record(qid, arm, "t", c, 5, "stop", False)
        for qid, c in conf.items()
        for arm in ("flat", "para")
    ]

    swept = sweep(questions, records, thresholds=(0.0, 0.25, 0.3, 0.7))

    assert choose_threshold(swept, "para", max_cost=0.0) == 0.25


# --------------------------------------------------------------------------
# render_sweep
# --------------------------------------------------------------------------


def test_render_marks_the_chosen_threshold_and_states_the_criterion():
    swept = para_only((0.2, 4, 0), (0.4, 7, 2))

    md = render_sweep(swept, arm="para", max_cost=0.2, chosen=0.4)

    assert md.startswith("## Abstention threshold sweep\n")
    assert "at most 20% of answerable questions" in md
    assert "**Chosen threshold: 0.40**" in md
    assert "| **0.40 ←** | 7/10 (70%) | 2/10 (20%) | 7/10 (70%) | 2/10 (20%) |" in md
    assert "| 0.20 | 4/10 (40%) | 0/10 (0%) |" in md


def test_render_says_so_when_nothing_fits():
    md = render_sweep(para_only((0.4, 7, 2)), arm="para", max_cost=0.1, chosen=None)

    assert "No threshold fits the budget" in md
    assert "←" not in md
