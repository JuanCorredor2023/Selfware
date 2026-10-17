"""The agent: question + chunks -> answer with provenance. Contract C3.

It is the only module in the project that spends money, so almost everything
here is in place so as not to spend it twice:

- The prompt is assembled with the fixed prefix first (D15), so that Nebius
  caches that prefix and the ~132 calls of a run pay for it once.
- Before calling, the on-disk cache is consulted (D16). An interrupted run does
  not pay again for what was already answered.
- With zero chunks **the model is not called**: there is nothing to answer from,
  and by D8 that case can be frequent in the PARA arm.

This module does not decide to abstain. It produces a `confidence` and
`abstain.py` compares it against a threshold, in Python code (D13). The model
never chooses its own path.

NOTE ON LANGUAGE. Everything the model actually reads -- `SYSTEM_INSTRUCTIONS`,
the section labels in `build_prompt`, and `ABSTENTION_SENTINEL` -- is kept in
Spanish on purpose. It is experiment data, not prose:

  1. The prompt string is part of the cache key (D16), so translating it
     invalidates all 53 cached entries and the run has to be paid again.
  2. The `expected` answers in the question set are written in Spanish. A model
     answering in English would be judged by RAGAS against Spanish references.
  3. The R18 measurement (0 of 8 false positives from the sentinel) was taken
     with exactly this wording. Change the wording and the number no longer
     describes what is running.
"""

from collections.abc import Callable
from pathlib import Path

from selfware.agent.cache import cache_key, load, save
from selfware.agent.confidence import TokenLogprob, confidence
from selfware.core.llm import MODEL_IDS, LLMResult, Tier, call_with_logprobs
from selfware.core.schemas import Answer, Chunk

#: Signature of `core.llm.call_with_logprobs`: `(tier, messages, **params)`.
#: `make_answerer` receives one of these instead of building a client, so the
#: tests pass a toy one and no budget is spent on testing.
LLMCall = Callable[..., LLMResult]

#: Fixed prompt prefix. It is a module constant on purpose: Nebius' prefix cache
#: requires this text to be **byte-for-byte identical** between calls. If it were
#: assembled with f-strings or rewritten per call, the prefix would change and
#: nothing would be cached.
#:
#: Spanish on purpose -- see the NOTE ON LANGUAGE in the module docstring.
SYSTEM_INSTRUCTIONS = """\
Respondes preguntas sobre el correo personal de una persona, usando únicamente los \
fragmentos que se te dan.

Reglas:
- Usa SOLO la información de los fragmentos. No completes con conocimiento propio.
- Si los fragmentos no contienen la respuesta, responde EXACTAMENTE con esta línea y \
nada más: SIN_RESPUESTA_EN_FRAGMENTOS
- Responde de forma breve y directa, sin repetir la pregunta.
- Si la pregunta pide una fecha, un monto o un número, dalo tal como aparece.\
"""

#: The abstention sentinel (R18). When the model emits this string, `_answer`
#: forces `confidence = 0.0`.
#:
#: Why it is needed. It was measured on 20 Sep that `generation_confidence` does
#: **not** distinguish a correct answer from a refusal, and that the signal is in
#: fact inverted: refusals scored a median of 0.982 against 0.967 for good
#: answers. The reason is that the metric rewards predictability, and "the
#: chunks do not contain that information" is a boilerplate phrase, whereas a
#: reference number or a date are specific and therefore improbable tokens. No
#: threshold separates the two groups.
#:
#: What this is NOT. It is not the model deciding to abstain: the model only
#: reports a fact about the chunks in front of it. The decision to abstain is
#: taken by `abstain.py` comparing against a threshold, in Python (D13). There
#: is still no tool calling.
#:
#: Why an uppercase string with underscores: it does not occur in natural prose,
#: so a false positive by coincidence is near impossible, and it is stable under
#: tokenization.
#:
#: The VALUE stays in Spanish -- see the NOTE ON LANGUAGE in the module
#: docstring. It appears verbatim inside SYSTEM_INSTRUCTIONS, and both are part
#: of the cache key.
#:
#: Risk that has to be measured, not assumed: that the model emits the sentinel
#: when it COULD have answered. That is checked against the answerable set -- if
#: any question that used to answer correctly starts abstaining, the sentinel is
#: costing retrieval and the wording of the rule needs revisiting.
ABSTENTION_SENTINEL = "SIN_RESPUESTA_EN_FRAGMENTOS"

#: Factory mark for the D8 case: there was no call to the server, so there is no
#: real `finish_reason`. Since it is not `"stop"`, the harness flags the row and
#: it stays out of the average without review. In the report it is told apart
#: from a truncated answer by looking at `n_chunks`: zero is missing retrieval,
#: not truncation.
NO_CHUNKS = "no_chunks"


def build_prompt(question: str, chunks: list[Chunk], profile: str | None = None) -> str:
    """Assemble the final prompt sent to the model.

    Order (D15), and the order is money:

        [fixed instructions] -> [profile] -> [chunks] -> [question]

    Nebius caches prefixes. The ~132 calls of a run share the instructions word
    for word, so with this order the prefix is cached and paid for in full only
    once. With the question at the start, every call would be a different prefix
    and nothing would be cached. It is verified by looking at
    `prompt_cache_hit_tokens` in the response: if it stays at 0 run after run,
    the prompt is in the wrong order.

    The profile (contract C5, comes from `WhoareU.md`) goes next to the prefix
    because it is constant for the whole run. If it varied per question, it
    would break the cache.

    From each chunk the text and its date are included, numbered from 1. The date
    is there because a good part of the question set asks *when* something
    happened, and it is structured data the model cannot reliably pull out of the
    text.

    **`para_path` is NOT included, on purpose.** It is the label under test:
    putting it in the prompt would let the model reason about the PARA structure
    directly. And since in the PARA arm every chunk would come from the same
    folder while in the flat arm they would be mixed, the model could notice that
    difference and the experiment would stop measuring retrieval and start
    measuring something else.

    Notice what this signature does NOT receive: **`strategy`**. By construction
    it is impossible for the two arms to receive prompts in different formats,
    which is what the protocol in section 3 requires and what would otherwise
    have to be remembered.

    The literal section labels are in Spanish on purpose -- see the NOTE ON
    LANGUAGE in the module docstring.

    Args:
        question: the question, as is.
        chunks: the retrieved chunks, already sorted by relevance (D9).
        profile: context about the owner of the mailbox, or `None`.

    Returns:
        The complete text, ready to send.
    """

    parts = []

    parts.append(SYSTEM_INSTRUCTIONS)

    if profile:
        parts.append(f"Contexto sobre la persona:\n{profile}")

    for i, chunk in enumerate(chunks, start=1):
        parts.append(f"[{i}] ({chunk.ts.strftime('%d %b %Y')}) {chunk.text}")

    parts.append(f"Pregunta:\n{question}")

    prompt = "\n\n".join(parts)
    return prompt


def to_token_logprobs(logprobs_content) -> list[TokenLogprob]:
    """Convert per-token logprobs into the `TokenLogprob`s of `confidence.py`.

    Accepts any sequence of objects with `.token` and `.logprob`: what
    `core.llm.LLMResult.tokens` carries, and also the SDK's
    `response.choices[0].logprobs.content`. Moving them into our dataclass keeps
    `confidence.py` independent of both.

    Args:
        logprobs_content: the token list, or `None` if the server returned no
            logprobs. Note that `core.llm.call_with_logprobs` turns "no logprobs"
            into an **empty list** without complaining, so the empty case is
            the one that actually arrives here.

    Returns:
        The same sequence, in our type, in the same order. The order matters:
        `answer_tokens` cuts at `</think>` counting from the start (D14).

    Raises:
        ValueError: if `logprobs_content` is `None` or comes back empty. We
            always ask for `logprobs=True`, so not receiving them means something
            changed on the server side. Silently returning an empty list would
            give confidence 0.0 to an answer that might have been good, and that
            row would abstain for no reason.
    """

    if not logprobs_content:
        raise ValueError("empty logprobs")

    tokens = []

    for token in logprobs_content:
        tokenlog = TokenLogprob(token=token.token, logprob=token.logprob)
        tokens.append(tokenlog)

    return tokens


def make_answerer(
    cache_dir: Path,
    *,
    tier: Tier = "ultra",
    llm_call: LLMCall = call_with_logprobs,
    profile: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4000,
) -> Callable[[str, list[Chunk]], Answer]:
    """Return the `answer` function the harness consumes.

    Answering for real needs the model tier, the cache folder and the sampling
    parameters. But the harness expects a two-argument function (`AnswerFn`).
    This factory receives everything else **once** and returns a function
    matching that contract:

        answerer = make_answerer(Path(".cache"))
        records = run(questions, retrieve_fake, answerer, k=5)

    It is the same pattern as `answer_simple()` in the harness tests: a function
    that returns another function.

    Every call to Token Factory goes through `core/llm.py` (architecture rule
    2): this module never builds a client nor names the API URL. Going through
    `call_with_logprobs` is also what fills `Answer.tier_calls`, which is what
    `/cost` and the ledger read.

    Everything after `cache_dir` is keyword-only on purpose. The old signature
    was `make_answerer(client, model, cache_dir)`; a caller still written that
    way now fails loudly with a `TypeError` instead of silently passing a
    client where a path should go.

    Args:
        cache_dir: on-disk cache folder (D16).
        tier: which model answers, as a `core.llm` tier. `"ultra"` by D5. The
            cache key uses the full model id, `MODEL_IDS[tier]`, not the tier
            name: that is the string the cache was keyed with before this
            module went through `core/llm.py`, so the entries already on disk
            stay valid.
        llm_call: the function that talks to Token Factory. Defaults to
            `core.llm.call_with_logprobs`. It is **received** so the tests can
            pass a toy one and no budget is spent on testing.
        profile: context about the mailbox owner (C5), constant during the run.
        temperature: **always 0 in the harness** (D7). Without determinism there
            is no way to tell whether a change in the number came from a change
            of our own or from chance.
        max_tokens: it has to leave room for the reasoning **plus** the answer.
            Measured: 56 of 60 output tokens were reasoning (93%). A `max_tokens`
            tuned to the answer cuts the reasoning off and produces systematic
            truncation (D17).

    Returns:
        A function `(question, chunks) -> Answer` which, in this order:

        1. If `chunks` comes in empty, it **does not call the model** and returns
           an `Answer` with `text=""`, `confidence=0.0` and
           `finish_reason=NO_CHUNKS`. With no chunks there is nothing to answer
           from, and by D8 this case can be frequent in the PARA arm: paying for
           those calls would be paying to fail.
        2. Builds the prompt with `build_prompt`.
        3. Computes the key with `cache_key(prompt, MODEL_IDS[tier], params)`
           and checks the cache.
        4. If there is nothing cached, calls `llm_call(tier, messages, **params)`
           -- the **same** `params` dict that went into the key, so what is sent
           and what is cached can never drift apart -- and stores the result.
        5. Computes `confidence(tokens, chunks)` and assembles the `Answer`.

        `used_web` is always `False` here: Tavily is used *after* abstaining, and
        that is decided by `abstain.py` (D13).

        `tier_calls` holds the call's `TierCall` when the model was actually
        called, and is **empty** on a cache hit or with no chunks. That is the
        honest record: a cache hit cost nothing, and reporting the original
        call again would make `/cost` count the same spend twice.

    What goes into the cache: the text, the `finish_reason` and the tokens with
    their logprobs -- **not the already-computed `confidence`**. The reason is
    D24: if the confidence formula is ever changed everything has to be
    recomputed, and with the raw data on disk that costs not one extra call.
    Storing the computed number would mean paying for the whole run again.

    `provenance` is not stored either: the caller already has the chunks, and
    since they are part of the prompt, they are part of the key. They match by
    construction.
    """

    def _answer(question: str, chunks: list[Chunk]) -> Answer:
        if not chunks:
            return Answer(
                text="",
                confidence=0.0,
                provenance=[],
                used_web=False,
                finish_reason=NO_CHUNKS,
            )

        prompt = build_prompt(question, chunks, profile)

        params = {
            "temperature": temperature,
            "max_tokens": max_tokens,
            "logprobs": True,
            "top_logprobs": 5,
        }
        key = cache_key(prompt, MODEL_IDS[tier], params)
        cached = load(cache_dir, key)

        if cached is None:
            messages = [{"role": "user", "content": prompt}]
            result = llm_call(tier, messages, **params)
            text = result.text
            finish_reason = result.finish_reason
            tokens = to_token_logprobs(result.tokens)
            tier_calls = [result.tier_call]

            save(
                cache_dir,
                key,
                {
                    "text": text,
                    "finish_reason": finish_reason,
                    "tokens": [
                        {"token": t.token, "logprob": t.logprob} for t in tokens
                    ],
                },
            )
        else:
            text = cached["text"]
            finish_reason = cached["finish_reason"]
            tokens = [
                TokenLogprob(token=d["token"], logprob=d["logprob"])
                for d in cached["tokens"]
            ]
            tier_calls = []

        if ABSTENTION_SENTINEL in text:
            return Answer(
                text=text,
                confidence=0.0,
                provenance=chunks,
                used_web=False,
                finish_reason=finish_reason,
                tier_calls=tier_calls,
            )

        return Answer(
            text=text,
            confidence=confidence(tokens, chunks),
            provenance=chunks,
            used_web=False,
            finish_reason=finish_reason,
            tier_calls=tier_calls,
        )

    return _answer
