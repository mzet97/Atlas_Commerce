"""Atlas M1 smoke API: health + readiness + first OTel trace.

Proves: FastAPI boots, Mongo replica set reachable, Redis reachable,
and spans export to the OTLP collector. NOT a domain service.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
import redis.asyncio as aioredis

MONGO_URL = os.environ["MONGO_URL"]
REDIS_URL = os.environ["REDIS_URL"]

_resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "atlas-smoke-api")})
_provider = TracerProvider(resource=_resource)
_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(_provider)
PymongoInstrumentor().instrument()
RedisInstrumentor().instrument()

app = FastAPI(title="atlas-smoke-api")
FastAPIInstrumentor.instrument_app(app)

_mongo = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
_redis = aioredis.from_url(REDIS_URL, socket_timeout=5)


def _trace_id() -> str:
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx.is_valid else "none"


@app.get("/health")
async def health() -> JSONResponse:
    await _mongo.admin.command("ping")
    await _redis.ping()
    return JSONResponse({"status": "ok", "mongo": "ok", "redis": "ok", "trace_id": _trace_id()})


@app.get("/ready")
async def ready() -> JSONResponse:
    try:
        await _mongo.admin.command("ping")
        mongo = "ok"
    except Exception:
        mongo = "fail"
    try:
        await _redis.ping()
        redis_state = "ok"
    except Exception:
        redis_state = "fail"
    code = 200 if mongo == "ok" and redis_state == "ok" else 503
    return JSONResponse(
        {"status": "ready" if code == 200 else "not-ready", "mongo": mongo, "redis": redis_state},
        status_code=code,
    )
