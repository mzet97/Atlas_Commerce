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
from .sweeper import expire_pending_loop


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Owner client + read-model pool per running loop; closed on shutdown."""
    import asyncio

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    repo = MongoOrderRepository(client, os.getenv("ORDER_DB", "order"))
    await repo.ensure_indexes()
    pool = await asyncpg.create_pool(os.environ["PG_DSN"], min_size=1, max_size=5)
    app.state.repo = repo
    app.state.pool = pool
    sweeper = asyncio.create_task(expire_pending_loop(repo))
    try:
        yield
    finally:
        sweeper.cancel()
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


class SetCouponRequest(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    code: str | None
    correlation_id: str


class UpsertCouponRequest(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    code: str
    kind: str
    value: int
    market_id: str | None = None
    min_subtotal_minor: int = 0
    correlation_id: str


class DeactivateCouponRequest(BaseModel):
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
        "subtotal_minor": order.subtotal_minor,
        "discount_minor": order.discount_minor,
        "tax_minor": order.tax_minor,
        "total_minor": order.total_minor,
        "currency": order.currency,
        "market_id": order.market_id,
        "coupon_code": order.coupon_code,
        "tax_rate_bps": order.tax_rate_bps,
        "reservation_ids": list(order.reservation_ids),
        "payment_intent_id": order.payment_intent_id,
        "failure_reason": order.failure_reason,
        "created_at": order.created_at,
    }


def _coupon_body(coupon: dict[str, object]) -> dict[str, object]:
    body = dict(coupon)
    body["active"] = bool(body.get("active", False))
    return body


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
    return JSONResponse({"id": cart.id, "items": cart.items,
                         "coupon_code": cart.coupon_code})


@app.post("/carts/{cart_id}/coupon", status_code=200)
async def set_coupon(
    cart_id: str, body: SetCouponRequest, request: Request
) -> JSONResponse:
    """Attach/clear a coupon code; validity (market, minimum) applies at quote."""
    repo = _repo(request)
    cart = await repo.get_cart(CartId(cart_id))
    if body.code is not None:
        coupon = await repo.get_coupon(body.code)
        if coupon is None or not bool(coupon.get("active", False)):
            raise domain.ValidationError(
                field="coupon_code", reason="unknown or inactive coupon"
            )
        cart.coupon_code = body.code
    else:
        cart.coupon_code = None
    await repo.save_cart(cart)
    return JSONResponse({"id": cart.id, "items": cart.items,
                         "coupon_code": cart.coupon_code})


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
            "subtotal_minor": quote.subtotal_minor,
            "discount_minor": quote.discount_minor,
            "tax_minor": quote.tax_minor,
            "tax_rate_bps": quote.tax_rate_bps,
            "total_minor": quote.total_minor,
            "market_id": quote.market_id,
            "coupon_code": quote.coupon_code,
            "expires_at": quote.expires_at,
        },
        status_code=201,
    )


# -- admin (coupon pricing rules; reached via Control /ops/coupons) ------


@app.post("/admin/coupons", status_code=201)
async def admin_upsert_coupon(body: UpsertCouponRequest, request: Request) -> JSONResponse:
    """Create or update a coupon rule (kind PERCENT/FIXED)."""
    if body.kind not in ("PERCENT", "FIXED"):
        raise domain.ValidationError(field="kind", reason="must be PERCENT or FIXED")
    if body.value <= 0:
        raise domain.ValidationError(field="value", reason="must be positive")
    repo = _repo(request)
    await repo.upsert_coupon(
        {
            "code": body.code,
            "kind": body.kind,
            "value": body.value,
            "market_id": body.market_id,
            "min_subtotal_minor": body.min_subtotal_minor,
            "active": True,
        }
    )
    coupon = await repo.get_coupon(body.code)
    assert coupon is not None
    return JSONResponse(_coupon_body(coupon), status_code=201)


@app.get("/admin/coupons")
async def admin_list_coupons(request: Request) -> JSONResponse:
    return JSONResponse([_coupon_body(c) for c in await _repo(request).list_coupons()])


@app.post("/admin/coupons/{code}/deactivate", status_code=200)
async def admin_deactivate_coupon(
    code: str, body: DeactivateCouponRequest, request: Request
) -> JSONResponse:
    repo = _repo(request)
    coupon = await repo.get_coupon(code)
    if coupon is None:
        raise domain.NotFound(f"coupon {code}")
    coupon["active"] = False
    await repo.upsert_coupon(coupon)
    updated = await repo.get_coupon(code)
    assert updated is not None
    return JSONResponse(_coupon_body(updated))


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


@app.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: str, body: ReconcileRequest, request: Request
) -> JSONResponse:
    """Operational cancel (M4, reached via Control four-eyes above threshold).

    PENDING -> CANCELLED with reservations released; terminal replay
    returns the order; CONFIRMED is refused until refunds land (M6).
    """
    order = await application.handle_ops_cancel(
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
