"""
src/selfware/api/_mock_agent.py -- Person 4's TEMPORARY mock.

The real agent is wired in api/_real_agent.py and used with
SELFWARE_AGENT=real. This mock is the default: it returns an Answer with the
EXACT shape of contract C3, so /ask, the dashboard and CI run without calling
Token Factory.

The two strategies return plausibly DIFFERENT answers on purpose, so the
flat/PARA toggle visibly changes something in a demo:

  * PARA -> fewer, on-topic chunks from the right PARA folder, higher
            confidence, a small Nano step plus one Ultra answer call.
  * flat -> mixed chunks (some stale or unrelated), lower confidence, one
            bigger Ultra call because more context is stuffed in.

A question that matches no known topic gets the low-confidence fallback
that also "searches the web" (used_web=True). The data mirrors
web/src/mocks/answers.js, which the dashboard uses on its own until it is
wired to this API.

MOCK CONVENTION: web results are chunks whose item_id starts with "web:"
and whose para_path is "web". Confirm against Person 3's real contract
before relying on it.

Once agent/answer.py exists: the change in api/app.py is one line --
swap this import for `from agent.answer import answer_question`.
Don't delete this file without telling the team; it's the mock that
documents the contract's shape while it isn't signed yet (day 5).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from selfware.core.llm import MODEL_IDS
from selfware.core.schemas import Answer, Chunk, TierCall

NANO = MODEL_IDS["nano"]
ULTRA = MODEL_IDS["ultra"]

# (model, tokens_in, tokens_out, latency_ms). cost_usd is NOT set here:
# api/app.py fills it with observability.cost.with_cost, same as it will
# for the real agent's TierCalls.
_CallSpec = tuple[str, int, int, float]


@dataclass(frozen=True)
class _Variant:
    text: str
    confidence: float
    chunks: tuple[Chunk, ...]
    calls: tuple[_CallSpec, ...]


@dataclass(frozen=True)
class _Topic:
    pattern: re.Pattern
    para: _Variant
    flat: _Variant


def _chunk(
    text: str, item_id: str, para_path: str, ts: str, similarity: float
) -> Chunk:
    """`ts` is written as an ISO string for readability and parsed into the
    datetime that contract C2 requires."""
    return Chunk(
        text=text,
        item_id=item_id,
        para_path=para_path,
        ts=datetime.fromisoformat(ts),
        similarity=similarity,
    )


_TOPICS = [
    _Topic(
        pattern=re.compile(r"thesis|advisor|defen[cs]e|committee", re.IGNORECASE),
        para=_Variant(
            text=(
                "Your thesis defense is on October 22, 2026 at 10:00. Dr. Ramirez "
                "confirmed the committee and asked for the final draft two weeks "
                "before the date."
            ),
            confidence=0.93,
            chunks=(
                _chunk(
                    "Confirming the defense for Thursday, October 22 at 10:00 in room B-204. The committee is Ramirez, Ortiz and Vega.",
                    "msg-3812",
                    "projects/thesis",
                    "2026-09-24T14:12:00Z",
                    0.94,
                ),
                _chunk(
                    "Please send the final draft no later than October 8 so the committee can read it before the defense.",
                    "msg-3790",
                    "projects/thesis",
                    "2026-09-19T09:40:00Z",
                    0.89,
                ),
                _chunk(
                    "Reminder: the defense slides must be uploaded to the department portal 48 hours in advance.",
                    "msg-3744",
                    "projects/thesis",
                    "2026-09-11T17:05:00Z",
                    0.81,
                ),
                _chunk(
                    "Graduation paperwork opens the week after the defense; bring your student ID.",
                    "msg-3611",
                    "areas/university",
                    "2026-09-02T11:30:00Z",
                    0.72,
                ),
            ),
            calls=((NANO, 610, 95, 310.0), (ULTRA, 1850, 210, 1400.0)),
        ),
        flat=_Variant(
            text=(
                "Your thesis defense appears to be in October, but the emails "
                "disagree: one mentions October 22 and an older one proposed a date "
                "in November. The most recent message says October 22."
            ),
            confidence=0.71,
            chunks=(
                _chunk(
                    "Confirming the defense for Thursday, October 22 at 10:00 in room B-204.",
                    "msg-3812",
                    "projects/thesis",
                    "2026-09-24T14:12:00Z",
                    0.86,
                ),
                _chunk(
                    "We could tentatively schedule the defense for the second week of November, pending the committee.",
                    "msg-3402",
                    "areas/university",
                    "2026-08-14T08:20:00Z",
                    0.79,
                ),
                _chunk(
                    "Weekly digest: three new papers on retrieval evaluation and a defense-day checklist template.",
                    "msg-3701",
                    "resources/ml-papers",
                    "2026-09-08T06:00:00Z",
                    0.68,
                ),
                _chunk(
                    "Final presentation for the internship is scheduled for Friday at 15:00.",
                    "msg-1954",
                    "archive/summer-internship-2025",
                    "2025-08-28T16:45:00Z",
                    0.61,
                ),
            ),
            calls=((ULTRA, 3120, 235, 1930.0),),
        ),
    ),
    _Topic(
        pattern=re.compile(r"trip|flight|hotel|travel|vacation", re.IGNORECASE),
        para=_Variant(
            text=(
                "The year-end trip is on hold. The last email (July 2) has a "
                "round-trip flight quote of $412 that expired on August 15, and "
                "nothing has been booked since."
            ),
            confidence=0.88,
            chunks=(
                _chunk(
                    "Flight quote: round trip, December 20 to January 3, $412 per person. Valid until August 15.",
                    "msg-2988",
                    "projects/year-end-trip",
                    "2026-07-02T10:15:00Z",
                    0.92,
                ),
                _chunk(
                    "Let's decide about the hotel once we know the flights. Holding off for now.",
                    "msg-2971",
                    "projects/year-end-trip",
                    "2026-06-28T19:02:00Z",
                    0.84,
                ),
            ),
            calls=((NANO, 590, 90, 300.0), (ULTRA, 1420, 180, 1250.0)),
        ),
        flat=_Variant(
            text=(
                "There is a flight quote of $412 for December, but I also found an "
                "unrelated apartment listing and a hotel receipt from an old trip, "
                "so I can't tell whether anything is booked."
            ),
            confidence=0.63,
            chunks=(
                _chunk(
                    "Flight quote: round trip, December 20 to January 3, $412 per person.",
                    "msg-2988",
                    "projects/year-end-trip",
                    "2026-07-02T10:15:00Z",
                    0.83,
                ),
                _chunk(
                    "Your hotel reservation has been confirmed. Check-in: March 3, 2024.",
                    "msg-1102",
                    "archive/apartment-2024",
                    "2024-02-10T12:00:00Z",
                    0.70,
                ),
                _chunk(
                    "Monthly statement: travel and lodging category totals.",
                    "msg-3655",
                    "areas/finances",
                    "2026-09-05T07:30:00Z",
                    0.64,
                ),
            ),
            calls=((ULTRA, 2860, 210, 1780.0),),
        ),
    ),
    _Topic(
        pattern=re.compile(
            r"hackathon|atlas|nebius|nvidia|submission|deadline", re.IGNORECASE
        ),
        para=_Variant(
            text=(
                "The hackathon submission deadline is October 27. Your team agreed "
                "to freeze features on October 20 and record the demo video by "
                "October 24."
            ),
            confidence=0.90,
            chunks=(
                _chunk(
                    "Reminder: submissions close October 27 at 23:59 UTC. Include the repo link, video and a short write-up.",
                    "msg-3830",
                    "projects/atlas-hackathon",
                    "2026-09-29T08:00:00Z",
                    0.95,
                ),
                _chunk(
                    "Proposed timeline: feature freeze Oct 20, demo video Oct 24, buffer for fixes until the 27th.",
                    "msg-3821",
                    "projects/atlas-hackathon",
                    "2026-09-27T21:14:00Z",
                    0.88,
                ),
                _chunk(
                    "Judges will review the repository, so keep it in English and document how to run it.",
                    "msg-3760",
                    "projects/atlas-hackathon",
                    "2026-09-15T13:22:00Z",
                    0.79,
                ),
            ),
            calls=((NANO, 620, 92, 305.0), (ULTRA, 1760, 190, 1330.0)),
        ),
        flat=_Variant(
            text=(
                "The submission deadline seems to be October 27, but I also see a "
                "different deadline from a newsletter about another competition, so "
                "treat this with caution."
            ),
            confidence=0.74,
            chunks=(
                _chunk(
                    "Reminder: submissions close October 27 at 23:59 UTC.",
                    "msg-3830",
                    "projects/atlas-hackathon",
                    "2026-09-29T08:00:00Z",
                    0.87,
                ),
                _chunk(
                    "Call for entries: the ML systems competition closes on November 3. Register now.",
                    "msg-3699",
                    "resources/ml-papers",
                    "2026-09-07T06:00:00Z",
                    0.75,
                ),
                _chunk(
                    "Deadline to file the university enrollment form is October 1.",
                    "msg-3688",
                    "areas/university",
                    "2026-09-06T09:10:00Z",
                    0.66,
                ),
            ),
            calls=((ULTRA, 3300, 220, 1990.0),),
        ),
    ),
]


def _tier_calls(specs: tuple[_CallSpec, ...]) -> list[TierCall]:
    # Fresh objects on every request: api/app.py mutates them (cost_usd).
    return [
        TierCall(model=m, tokens_in=i, tokens_out=o, latency_ms=lat, cost_usd=0.0)
        for m, i, o, lat in specs
    ]


def _fallback(query: str, strategy: str) -> Answer:
    """No topic matched: low confidence, and the agent 'searches the web'."""
    is_para = strategy == "para"
    web_ts = "2026-09-29T12:00:00Z"
    chunks = [
        _chunk(
            f"Newsletter mentioning a topic related to “{query}”, without the details you asked about.",
            "msg-3702",
            "resources/ml-papers" if is_para else "areas/university",
            "2026-09-08T06:00:00Z",
            0.34 if is_para else 0.29,
        ),
        _chunk(
            f"Reference guide with a step-by-step explanation related to “{query}”.",
            "web:docs.example.org/guide",
            "web",
            web_ts,
            0.81,
        ),
        _chunk(
            "Community answer summarizing the common approach and its caveats.",
            "web:stackoverflow.example.com/questions/1234",
            "web",
            web_ts,
            0.74,
        ),
    ]
    calls = (
        ((NANO, 600, 90, 300.0), (ULTRA, 1500, 170, 1300.0), (ULTRA, 2300, 260, 1800.0))
        if is_para
        else ((ULTRA, 3000, 210, 1850.0), (ULTRA, 2300, 260, 1800.0))
    )
    return Answer(
        text=(
            "I couldn't find this in your email, so I searched the web. The "
            "results below cover the topic in general terms; I could not check "
            "them against anything you wrote, so please verify before relying "
            "on them."
        ),
        confidence=0.38 if is_para else 0.31,
        provenance=chunks,
        used_web=True,
        finish_reason="stop",
        tier_calls=_tier_calls(calls),
    )


def answer_question(query: str, strategy: str) -> Answer:
    """Same signature agent.answer.answer_question() will have to have
    once it's real (contract C3). Makes no external calls."""
    for topic in _TOPICS:
        if topic.pattern.search(query):
            variant = topic.flat if strategy == "flat" else topic.para
            return Answer(
                text=variant.text,
                confidence=variant.confidence,
                provenance=list(variant.chunks),
                used_web=False,
                finish_reason="stop",
                tier_calls=_tier_calls(variant.calls),
            )
    return _fallback(query, strategy)
