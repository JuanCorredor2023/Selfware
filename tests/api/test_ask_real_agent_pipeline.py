"""The REAL agent code behind /ask, with only the outside world faked.

Real: agent.ask.make_answer_question, agent.answer.make_answerer (prompt,
confidence from logprobs, cache), api/app.py (cost, OTel, ledger).
Faked: retrieval (tests/fakes/retrieve_fake) and the Token Factory call
(a toy `llm_call`). No network, no credits, no chromadb.

This is the shape the day SELFWARE_AGENT=real runs on real data, minus the
data. If a contract drifts between agent/ and api/, it breaks here first.
"""

import math

import pytest
from fastapi.testclient import TestClient

from selfware.agent.answer import make_answerer
from selfware.agent.ask import make_answer_question
from selfware.api import app as app_module
from selfware.context.domain import Strategy
from selfware.core.llm import LLMResult, TokenLogprob
from selfware.core.schemas import TierCall
from selfware.observability.ledger import ledger
from tests.fakes.retrieve_fake import retrieve_fake

ULTRA = "nvidia/Nemotron-3-Ultra-550b-a55b"


def _fake_llm(tier, messages, **kwargs):
    return LLMResult(
        text="11",
        finish_reason="stop",
        tokens=[
            TokenLogprob("</think>", math.log(0.99)),
            TokenLogprob("1", math.log(0.9)),
            TokenLogprob("1", math.log(0.9)),
            TokenLogprob("<|im_end|>", math.log(0.999)),
        ],
        tier_call=TierCall(
            model=ULTRA, tokens_in=1500, tokens_out=80, latency_ms=900.0, cost_usd=0.0
        ),
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    ledger.reset()
    real_answer_question = make_answer_question(
        retrieve=lambda q, s, k: retrieve_fake(q, Strategy(s), k).chunks,
        answer=make_answerer(tmp_path, llm_call=_fake_llm),
    )
    monkeypatch.setattr(app_module, "answer_question", real_answer_question)
    yield TestClient(app_module.app)
    ledger.reset()


@pytest.mark.parametrize("strategy", ["flat", "para"])
def test_ask_returns_a_full_answer_from_the_real_agent(client, strategy):
    body = client.get(
        "/ask", params={"q": "when is the rent due?", "strategy": strategy}
    ).json()

    assert body["finish_reason"] == "stop"
    assert 0.0 <= body["confidence"] <= 1.0
    # At most k=5 (D11). The fake PARA arm only has the target folder's chunks.
    assert 1 <= len(body["provenance"]) <= 5
    if strategy == "para":
        assert len({c["para_path"] for c in body["provenance"]}) == 1
    first = body["provenance"][0]
    assert set(first) == {"text", "item_id", "para_path", "ts", "similarity"}
    assert isinstance(first["ts"], str)  # datetime serialised at the HTTP boundary
    assert body["used_web"] is False


def test_the_agents_tier_calls_are_priced_and_reach_cost(client):
    body = client.get("/ask", params={"q": "anything", "strategy": "flat"}).json()

    assert body["tier_calls"][0]["model"] == ULTRA
    assert body["tier_calls"][0]["cost_usd"] > 0

    cost = client.get("/cost").json()
    assert cost["query_count"] == 1
    assert cost["tiers"][0]["tier"] == "ultra"
    assert cost["unpriced_calls"] == 0


def test_an_unknown_strategy_never_reaches_the_agent(client):
    assert client.get("/ask", params={"q": "x", "strategy": "PARA"}).status_code == 422
