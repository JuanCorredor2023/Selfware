"""The judge RAGAS talks to, routed through `core/llm.py` (D38).

RAGAS does not call a model itself: it asks a LangChain chat model. The lab
prototype (`verificar_ragas.py`) handed it a `ChatOpenAI` built with the Token
Factory URL -- a direct client outside `core/llm.py`, which `CLAUDE.md` and
architecture rule 2 forbid. B4 is still open for the team.

`TokenFactoryJudge` is the way around it: a LangChain chat model whose only job
is to forward each request to `core.llm.call("judge", ...)`. RAGAS believes it is
talking to an ordinary model; every call still leaves through the single exit
point, with no URL and no client here, and each one leaves a `TierCall`, so the
tokens a scoring run spent can be reported.

Two things about how RAGAS 0.3.1 drives a LangChain model, read from its source
(`ragas/llms/base.py`) and the reason for two choices here:

- If the model has a `temperature` attribute, RAGAS **overwrites it** (1e-8, or
  higher when it asks for several completions). D7 wants 0 everywhere, so this
  class has **no** `temperature` attribute and always sends 0.
- If the model has no `n` attribute, RAGAS sends the same prompt `n` times
  instead of asking for `n` completions. Fine: at temperature 0 they agree.

No embeddings model: context precision and context recall -- the two metrics of
H1 -- only use the judge.

**This module must never import `ragas`.** Importing `ragas` runs
`nest_asyncio.apply()` at import time (`ragas/executor.py`, line 15): it patches
`asyncio` for the whole process and, on Python 3.14, breaks `anyio`, which
FastAPI runs on. Imported from the API process, it would take `/ask` down. The
adapter needs only `langchain_core`; whatever does import `ragas` imports it
inside a function, in the evaluation process only. A test checks it.
"""

import sys
import types
from collections.abc import Callable
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from selfware.core.llm import call
from selfware.core.schemas import TierCall
from selfware.eval.ragas_runner import METRICS, JudgeFn, JudgeInput

#: LangChain message type -> the `role` `core.llm.call` (OpenAI format) expects.
ROLES: dict[str, str] = {
    "system": "system",
    "human": "user",
    "ai": "assistant",
}

#: Signature of `core.llm.call`: `(tier, messages, **kwargs) -> (text, TierCall)`.
LLMCall = Callable[..., tuple[str, TierCall]]


def _to_openai_messages(messages: list[BaseMessage]) -> list[dict]:
    """Turn LangChain messages into the `[{"role", "content"}]` of `core.llm`.

    Order is kept: a judge prompt is a system message, then the user's, and
    swapping them changes what the judge is asked.

    Args:
        messages: what RAGAS built, as LangChain `BaseMessage`s. Each has a
            `.type` (a key of `ROLES`) and a `.content`.

    Returns:
        One `{"role": ..., "content": ...}` dict per message, same order.

    Raises:
        ValueError: if a message's `.type` is not in `ROLES` (a tool or
            function message: RAGAS should never send one, and sending it on
            with a guessed role would make the judge answer something else).
            The type is right (a `str`), its value is not.
        TypeError: if its `.content` is not a `str` (a multimodal list: the
            judge only reads text). Here the type itself is wrong.
    """

    openai_messages = []

    for msg in messages:
        if msg.type not in ROLES:
            raise ValueError(f"unsupported message type {msg.type!r}")
        if not isinstance(msg.content, str):
            raise TypeError(
                f"message content must be a str, got {type(msg.content).__name__}"
            )
        openai_messages.append({"role": ROLES[msg.type], "content": msg.content})

    return openai_messages


class TokenFactoryJudge(BaseChatModel):
    """A LangChain chat model that answers through `core.llm.call("judge")`.

    Wrap it for RAGAS with `ragas.llms.LangchainLLMWrapper(TokenFactoryJudge())`.

    Attributes:
        llm_call: the function that talks to Token Factory. `core.llm.call` by
            default; the tests pass a toy one, so no budget is spent on testing.
        max_tokens: room for the judge's JSON verdict. A cut verdict does not
            parse, and RAGAS turns it into NaN, which `make_ragas_scorer`
            refuses: generous on purpose.
        tier_calls: every call made through this judge, in order. What lets a
            scoring run report the tokens it consumed (`CLAUDE.md`).
    """

    llm_call: LLMCall = Field(default=call)
    max_tokens: int = 4096
    tier_calls: list[TierCall] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "token-factory-judge"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        """One call to the judge tier. What LangChain calls under `invoke`.

        `kwargs` from LangChain are ignored on purpose: sampling is fixed here
        (temperature 0, D7), not by whoever drives the model.
        """
        extra = {"stop": stop} if stop else {}
        text, tier_call = self.llm_call(
            "judge",
            _to_openai_messages(messages),
            temperature=0.0,
            max_tokens=self.max_tokens,
            **extra,
        )
        self.tier_calls.append(tier_call)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


# --------------------------------------------------------------------------
# R3: the real judge -- JudgeInputs in, one RAGAS score per input out
# --------------------------------------------------------------------------

#: Marks the do-nothing `nest_asyncio` this module installs (see below).
_NOOP_MARK = "_selfware_noop"


def _import_ragas() -> types.ModuleType:
    """Import `ragas` with `nest_asyncio` neutralized first. Returns `ragas`.

    Why this exists. `ragas` runs `nest_asyncio.apply()` the moment it is
    imported (`ragas/executor.py`, line 15). On Python 3.14, `nest_asyncio`
    1.6.0 breaks asyncio's notion of the current task, and anything with a
    timeout then fails: RAGAS's own executor wraps every metric call in one, so
    **every score came back NaN and the judge was never called**, with
    `RuntimeError: Timeout should be used inside a task`. The lab ran on
    Python 3.12 (D1), where the patch is harmless; the repo is on 3.14.

    What it does. Before `ragas` is imported, it puts in `sys.modules` a
    `nest_asyncio` whose `apply()` does nothing. `ragas` imports that one, the
    real patch never happens, and asyncio keeps working. `nest_asyncio` only
    matters when code runs *inside* an already running event loop (a notebook);
    the evaluation command is a plain script, so nothing needs it.

    It affects this process only, and only from the first call on: the API
    process must still never import `ragas` (module docstring).

    Raises:
        RuntimeError: if `ragas` was already imported without this function --
            the real patch has then been applied and cannot be undone, so
            scoring would silently produce NaN.
    """
    current = sys.modules.get("nest_asyncio")
    already_neutral = getattr(current, _NOOP_MARK, False)
    if "ragas" in sys.modules and not already_neutral:
        raise RuntimeError(
            "ragas was imported before selfware.eval.ragas_judge could neutralize "
            "nest_asyncio; on Python 3.14 every score would come back NaN. "
            "Import ragas only through make_ragas_judge."
        )
    if not already_neutral:
        noop = types.ModuleType("nest_asyncio")
        noop.apply = lambda *args, **kwargs: None
        setattr(noop, _NOOP_MARK, True)
        sys.modules["nest_asyncio"] = noop

    import ragas

    return ragas


def _extract_scores(rows: list[dict], key: str, expected: int) -> list[float]:
    """Pull one metric's scores out of `EvaluationResult.scores`, in order.

    RAGAS 0.3.1 returns `result.scores` as **one dict per sample, in the order
    of the dataset**, keyed by the metric's *internal* name -- e.g.
    `{"llm_context_precision_with_reference": 0.83}` -- read from
    `ragas/evaluation.py`. Not our names: `METRICS` maps ours to its classes,
    and the class carries the key (`metric.name`).

    A failed row is not an exception here: with `raise_exceptions=False` RAGAS
    puts NaN in its place, and `make_ragas_scorer` refuses NaN with the rows
    named. So NaN passes through this function untouched, on purpose.

    Args:
        rows: `result.scores`.
        key: the metric's internal name, `metric_instance.name`.
        expected: how many inputs were sent. The scores are paired with the
            inputs **by position**, so a missing or extra row would put every
            score after it on the wrong question.

    Returns:
        The scores as plain `float`s, in the order of `rows`.

    Raises:
        ValueError: if `len(rows) != expected`, or a row lacks `key` -- both
            mean RAGAS answered something other than what was asked.
    """
    if len(rows) != expected:
        raise ValueError(f"RAGAS returned {len(rows)} rows for {expected} inputs")

    scores = []

    for i, r in enumerate(rows):
        if key not in r:
            raise ValueError(f"row {i} has no {key!r}")
        scores.append(float(r[key]))

    return scores


def make_ragas_judge(
    metric: str,
    judge: TokenFactoryJudge | None = None,
    *,
    show_progress: bool = False,
) -> JudgeFn:
    """Return the real `JudgeFn` for `make_ragas_scorer`, backed by RAGAS.

    The returned function turns the `JudgeInput`s into RAGAS samples, runs
    `ragas.evaluate` with ONE metric and the judge of R2, and returns one score
    per input, in order:

        scorer = make_ragas_scorer("context_precision", make_ragas_judge("context_precision"))

    **`ragas` is imported inside the returned function**, when scoring starts,
    never at module level, and always through `_import_ragas` -- see the module
    docstring and `_import_ragas`: imported plainly, it breaks asyncio on Python
    3.14 and every score comes back NaN.

    **The judge is always passed to `evaluate`.** Given no `llm`, RAGAS builds a
    default OpenAI client of its own (`llm_factory()`), which would leave
    through api.openai.com, outside `core/llm.py`. A test checks that the judge
    received every call.

    `response` is sent although neither metric of H1 reads it (their required
    columns are `user_input`, `retrieved_contexts` and `reference`): it keeps the
    samples complete, and a metric that needs it can be added without changing
    the inputs.

    Args:
        metric: a key of `METRICS`. Checked here, before any credit is spent.
        judge: the `TokenFactoryJudge` to use. Pass your own to read its
            `tier_calls` afterwards (the tokens a run spent); `None` builds one
            on `core.llm.call`.
        show_progress: RAGAS's progress bar. Off by default: tests and logs.

    Raises:
        ValueError: here, for an unknown `metric`.
    """
    if metric not in METRICS:
        raise ValueError(f"unknown metric {metric!r}; expected one of {list(METRICS)}")
    judge = judge or TokenFactoryJudge()

    def run(inputs: list[JudgeInput]) -> list[float]:
        if not inputs:
            return []

        _import_ragas()
        import ragas.metrics
        from ragas import EvaluationDataset, SingleTurnSample, evaluate
        from ragas.llms import LangchainLLMWrapper

        instance = getattr(ragas.metrics, METRICS[metric])()
        samples = [
            SingleTurnSample(
                user_input=i.user_input,
                retrieved_contexts=list(i.retrieved_contexts),
                reference=i.reference,
                response=i.response,
            )
            for i in inputs
        ]
        result = evaluate(
            dataset=EvaluationDataset(samples=samples),
            metrics=[instance],
            llm=LangchainLLMWrapper(judge),
            raise_exceptions=False,
            show_progress=show_progress,
        )
        return _extract_scores(result.scores, instance.name, len(inputs))

    return run
