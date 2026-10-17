"""Invariants of `answer_fake`: the shape of `agent/answer.py`, nothing more."""

from datetime import UTC, datetime

from selfware.core.schemas import Answer, Chunk
from tests.fakes.answer_fake import FAKE_TEXT, answer_fake


def chunk(item_id: str) -> Chunk:
    return Chunk(
        text="FAKE chunk",
        item_id=item_id,
        para_path="areas",
        ts=datetime(2026, 9, 1, tzinfo=UTC),
        similarity=0.5,
    )


def test_it_returns_an_answer():
    assert isinstance(answer_fake("q?", [chunk("itm-01")]), Answer)


def test_without_chunks_it_mimics_no_chunks():
    """Like `agent/answer.py`: no chunks, no model call, confidence 0."""
    ans = answer_fake("q?", [])

    assert ans.finish_reason == "no_chunks"
    assert ans.confidence == 0.0
    assert ans.provenance == []


def test_it_is_deterministic():
    chunks = [chunk("itm-01"), chunk("itm-02")]

    assert answer_fake("q?", chunks) == answer_fake("q?", chunks)


def test_the_text_says_it_is_fake():
    """Nobody should mistake its output for an answer."""
    ans = next(
        a
        for a in (answer_fake(f"q{i}?", [chunk("itm-01")]) for i in range(50))
        if a.finish_reason == "stop"
    )

    assert ans.text == FAKE_TEXT


def test_the_confidence_falls_in_zero_one():
    for i in range(50):
        assert 0.0 <= answer_fake(f"q{i}?", [chunk("itm-01")]).confidence < 1.0


def test_different_chunks_give_different_confidences():
    """The two arms of one question retrieve different chunks; their
    confidences must not come out identical by construction."""
    a = answer_fake("q?", [chunk("itm-01")])
    b = answer_fake("q?", [chunk("itm-02")])

    assert a.confidence != b.confidence


def test_some_answers_come_back_truncated_but_few():
    """About 1 in 20, so the truncated column is exercised but stays small."""
    finishes = [
        answer_fake(f"q{i}?", [chunk("itm-01")]).finish_reason for i in range(400)
    ]

    assert 0 < finishes.count("length") < 60
    assert set(finishes) == {"stop", "length"}
