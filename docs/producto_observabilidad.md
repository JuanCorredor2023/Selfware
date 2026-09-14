# Persona 4 — Producto y observabilidad (borrador de contrato)

> Borrador para la firma de contratos del día 5. Tres párrafos: qué hace, qué expone, qué consume.

## Qué hace

Este módulo es "la evidencia": todo lo que el juez del hackathon ve en vivo, y el único punto de salida del proyecto hacia Nebius Token Factory. Cubre cuatro carpetas: `core/llm.py` (cliente único a Token Factory, enruta entre Nemotron Nano y Nemotron Ultra), `observability/` (OpenTelemetry + cálculo de costo por escalón), `api/` (FastAPI que expone el sistema) y `web/` (dashboard en React).

## Qué expone

La API expone `/health` (listo desde semana 1), y próximamente `/ask` y `/ask?strategy=flat|para` (pregunta al agente, eligiendo estrategia de recuperación), `/provenance` (procedencia de una respuesta: carpeta PARA + correos + fechas), `/cost` (panel de costo por escalón: % Nano vs Ultra, costo por consulta, latencia) y `/projects` (tracker de proyectos derivado de PARA). El dashboard expone el toggle en vivo plano vs PARA (A1), la procedencia visible (A2) y el panel de costo (A4).

## Qué consume

Del agente (contrato C3) consume `Answer(text, confidence, provenance, used_web, tier_calls)` para armar la respuesta de `/ask`. Del módulo de contexto (contrato C2) consume indirectamente `retrieve(query, strategy, k)` a través del parámetro `strategy` de `/ask`. Y genera él mismo, en `core/llm.py`, el contrato C4 (`TierCall`) que alimenta tanto el panel de costo como el reporte de evaluación de Persona 3.
