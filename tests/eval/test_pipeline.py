"""Tests for `pipeline.evaluate`. No network, no files, no budget.

The doubles here are deliberately tiny and local: what is under test is the
order and the wiring of the composition, not retrieval or answering.
"""

from datetime import UTC, datetime

from selfware.core.schemas import Answer, Chunk, Question
from selfware.eval.harness import Retrieved
from selfware.eval.pipeline import evaluate
from selfware.eval.report import GROUPINGS

# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


def question(qid: str, category: str | None = "areas", answerable: bool = True):
    return Question(
        id=qid,
        q=f"question {qid}?",
        expected="an answer" if answerable else None,
        category=category if answerable else None,
        evidence="somewhere" if answerable else None,
        answerable=answerable,
        hops=1 if answerable else None,
        source="human",
    )


QUESTIONS = [
    question("q1", "areas"),
    question("q2", "areas"),
    question("q3", "projects"),
    question("q4", "resources"),
    question("a1", answerable=False),
]

CHUNK = Chunk(
    text="a chunk",
    item_id="itm-1",
    para_path="areas",
    ts=datetime(2026, 9, 1, tzinfo=UTC),
    similarity=0.8,
)


def retrieve_toy(log: list | None = None):
    def _retrieve(query, strategy, k):
        if log is not None:
            log.append(k)
        return Retrieved(chunks=[CHUNK])

    return _retrieve


def answer_toy(query, chunks):
    """Abstains (confidence 0.0) on the unanswerable question, answers the rest."""
    return Answer(
        text="an answer",
        confidence=0.0 if "a1" in query else 0.8,
        provenance=list(chunks),
        used_web=False,
        finish_reason="stop",
    )


def score_toy(log: list | None = None):
    """PARA a bit better than flat, by a different amount per question."""
    bumps = {"q1": 0.10, "q2": 0.30, "q3": -0.05, "q4": 0.20, "a1": 0.0}

    def _score(questions, records):
        if log is not None:
            log.append((questions, records))
        return {
            (r.question_id, r.strategy): 0.4
            + (bumps[r.question_id] if r.strategy == "para" else 0.0)
            for r in records
        }

    return _score


def evaluate_toy(**overrides) -> str:
    kwargs = {
        "run": "toy-run",
        "metric": "toy_metric",
        "threshold": 0.3,
        "n_resamples": 200,
    }
    return evaluate(
        QUESTIONS, retrieve_toy(), answer_toy, score_toy(), **(kwargs | overrides)
    )


# --------------------------------------------------------------------------
# evaluate
# --------------------------------------------------------------------------


def test_it_returns_the_markdown_report():
    md = evaluate_toy()

    assert isinstance(md, str)
    assert md.startswith("# Atlas — flat vs PARA\n")


def test_it_is_deterministic():
    """Same inputs, same report: the 'reproducible' in 'one command'."""
    assert evaluate_toy() == evaluate_toy()


def test_every_cut_is_rendered_in_groupings_order():
    md = evaluate_toy()
    headings = [
        "## toy_metric overall" if cut == "all" else f"## toy_metric by {cut}"
        for cut in GROUPINGS
    ]

    positions = [md.index(h) for h in headings]

    assert positions == sorted(positions)


def test_k_reaches_retrieve():
    log = []

    evaluate(
        QUESTIONS,
        retrieve_toy(log),
        answer_toy,
        score_toy(),
        run="r",
        metric="m",
        threshold=0.3,
        k=7,
        n_resamples=200,
    )

    assert set(log) == {7}


def test_score_receives_the_questions_and_the_harness_rows():
    log = []

    evaluate(
        QUESTIONS,
        retrieve_toy(),
        answer_toy,
        score_toy(log),
        run="r",
        metric="m",
        threshold=0.3,
        n_resamples=200,
    )
    questions, records = log[0]

    assert questions == QUESTIONS
    assert len(records) == 2 * len(QUESTIONS)


def test_the_operational_table_is_in_the_report():
    """Four answerable questions per arm; the unanswerable one stays out."""
    assert "| flat | 4 | 0 | 0 | 0 | 0.80 |" in evaluate_toy()


def test_the_abstention_table_uses_the_threshold():
    md = evaluate_toy(threshold=0.5)

    assert "## Abstention (threshold 0.50)" in md
    assert "| flat | 1/1 (100%) | 0/4 (0%) |" in md


def test_the_header_carries_the_run_settings():
    md = evaluate_toy(k=3, n_resamples=500, seed=4)

    assert "`toy-run`" in md
    assert "k=3" in md
    assert "500 resamples, seed 4" in md


def test_the_seed_reaches_the_bootstrap():
    """The header would show the seed even if it never reached `summarize`;
    the intervals only change if it did."""
    a = evaluate_toy(seed=1).replace("seed 1", "")
    b = evaluate_toy(seed=2).replace("seed 2", "")

    assert a != b


def test_the_warning_is_passed_through():
    assert "> ⚠️ toy data" in evaluate_toy(warning="toy data")
    assert "⚠️" not in evaluate_toy()
