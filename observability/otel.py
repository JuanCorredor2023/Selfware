"""
observability/otel.py -- Persona 4.

Setup de OpenTelemetry + registro de llamadas a Token Factory como spans.

Decision de diseno, para que quede explicita y se pueda defender en la
firma de contratos: core/llm.py NO importa este archivo. La regla del
monolito dice "ningun modulo importa de otro excepto de core/", y
observability/ es la excepcion cross-cutting ("todos instrumentan", segun
el diagrama de arquitectura) -- pero la excepcion es que TODOS pueden
importar observability/, no que core/ pueda importar hacia afuera. Por
eso: core/llm.py produce un TierCall y lo devuelve; quien lo llama
(api/app.py hoy, agent/ o ingest/ despues) es quien decide instrumentarlo
llamando a record_tier_call(). Asi core/llm.py se mantiene sin
dependencias, y el grep de la URL de Token Factory sigue encontrando un
solo archivo.

Exporter: por ahora a consola (ConsoleSpanExporter). No hay backend de
trazas desplegado todavia -- cuando lo haya, el cambio es local a este
archivo, nadie mas se entera.
"""

from __future__ import annotations

import time

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

from core.schemas import TierCall

_configured = False


def setup_tracing(service_name: str = "atlas-api") -> None:
    """Configura el TracerProvider global una sola vez. Llamarla mas de
    una vez no duplica el processor (es idempotente)."""
    global _configured
    if _configured:
        return
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name})
    )
    # SimpleSpanProcessor exporta cada span apenas termina (sincrono).
    # BatchSpanProcessor lo haria en un hilo aparte y con delay -- bien
    # para produccion con un backend real, mal para consola/tests locales
    # (el hilo puede intentar exportar despues de que el proceso/test ya
    # cerro stdout).
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _configured = True


def record_tier_call(tier_call: TierCall, span_name: str = "token_factory.call") -> None:
    """Emite un span que representa una llamada YA hecha a Token Factory
    (real o simulada). No hace la llamada, solo la registra -- por eso
    reconstruye el tiempo de inicio a partir de latency_ms, para que la
    duracion del span sea la duracion real de la llamada, no el tiempo
    que toma registrar el span."""
    if not _configured:
        setup_tracing()

    tracer = trace.get_tracer(__name__)
    end_ns = time.time_ns()
    start_ns = end_ns - int(tier_call.latency_ms * 1_000_000)

    span = tracer.start_span(span_name, start_time=start_ns)
    span.set_attribute("llm.model", tier_call.model)
    span.set_attribute("llm.tokens_in", tier_call.tokens_in)
    span.set_attribute("llm.tokens_out", tier_call.tokens_out)
    span.set_attribute("llm.latency_ms", tier_call.latency_ms)
    span.set_attribute("llm.cost_usd", tier_call.cost_usd)
    span.end(end_time=end_ns)
