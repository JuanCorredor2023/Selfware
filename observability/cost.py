"""
observability/cost.py -- Person 4.

Converts tokens -> USD cost per tier (Nano vs Ultra).

Status: real prices, region eu-north1, from
https://tokenfactory.nebius.com/organization/prices (checked 2026-09-19).
Nano's prices are valid from 01 Jan 2026, Ultra's from 01 Jun 2026 -- if
Nebius publishes a new price list, update this table and re-check both
"valid from" dates.

Batch pricing (cheaper, asynchronous) also exists for both models but
isn't used here -- core/llm.py only makes synchronous calls today. Add a
"batch" variant to this table if/when that changes.
"""

from core.schemas import TierCall

# USD per 1,000,000 tokens. Keys MUST match core.llm.MODEL_IDS values
# exactly (case-sensitive) -- that's the only thing that connects a real
# TierCall.model string to a price here. A key that doesn't match falls
# through to $0.0 in estimate_cost_usd() below, silently.
PRICE_PER_MILLION_TOKENS_USD = {
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": {"input": 0.06, "output": 0.24},
    "nvidia/Nemotron-3-Ultra-550b-a55b": {"input": 1.00, "output": 3.00},
}


def estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    prices = PRICE_PER_MILLION_TOKENS_USD.get(model)
    if prices is None:
        return 0.0
    return (tokens_in * prices["input"] + tokens_out * prices["output"]) / 1_000_000


def with_cost(tier_call: TierCall) -> TierCall:
    """Returns the same TierCall with cost_usd filled in."""
    tier_call.cost_usd = estimate_cost_usd(
        tier_call.model, tier_call.tokens_in, tier_call.tokens_out
    )
    return tier_call
