"""
api/_calls.py -- Person 4.

TierCalls made while answering one question that are NOT in `Answer.tier_calls`
(today: the PARA query classifier, which runs inside retrieval, before the agent
sees anything). `/ask` collects them per request and adds them to the answer, so
they are priced, traced and counted in /cost like any other call.

Per-request through a ContextVar: /ask handles requests in worker threads, each
with its own context, so concurrent questions do not mix their calls.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from selfware.core.schemas import TierCall

_current: ContextVar[list[TierCall] | None] = ContextVar(
    "extra_tier_calls", default=None
)


@contextmanager
def track_extra_calls() -> Iterator[list[TierCall]]:
    """Inside the block, `note_tier_call` appends to the yielded list."""
    calls: list[TierCall] = []
    token = _current.set(calls)
    try:
        yield calls
    finally:
        _current.reset(token)


def note_tier_call(tier_call: TierCall) -> None:
    """No-op outside `track_extra_calls` (e.g. scripts, tests)."""
    calls = _current.get()
    if calls is not None:
        calls.append(tier_call)
