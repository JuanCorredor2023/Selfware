"""Invariants of `scores_fake`."""

from selfware.eval.harness import Record
from tests.fakes.scores_fake import scores_fake


def rec(qid: str, strategy: str, n_chunks: int = 5) -> Record:
    return Record(
        question_id=qid,
        strategy=strategy,
        text="t",
        confidence=0.5,
        n_chunks=n_chunks,
        finish_reason="stop" if n_chunks else "no_chunks",
        flagged=n_chunks == 0,
    )


def test_one_score_per_row():
    records = [rec("q1", "flat"), rec("q1", "para"), rec("q2", "flat")]

    scores = scores_fake([], records)

    assert set(scores) == {("q1", "flat"), ("q1", "para"), ("q2", "flat")}


def test_scores_fall_in_zero_one():
    records = [rec(f"q{i}", s) for i in range(30) for s in ("flat", "para")]

    assert all(0.0 <= v < 1.0 for v in scores_fake([], records).values())


def test_it_is_deterministic():
    records = [rec("q1", "flat"), rec("q1", "para")]

    assert scores_fake([], records) == scores_fake([], records)


def test_no_chunks_scores_zero():
    """Like RAGAS over an empty context: what makes a PARA arm that retrieved
    nothing count against it (2a, decision 1)."""
    scores = scores_fake([], [rec("q1", "para", n_chunks=0)])

    assert scores[("q1", "para")] == 0.0
