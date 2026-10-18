"""
observability/ledger.py -- Person 4.

In-memory record of every TierCall the API has seen, and the aggregate the
dashboard's cost panel (A4) shows. The cost MATH is not here: each TierCall
arrives with cost_usd already filled by observability.cost.with_cost. This
file only groups and sums.

In-memory means a process restart empties it. That is enough for a live
demo; if the cost history has to survive restarts, the change is local to
this file (swap the list for a table) and nobody else needs to know.
"""

from __future__ import annotations

from threading import Lock

from selfware.core.llm import MODEL_IDS
from selfware.core.schemas import TierCall
from selfware.observability.cost import is_priced

_TIER_BY_MODEL = {model_id: tier for tier, model_id in MODEL_IDS.items()}

TIER_LABEL = {
    "nano": "Nemotron Nano",
    "super": "Nemotron Super",
    "ultra": "Nemotron Ultra",
    "judge": "Qwen3 judge",
    "embedder": "Qwen3 embedder",
    "other": "Other",
}


def tier_of(model: str) -> str:
    """'nano' / 'super' / 'ultra' / 'judge' for a known model id, 'other' for anything else."""
    return _TIER_BY_MODEL.get(model, "other")


class CallLedger:
    def __init__(self) -> None:
        self._lock = Lock()
        self._calls: list[TierCall] = []
        self._query_count = 0

    def record_query(self, tier_calls: list[TierCall]) -> None:
        """Records every TierCall produced while answering ONE question."""
        with self._lock:
            self._calls.extend(tier_calls)
            self._query_count += 1

    def reset(self) -> None:
        with self._lock:
            self._calls.clear()
            self._query_count = 0

    def summary(self) -> dict:
        with self._lock:
            calls = list(self._calls)
            query_count = self._query_count

        total_usd = sum(c.cost_usd for c in calls)
        by_tier: dict[str, dict] = {}
        for c in calls:
            t = by_tier.setdefault(
                tier_of(c.model),
                {"calls": 0, "cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0},
            )
            t["calls"] += 1
            t["cost_usd"] += c.cost_usd
            t["tokens_in"] += c.tokens_in
            t["tokens_out"] += c.tokens_out

        tiers = [
            {
                "tier": tier,
                "label": TIER_LABEL[tier],
                **t,
                "call_share": t["calls"] / len(calls),
                "cost_share": t["cost_usd"] / total_usd if total_usd else 0.0,
            }
            for tier, t in by_tier.items()
        ]
        tiers.sort(key=lambda t: t["cost_usd"], reverse=True)

        return {
            "total_usd": total_usd,
            "per_query_usd": total_usd / query_count if query_count else 0.0,
            "avg_latency_ms": (
                sum(c.latency_ms for c in calls) / len(calls) if calls else 0.0
            ),
            "tokens_in": sum(c.tokens_in for c in calls),
            "tokens_out": sum(c.tokens_out for c in calls),
            "call_count": len(calls),
            "query_count": query_count,
            # Calls whose model has no price: their cost_usd is 0.0, so the
            # total above is understated by the real spend of these calls.
            "unpriced_calls": sum(1 for c in calls if not is_priced(c.model)),
            "tiers": tiers,
        }


# The API's single ledger. Tests reset it between cases.
ledger = CallLedger()
