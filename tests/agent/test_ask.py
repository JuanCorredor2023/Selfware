"""Tests for `agent/ask.py`. No network, no budget.

The doubles record what they were called with, so the tests can check the
wiring -- what reaches `retrieve`, what reaches `answer` -- and not just the
final object.
"""

from datetime import UTC, datetime

import pytest

from selfware.agent.ask import VALID_STRATEGIES, make_answer_question
from selfware.core.schemas import Answer, Chunk, TierCall
from tests.fakes.answer_fake import answer_fake
from tests.fakes.retrieve_fake import retrieve_fake

# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------

CHUNK = Chunk(
    text="a chunk",
    item_id="itm-1",
    para_path="areas",
    ts=datetime(2026, 9, 1, tzinfo=UTC),
    similarity=0.8,
)

TIER_CALL = TierCall(
    model="model-x", tokens_in=100, tokens_out=50, latency_ms=1.0, cost_usd=0.0
)


def retrieve_that_records(log: list):
    def _retrieve(query, strategy, k):
        log.append((query, strategy, k))
        return [CHUNK]

    return _retrieve


def answer_that_records(log: list):
    def _answer(query, chunks):
        log.append((query, chunks))
        return Answer(
            text="an answer",
            confidence=0.7,
            provenance=list(chunks),
            used_web=False,
            finish_reason="stop",
            tier_calls=[TIER_CALL],
        )

    return _answer


# --------------------------------------------------------------------------
# make_answer_question
# --------------------------------------------------------------------------


def test_it_returns_a_function_of_query_and_strategy():
    answer_question = make_answer_question(
        retrieve_that_records([]), answer_that_records([])
    )

    assert isinstance(answer_question("which day?", "para"), Answer)


def test_nothing_is_called_when_the_factory_runs():
    """Retrieval and answering happen per question, not at start-up."""
    r_log, a_log = [], []

    make_answer_question(retrieve_that_records(r_log), answer_that_records(a_log))

    assert r_log == []
    assert a_log == []


def test_retrieve_gets_the_query_the_strategy_and_k():
    log = []
    answer_question = make_answer_question(
        retrieve_that_records(log), answer_that_records([]), k=7
    )

    answer_question("which day?", "flat")

    assert log == [("which day?", "flat", 7)]


def test_k_defaults_to_the_evaluations_5():
    """D11: the demo runs the same configuration as the report's number."""
    log = []
    answer_question = make_answer_question(
        retrieve_that_records(log), answer_that_records([])
    )

    answer_question("q?", "para")

    assert log[0][2] == 5


def test_answer_gets_the_query_and_the_retrieved_chunks():
    log = []
    answer_question = make_answer_question(
        retrieve_that_records([]), answer_that_records(log)
    )

    answer_question("which day?", "para")

    assert log == [("which day?", [CHUNK])]


def test_the_agents_answer_comes_back_untouched():
    """Including `tier_calls`: `/ask` prices them and `/cost` adds them up."""
    answer_question = make_answer_question(
        retrieve_that_records([]), answer_that_records([])
    )

    ans = answer_question("q?", "flat")

    assert ans.tier_calls == [TIER_CALL]
    assert ans.provenance == [CHUNK]


@pytest.mark.parametrize("strategy", ["PARA", "Flat", "hybrid", ""])
def test_an_unknown_strategy_raises_before_retrieving(strategy):
    """F5: a typo must fail loudly at the edge, not reach the retriever."""
    log = []
    answer_question = make_answer_question(
        retrieve_that_records(log), answer_that_records([])
    )

    with pytest.raises(ValueError):
        answer_question("q?", strategy)

    assert log == []


@pytest.mark.parametrize("k", [0, -1])
def test_a_k_below_one_is_rejected_by_the_factory(k):
    with pytest.raises(ValueError):
        make_answer_question(retrieve_that_records([]), answer_that_records([]), k=k)


def test_the_valid_strategies_are_the_two_arms():
    assert VALID_STRATEGIES == ("flat", "para")


@pytest.mark.parametrize("strategy", VALID_STRATEGIES)
def test_end_to_end_with_the_fakes(strategy):
    """Wired the way an edge would wire it: the evaluation's `Retrieved`
    adapted with `.chunks`. Covers the PARA fallback case too: the fake's
    `archive` folder is empty, and the answer still comes back."""
    answer_question = make_answer_question(
        retrieve=lambda q, s, k: retrieve_fake(q, s, k).chunks,
        answer=answer_fake,
    )

    ans = answer_question("how much did I pay?", strategy)

    assert ans.provenance == retrieve_fake("how much did I pay?", strategy, 5).chunks
    assert len(ans.provenance) == 5
