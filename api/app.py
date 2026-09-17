"""
api/app.py -- Persona 4.

FastAPI. Semana 2: se agrega /ask (contrato C3), todavia contra un agente
simulado (ver api/_mock_agent.py) porque agent/answer.py (Persona 3) no
esta listo. Faltan /provenance, /cost, /projects.
"""

from dataclasses import asdict
from typing import Literal

from fastapi import FastAPI

from api._mock_agent import answer_question  # TODO(persona-3): swap por agent.answer

app = FastAPI(title="Atlas / Selfware API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ask")
def ask(q: str, strategy: Literal["flat", "para"] = "para") -> dict:
    """Responde una pregunta. `strategy` elige el indice (contrato C2).
    Devuelve el Answer (contrato C3) como dict."""
    answer = answer_question(q, strategy)
    return asdict(answer)
