"""
core/llm.py -- UNICO cliente del proyecto hacia Nebius Token Factory.

Regla del equipo: ningun otro modulo debe llamar directamente a Token
Factory. Un grep por "tokenfactory.nebius.com" en el repo debe encontrar
exactamente este archivo.

Estado: BORRADOR -- Persona 4, semana 1 (reinicio).
Falta:
  - API key real (esperando aprobacion de Nebius Builder Program / creditos
    del hackathon)
  - Confirmar los identificadores exactos de modelo en
    https://tokenfactory.nebius.com/models/catalog una vez haya acceso
  - Precios reales por modelo en
    https://tokenfactory.nebius.com/organization/prices
    (observability/cost.py tiene un placeholder)
"""

from __future__ import annotations

import os
import time
from typing import Literal

from openai import OpenAI
from dotenv import load_dotenv

from core.schemas import TierCall

# Carga el archivo local de desarrollo sin sobrescribir una variable de entorno
# ya configurada por el entorno de despliegue. El archivo .env está ignorado por Git.
load_dotenv()

BASE_URL = "https://api.tokenfactory.nebius.com/v1/"

# Confirmados el 2026-09-13 en el catálogo de la cuenta de Token Factory.
# Conservamos los IDs con las mayúsculas exactas que expone el servicio.
MODEL_IDS = {
    "nano": "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",
    "ultra": "nvidia/Nemotron-3-Ultra-550b-a55b",
}

Tier = Literal["nano", "ultra"]

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """Crea (una sola vez) el cliente OpenAI-compatible hacia Token Factory."""
    global _client
    if _client is None:
        api_key = os.environ.get("NEBIUS_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Falta NEBIUS_API_KEY. Copia .env.example a .env y pon tu "
                "key de https://tokenfactory.nebius.com/project/api-keys"
            )
        _client = OpenAI(base_url=BASE_URL, api_key=api_key)
    return _client


def call(tier: Tier, messages: list[dict], **kwargs) -> tuple[str, TierCall]:
    """
    Unico punto de entrada del proyecto a Token Factory.

    Args:
        tier: "nano" (clasificacion PARA, barato) o "ultra" (agente de
            respuesta, razonamiento).
        messages: mensajes estilo OpenAI chat
            ([{"role": ..., "content": ...}]).

    Returns:
        (texto_de_respuesta, TierCall) -- TierCall es el contrato C4 hacia
        observability/.
    """
    client = _get_client()
    model = MODEL_IDS[tier]

    start = time.perf_counter()
    response = client.chat.completions.create(
        model=model, messages=messages, **kwargs
    )
    latency_ms = (time.perf_counter() - start) * 1000

    text = response.choices[0].message.content
    usage = response.usage

    tier_call = TierCall(
        model=model,
        tokens_in=usage.prompt_tokens if usage else 0,
        tokens_out=usage.completion_tokens if usage else 0,
        latency_ms=latency_ms,
        cost_usd=0.0,  # TODO(persona-4): calcular con observability/cost.py
    )

    return text, tier_call


if __name__ == "__main__":
    # Smoke test manual: python -m core.llm
    # Una sola llamada barata a Nano, con salida acotada. No usar Ultra para
    # comprobar credenciales o conectividad.
    text, tc = call(
        "nano",
        [{"role": "user", "content": "Responde exactamente: OK"}],
        max_tokens=4,
        temperature=0,
    )
    print(f"[nano smoke test] {text!r}")
    print(f"  TierCall: {tc}")
