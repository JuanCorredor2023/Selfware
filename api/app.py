"""
api/app.py -- Person 4.

FastAPI. Week 2: /ask (contract C3) against a simulated agent (see
api/_mock_agent.py), with cost (observability/cost.py) and OpenTelemetry
traces (observability/otel.py) already wired on top of the response's
TierCalls. Still missing /provenance, /cost, /projects.
"""

from dataclasses import asdict
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api._mock_agent import answer_question  # TODO(person-3): swap for agent.answer
from observability.cost import with_cost
from observability.otel import record_tier_call, setup_tracing

setup_tracing(service_name="atlas-api")

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
    return asdict(answer)
