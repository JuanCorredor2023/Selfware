"""
api/app.py -- Person 4.

FastAPI (src/selfware/api/app.py). /ask (contract C3) against a simulated agent (see
api/_mock_agent.py), with cost (observability/cost.py), OpenTelemetry
traces (observability/otel.py) and the cost ledger (observability/ledger.py)
wired on top of the response's TierCalls. /cost aggregates that ledger.
/para, /projects, /areas, /resources and /archive serve the mocked PARA tree
(api/_mock_para.py) in the shape the real index should provide.
/ask uses the mock agent unless SELFWARE_AGENT=real (api/_real_agent.py).
Still missing: /provenance (its data already travels inside /ask).
"""

import os
from collections.abc import Callable
from dataclasses import asdict
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from selfware.api import _mock_agent
from selfware.api._mock_para import get_category, get_tree
from selfware.core.schemas import Answer
from selfware.observability.cost import with_cost
from selfware.observability.ledger import ledger
from selfware.observability.otel import record_tier_call, setup_tracing

setup_tracing(service_name="atlas-api")


def _load_answer_question() -> Callable[[str, str], Answer]:
    """SELFWARE_AGENT=real wires agent + retrieval + Token Factory (needs
    chromadb, an indexed collection and NEBIUS_API_KEY). Anything else keeps
    the mock agent, which is the default so the app and CI run with no keys."""
    if os.environ.get("SELFWARE_AGENT", "mock").lower() == "real":
        from selfware.api._real_agent import build_answer_question

        return build_answer_question()
    return _mock_agent.answer_question


answer_question = _load_answer_question()

app = FastAPI(title="Atlas / Selfware API")

# Dev only: lets the dashboard (Vite, localhost:5173) call the API
# (localhost:8000) from the browser. Narrow this to the real public
# dashboard URL before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ask")
def ask(q: str, strategy: Literal["flat", "para"] = "para") -> dict:
    """Answers a question. `strategy` picks the index (contract C2).
    Returns the Answer (contract C3) as a dict. Every TierCall the
    response carries gets its cost computed and recorded as an OTel
    span -- today with simulated data (see api/_mock_agent.py), but the
    wiring is real: the day the real agent replaces the mock, this keeps
    working untouched."""
    answer = answer_question(q, strategy)
    for tier_call in answer.tier_calls:
        with_cost(tier_call)
        record_tier_call(tier_call)
    ledger.record_query(answer.tier_calls)
    return asdict(answer)


@app.get("/cost")
def cost() -> dict:
    """Cost panel data (A4): totals, cost per query, average latency and the
    split by model tier, aggregated over every question answered since the
    API started. The prices come from observability/cost.py."""
    return ledger.summary()


@app.get("/para")
def para() -> list[dict]:
    """The four PARA categories with their items, in display order."""
    return get_tree()


@app.get("/projects")
def projects() -> list[dict]:
    return get_category("projects")


@app.get("/areas")
def areas() -> list[dict]:
    return get_category("areas")


@app.get("/resources")
def resources() -> list[dict]:
    return get_category("resources")


@app.get("/archive")
def archive() -> list[dict]:
    return get_category("archive")
