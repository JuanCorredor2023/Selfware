"""
observability/otel.py -- Person 4.

OpenTelemetry setup + recording Token Factory calls as spans.

Design decision, spelled out so it can be defended at contract sign-off:
core/llm.py does NOT import this file. The monolith rule says "no module
imports another except core/", and observability/ is the cross-cutting
exception ("everyone instruments", per the architecture diagram) -- but
the exception is that EVERYONE can import observability/, not that core/
can import outward. So: core/llm.py produces a TierCall and returns it;
whoever calls it (api/app.py today, agent/ or ingest/ later) decides
whether to instrument it by calling record_tier_call(). That keeps
core/llm.py dependency-free, and grepping for the Token Factory URL still
finds exactly one file.

Exporter: console for now (ConsoleSpanExporter). There's no tracing
backend deployed yet -- when there is, the change is local to this file,
nobody else needs to know.
"""

from __future__ import annotations

import time

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

from selfware.core.schemas import TierCall

_configured = False


def setup_tracing(service_name: str = "atlas-api") -> None:
    """Configures the global TracerProvider once. Idempotent -- calling
    it more than once does not duplicate the processor."""
    global _configured
    if _configured:
        return
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    # SimpleSpanProcessor exports each span as soon as it ends (sync).
    # BatchSpanProcessor would do it on a background thread with a delay
    # -- good for production with a real backend, bad for a console
    # exporter / local tests (the background thread can try to export
    # after the process/test has already closed stdout).
    provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _configured = True


def record_tier_call(
    tier_call: TierCall, span_name: str = "token_factory.call"
) -> None:
    """Emits a span representing a call to Token Factory that ALREADY
    happened (real or simulated). It doesn't make the call, only records
    it -- that's why it reconstructs the start time from latency_ms, so
    the span's duration reflects the actual call duration, not the time
    it takes to record the span."""
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
