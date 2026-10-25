"""
scripts/_tally.py -- Person 3.

Counts the Token Factory spend of a script run, per tier, without touching the
modules that make the calls. `context/` throws away the `TierCall` that
`core.llm.call` and `core.llm.embed` return, so the composition root wraps the
name those modules imported and reads the `TierCall` on its way back.

    tally = Tally()
    tally.wrap(selfware.context.classifier, "call")
    tally.wrap(selfware.context.embedder, "embed")
    ...
    print(tally.summary())

Only token counts and cost are kept: never the prompt or the response.
"""

import threading
from collections import defaultdict
from types import ModuleType

from selfware.core.schemas import TierCall
from selfware.observability.cost import estimate_cost_usd


class Tally:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.calls: dict[str, int] = defaultdict(int)
        self.tokens_in: dict[str, int] = defaultdict(int)
        self.tokens_out: dict[str, int] = defaultdict(int)
        self.cost_usd: dict[str, float] = defaultdict(float)

    def add(self, tier_call: TierCall | None) -> None:
        if tier_call is None:
            return
        with self._lock:
            model = tier_call.model
            self.calls[model] += 1
            self.tokens_in[model] += tier_call.tokens_in
            self.tokens_out[model] += tier_call.tokens_out
            self.cost_usd[model] += estimate_cost_usd(
                model, tier_call.tokens_in, tier_call.tokens_out
            )

    def wrap(self, module: ModuleType, name: str) -> None:
        """Replace `module.name` (a function returning `(x, TierCall)`) with one
        that records the `TierCall` and returns the same tuple."""
        original = getattr(module, name)

        def counted(*args, **kwargs):
            result = original(*args, **kwargs)
            self.add(result[1])
            return result

        setattr(module, name, counted)

    def total_usd(self) -> float:
        return sum(self.cost_usd.values())

    def summary(self) -> str:
        lines = [
            f"  {model}: {self.calls[model]} calls, {self.tokens_in[model]:,} in, "
            f"{self.tokens_out[model]:,} out, ~US${self.cost_usd[model]:.4f}"
            for model in sorted(self.calls)
        ]
        lines.append(f"  total ~US${self.total_usd():.4f}")
        return "\n".join(lines)
