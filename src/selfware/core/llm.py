"""
core/llm.py -- SINGLE client for this project to Nebius Token Factory.

Team rule: no other module should call Token Factory directly. A grep for
"tokenfactory.nebius.com" across the repo must find exactly this file.

Owner: Person 4. Two entry points: call() returns just the text;
call_with_logprobs() also returns finish_reason and per-token logprobs.
Real per-model pricing lives in observability/cost.py, keyed by the
exact MODEL_IDS strings below (case-sensitive).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI

from selfware.core.schemas import TierCall

# Loads the local dev .env file without overriding a variable already set
# by the deployment environment. .env is gitignored.
load_dotenv()

BASE_URL = "https://api.tokenfactory.nebius.com/v1/"

# Confirmed on 2026-09-13 in the Token Factory account's model catalog.
# We keep the exact casing the service exposes.
MODEL_IDS = {
    "nano": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    "ultra": "nvidia/Nemotron-3-Ultra-550b-a55b",
    # Mid-size Nemotron (120B, 12B active). Id as listed in the Token Factory
    # model catalog on 2026-09-30 -- note the lowercase, unlike Nano.
    "super": "nvidia/nemotron-3-super-120b-a12b",
    # The RAGAS judge must be a DIFFERENT model from the generator (D12),
    # otherwise the metric measures whether the model agrees with itself.
    # Chosen 2026-09-20; the catalog also lists Qwen/Qwen3-30B-A3B-Instruct-2507
    # as a cheaper fallback (priced in observability/cost.py).
    "judge": "Qwen/Qwen3-235B-A22B-Instruct-2507",
    "embedder":"Qwen/Qwen3-Embedding-8B" 
}

Tier = Literal["nano", "super", "ultra", "judge"]

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Builds (once) the OpenAI-compatible client pointed at Token Factory."""
    global _client
    if _client is None:
        api_key = os.environ.get("NEBIUS_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Missing NEBIUS_API_KEY. Copy .env.example to .env and set "
                "your key from https://tokenfactory.nebius.com/project/api-keys"
            )
        _client = OpenAI(base_url=BASE_URL, api_key=api_key)
    return _client


def _request(tier: Tier, messages: list[dict], **kwargs):
    """One chat completion against Token Factory, timed.

    Returns (raw SDK response, TierCall). Shared by call() and
    call_with_logprobs() so the timing and token accounting exist once.
    """
    client = _get_client()
    model = MODEL_IDS[tier]

    start = time.perf_counter()
    response = client.chat.completions.create(model=model, messages=messages, **kwargs)
    latency_ms = (time.perf_counter() - start) * 1000

    usage = response.usage
    tier_call = TierCall(
        model=model,
        tokens_in=usage.prompt_tokens if usage else 0,
        tokens_out=usage.completion_tokens if usage else 0,
        latency_ms=latency_ms,
        # Filled by whoever instruments the call: observability.cost.with_cost.
        # core/ does not import observability/ (see observability/otel.py).
        cost_usd=0.0,
    )
    return response, tier_call


def call(tier: Tier, messages: list[dict], **kwargs) -> tuple[str, TierCall]:
    """
    The project's single entry point to Token Factory.

    Args:
        tier: "nano" (PARA classification, cheap), "super" (mid-size
            Nemotron), "ultra" (answering agent, real reasoning) or
            "judge" (evaluation metric model).
        messages: OpenAI-style chat messages
            ([{"role": ..., "content": ...}]).

    Returns:
        (response_text, TierCall) -- TierCall is contract C4 towards
        observability/.

    Only the text comes back. When the caller also needs the finish reason
    or the per-token logprobs (the agent's confidence), use
    call_with_logprobs() instead.
    """
    response, tier_call = _request(tier, messages, **kwargs)
    return response.choices[0].message.content, tier_call


@dataclass(frozen=True)
class TokenLogprob:
    """One generated token and the log-probability the model gave it."""

    token: str
    logprob: float


@dataclass
class LLMResult:
    """Everything the agent needs from one call: the text, WHY it ended, the
    per-token logprobs (for the confidence score) and the cost record."""

    text: str
    finish_reason: str
    tokens: list[TokenLogprob]
    tier_call: TierCall


def call_with_logprobs(tier: Tier, messages: list[dict], **kwargs) -> LLMResult:
    """Like call(), but keeps what call() throws away.

    Asks the server for logprobs (pass `top_logprobs=N` in kwargs if the
    alternatives are wanted too) and returns them with the finish_reason.

    finish_reason is whatever the server said: anything other than "stop"
    means the answer was cut short (for example "length" when max_tokens ran
    out -- reasoning models spend most of their budget thinking, so this
    happens). If the server sends none it is reported as "unknown", never
    silently treated as a normal end.
    """
    kwargs.setdefault("logprobs", True)
    response, tier_call = _request(tier, messages, **kwargs)
    choice = response.choices[0]

    content = choice.logprobs.content if choice.logprobs else None
    tokens = [TokenLogprob(token=t.token, logprob=t.logprob) for t in content or []]

    return LLMResult(
        text=choice.message.content,
        finish_reason=choice.finish_reason or "unknown",
        tokens=tokens,
        tier_call=tier_call,
    )

def embed(texts: list[str], **kwargs):
    """
    Embeddings against Token Factory. Parallel to call(), but hits the
    embeddings endpoint instead of chat completions.

    Args:
        texts: the strings to embed. The caller applies any query/document
            prefix BEFORE calling this -- embed() is prefix-agnostic, it just
            turns text into vectors (asymmetric retrieval logic lives in the
            retrieval lane, not here).
        **kwargs: forwarded to the endpoint (e.g. dimensions=1024 to truncate
            via MRL; omitted here means the model's default dimension).

    Returns:
        (vectors, TierCall) -- vectors[i] corresponds to texts[i], order
        preserved by sorting on the response's .index. TierCall is the same
        cost/telemetry contract call() returns, with tokens_out=0 because the
        embeddings endpoint generates no completion tokens.
    """

    client = _get_client()
    model  = MODEL_IDS["embedding"]

    start = time.perf_counter()
    response = client.embeddings.create(model=model, input=texts, **kwargs)
    latency_ms = (time.perf_counter() - start) * 1000

    ordered = sorted(response.data, key=lambda item: item.index)
    vectors = [item.embedding for item in ordered]

    usage = response.usage
    tier_call = TierCall(
        model=model,
        tokens_in=usage.prompt_tokens if usage else 0,
        tokens_out=0,
        latency_ms=latency_ms,
        # Filled by whoever instruments the call: observability.cost.with_cost.
        # core/ does not import observability/ (see observability/otel.py).
        cost_usd=0.0,
    )
    return vectors, tier_call


if __name__ == "__main__":
    # Manual smoke test: python -m selfware.core.llm
    # A single cheap call to Nano, with capped output. Never use Ultra to
    # check credentials or connectivity.
    text, tc = call(
        "nano",
        [{"role": "user", "content": "Reply with exactly: OK"}],
        max_tokens=4,
        temperature=0,
    )
    print(f"[nano smoke test] {text!r}")
    print(f"  TierCall: {tc}")
