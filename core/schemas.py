"""
core/schemas.py — BORRADOR.

El dueño real de este archivo es Persona 1 (segun el plan). Esto es un
placeholder para poder trabajar en paralelo antes de la firma de contratos
(dia 5): "Contratos entre carriles el dia 5 con datos falsos si hace falta."

Solo incluye lo que Persona 4 necesita ya: el contrato C4 (TierCall).
Cuando Persona 1 suba el schema oficial, este archivo se reemplaza por el
suyo y se borra esta nota.
"""

from dataclasses import dataclass


@dataclass
class TierCall:
    """Contrato C4: core/llm.py -> observability/. Una entrada por cada
    llamada a Token Factory (Nano o Ultra)."""

    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float
