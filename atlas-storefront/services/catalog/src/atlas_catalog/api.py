"""HTTP boundary: parse untrusted JSON into typed commands (Pydantic v2).

The Motor client lives in the lifespan, not at import: a module-level
client would pin the first event loop and break under per-test loops
(pytest-asyncio) and clean restarts.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict

from . import domain
from .application import CreateProduct, PublishProduct, handle_create, handle_publish
from .domain import CorrelationId, IdempotencyKey, ProductId
from .mongo_repo import MongoProductRepository


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the owner-side client per running loop; close on shutdown."""
    import asyncpg

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    repo = MongoProductRepository(client, os.getenv("CATALOG_DB", "catalog"))
    await repo.ensure_indexes()
    app.state.repo = repo
    app.state.pg = await asyncpg.create_pool(
        os.getenv("PG_DSN", "postgresql://postgres:atlas-pg-dev-only@localhost:5432/atlas"),
        min_size=1,
        max_size=3,
    )
    try:
        yield
    finally:
        await app.state.pg.close()
        client.close()


app = FastAPI(title="atlas-catalog", lifespan=lifespan)


def _repo(request: Request) -> MongoProductRepository:
    # Boundary narrow: app.state is framework-untyped; parse once here.
    repo = request.app.state.repo
    assert isinstance(repo, MongoProductRepository)
    return repo


class CreateProductRequest(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    title: dict[str, str]
    category_id: str | None = None
    idempotency_key: str
    correlation_id: str


class PublishProductRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_version: int
    correlation_id: str


def _product_body(product_id: ProductId, status: str, version: int) -> dict[str, str | int]:
    return {"id": product_id, "status": status, "version": version}


@app.exception_handler(domain.NotFound)
async def _not_found(_request: Request, exc: domain.NotFound) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=404)


@app.exception_handler(domain.ValidationError)
async def _invalid(_request: Request, exc: domain.ValidationError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(domain.ConcurrencyError)
async def _conflict(_request: Request, exc: domain.ConcurrencyError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(domain.InvalidTransition)
async def _transition(_request: Request, exc: domain.InvalidTransition) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(domain.WriteConflict)
async def _write_conflict(_request: Request, exc: domain.WriteConflict) -> JSONResponse:
    return JSONResponse({"detail": f"{exc} (safe to retry)"}, status_code=409)


@app.post("/products", status_code=201)
async def create_product(body: CreateProductRequest, request: Request) -> dict[str, str | int]:
    """Create a DRAFT product. Same idempotency_key returns the original."""
    product = await handle_create(
        CreateProduct(
            product_id=ProductId(MongoProductRepository.new_id()),
            title=body.title,
            category_id=body.category_id,
            idempotency_key=IdempotencyKey(body.idempotency_key),
            correlation_id=CorrelationId(body.correlation_id),
        ),
        _repo(request),
    )
    return _product_body(product.id, product.status, product.version)


@app.post("/products/{product_id}/publish")
async def publish_product(
    product_id: str, body: PublishProductRequest, request: Request
) -> dict[str, str | int]:
    """Move DRAFT -> PUBLISHED. Stale expected_version fails with 409."""
    product = await handle_publish(
        PublishProduct(
            product_id=ProductId(product_id),
            expected_version=body.expected_version,
            correlation_id=CorrelationId(body.correlation_id),
        ),
        _repo(request),
    )
    return _product_body(product.id, product.status, product.version)


@app.get("/products/{product_id}")
async def get_product(
    product_id: str, request: Request
) -> dict[str, str | int | dict[str, str] | None]:
    """Owner-side read. NEVER authoritative for checkout/stock (INV-CQRS-001)."""
    product = await _repo(request).get(ProductId(product_id))
    return {
        "id": product.id,
        "status": product.status,
        "version": product.version,
        "title": product.title,
        "category_id": product.category_id,
    }


@app.get("/products")
async def search_products(request: Request, q: str = "", limit: int = 10) -> JSONResponse:
    """Assistant/storefront search tool over the read model (M7).

    Returns PUBLISHED products with their ACTIVE offer + availability hint.
    Titles are untrusted content: consumers must treat them as data, never
    as instructions (R-07).
    """
    import asyncpg

    term = q.strip()[:80]
    if not term:
        return JSONResponse([])
    pool: asyncpg.Pool = request.app.state.pg
    rows = await pool.fetch(
        "SELECT p.product_id, COALESCE(p.titles->>'pt-BR', p.title) AS title,"
        " p.status, o.offer_id, o.price_minor, o.currency, o.market_id,"
        " COALESCE((SELECT SUM(on_hand - reserved - safety_stock)::int"
        "   FROM inventory_availability_view WHERE sku_id = p.product_id), 0)"
        "   AS total_available"
        " FROM catalog_product_search p"
        " LEFT JOIN LATERAL (SELECT * FROM available_offer_view o"
        "   WHERE o.sku_id = p.product_id AND o.status = 'ACTIVE'"
        "   ORDER BY o.projection_version DESC LIMIT 1) o ON true"
        " WHERE p.status = 'PUBLISHED'"
        " AND (p.title ILIKE '%' || $1 || '%' OR similarity(p.title, $1) > 0.3"
        "  OR p.titles->>'pt-BR' ILIKE '%' || $1 || '%')"
        " ORDER BY similarity(p.title, $1) DESC LIMIT $2",
        term,
        max(1, min(limit, 20)),
    )
    return JSONResponse([dict(row) for row in rows])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
