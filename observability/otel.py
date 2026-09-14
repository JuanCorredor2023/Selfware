"""
observability/otel.py -- Persona 4.

Setup de OpenTelemetry para instrumentar core/llm.py y api/app.py.

Estado: pendiente. Semana 1 solo necesitamos que TierCall exista y se
pueda loguear (ver core/llm.py). La instrumentacion real con OTel (spans,
exporter) es tarea de semana 2-3 segun el plan.
"""


def setup_tracing(service_name: str = "atlas-api") -> None:
    """TODO(persona-4, semana 2): configurar TracerProvider + exporter y
    envolver cada llamada de core/llm.py en un span."""
    raise NotImplementedError("Pendiente para semana 2-3 del plan.")
