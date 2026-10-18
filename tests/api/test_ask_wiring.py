"""/ask must price and record whatever agent it is wired to (mock or real)."""

import pytest
from fastapi.testclient import TestClient

from selfware.api import app as app_module
from selfware.core.schemas import Answer, TierCall
from selfware.observability.ledger import ledger

ULTRA = "nvidia/Nemotron-3-Ultra-550b-a55b"


def _fake_answer_question(query: str, strategy: str) -> Answer:
    return Answer(
        text=f"{strategy}:{query}",
        confidence=0.9,
        provenance=[],
        used_web=False,
        finish_reason="stop",
        tier_calls=[
            TierCall(
                model=ULTRA,
                tokens_in=1000,
                tokens_out=100,
                latency_ms=10.0,
                cost_usd=0.0,
            )
        ],
    )


@pytest.fixture(autouse=True)
def _clean_ledger():
    ledger.reset()
    yield
    ledger.reset()


def test_ask_prices_and_records_the_tier_calls_of_the_wired_agent(monkeypatch):
    monkeypatch.setattr(app_module, "answer_question", _fake_answer_question)
    client = TestClient(app_module.app)

    body = client.get("/ask", params={"q": "hello", "strategy": "flat"}).json()

    assert body["text"] == "flat:hello"
    assert body["tier_calls"][0]["cost_usd"] > 0  # priced by with_cost
    assert client.get("/cost").json()["query_count"] == 1


def test_default_agent_is_the_mock(monkeypatch):
    monkeypatch.delenv("SELFWARE_AGENT", raising=False)
    assert app_module._load_answer_question().__module__.endswith("_mock_agent")
