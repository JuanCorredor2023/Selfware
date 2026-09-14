"""
observability/cost.py -- Persona 4.

Convierte tokens -> costo en USD por escalon (Nano vs Ultra).

Estado: BORRADOR. Los precios de abajo son placeholders -- hay que
reemplazarlos con los reales de
https://tokenfactory.nebius.com/organization/prices
en cuanto haya cuenta activa.
"""

from core.schemas import TierCall

# TODO(persona-4): reemplazar con precios reales (USD por 1M de tokens)
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
    """Devuelve el mismo TierCall con cost_usd ya calculado."""
    tier_call.cost_usd = estimate_cost_usd(
        tier_call.model, tier_call.tokens_in, tier_call.tokens_out
    )
    return tier_call
