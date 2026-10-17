"""Tests for `eval/ragas_runner.py`. No RAGAS, no network, no budget.

The judge is a toy that records what it was handed: what is under test is
which rows reach it and how its answer comes back, not RAGAS.
"""

import math
import subprocess
import sys

import pytest

from selfware.core.schemas import Question
from selfware.eval.harness import Record
from selfware.eval.pipeline import evaluate
from selfware.eval.ragas_runner import (
    METRICS,
    JudgeInput,
    make_ragas_scorer,
    to_judge_inputs,
)
from tests.fakes.answer_fake import answer_fake
from tests.fakes.retrieve_fake import retrieve_fake

# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


def question(qid: str, answerable: bool = True) -> Question:
    return Question(
        id=qid,
        q=f"question {qid}?",
        expected=f"answer {qid}" if answerable else None,
        category="areas" if answerable else None,
        evidence="somewhere" if answerable else None,
        answerable=answerable,
        hops=1 if answerable else None,
        source="human",
    )


def rec(
    qid: str,
    strategy: str = "flat",
    finish: str = "stop",
    contexts: tuple[str, ...] = ("ctx one", "ctx two"),
) -> Record:
    return Record(
        question_id=qid,
        strategy=strategy,
        text=f"response {qid} {strategy}",
        confidence=0.5,
        n_chunks=len(contexts),
        finish_reason=finish,
        flagged=finish != "stop",
        contexts=contexts,
    )


def judge_that_records(log: list, value: float = 0.5):
    def _judge(inputs):
        log.append(list(inputs))
        return [value] * len(inputs)

    return _judge


# --------------------------------------------------------------------------
# to_judge_inputs
# --------------------------------------------------------------------------


def test_a_normal_row_becomes_a_judge_input_with_ragas_fields():
    inputs, known = to_judge_inputs([question("q1")], [rec("q1", "para")])

    assert inputs == [
        JudgeInput(
            question_id="q1",
            strategy="para",
            user_input="question q1?",
            retrieved_contexts=("ctx one", "ctx two"),
            reference="answer q1",
            response="response q1 para",
        )
    ]
    assert known == {}


def test_inputs_follow_the_order_of_records():
    qs = [question("q1"), question("q2")]
    records = [rec("q2", "flat"), rec("q1", "para"), rec("q1", "flat")]

    inputs, _ = to_judge_inputs(qs, records)

    assert [(i.question_id, i.strategy) for i in inputs] == [
        ("q2", "flat"),
        ("q1", "para"),
        ("q1", "flat"),
    ]


def test_unanswerable_rows_are_ignored():
    """D21: no reference, and out of precision/recall. Not even a 0."""
    inputs, known = to_judge_inputs([question("a1", answerable=False)], [rec("a1")])

    assert inputs == []
    assert known == {}


def test_truncated_rows_are_ignored():
    """`paired_differences` excludes them anyway: judging them is paying for
    nothing. Not even a 0: a 0 would read as the arm failing."""
    inputs, known = to_judge_inputs([question("q1")], [rec("q1", finish="length")])

    assert inputs == []
    assert known == {}


def test_no_chunks_scores_zero_without_the_judge():
    records = [rec("q1", "para", finish="no_chunks", contexts=())]

    inputs, known = to_judge_inputs([question("q1")], records)

    assert inputs == []
    assert known == {("q1", "para"): 0.0}


def test_rows_of_questions_not_passed_in_are_ignored():
    inputs, known = to_judge_inputs([question("q1")], [rec("q1"), rec("stray")])

    assert [i.question_id for i in inputs] == ["q1"]
    assert known == {}


# --------------------------------------------------------------------------
# make_ragas_scorer
# --------------------------------------------------------------------------


def test_the_metrics_are_the_two_of_h1():
    assert set(METRICS) == {"context_precision", "context_recall"}


def test_an_unknown_metric_fails_before_any_credit_is_spent():
    log = []

    with pytest.raises(ValueError):
        make_ragas_scorer("faithfulness", judge_that_records(log))

    assert log == []


def test_the_judge_is_called_once_with_every_input():
    """One batch per metric, not one call per row."""
    log = []
    score = make_ragas_scorer("context_precision", judge_that_records(log))
    qs = [question("q1"), question("q2")]
    records = [rec("q1", "flat"), rec("q1", "para"), rec("q2", "flat")]

    score(qs, records)

    assert len(log) == 1
    assert len(log[0]) == 3


def test_scores_are_keyed_by_question_and_arm_and_merged_with_the_zeros():
    score = make_ragas_scorer("context_recall", judge_that_records([], value=0.7))
    records = [rec("q1", "flat"), rec("q1", "para", finish="no_chunks", contexts=())]

    scores = score([question("q1")], records)

    assert scores == {("q1", "flat"): 0.7, ("q1", "para"): 0.0}


def test_nothing_to_judge_means_no_call():
    log = []
    score = make_ragas_scorer("context_precision", judge_that_records(log))

    scores = score([question("a1", answerable=False)], [rec("a1")])

    assert log == []
    assert scores == {}


def test_a_judge_returning_the_wrong_count_raises():
    score = make_ragas_scorer("context_precision", lambda inputs: [0.5])

    with pytest.raises(ValueError, match="2 inputs"):
        score([question("q1")], [rec("q1", "flat"), rec("q1", "para")])


@pytest.mark.parametrize("bad", [math.nan, -0.1, 1.5])
def test_a_judge_score_outside_0_1_or_nan_raises(bad):
    """RAGAS returns NaN when it cannot parse the judge's output; a NaN in the
    report would print `nan` across a whole table."""
    score = make_ragas_scorer("context_precision", lambda inputs: [bad])

    with pytest.raises(ValueError, match="outside"):
        score([question("q1")], [rec("q1")])


def test_this_module_does_not_import_ragas():
    """D2: `ragas` may not be installed, and importing it patches asyncio for
    the whole process (`nest_asyncio.apply()`), which breaks the API. Checked in
    a fresh interpreter: looking at this process's `sys.modules` would fail as
    soon as any other test imported `ragas`."""
    done = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, selfware.eval.ragas_runner; print('ragas' in sys.modules)",
        ],
        capture_output=True,
        check=False,
        text=True,
        timeout=120,
    )

    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "False"


def test_end_to_end_through_evaluate():
    """The scorer drops into `evaluate` where `scores_fake` was."""
    qs = [question(f"q{i}") for i in range(6)] + [question("a1", answerable=False)]

    md = evaluate(
        qs,
        retrieve_fake,
        answer_fake,
        make_ragas_scorer("context_precision", judge_that_records([], value=0.6)),
        run="ragas-toy",
        metric="context_precision",
        threshold=0.3,
        n_resamples=200,
    )

    assert "## context_precision overall" in md
