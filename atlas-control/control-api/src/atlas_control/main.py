"""Uvicorn entry: Control API (lifespan builds per-loop clients)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .ai_ops import router as ai_router
from .auth import Forbidden
from .catalog_ops import router as catalog_router
from .command_channel import Unauthorized
from .finance_ops import router as finance_router
from .fulfillment_ops import router as fulfillment_router
from .order_ops import router as order_router
from .pricing_ops import router as pricing_router
from .stock_ops import router as stock_router

_resource = Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "atlas-control")})
_provider = TracerProvider(resource=_resource)
_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(_provider)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Pool + config per running loop; closed on shutdown."""
    app.state.issuer = os.environ["KEYCLOAK_ISSUER"]
    app.state.catalog_url = os.environ["CATALOG_API_URL"]
    app.state.offers_url = os.environ["OFFERS_API_URL"]
    app.state.inventory_url = os.environ["INVENTORY_API_URL"]
    app.state.payment_url = os.environ["PAYMENT_API_URL"]
    app.state.order_url = os.environ["ORDER_API_URL"]
    app.state.pool = await asyncpg.create_pool(os.environ["CONTROL_PG_DSN"])
    app.state.atlas_pool = await asyncpg.create_pool(os.environ["ATLAS_PG_DSN"])
    try:
        yield
    finally:
        await app.state.atlas_pool.close()
        await app.state.pool.close()


app = FastAPI(title="atlas-control", lifespan=lifespan)
app.include_router(catalog_router)
app.include_router(pricing_router)
app.include_router(stock_router)
app.include_router(order_router)
app.include_router(finance_router)
app.include_router(fulfillment_router)
app.include_router(ai_router)
FastAPIInstrumentor.instrument_app(app)


@app.exception_handler(Unauthorized)
async def _unauthorized(_request: Request, exc: Unauthorized) -> JSONResponse:
    return JSONResponse({"detail": exc.detail}, status_code=401)


@app.exception_handler(Forbidden)
async def _forbidden(_request: Request, exc: Forbidden) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=403)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
