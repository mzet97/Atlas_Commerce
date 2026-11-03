"""Uvicorn entry: atlas-order API (owner writes live here)."""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .api import app

_resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "atlas-order")})
_provider = TracerProvider(resource=_resource)
_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(_provider)
PymongoInstrumentor().instrument()
FastAPIInstrumentor.instrument_app(app)

__all__ = ["app"]
