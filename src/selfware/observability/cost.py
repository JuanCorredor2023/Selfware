"""
observability/cost.py -- Person 4.

Converts tokens -> USD cost per model (Nano, Super, Ultra and the eval judge).

Status: real prices, region eu-north1, from
https://tokenfactory.nebius.com/organization/prices (checked 2026-09-19).
Nano's prices are valid from 01 Jan 2026, Ultra's from 01 Jun 2026 -- if
Nebius publishes a new price list, update this table and re-check both
"valid from" dates.

Batch pricing (cheaper, asynchronous) also exists for both models but
isn't used here -- core/llm.py only makes synchronous calls today. Add a
"batch" variant to this table if/when that changes.
"""

import logging

from selfware.core.schemas import TierCall

logger = logging.getLogger(__name__)

# USD per 1,000,000 tokens. Keys MUST match core.llm.MODEL_IDS values
# exactly (case-sensitive) -- that's the only thing that connects a real
# TierCall.model string to a price here. A key that doesn't match falls
# through to $0.0 in estimate_cost_usd() below, silently.
PRICE_PER_MILLION_TOKENS_USD = {
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": {"input": 0.06, "output": 0.24},
    "nvidia/Nemotron-3-Ultra-550b-a55b": {"input": 1.00, "output": 3.00},
    # Nemotron Super (core.llm.MODEL_IDS["super"]). Source: model-catalog.md,
    # checked 2026-09-30; confirm on the organization price page like the judge.
    "nvidia/nemotron-3-super-120b-a12b": {"input": 0.30, "output": 0.90},
    # Evaluation judge (core.llm.MODEL_IDS["judge"]) and its cheaper fallback.
    # Source: https://tokenfactory.nebius.com/model-catalog.md, checked
    # 2026-09-30. The catalog does not state region or a valid-from date:
    # confirm against the organization price page like the two above.
    "Qwen/Qwen3-235B-A22B-Instruct-2507": {"input": 0.20, "output": 0.60},
    "Qwen/Qwen3-30B-A3B-Instruct-2507": {"input": 0.10, "output": 0.30},
     "Qwen/Qwen3-Embedding-8B": {"input": 0.01, "output": 0.0},
}

# Models already reported as unpriced, so the warning is logged once each.
_warned_models: set[str] = set()


def is_priced(model: str) -> bool:
    """True if the price table knows this exact model id."""
    return model in PRICE_PER_MILLION_TOKENS_USD


def estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    prices = PRICE_PER_MILLION_TOKENS_USD.get(model)
    if prices is None:
        # Returning 0.0 keeps an already-paid answer from being lost to a
        # bookkeeping gap, but it must never be SILENT: the spend is real and
        # this number understates it. Logged once per model here, and counted
        # in GET /cost (`unpriced_calls`) so the dashboard can say so.
        if model not in _warned_models:
            _warned_models.add(model)
            logger.warning(
                "No price for model %r in observability/cost.py: its calls are "
                "reported as $0.00, so the total cost is understated.",
                model,
            )
        return 0.0
    return (tokens_in * prices["input"] + tokens_out * prices["output"]) / 1_000_000


def with_cost(tier_call: TierCall) -> TierCall:
    """Returns the same TierCall with cost_usd filled in."""
    tier_call.cost_usd = estimate_cost_usd(
        tier_call.model, tier_call.tokens_in, tier_call.tokens_out
    )
    return tier_call
