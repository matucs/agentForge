"""OpenTelemetry tracing (spec §16). Spans are always real — only the
export target differs based on configuration: a real OTLP exporter if
OTEL_EXPORTER_OTLP_ENDPOINT is set, otherwise a console exporter so the
project still works, and still produces real spans, with zero external
dependencies (spec's "local fallback" requirement).
"""

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)

from app.config import get_settings

_CONFIGURED = False


def configure_tracing() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: "agentforge-backend"}))

    if settings.otel_exporter_otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        otlp_exporter = OTLPSpanExporter(
            endpoint=f"{settings.otel_exporter_otlp_endpoint}/v1/traces"
        )
        # Batching genuinely matters for a real network export target.
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    else:
        # SimpleSpanProcessor (synchronous, no background export thread) —
        # BatchSpanProcessor's worker thread can outlive a short-lived
        # process (e.g. a test run or `make eval` invocation) and crash on
        # shutdown trying to write to an already-closed stdout. Console
        # export is local/low-volume anyway, so batching buys nothing here.
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _CONFIGURED = True


def get_tracer(name: str) -> trace.Tracer:
    configure_tracing()
    return trace.get_tracer(name)
