"""
core/llm.py -- SINGLE client for this project to Nebius Token Factory.

Team rule: no other module should call Token Factory directly. A grep for
"tokenfactory.nebius.com" across the repo must find exactly this file.

Status: DRAFT -- Person 4, week 1 (restart).
Real per-model pricing lives in observability/cost.py, keyed by the
exact MODEL_IDS strings below (case-sensitive).
"""

from __future__ import annotations

import os
import time
from typing import Literal

from openai import OpenAI
from dotenv import load_dotenv

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
}

Tier = Literal["nano", "ultra"]

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


def call(tier: Tier, messages: list[dict], **kwargs) -> tuple[str, TierCall]:
    """
    The project's single entry point to Token Factory.

    Args:
        tier: "nano" (PARA classification, cheap) or "ultra" (answering
            agent, real reasoning).
        messages: OpenAI-style chat messages
            ([{"role": ..., "content": ...}]).

    Returns:
        (response_text, TierCall) -- TierCall is contract C4 towards
        observability/.
    """
    client = _get_client()
    model = MODEL_IDS[tier]

    start = time.perf_counter()
    response = client.chat.completions.create(model=model, messages=messages, **kwargs)
    latency_ms = (time.perf_counter() - start) * 1000

    text = response.choices[0].message.content
    usage = response.usage

    tier_call = TierCall(
        model=model,
        tokens_in=usage.prompt_tokens if usage else 0,
        tokens_out=usage.completion_tokens if usage else 0,
        latency_ms=latency_ms,
        cost_usd=0.0,  # TODO(person-4): compute via observability/cost.py
    )

    return text, tier_call


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
