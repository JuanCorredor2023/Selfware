"""
scripts/e2e_smoke.py -- Person 4.

Manual end-to-end smoke test. Makes ONE real call to Token Factory (a
short "ping" prompt, capped output) and pushes it through the exact
same pipeline api/app.py uses for a real /ask: core.llm.call() ->
observability.cost.with_cost() -> observability.otel.record_tier_call().

This is NOT part of `pytest` on purpose -- it costs real money and
needs network access to Nebius, neither of which belongs in the
automated test suite. Run it by hand when you want to confirm the
whole chain (real call, cost math, OTel span) actually works together,
not just that each piece works in isolation against fixtures.

Usage (from the repo root, with .venv active and NEBIUS_API_KEY set):

    python -m scripts.e2e_smoke              # Nano only (cheap, default)
    python -m scripts.e2e_smoke --ultra       # also calls Ultra

Do not add --ultra without knowing why: it costs ~16x more per token
than Nano (see observability/cost.py). For a prompt this short the
absolute cost is still a fraction of a cent, but per AGENTS.md the
rule is "explain purpose, estimate cost, confirm" before touching
Ultra -- this flag existing doesn't waive that, it's just what makes
running it possible once you've decided to.
"""

from __future__ import annotations

import argparse

from core.llm import Tier, call
from observability.cost import with_cost
from observability.otel import record_tier_call, setup_tracing

# Deliberately small: this is a connectivity + wiring check, not a real
# question. max_tokens caps the (paid) output; temperature=0 makes the
# model's reply reproducible run to run.
#
# NOTE: the Nemotron-3 models are "reasoning" models -- they spend
# tokens on an internal chain-of-thought before writing the final
# answer. Three live runs on 2026-09-19 pinned down how much budget
# each tier actually needs for this trivial prompt:
#   max_tokens=8:   Nano content=None, Ultra mid-thought fragment (both cut off)
#   max_tokens=40:  Ultra finishes clean in 29 tokens ("pong"); Nano still
#                    cut off at 40/40, content=None
#   max_tokens=200: Nano finally finishes in 65 tokens ("\npong")
# So Ultra settles in ~29 tokens, Nano needs ~65 -- more than double,
# which is the opposite of what you'd expect from the "cheap and fast"
# tier, and lines up with Nano also being slower here (1115-1437ms vs
# Ultra's 790ms). 100 gives both tiers comfortable headroom by default.
# Confirmed, not just suspected: worth factoring into the agent's real
# token/latency budget once it relies on Nano for fast classification
# calls -- it may not be as fast as the plan assumes. Whether the API
# exposes a way to turn reasoning off (some NVIDIA Nemotron models
# support a "detailed thinking on/off" system-prompt convention) is
# still unverified -- check the model card on Nebius/NVIDIA before
# assuming a parameter name.
PING_MESSAGES = [{"role": "user", "content": "Reply with exactly: pong"}]
MAX_TOKENS = 100


def run_tier(tier: Tier) -> None:
    print(f"\n=== calling {tier} ===")
    text, tier_call = call(tier, PING_MESSAGES, max_tokens=MAX_TOKENS, temperature=0)
    print(f"response text: {text!r}")

    with_cost(tier_call)  # fills tier_call.cost_usd in place
    print(
        f"tokens_in={tier_call.tokens_in} tokens_out={tier_call.tokens_out} "
        f"latency_ms={tier_call.latency_ms:.1f} cost_usd={tier_call.cost_usd:.8f}"
    )

    record_tier_call(tier_call)  # emits the OTel span (printed by the
    # ConsoleSpanExporter above/below this line -- if you see a span
    # with name "token_factory.call" and these same attribute values,
    # observability is wired correctly end to end).


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ultra",
        action="store_true",
        help="Also call Ultra. Costs more per token -- see AGENTS.md before using this.",
    )
    args = parser.parse_args()

    setup_tracing(service_name="e2e-smoke")

    run_tier("nano")
    if args.ultra:
        run_tier("ultra")
    else:
        print("\n(skipped ultra -- pass --ultra to also test it)")


if __name__ == "__main__":
    main()
