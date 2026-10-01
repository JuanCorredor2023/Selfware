"""core/llm.py without the network: a fake client stands in for Token Factory,
so these tests spend no credits."""

from types import SimpleNamespace

import pytest

from selfware.core import llm


class FakeClient:
    """Records the arguments of the last request and replays one response."""

    def __init__(self, response):
        self.last_request = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self._response = response

    def _create(self, **kwargs):
        self.last_request = kwargs
        return self._response


def make_response(text="hello", finish_reason="stop", logprobs=None, usage=(12, 7)):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=text),
                finish_reason=finish_reason,
                logprobs=logprobs,
            )
        ],
        usage=SimpleNamespace(prompt_tokens=usage[0], completion_tokens=usage[1])
        if usage
        else None,
    )


def with_fake_client(monkeypatch, response):
    fake = FakeClient(response)
    monkeypatch.setattr(llm, "_get_client", lambda: fake)
    return fake


MESSAGES = [{"role": "user", "content": "hi"}]


def test_judge_tier_exists_and_differs_from_the_generators():
    assert llm.MODEL_IDS["judge"] == "Qwen/Qwen3-235B-A22B-Instruct-2507"
    # D12: the judge must not be the model that generated the answer.
    assert llm.MODEL_IDS["judge"] not in (
        llm.MODEL_IDS["nano"],
        llm.MODEL_IDS["ultra"],
    )


def test_call_returns_text_and_a_tier_call(monkeypatch):
    fake = with_fake_client(monkeypatch, make_response("OK"))
    text, tier_call = llm.call("nano", MESSAGES, max_tokens=4)
    assert text == "OK"
    assert tier_call.model == llm.MODEL_IDS["nano"]
    assert (tier_call.tokens_in, tier_call.tokens_out) == (12, 7)
    assert tier_call.latency_ms >= 0
    assert tier_call.cost_usd == 0.0  # priced later by observability.cost
    assert fake.last_request["max_tokens"] == 4
    assert "logprobs" not in fake.last_request  # call() is unchanged


def test_super_tier_exists_and_is_distinct():
    assert llm.MODEL_IDS["super"] == "nvidia/nemotron-3-super-120b-a12b"
    assert llm.MODEL_IDS["super"] not in (llm.MODEL_IDS["nano"], llm.MODEL_IDS["ultra"])


def test_call_routes_the_judge_tier_to_the_judge_model(monkeypatch):
    fake = with_fake_client(monkeypatch, make_response())
    llm.call("judge", MESSAGES)
    assert fake.last_request["model"] == llm.MODEL_IDS["judge"]


def test_call_with_logprobs_returns_tokens_and_finish_reason(monkeypatch):
    logprobs = SimpleNamespace(
        content=[
            SimpleNamespace(token="Hel", logprob=-0.1),
            SimpleNamespace(token="lo", logprob=-0.4),
        ]
    )
    fake = with_fake_client(monkeypatch, make_response("Hello", "length", logprobs))
    result = llm.call_with_logprobs("ultra", MESSAGES, top_logprobs=5)

    assert result.text == "Hello"
    assert result.finish_reason == "length"  # truncation is visible
    assert result.tokens == [
        llm.TokenLogprob("Hel", -0.1),
        llm.TokenLogprob("lo", -0.4),
    ]
    assert result.tier_call.model == llm.MODEL_IDS["ultra"]
    assert result.tier_call.tokens_out == 7
    assert fake.last_request["logprobs"] is True
    assert fake.last_request["top_logprobs"] == 5


def test_call_with_logprobs_lets_the_caller_turn_logprobs_off(monkeypatch):
    fake = with_fake_client(monkeypatch, make_response())
    llm.call_with_logprobs("nano", MESSAGES, logprobs=False)
    assert fake.last_request["logprobs"] is False


def test_missing_logprobs_give_an_empty_token_list(monkeypatch):
    with_fake_client(monkeypatch, make_response(logprobs=None))
    assert llm.call_with_logprobs("nano", MESSAGES).tokens == []


def test_missing_finish_reason_is_reported_as_unknown_not_stop(monkeypatch):
    with_fake_client(monkeypatch, make_response(finish_reason=None))
    assert llm.call_with_logprobs("nano", MESSAGES).finish_reason == "unknown"


def test_missing_usage_counts_zero_tokens(monkeypatch):
    with_fake_client(monkeypatch, make_response(usage=None))
    _, tier_call = llm.call("nano", MESSAGES)
    assert (tier_call.tokens_in, tier_call.tokens_out) == (0, 0)


def test_unknown_tier_is_rejected(monkeypatch):
    with_fake_client(monkeypatch, make_response())
    with pytest.raises(KeyError):
        llm.call("does-not-exist", MESSAGES)
