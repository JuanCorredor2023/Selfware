"""Tests for `eval/ragas_judge.py`. No network, no budget.

**Nothing here imports `ragas` in the test process.** Importing `ragas` runs
`nest_asyncio.apply()` (`ragas/executor.py`, line 15), which patches `asyncio`
for the whole process and, on Python 3.14, breaks `anyio` -- and with it every
FastAPI test that runs after. The one test that needs RAGAS's own wrapper runs
in a fresh interpreter (`run_isolated`).

Skipped as a whole when `ragas` is not installed: its pins are proposed to
Person 1 (D39) and may not be in every environment yet. `find_spec` checks that
without importing it.
"""

import importlib.util
import json
import subprocess
import sys
import textwrap

import pytest

if importlib.util.find_spec("ragas") is None:
    pytest.skip("ragas is not installed (D39)", allow_module_level=True)

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from selfware.core.schemas import TierCall
from selfware.eval.ragas_judge import (
    ROLES,
    TokenFactoryJudge,
    _extract_scores,
    _to_openai_messages,
    make_ragas_judge,
)


def run_isolated(code: str) -> str:
    """Run `code` in a fresh Python, so its imports cannot leak into this one.
    Returns its stdout; a non-zero exit fails the test with its stderr."""
    done = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        capture_output=True,
        check=False,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


# --------------------------------------------------------------------------
# Test doubles
# --------------------------------------------------------------------------


class FakeCall:
    """Toy `core.llm.call`. Records what it got, answers `reply`."""

    def __init__(self, reply: str = '{"verdict": 1}'):
        self.calls = []
        self.reply = reply

    def __call__(self, tier, messages, **kwargs):
        self.calls.append({"tier": tier, "messages": messages, **kwargs})
        tc = TierCall(
            model="judge-x", tokens_in=100, tokens_out=20, latency_ms=1.0, cost_usd=0.0
        )
        return self.reply, tc


# --------------------------------------------------------------------------
# _to_openai_messages
# --------------------------------------------------------------------------


def test_roles_cover_the_three_message_types_ragas_sends():
    assert ROLES == {"system": "system", "human": "user", "ai": "assistant"}


def test_each_type_maps_to_its_openai_role_in_order():
    out = _to_openai_messages(
        [
            SystemMessage(content="be a judge"),
            HumanMessage(content="is this relevant?"),
            AIMessage(content="yes"),
        ]
    )

    assert out == [
        {"role": "system", "content": "be a judge"},
        {"role": "user", "content": "is this relevant?"},
        {"role": "assistant", "content": "yes"},
    ]


def test_an_empty_list_gives_an_empty_list():
    assert _to_openai_messages([]) == []


def test_an_unknown_message_type_raises():
    """A tool message with a guessed role would make the judge answer
    something else, silently."""
    with pytest.raises(ValueError):
        _to_openai_messages([ToolMessage(content="x", tool_call_id="1")])


def test_non_text_content_raises_a_type_error():
    """A multimodal list: the judge only reads text. A wrong TYPE, so
    `TypeError`; a wrong value of the right type would be `ValueError`."""
    message = HumanMessage(content=[{"type": "text", "text": "hi"}])

    with pytest.raises(TypeError, match="list"):
        _to_openai_messages([message])


# --------------------------------------------------------------------------
# TokenFactoryJudge
# --------------------------------------------------------------------------


def test_invoke_goes_through_the_judge_tier():
    fake = FakeCall(reply="the verdict")
    judge = TokenFactoryJudge(llm_call=fake)

    out = judge.invoke([HumanMessage(content="is this relevant?")])

    assert out.content == "the verdict"
    assert fake.calls[0]["tier"] == "judge"
    assert fake.calls[0]["messages"] == [
        {"role": "user", "content": "is this relevant?"}
    ]


def test_it_always_sends_temperature_zero_and_max_tokens():
    """D7: temperature 0 in the whole harness, the judge included."""
    fake = FakeCall()
    judge = TokenFactoryJudge(llm_call=fake, max_tokens=1234)

    judge.invoke([HumanMessage(content="q")])

    assert fake.calls[0]["temperature"] == 0.0
    assert fake.calls[0]["max_tokens"] == 1234


def test_every_call_leaves_its_tier_call():
    """What lets a scoring run report the tokens it consumed."""
    fake = FakeCall()
    judge = TokenFactoryJudge(llm_call=fake)

    judge.invoke([HumanMessage(content="one")])
    judge.invoke([HumanMessage(content="two")])

    assert [tc.tokens_in for tc in judge.tier_calls] == [100, 100]


def test_stop_is_forwarded_only_when_given():
    fake = FakeCall()
    judge = TokenFactoryJudge(llm_call=fake)

    judge.invoke([HumanMessage(content="q")])
    judge.invoke([HumanMessage(content="q")], stop=["\n"])

    assert "stop" not in fake.calls[0]
    assert fake.calls[1]["stop"] == ["\n"]


def test_it_has_no_temperature_attribute_for_ragas_to_overwrite():
    """RAGAS sets `.temperature` on any model that has one (to 1e-8 or more)."""
    assert not hasattr(TokenFactoryJudge(llm_call=FakeCall()), "temperature")


def test_ragas_cannot_change_the_temperature():
    """Through RAGAS's own wrapper, asking for 3 completions at a high
    temperature: every call still goes out at 0. In a fresh interpreter,
    because importing `ragas` patches asyncio for the whole process."""
    out = run_isolated(
        """
        from langchain_core.messages import HumanMessage
        from langchain_core.prompt_values import ChatPromptValue
        from ragas.llms import LangchainLLMWrapper

        from selfware.core.schemas import TierCall
        from selfware.eval.ragas_judge import TokenFactoryJudge

        temps = []
        def fake(tier, messages, **kw):
            temps.append(kw["temperature"])
            return "ok", TierCall("m", 1, 1, 1.0, 0.0)

        wrapper = LangchainLLMWrapper(TokenFactoryJudge(llm_call=fake))
        prompt = ChatPromptValue(messages=[HumanMessage(content="q")])
        result = wrapper.generate_text(prompt, n=3, temperature=0.9)
        print(len(result.generations[0]), sorted(set(temps)))
        """
    )

    assert out == "3 [0.0]"


def test_importing_the_judge_does_not_import_ragas():
    """The API process must never import `ragas`: its `nest_asyncio.apply()`
    would break `/ask`. The adapter needs only `langchain_core`."""
    out = run_isolated(
        """
        import sys
        import selfware.eval.ragas_judge
        print("ragas" in sys.modules)
        """
    )

    assert out == "False"


def test_the_default_call_is_core_llm():
    """By default it leaves through the single exit point, nowhere else."""
    from selfware.core import llm

    assert TokenFactoryJudge().llm_call is llm.call


# --------------------------------------------------------------------------
# R3: _extract_scores (pure, no ragas)
# --------------------------------------------------------------------------

KEY = "llm_context_precision_with_reference"


def test_it_extracts_the_metric_in_order():
    rows = [{KEY: 0.25}, {KEY: 1.0}, {KEY: 0.5}]

    assert _extract_scores(rows, KEY, expected=3) == [0.25, 1.0, 0.5]


def test_scores_come_back_as_plain_floats():
    """RAGAS may hand back ints (a 0/1 verdict) or numpy floats."""
    out = _extract_scores([{KEY: 1}, {KEY: 0}], KEY, expected=2)

    assert out == [1.0, 0.0]
    assert all(type(v) is float for v in out)


def test_nan_passes_through_for_the_scorer_to_refuse():
    """A failed row is NaN, not an exception: `make_ragas_scorer` refuses it
    with the rows named, which says more than a crash here would."""
    out = _extract_scores([{KEY: float("nan")}], KEY, expected=1)

    assert out[0] != out[0]  # NaN is the only value not equal to itself


def test_a_missing_or_extra_row_raises():
    """Scores pair with inputs by position: one row off shifts every score."""
    with pytest.raises(ValueError, match="2"):
        _extract_scores([{KEY: 1.0}], KEY, expected=2)
    with pytest.raises(ValueError):
        _extract_scores([{KEY: 1.0}, {KEY: 1.0}], KEY, expected=1)


def test_a_row_without_the_metric_raises():
    with pytest.raises(ValueError, match="context_recall"):
        _extract_scores([{KEY: 1.0}], "context_recall", expected=1)


# --------------------------------------------------------------------------
# R3: make_ragas_judge
# --------------------------------------------------------------------------


def test_an_unknown_metric_fails_before_anything_runs():
    with pytest.raises(ValueError):
        make_ragas_judge("faithfulness")


def test_nothing_to_judge_returns_nothing_without_importing_ragas():
    out = run_isolated(
        """
        import sys
        from selfware.eval.ragas_judge import make_ragas_judge
        print(make_ragas_judge("context_recall")([]), "ragas" in sys.modules)
        """
    )

    assert out == "[] False"


#: End to end through real RAGAS with a fake judge, in a fresh interpreter.
#: `{reply}` is the JSON the fake judge answers with; prints the scores, the
#: number of judge calls and the set of tiers they went to.
END_TO_END = """
import json, os, warnings
warnings.simplefilter("ignore")
os.environ.pop("OPENAI_API_KEY", None)   # RAGAS's own OpenAI client cannot work
from selfware.core.schemas import TierCall
from selfware.eval.ragas_judge import TokenFactoryJudge, make_ragas_judge
from selfware.eval.ragas_runner import JudgeInput

tiers = []
def fake(tier, messages, **kw):
    tiers.append(tier)
    return json.dumps({reply}), TierCall("judge-x", 50, 10, 1.0, 0.0)

judge = TokenFactoryJudge(llm_call=fake)
inputs = [
    JudgeInput("q1", "flat", "which day?", ("charged on the 9th", "noise"), "the 9th", "x"),
    JudgeInput("q2", "para", "how much?", ("costs 20 dollars",), "20 dollars", "x"),
]
scores = make_ragas_judge("{metric}", judge)(inputs)
print(json.dumps([[round(v, 6) for v in scores], len(tiers), sorted(set(tiers)), len(judge.tier_calls)]))
"""

PRECISION_YES = {"reason": "r", "verdict": 1}
PRECISION_NO = {"reason": "r", "verdict": 0}
RECALL_YES = {"classifications": [{"statement": "s", "reason": "r", "attributed": 1}]}
RECALL_NO = {"classifications": [{"statement": "s", "reason": "r", "attributed": 0}]}


@pytest.mark.parametrize(
    ("metric", "reply", "scores", "calls"),
    [
        # precision: one judge call per retrieved context (2 + 1)
        ("context_precision", PRECISION_YES, [1.0, 1.0], 3),
        ("context_precision", PRECISION_NO, [0.0, 0.0], 3),
        # recall: one judge call per sample
        ("context_recall", RECALL_YES, [1.0, 1.0], 2),
        ("context_recall", RECALL_NO, [0.0, 0.0], 2),
    ],
)
def test_end_to_end_through_real_ragas(metric, reply, scores, calls):
    """Real `ragas.evaluate`, fake judge, no network. Proves at once that the
    scores follow the judge's verdicts, that every call went to the judge tier
    of `core/llm.py` -- RAGAS never built its own OpenAI client -- and that
    nest_asyncio was neutralized: without it every score is NaN."""
    out = json.loads(
        run_isolated(
            END_TO_END.replace("{reply}", repr(reply)).replace("{metric}", metric)
        )
    )

    assert out[0] == pytest.approx(scores)
    assert out[1] == calls
    assert out[2] == ["judge"]
    assert out[3] == calls


def test_asyncio_still_works_after_scoring():
    """`_import_ragas` keeps the real nest_asyncio patch out: a timeout, the
    thing it breaks on Python 3.14, still works afterwards."""
    out = run_isolated(
        """
        import asyncio
        from selfware.eval.ragas_judge import _import_ragas
        _import_ragas()
        async def main():
            await asyncio.wait_for(asyncio.sleep(0), timeout=1)
            return "ok"
        print(asyncio.run(main()))
        """
    )

    assert out == "ok"


def test_ragas_imported_the_plain_way_first_is_refused():
    """Then the real patch is already in, and scoring would silently give NaN."""
    out = run_isolated(
        """
        import ragas
        from selfware.eval.ragas_judge import _import_ragas
        try:
            _import_ragas()
        except RuntimeError:
            print("refused")
        """
    )

    assert out == "refused"
