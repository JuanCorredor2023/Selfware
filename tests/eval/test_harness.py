"""Tests for `harness.py`. None of them touches the network or spends budget.

This is where receiving `retrieve` and `answer` instead of importing them pays
off: both are three-line toy functions, defined below.
"""

import json
from datetime import UTC, datetime

import pytest

from selfware.core.schemas import Answer, Chunk, Question
from selfware.eval.harness import STRATEGIES, Retrieved, load_questions, run

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
        return Retrieved(chunks=[chunk(0.9 - i * 0.1) for i in range(min(n, k))])

    return _retrieve


def retrieve_that_records(log: list):
    """Retrieval that notes down what arguments it was called with."""

    def _retrieve(query, strategy, k):
        log.append((query, strategy, k))
        return Retrieved(chunks=[chunk()])

    return _retrieve


def retrieve_like_person_2(fallback_on: set[str]):
    """Mimics the real retriever's extra outputs (F4): the PARA arm classifies
    into `"areas"` and falls back to flat for the questions in `fallback_on`."""

    def _retrieve(query, strategy, k):
        if strategy == "flat":
            return Retrieved(chunks=[chunk()])
        return Retrieved(
            chunks=[chunk()],
            fell_back_to_flat=query in fallback_on,
            query_category="areas",
        )

    return _retrieve


def answer_that_records(log: list):
    """Toy agent that notes down exactly what `chunks` it was handed."""

    def _answer(query, chunks):
        log.append(chunks)
        return Answer(
            text="an answer",
            confidence=0.5,
            provenance=list(chunks),
            used_web=False,
            finish_reason="stop",
        )

    return _answer


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


# --------------------------------------------------------------------------
# F4: what retrieve says beyond the chunks travels to the row
# --------------------------------------------------------------------------


def test_the_answer_receives_only_the_chunks():
    """The agent's contract is (question, list[Chunk]): handing it the whole
    Retrieved would break `build_prompt` the first time it iterates."""
    log = []

    run([question("q1")], retrieve_that_always_brings(2), answer_that_records(log))

    assert all(isinstance(chunks, list) for chunks in log)
    assert all(isinstance(c, Chunk) for chunks in log for c in chunks)


def test_the_fallback_travels_to_the_para_row():
    q = question("q1")
    rows = run([q], retrieve_like_person_2(fallback_on={q.q}), answer_simple())
    flat, para = rows

    assert flat.fell_back_to_flat is False
    assert para.fell_back_to_flat is True


def test_no_fallback_is_recorded_as_false():
    rows = run(
        [question("q1")], retrieve_like_person_2(fallback_on=set()), answer_simple()
    )

    assert [r.fell_back_to_flat for r in rows] == [False, False]


def test_the_query_category_travels_to_the_row():
    rows = run([question("q1")], retrieve_like_person_2(set()), answer_simple())
    flat, para = rows

    assert flat.query_category is None
    assert para.query_category == "areas"


# --------------------------------------------------------------------------
# Step 7a: the chunk texts travel to the row, for RAGAS
# --------------------------------------------------------------------------


def retrieve_texts(*texts: str):
    """Retrieval that hands back chunks with these texts, in this order."""

    def _retrieve(query, strategy, k):
        return Retrieved(
            chunks=[
                Chunk(
                    text=t,
                    item_id=f"itm-{i}",
                    para_path="areas",
                    ts=datetime(2026, 9, 1, tzinfo=UTC),
                    similarity=0.9 - i * 0.1,
                )
                for i, t in enumerate(texts)
            ]
        )

    return _retrieve


def test_the_chunk_texts_travel_to_the_row_in_order():
    """D9: the order is retrieval's. RAGAS context precision is rank-aware, so
    reordering here would change the number."""
    rows = run([question("q1")], retrieve_texts("first", "second"), answer_simple())

    assert all(r.contexts == ("first", "second") for r in rows)


def test_contexts_is_a_tuple():
    """A frozen row whose contexts could still be edited would not be frozen."""
    rows = run([question("q1")], retrieve_texts("only"), answer_simple())

    assert all(isinstance(r.contexts, tuple) for r in rows)


def test_contexts_and_n_chunks_agree():
    rows = run([question("q1")], retrieve_that_always_brings(3), answer_simple())

    assert all(len(r.contexts) == r.n_chunks == 3 for r in rows)


def test_no_chunks_means_no_contexts():
    rows = run([question("q1")], retrieve_that_always_brings(0), answer_simple())

    assert all(r.contexts == () for r in rows)


def test_the_chunk_item_ids_travel_to_the_row_in_order():
    def _retrieve(query, strategy, k):
        return Retrieved(
            chunks=[
                Chunk("a", "mail-1", "areas", datetime(2026, 1, 1, tzinfo=UTC), 0.9),
                Chunk("b", "mail-2", "areas", datetime(2026, 1, 1, tzinfo=UTC), 0.8),
            ]
        )

    records = run([question("q1")], _retrieve, answer_simple())
    assert all(r.item_ids == ("mail-1", "mail-2") for r in records)


def test_an_answer_that_raises_is_a_flagged_row_not_a_crash():
    def _answer(query, chunks):
        raise RuntimeError("malformed response")

    records = run(
        [question("q1"), question("q2")], retrieve_that_always_brings(2), _answer
    )
    assert len(records) == 4
    assert all(r.flagged for r in records)
    assert all(r.finish_reason == "error:RuntimeError" for r in records)
    assert all(r.n_chunks == 2 and r.text == "" for r in records)
