"""
api/app.py -- Persona 4.

FastAPI. Semana 2: /ask (contrato C3) contra un agente simulado (ver
api/_mock_agent.py), con costo (observability/cost.py) y trazas de
OpenTelemetry (observability/otel.py) ya conectados sobre los TierCall
que trae la respuesta. Faltan /provenance, /cost, /projects.
"""

from dataclasses import asdict
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api._mock_agent import answer_question  # TODO(persona-3): swap por agent.answer
from observability.cost import with_cost
from observability.otel import record_tier_call, setup_tracing

setup_tracing(service_name="atlas-api")

app = FastAPI(title="Atlas / Selfware API")

# Dev only: permite que el dashboard (Vite, localhost:5173) llame a la API
# (localhost:8000) desde el navegador. Antes de desplegar hay que acotar
# esto a la URL publica real del dashboard.
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
    """Responde una pregunta. `strategy` elige el indice (contrato C2).
    Devuelve el Answer (contrato C3) como dict. Cada TierCall que trae la
    respuesta se le calcula el costo y se registra como span de OTel --
    hoy son datos simulados (ver api/_mock_agent.py), pero el cableado es
    real: el dia que el agente real reemplace al mock, esto sigue
    funcionando sin tocarlo."""
    answer = answer_question(q, strategy)
    for tier_call in answer.tier_calls:
        with_cost(tier_call)
        record_tier_call(tier_call)
    return asdict(answer)
