"""
observability/cost.py -- Person 4.

Converts tokens -> USD cost per tier (Nano vs Ultra).

Status: DRAFT. Prices below are placeholders -- replace them with the
real ones from https://tokenfactory.nebius.com/organization/prices once
the account is active.
"""

from core.schemas import TierCall

# TODO(person-4): replace with real prices (USD per 1M tokens)
PRICE_PER_MILLION_TOKENS_USD = {
    "nvidia/nemotron-3-nano-30b-a3b": {"input": 0.0, "output": 0.0},
    "nvidia/nemotron-3-ultra-550b-a55b": {"input": 0.0, "output": 0.0},
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
