"""Tests for `agent/abstain.py`. No network, no budget."""

import pytest

from selfware.agent.abstain import should_abstain
from selfware.core.schemas import Answer, Question
from selfware.eval.harness import Record
from selfware.eval.report import abstention_table


def answer(confidence: float, finish_reason: str = "stop") -> Answer:
    return Answer(
        text="" if finish_reason == "no_chunks" else "an answer",
        confidence=confidence,
        provenance=[],
        used_web=False,
        finish_reason=finish_reason,
    )


# --------------------------------------------------------------------------
# The confidence rule (D13)
# --------------------------------------------------------------------------


def test_a_confident_normal_answer_is_shown():
    assert should_abstain(answer(0.8), threshold=0.3) is False


def test_a_low_confidence_answer_abstains():
    assert should_abstain(answer(0.1), threshold=0.3) is True


def test_exactly_at_the_threshold_it_answers():
    """Strictly less, like `abstention_table`."""
    assert should_abstain(answer(0.3), threshold=0.3) is False


def test_threshold_zero_shows_every_normal_answer():
    """Nothing is below 0: with a 0 threshold only rule 2 can abstain."""
    assert should_abstain(answer(0.0), threshold=0.0) is False


# --------------------------------------------------------------------------
# The "did not end normally" rule (step 8, decision 1)
# --------------------------------------------------------------------------


def test_a_truncated_answer_abstains_even_when_confident():
    """Cut mid-sentence: it must never reach the user."""
    assert should_abstain(answer(0.95, "length"), threshold=0.3) is True


def test_a_no_chunks_answer_abstains_even_at_threshold_zero():
    """Empty text: there is nothing to show, whatever the threshold."""
    assert should_abstain(answer(0.0, "no_chunks"), threshold=0.0) is True


def test_any_unexpected_finish_reason_abstains():
    """`core/llm.py` reports a missing reason as "unknown"; never treat it as
    a normal end."""
    assert should_abstain(answer(0.9, "unknown"), threshold=0.3) is True


def test_it_returns_a_real_bool():
    """`/ask` will put it in a JSON field: a truthy number would be a surprise."""
    assert type(should_abstain(answer(0.8), threshold=0.3)) is bool


@pytest.mark.parametrize("threshold", [-0.1, 1.5])
def test_a_threshold_outside_0_1_raises(threshold):
    with pytest.raises(ValueError):
        should_abstain(answer(0.5), threshold=threshold)


# --------------------------------------------------------------------------
# Same rule as the evaluation, on the rows the evaluation counts
# --------------------------------------------------------------------------


@pytest.mark.parametrize("threshold", [0.0, 0.2, 0.35, 0.5, 0.9, 1.0])
def test_it_agrees_with_the_abstention_table_on_normal_rows(threshold):
    """The rule lives twice (rule 1 keeps `agent/` and `eval/` apart). On the
    rows `abstention_table` counts -- normal ones -- both must give the same
    count, or the calibrated threshold would not mean what `/ask` does."""
    confidences = [0.0, 0.1, 0.2, 0.3, 0.35, 0.4, 0.5, 0.75, 0.9, 1.0]
    questions = [
        Question(f"a{i}", "?", None, None, None, False, None) for i in range(10)
    ]
    records = [
        Record(f"a{i}", "flat", "an answer", c, 5, "stop", False)
        for i, c in enumerate(confidences)
    ]

    flat, _ = abstention_table(questions, records, threshold)
    ours = sum(should_abstain(answer(c), threshold) for c in confidences)

    assert ours == flat.abstained_unanswerable
