"""Tests for `retrieval_metrics.py`. No network, no budget."""

from selfware.core.schemas import Question
from selfware.eval.harness import Record
from selfware.eval.retrieval_metrics import (
    hit_at_k,
    reciprocal_rank,
    render_routing,
    routing_table,
)


def question(qid: str, evidence: str | None, category: str | None = "projects"):
    return Question(
        id=qid,
        q="?",
        expected="x" if evidence else None,
        category=category if evidence else None,
        evidence=evidence,
        answerable=evidence is not None,
        hops=1 if evidence else None,
    )


def record(qid, strategy, item_ids, query_category=None, fell_back=False):
    return Record(
        question_id=qid,
        strategy=strategy,
        text="",
        confidence=0.5,
        n_chunks=len(item_ids),
        finish_reason="stop",
        flagged=False,
        fell_back_to_flat=fell_back,
        query_category=query_category,
        contexts=tuple("t" for _ in item_ids),
        item_ids=tuple(item_ids),
    )


QUESTIONS = [question("q1", "mail-1"), question("x1", None)]
RECORDS = [
    record("q1", "flat", ["mail-9", "mail-1", "mail-3"]),
    record("q1", "para", ["mail-7"], query_category="areas"),
    record("x1", "flat", ["mail-1"]),
    record("x1", "para", ["mail-1"], query_category="areas"),
]


def test_hit_at_k_respects_k():
    assert hit_at_k(2)(QUESTIONS, RECORDS) == {("q1", "flat"): 1.0, ("q1", "para"): 0.0}
    assert hit_at_k(1)(QUESTIONS, RECORDS)[("q1", "flat")] == 0.0


def test_reciprocal_rank():
    assert reciprocal_rank(QUESTIONS, RECORDS) == {
        ("q1", "flat"): 0.5,
        ("q1", "para"): 0.0,
    }


def test_unanswerable_questions_are_not_scored():
    assert all(qid != "x1" for qid, _ in reciprocal_rank(QUESTIONS, RECORDS))


def test_routing_counts_the_folder_the_classifier_chose():
    questions = [question("a", "m1"), question("b", "m2"), question("c", "m3", "areas")]
    records = [
        record("a", "para", [], query_category="projects"),
        record("b", "para", [], query_category="resources", fell_back=True),
        record("c", "para", [], query_category="areas"),
        record("a", "flat", []),
    ]
    rows = {r.category: r for r in routing_table(questions, records)}
    assert rows["projects"].n == 2
    assert rows["projects"].routed_right == 1
    assert rows["projects"].fell_back == 1
    assert rows["projects"].chosen == (("projects", 1), ("resources", 1))
    assert rows["areas"].routed_right == 1
    assert "| projects | 2 | 1 (50%) | 1 |" in render_routing(list(rows.values()))


def test_an_alternate_email_counts_as_a_hit():
    """A reminder that repeats the answer is a correct retrieval (evidence_alt)."""
    from selfware.eval.retrieval_metrics import make_reciprocal_rank

    questions = [question("q1", "mail-1")]
    records = [record("q1", "flat", ["mail-9", "mail-5", "mail-1"])]
    accepted = {"q1": frozenset({"mail-5"})}
    assert hit_at_k(2)(questions, records)[("q1", "flat")] == 0.0
    assert hit_at_k(2, accepted)(questions, records)[("q1", "flat")] == 1.0
    assert make_reciprocal_rank(accepted)(questions, records)[("q1", "flat")] == 0.5
    assert reciprocal_rank(questions, records)[("q1", "flat")] == 1 / 3
