"""
api/_mock_agent.py -- MOCK temporal de Persona 4.

El agente real (agent/answer.py) es responsabilidad de Persona 3 y todavia
no existe. Mientras tanto, esta funcion devuelve un Answer con la forma
EXACTA del contrato C3, para que /ask se pueda construir y probar ya, sin
llamar a Token Factory.

Cuando agent/answer.py exista: el cambio en api/app.py es una linea --
reemplazar el import de aqui por `from agent.answer import answer_question`.
No borrar este archivo sin avisar al equipo; es el mock que documenta la
forma del contrato mientras no esta firmado (dia 5).
"""

from __future__ import annotations

from core.schemas import Answer, Chunk, TierCall


def answer_question(query: str, strategy: str) -> Answer:
    """Misma firma que debera tener agent.answer.answer_question() cuando
    exista de verdad (contrato C3). No hace ninguna llamada externa."""

    fake_chunks = [
        Chunk(
            text=f"[MOCK] fragmento relacionado con: {query!r}",
            item_id="mock-item-1",
            para_path="projects/mock-proyecto",
            ts="2026-09-01T00:00:00Z",
            score=0.87,
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
        text=f"[MOCK] Respuesta simulada para: {query!r} (estrategia={strategy})",
        confidence=0.5,
        provenance=fake_chunks,
        used_web=False,
        tier_calls=[fake_tier_call],
    )
