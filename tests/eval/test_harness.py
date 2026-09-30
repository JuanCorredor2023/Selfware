"""Tests for `harness.py`. None of them touches the network or spends budget.

This is where receiving `retrieve` and `answer` instead of importing them pays
off: both are three-line toy functions, defined below.
"""

import json
from datetime import UTC, datetime

import pytest

from selfware.core.schemas import Answer, Chunk, Question
from selfware.eval.harness import STRATEGIES, load_questions, run

# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


def chunk(similarity: float = 0.8) -> Chunk:
    return Chunk(
        text="does not matter",
        item_id="itm-001",
        para_path="areas/finance",
        ts=datetime(2026, 8, 14, tzinfo=UTC),
        similarity=similarity,
    )


def question(qid: str, answerable: bool = True) -> Question:
    return Question(
        id=qid,
        q=f"question {qid}?",
        expected="something" if answerable else None,
        category="area" if answerable else None,
        evidence="an email" if answerable else None,
        answerable=answerable,
        hops=1 if answerable else None,
        source="ai-drafted",
    )


def retrieve_that_always_brings(n: int):
    """Return a retrieval function that always hands back `n` chunks."""

    def _retrieve(query, strategy, k):
        return [chunk(0.9 - i * 0.1) for i in range(min(n, k))]

    return _retrieve


def retrieve_that_records(log: list):
    """Retrieval that notes down what arguments it was called with."""

    def _retrieve(query, strategy, k):
        log.append((query, strategy, k))
        return [chunk()]

    return _retrieve


def answer_simple(finish_reason: str = "stop", confidence: float = 0.7):
    """Return a toy agent with fixed `finish_reason` and confidence."""

    def _answer(query, chunks):
        return Answer(
            text=f"answer to {query}",
            confidence=confidence,
            provenance=list(chunks),
            used_web=False,
            finish_reason=finish_reason,
        )

    return _answer


# --------------------------------------------------------------------------
# load_questions
# --------------------------------------------------------------------------


def write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


ROW = {
    "id": "sd-p01",
    "q": "am I in the contest yet?",
    "expected": "Yes",
    "category": "project",
    "evidence": "an email, 16 Sep 2026",
    "answerable": True,
    "hops": 1,
    "source": "ai-drafted",
}


def test_loads_one_question(tmp_path):
    path = tmp_path / "q.jsonl"
    write_jsonl(path, [ROW])

    questions = load_questions(path)

    assert len(questions) == 1
    assert questions[0].id == "sd-p01"
    assert questions[0].category == "project"
    assert questions[0].answerable is True


def test_it_keeps_the_order_of_the_file(tmp_path):
    """The order is part of the reproducibility of the run."""
    path = tmp_path / "q.jsonl"
    write_jsonl(path, [{**ROW, "id": f"sd-p{i:02}"} for i in range(1, 6)])

    assert [q.id for q in load_questions(path)] == [
        "sd-p01",
        "sd-p02",
        "sd-p03",
        "sd-p04",
        "sd-p05",
    ]


def test_it_skips_blank_lines(tmp_path):
    path = tmp_path / "q.jsonl"
    path.write_text(json.dumps(ROW) + "\n\n\n", encoding="utf-8")

    assert len(load_questions(path)) == 1


def test_it_ignores_editorial_fields_not_in_the_contract(tmp_path):
    """The real files carry `note` and `pii`. They are not in C6 and must not break."""
    path = tmp_path / "q.jsonl"
    write_jsonl(path, [{**ROW, "note": "check this", "pii": True}])

    assert load_questions(path)[0].id == "sd-p01"


def test_it_loads_an_unanswerable_question(tmp_path):
    """The abstention ones carry `null` in category, evidence and hops (D21)."""
    path = tmp_path / "abstain.jsonl"
    write_jsonl(
        path,
        [
            {
                "id": "sd-ab01",
                "q": "what is my current rating?",
                "expected": "Not in the email",
                "category": None,
                "evidence": None,
                "answerable": False,
                "hops": None,
                "source": "ai-drafted",
            }
        ],
    )

    q = load_questions(path)[0]
    assert q.answerable is False
    assert q.category is None
    assert q.hops is None


def test_a_duplicate_id_raises(tmp_path):
    """Two questions with the same id would make the report cross the wrong rows,
    and the symptom would be odd numbers, not an exception."""
    path = tmp_path / "q.jsonl"
    write_jsonl(path, [ROW, ROW])

    with pytest.raises(ValueError):
        load_questions(path)


def test_a_missing_required_field_raises(tmp_path):
    path = tmp_path / "q.jsonl"
    incomplete = {k: v for k, v in ROW.items() if k != "answerable"}
    write_jsonl(path, [incomplete])

    with pytest.raises(KeyError):
        load_questions(path)


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------


def test_every_question_goes_through_both_arms():
    """D18, paired design: this is what gives the statistical power."""
    questions = [question("q1"), question("q2")]

    rows = run(questions, retrieve_that_always_brings(3), answer_simple())

    assert len(rows) == 4
    assert {(r.question_id, r.strategy) for r in rows} == {
        ("q1", "flat"),
        ("q1", "para"),
        ("q2", "flat"),
        ("q2", "para"),
    }


def test_the_row_order_is_deterministic():
    questions = [question("q1"), question("q2")]

    rows = run(questions, retrieve_that_always_brings(1), answer_simple())

    assert [(r.question_id, r.strategy) for r in rows] == [
        ("q1", STRATEGIES[0]),
        ("q1", STRATEGIES[1]),
        ("q2", STRATEGIES[0]),
        ("q2", STRATEGIES[1]),
    ]


def test_the_same_k_goes_to_both_arms():
    """D11: a different `k` per arm stops comparing the filter and compares two
    configurations."""
    log = []

    run([question("q1")], retrieve_that_records(log), answer_simple(), k=5)

    assert [k for _, _, k in log] == [5, 5]
    assert [s for _, s, _ in log] == list(STRATEGIES)


def test_an_empty_chunk_list_does_not_break_and_is_counted():
    """D8: PARA legitimately returns []. Counting those zeros is what turns the
    failure into the finding 'PARA retrieves nothing in N% of cases'."""
    rows = run([question("q1")], retrieve_that_always_brings(0), answer_simple())

    assert all(r.n_chunks == 0 for r in rows)


def test_it_counts_the_retrieved_chunks():
    rows = run([question("q1")], retrieve_that_always_brings(3), answer_simple(), k=5)

    assert all(r.n_chunks == 3 for r in rows)


def test_a_truncated_answer_is_flagged():
    """D17: `finish_reason='length'` means it hit max_tokens. The text looks
    reasonable until you read it in full."""
    rows = run(
        [question("q1")], retrieve_that_always_brings(1), answer_simple("length")
    )

    assert all(r.flagged for r in rows)
    assert all(r.finish_reason == "length" for r in rows)


def test_a_normal_answer_is_not_flagged():
    rows = run([question("q1")], retrieve_that_always_brings(1), answer_simple("stop"))

    assert not any(r.flagged for r in rows)


def test_the_unanswerable_ones_are_run_too():
    """D21: what changes is not the run, it is the evaluation. That is report.py's job."""
    rows = run(
        [question("ab1", answerable=False)],
        retrieve_that_always_brings(2),
        answer_simple(),
    )

    assert len(rows) == 2


def test_the_confidence_travels_to_the_row():
    rows = run(
        [question("q1")], retrieve_that_always_brings(1), answer_simple(confidence=0.42)
    )

    assert all(r.confidence == pytest.approx(0.42) for r in rows)
