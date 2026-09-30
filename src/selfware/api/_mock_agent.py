"""
api/_mock_agent.py -- Person 4's TEMPORARY mock.

The real agent (agent/answer.py) is Person 3's responsibility and doesn't
exist yet. In the meantime, this function returns an Answer with the
EXACT shape of contract C3, so /ask can be built and tested now, without
calling Token Factory.

Once agent/answer.py exists: the change in api/app.py is one line --
swap this import for `from agent.answer import answer_question`.
Don't delete this file without telling the team; it's the mock that
documents the contract's shape while it isn't signed yet (day 5).
"""

from __future__ import annotations

from datetime import UTC, datetime

from selfware.core.schemas import Answer, Chunk, TierCall


def answer_question(query: str, strategy: str) -> Answer:
    """Same signature agent.answer.answer_question() will have to have
    once it's real (contract C3). Makes no external calls."""

    fake_chunks = [
        Chunk(
            text=f"[MOCK] snippet related to: {query!r}",
            item_id="mock-item-1",
            para_path="projects/mock-project",
            ts=datetime(2026, 9, 1, tzinfo=UTC),
            similarity=0.87,
        ),
    ]

    fake_tier_call = TierCall(
        model="mock/no-model",
        tokens_in=0,
        tokens_out=0,
        latency_ms=0.0,
        cost_usd=0.0,
    )

    return Answer(
        text=f"[MOCK] Simulated answer for: {query!r} (strategy={strategy})",
        confidence=0.5,
        provenance=fake_chunks,
        used_web=False,
        finish_reason="stop",
        tier_calls=[fake_tier_call],
    )
