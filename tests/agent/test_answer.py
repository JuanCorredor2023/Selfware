"""Tests for `answer.py`. None of them calls Token Factory or spends a cent.

The function that talks to Token Factory is **received** as a parameter
(`llm_call`), so a toy one is passed in here: `FakeLLM` records what it was
called with and returns a fabricated `LLMResult`, the same type
`core.llm.call_with_logprobs` returns.
"""

import math
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import selfware
from selfware.agent.answer import (
    ABSTENTION_SENTINEL,
    NO_CHUNKS,
    SYSTEM_INSTRUCTIONS,
    build_prompt,
    make_answerer,
    to_token_logprobs,
)
from selfware.agent.cache import cache_key, save
from selfware.core.llm import LLMResult, TokenLogprob
from selfware.core.schemas import Chunk, TierCall

# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


def chunk(text: str, similarity: float = 0.8, day: int = 14) -> Chunk:
    return Chunk(
        text=text,
        item_id=f"itm-{day:03}",
        para_path="areas/finance",
        ts=datetime(2026, 8, day, tzinfo=UTC),
        similarity=similarity,
    )


def tokens_sdk(pairs: list[tuple[str, float]]):
    """Mimics `response.choices[0].logprobs.content`: objects with .token and .logprob."""
    return [SimpleNamespace(token=t, logprob=lp) for t, lp in pairs]


#: A plausible response: reasoning, the marker, two content tokens and the chat
#: format closing -- the shape verified on 14 Sep.
TYPICAL_TOKENS = [
    ("thinking", math.log(0.5)),
    ("</think>", math.log(0.99)),
    ("1", math.log(0.9)),
    ("1", math.log(0.9)),
    ("<|im_end|>", math.log(0.999)),
]


class FakeLLM:
    """Toy `call_with_logprobs`. Records the calls and returns whatever it is told to."""

    def __init__(self, content="11", finish_reason="stop", pairs=None):
        self.calls = []
        self.tier_call = TierCall(
            model="model-x", tokens_in=120, tokens_out=60, latency_ms=1.0, cost_usd=0.0
        )
        self._result = LLMResult(
            text=content,
            finish_reason=finish_reason,
            tokens=[
                TokenLogprob(token=t, logprob=lp)
                for t, lp in (TYPICAL_TOKENS if pairs is None else pairs)
            ],
            tier_call=self.tier_call,
        )

    def __call__(self, tier, messages, **kwargs):
        self.calls.append({"tier": tier, "messages": messages, **kwargs})
        return self._result


def must_not_call(tier, messages, **kwargs):
    raise AssertionError(
        "the model was called, but the answer should come from the cache"
    )


# --------------------------------------------------------------------------
# build_prompt
# --------------------------------------------------------------------------


def test_the_fixed_prefix_goes_first():
    """D15: if this fails, Nebius caches nothing and the prefix is paid 132 times."""
    prompt = build_prompt("which day is it charged?", [chunk("charged on the 14th")])

    assert prompt.startswith(SYSTEM_INSTRUCTIONS)


def test_the_question_goes_last():
    prompt = build_prompt("which day is it charged?", [chunk("charged on the 14th")])

    assert prompt.index("which day is it charged?") > prompt.index(
        "charged on the 14th"
    )


def test_two_different_questions_share_the_prefix():
    a = build_prompt("question one?", [chunk("something")])
    b = build_prompt("question two?", [chunk("something")])

    assert a.startswith(SYSTEM_INSTRUCTIONS)
    assert b.startswith(SYSTEM_INSTRUCTIONS)


def test_it_includes_the_text_of_every_chunk():
    prompt = build_prompt("?", [chunk("first one"), chunk("second one")])

    assert "first one" in prompt
    assert "second one" in prompt


def test_it_includes_the_date_of_the_chunks():
    prompt = build_prompt("?", [chunk("something", day=9)])

    assert "2026" in prompt


def test_it_does_not_include_para_path():
    """The PARA label is what is under test. In the prompt it would let the model
    reason about the structure directly, and the two arms would stop being
    comparable."""
    prompt = build_prompt("?", [chunk("something")])

    assert "areas/finance" not in prompt


def test_the_profile_goes_before_the_chunks():
    prompt = build_prompt("?", [chunk("a chunk")], profile="a student")

    assert prompt.index("a student") < prompt.index("a chunk")


def test_without_a_profile_nothing_odd_shows_up():
    prompt = build_prompt("?", [chunk("a chunk")])

    assert "None" not in prompt


# --------------------------------------------------------------------------
# to_token_logprobs
# --------------------------------------------------------------------------


def test_it_converts_preserving_order_and_values():
    out = to_token_logprobs(tokens_sdk([("a", -0.1), ("b", -0.2)]))

    assert [(t.token, t.logprob) for t in out] == [("a", -0.1), ("b", -0.2)]


def test_without_logprobs_it_raises():
    with pytest.raises(ValueError):
        to_token_logprobs(None)


def test_empty_logprobs_raises():
    with pytest.raises(ValueError):
        to_token_logprobs([])


# --------------------------------------------------------------------------
# make_answerer
# --------------------------------------------------------------------------


def test_without_chunks_the_model_is_not_called(tmp_path):
    """D8: the PARA arm legitimately returns [], and it can happen often. Paying
    for those calls would be paying to fail."""
    llm = FakeLLM()
    answerer = make_answerer(tmp_path, llm_call=llm)

    ans = answerer("which day is it charged?", [])

    assert llm.calls == []
    assert ans.finish_reason == NO_CHUNKS
    assert ans.confidence == 0.0
    assert ans.provenance == []


def test_with_chunks_the_model_is_called(tmp_path):
    llm = FakeLLM()
    answerer = make_answerer(tmp_path, llm_call=llm)

    answerer("which day is it charged?", [chunk("charged on the 14th")])

    assert len(llm.calls) == 1


def test_it_sends_the_protocol_parameters(tmp_path):
    """D7 temperature=0, and logprobs so confidence can be measured (D24)."""
    llm = FakeLLM()
    answerer = make_answerer(tmp_path, llm_call=llm)

    answerer("?", [chunk("something")])
    kwargs = llm.calls[0]

    assert kwargs["tier"] == "ultra"
    assert kwargs["temperature"] == 0.0
    assert kwargs["logprobs"] is True
    assert kwargs["top_logprobs"] == 5


def test_an_identical_second_call_comes_from_the_cache(tmp_path):
    """D16: the budget is ~$50 and the evaluation is run ten or fifteen times."""
    llm = FakeLLM()
    answerer = make_answerer(tmp_path, llm_call=llm)
    chunks = [chunk("charged on the 14th")]

    first = answerer("which day is it charged?", chunks)
    second = answerer("which day is it charged?", chunks)

    assert len(llm.calls) == 1
    assert second.text == first.text
    assert second.confidence == pytest.approx(first.confidence)


def test_a_different_question_does_not_reuse_the_cache(tmp_path):
    llm = FakeLLM()
    answerer = make_answerer(tmp_path, llm_call=llm)
    chunks = [chunk("charged on the 14th")]

    answerer("which day is it charged?", chunks)
    answerer("how much is the charge?", chunks)

    assert len(llm.calls) == 2


def test_the_text_and_the_finish_reason_travel_to_the_answer(tmp_path):
    llm = FakeLLM(content="On the 14th", finish_reason="stop")
    answerer = make_answerer(tmp_path, llm_call=llm)

    ans = answerer("?", [chunk("something")])

    assert ans.text == "On the 14th"
    assert ans.finish_reason == "stop"


def test_a_truncated_answer_keeps_its_finish_reason(tmp_path):
    """D17: the harness will flag it; here the point is not to lose the data."""
    llm = FakeLLM(finish_reason="length")
    answerer = make_answerer(tmp_path, llm_call=llm)

    ans = answerer("?", [chunk("something")])

    assert ans.finish_reason == "length"


def test_the_provenance_is_the_chunks_received(tmp_path):
    llm = FakeLLM()
    answerer = make_answerer(tmp_path, llm_call=llm)
    chunks = [chunk("one"), chunk("two")]

    ans = answerer("?", chunks)

    assert ans.provenance == chunks


def test_used_web_is_always_false(tmp_path):
    """Tavily is used AFTER abstaining, and that is decided by abstain.py (D13)."""
    llm = FakeLLM()
    answerer = make_answerer(tmp_path, llm_call=llm)

    assert answerer("?", [chunk("something")]).used_web is False
    assert answerer("?", []).used_web is False


def test_the_confidence_combines_the_two_signals(tmp_path):
    """The answer tokens are worth 0.9 and the top-1 similarity is 0.30.
    By D24 the weaker one wins."""
    llm = FakeLLM()
    answerer = make_answerer(tmp_path, llm_call=llm)

    ans = answerer("?", [chunk("something", similarity=0.30)])

    assert ans.confidence == pytest.approx(0.30)


# --------------------------------------------------------------------------
# Going through core/llm.py (integration step 1)
# --------------------------------------------------------------------------

#: The model id and parameters the 53 answers already on disk were keyed with
#: (atlas-lab, Sep 20). Written out literally ON PURPOSE: if `MODEL_IDS["ultra"]`
#: or the params ever change, the test below must fail, because that change
#: throws the whole cache away and the run has to be paid again (D16).
LEGACY_MODEL = "nvidia/Nemotron-3-Ultra-550b-a55b"
LEGACY_PARAMS = {
    "temperature": 0.0,
    "max_tokens": 4000,
    "logprobs": True,
    "top_logprobs": 5,
}


def test_it_sends_the_prompt_as_a_single_user_message(tmp_path):
    llm = FakeLLM()
    answerer = make_answerer(tmp_path, llm_call=llm)
    chunks = [chunk("charged on the 14th")]

    answerer("which day is it charged?", chunks)

    assert llm.calls[0]["messages"] == [
        {"role": "user", "content": build_prompt("which day is it charged?", chunks)}
    ]


def test_it_sends_exactly_the_cached_params(tmp_path):
    """What is sent and what goes into the key are the same dict. If they could
    differ, a change to one would serve answers produced with the other."""
    llm = FakeLLM()
    answerer = make_answerer(tmp_path, llm_call=llm)

    answerer("?", [chunk("something")])
    sent = {k: v for k, v in llm.calls[0].items() if k not in ("tier", "messages")}

    assert sent == LEGACY_PARAMS


def test_a_real_call_reports_its_tier_call(tmp_path):
    """Without this `/cost` never sees what the agent spends (acta 2026-09-30)."""
    llm = FakeLLM()
    answerer = make_answerer(tmp_path, llm_call=llm)

    ans = answerer("?", [chunk("something")])

    assert ans.tier_calls == [llm.tier_call]


def test_a_cache_hit_reports_no_tier_call(tmp_path):
    """A cache hit cost nothing. Reporting the original call again would make
    `/cost` count the same spend twice."""
    llm = FakeLLM()
    answerer = make_answerer(tmp_path, llm_call=llm)
    chunks = [chunk("something")]

    answerer("?", chunks)
    second = answerer("?", chunks)

    assert second.tier_calls == []


def test_the_sentinel_still_reports_its_tier_call(tmp_path):
    """Abstaining is not free: the model was called and the call was paid."""
    llm = FakeLLM(content=ABSTENTION_SENTINEL)
    answerer = make_answerer(tmp_path, llm_call=llm)

    ans = answerer("?", [chunk("something")])

    assert ans.tier_calls == [llm.tier_call]


def test_without_chunks_there_is_no_tier_call(tmp_path):
    ans = make_answerer(tmp_path, llm_call=FakeLLM())("?", [])

    assert ans.tier_calls == []


def test_the_entries_already_on_disk_are_still_hits(tmp_path):
    """D16. An entry written with the pre-migration key must be served without
    calling the model. If this fails, the migration silently invalidated the
    53 cached answers and the next run pays for all of them again."""
    question, chunks = "which day is it charged?", [chunk("charged on the 14th")]
    key = cache_key(build_prompt(question, chunks), LEGACY_MODEL, LEGACY_PARAMS)
    save(
        tmp_path,
        key,
        {
            "text": "On the 14th",
            "finish_reason": "stop",
            "tokens": [{"token": t, "logprob": lp} for t, lp in TYPICAL_TOKENS],
        },
    )
    answerer = make_answerer(tmp_path, llm_call=must_not_call)

    ans = answerer(question, chunks)

    assert ans.text == "On the 14th"


def test_another_tier_does_not_reuse_the_cache(tmp_path):
    """The key carries the model id, not just the prompt (D12): an answer from
    one model must never be served as if another one had produced it."""
    chunks = [chunk("something")]
    make_answerer(tmp_path, llm_call=FakeLLM())("?", chunks)
    llm = FakeLLM()

    make_answerer(tmp_path, tier="super", llm_call=llm)("?", chunks)

    assert len(llm.calls) == 1
    assert llm.calls[0]["tier"] == "super"


def test_empty_logprobs_from_core_llm_raise(tmp_path):
    """`call_with_logprobs` turns "no logprobs" into `[]` without complaining.
    Accepting it would give confidence 0.0 to a possibly good answer, and the
    row would abstain for no reason."""
    llm = FakeLLM(pairs=[])
    answerer = make_answerer(tmp_path, llm_call=llm)

    with pytest.raises(ValueError):
        answerer("?", [chunk("something")])


def test_the_old_positional_signature_fails_loudly(tmp_path):
    """`make_answerer(client, model, cache_dir)` was the signature before step 1.
    A caller still written that way must break, not run with a client where the
    cache path should be."""
    with pytest.raises(TypeError):
        make_answerer(object(), "model-x", tmp_path)


def test_agent_and_eval_never_call_the_sdk_directly():
    """Architecture rule 2: every call to Token Factory goes through
    `core/llm.py`. Checked on my two modules only; the others are not mine."""
    root = Path(selfware.__file__).parent
    offenders = [
        str(path.relative_to(root))
        for module in ("agent", "eval")
        for path in (root / module).rglob("*.py")
        if "chat.completions" in path.read_text(encoding="utf-8")
        or "tokenfactory.nebius.com" in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


# --------------------------------------------------------------------------
# Abstention sentinel (R18)
# --------------------------------------------------------------------------


def test_the_instructions_ask_for_the_sentinel():
    """If the rule disappears from the prompt, the model stops emitting it and the
    detection below never fires -- silently, without any test failing."""
    assert ABSTENTION_SENTINEL in SYSTEM_INSTRUCTIONS


def test_the_sentinel_forces_zero_confidence(tmp_path):
    """The case that motivates all of this: a fluent refusal scored 0.98."""
    llm = FakeLLM(content=ABSTENTION_SENTINEL)
    answerer = make_answerer(tmp_path, llm_call=llm)
    ans = answerer("what is my rating?", [chunk("something irrelevant")])
    assert ans.confidence == 0.0


def test_a_normal_answer_keeps_its_confidence(tmp_path):
    """The sentinel must not touch good answers."""
    llm = FakeLLM(content="On the 9th")
    answerer = make_answerer(tmp_path, llm_call=llm)
    ans = answerer("which day?", [chunk("charged on the 9th")])
    assert ans.confidence > 0.0


def test_the_sentinel_is_detected_even_with_whitespace(tmp_path):
    """Models add newlines and spaces. Detecting by exact equality would fail on
    one stray `\\n`, and the failure would be invisible: the row would come out
    with high confidence and `abstain.py` would not abstain."""
    llm = FakeLLM(content=f"  {ABSTENTION_SENTINEL}\n")
    answerer = make_answerer(tmp_path, llm_call=llm)
    ans = answerer("what is my rating?", [chunk("something irrelevant")])
    assert ans.confidence == 0.0


def test_the_sentinel_text_travels_intact(tmp_path):
    """`report.py` needs to be able to count abstentions, so the text is kept as
    is: not deleted, not replaced with an empty string."""
    llm = FakeLLM(content=ABSTENTION_SENTINEL)
    answerer = make_answerer(tmp_path, llm_call=llm)
    ans = answerer("what is my rating?", [chunk("something")])
    assert ABSTENTION_SENTINEL in ans.text
