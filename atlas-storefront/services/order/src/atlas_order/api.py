"""HTTP boundary: carts, quotes, checkouts, reconciliation."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import asyncpg
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict

from . import application, domain
from .application import CheckoutCommand
from .domain import Cart, CartId, OrderId, QuoteId
from .mongo_repo import MongoOrderRepository


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Owner client + read-model pool per running loop; closed on shutdown."""
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    repo = MongoOrderRepository(client, os.getenv("ORDER_DB", "order"))
    await repo.ensure_indexes()
    pool = await asyncpg.create_pool(os.environ["PG_DSN"], min_size=1, max_size=5)
    app.state.repo = repo
    app.state.pool = pool
    try:
        yield
    finally:
        await pool.close()
        client.close()


app = FastAPI(title="atlas-order", lifespan=lifespan)


def _repo(request: Request) -> MongoOrderRepository:
    repo = request.app.state.repo
    assert isinstance(repo, MongoOrderRepository)
    return repo


def _pool(request: Request) -> asyncpg.Pool:
    pool = request.app.state.pool
    assert isinstance(pool, asyncpg.Pool)
    return pool


class CreateCartRequest(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    customer_id: str
    correlation_id: str


class AddItemRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    offer_id: str
    quantity: int
    correlation_id: str


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    quote_id: str
    customer_id: str
    card_last4: str
    idempotency_key: str
    correlation_id: str


class ReconcileRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    correlation_id: str


def _order_body(order: domain.Order) -> dict[str, object]:
    return {
        "id": order.id,
        "status": order.status,
        "version": order.version,
        "quote_id": order.quote_id,
        "customer_id": order.customer_id,
        "lines": [dict(line) for line in order.lines],
        "total_minor": order.total_minor,
        "currency": order.currency,
        "reservation_ids": list(order.reservation_ids),
        "payment_intent_id": order.payment_intent_id,
        "failure_reason": order.failure_reason,
    }


@app.exception_handler(domain.NotFound)
async def _not_found(_request: Request, exc: domain.NotFound) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=404)


@app.exception_handler(domain.ValidationError)
async def _validation(_request: Request, exc: domain.ValidationError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(domain.InvalidTransition)
async def _transition(_request: Request, exc: domain.InvalidTransition) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(domain.WriteConflict)
async def _conflict(_request: Request, exc: domain.WriteConflict) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(application.DownstreamError)
async def _downstream(_request: Request, exc: application.DownstreamError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=502)


@app.post("/carts", status_code=201)
async def create_cart(body: CreateCartRequest, request: Request) -> JSONResponse:
    """Open a cart. Retries open a new cart; the money boundary is checkout."""
    import uuid

    cart = Cart(id=CartId(f"c-{uuid.uuid4().hex[:12]}"), customer_id=body.customer_id)
    await _repo(request).save_cart(cart)
    return JSONResponse({"id": cart.id, "customer_id": cart.customer_id,
                         "items": cart.items}, status_code=201)


@app.post("/carts/{cart_id}/items", status_code=200)
async def add_item(cart_id: str, body: AddItemRequest, request: Request) -> JSONResponse:
    """Last-write-wins per client sequencing; checkout is the idempotent gate."""
    repo = _repo(request)
    cart = await repo.get_cart(CartId(cart_id))
    cart.add_item(body.offer_id, body.quantity)
    await repo.save_cart(cart)
    return JSONResponse({"id": cart.id, "items": cart.items})


@app.post("/carts/{cart_id}/quote", status_code=201)
async def quote_cart(cart_id: str, request: Request) -> JSONResponse:
    """Price the cart from the offer read model. Immutable, 15min TTL."""
    quote = await application.handle_quote(_repo(request), _pool(request), cart_id)
    return JSONResponse(
        {
            "id": quote.id,
            "cart_id": quote.cart_id,
            "currency": quote.currency,
            "lines": [dict(line) for line in quote.lines],
            "total_minor": quote.total_minor,
            "expires_at": quote.expires_at,
        },
        status_code=201,
    )


@app.post("/checkouts", status_code=201)
async def checkout(body: CheckoutRequest, request: Request) -> JSONResponse:
    """Drive the saga: 201 CONFIRMED, 202 PENDING, 402 CANCELLED, 409 REJECTED."""
    order, status = await application.handle_checkout(
        _repo(request),
        CheckoutCommand(
            quote_id=body.quote_id,
            customer_id=body.customer_id,
            card_last4=body.card_last4,
            idempotency_key=body.idempotency_key,
            correlation_id=body.correlation_id,
        ),
        datetime.now(UTC).isoformat(),
    )
    return JSONResponse(_order_body(order), status_code=status)


@app.get("/orders/{order_id}")
async def get_order(order_id: str, request: Request) -> JSONResponse:
    """Read a single order (stale-read drill: projection may lag this view)."""
    order = await _repo(request).get(OrderId(order_id))
    return JSONResponse(_order_body(order))


@app.post("/orders/{order_id}/ship")
async def ship_order(
    order_id: str, body: ReconcileRequest, request: Request
) -> JSONResponse:
    """Fulfillment handoff CONFIRMED -> SHIPPED. Idempotent replay 200."""
    order = await application.handle_ship(
        _repo(request), order_id, body.correlation_id
    )
    return JSONResponse(_order_body(order))


@app.post("/orders/{order_id}/reconcile")
async def reconcile_order(
    order_id: str, body: ReconcileRequest, request: Request
) -> JSONResponse:
    """PENDING resolves via payment truth; terminal orders return untouched."""
    order, status = await application.handle_reconcile(
        _repo(request), order_id, body.correlation_id
    )
    return JSONResponse(_order_body(order), status_code=status)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


__all__ = ["QuoteId", "app"]
