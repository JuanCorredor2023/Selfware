"""
core/schemas.py -- DRAFT.

The real owner of this file is Person 1 (per the plan). This is a
placeholder so we can work in parallel before contracts are signed
(day 5): "Contracts between lanes on day 5, with fake data if needed."

It only includes what Person 4 needs right now: contract C4 (TierCall).
Once Person 1 ships the official schema, this file gets replaced by
theirs and this note goes away.
"""

from dataclasses import dataclass


@dataclass
class TierCall:
    """Contract C4: core/llm.py -> observability/. One entry per call to
    Token Factory (Nano or Ultra)."""

    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float


@dataclass
class Chunk:
    """Contract C2: context -> agent, eval, api. A retrieved snippet,
    with its provenance (so the dashboard can show it, A2)."""

    text: str
    item_id: str
    para_path: str
    ts: str
    score: float


@dataclass
class Answer:
    """Contract C3: agent -> api, eval. The agent's full response."""

    text: str
    confidence: float
    provenance: list[Chunk]
    used_web: bool
    tier_calls: list[TierCall]
