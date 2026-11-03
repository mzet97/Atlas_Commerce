"""Application: quote pricing (read model) + checkout saga + reconciliation.

Saga legs are idempotent by construction: reservation and payment keys
derive from the checkout key, and this saga is the sole transitioner of
its own reservations — a 409 on confirm/release means a previous attempt
already converged, never a foreign writer. Every leg persists progress
markers under optimistic concurrency; losers reload and continue.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

import asyncpg
import httpx

from . import domain, pricing
from .domain import (
    Cart,
    CartId,
    CorrelationId,
    IdempotencyKey,
    Order,
    OrderId,
    Quote,
    QuoteId,
)
from .mongo_repo import MongoOrderRepository

MAX_DRIVE_STEPS = 8


class DownstreamError(Exception):
    """Inventory/payment unreachable or timed out (saga stays PENDING)."""


class StockShortage(Exception):
    """A quote line has no stock (order REJECTED, nothing charged)."""


@dataclass(frozen=True, slots=True)
class CheckoutCommand:
    quote_id: str
    customer_id: str
    card_last4: str
    idempotency_key: str
    correlation_id: str


def _inventory_base() -> str:
    return os.getenv("INVENTORY_API_URL", "http://localhost:8104")


def _payment_base() -> str:
    return os.getenv("PAYMENT_API_URL", "http://localhost:8105")


def _corr(correlation_id: str) -> CorrelationId:
    return CorrelationId(correlation_id)


def _warehouses() -> list[str]:
    """Fulfillment sources, tried in order per line (env-configurable)."""
    return [w.strip() for w in os.getenv("WAREHOUSES", "W1").split(",") if w.strip()]


async def fetch_offer(pool: asyncpg.Pool, offer_id: str) -> dict[str, object] | None:
    """Price truth is the offer read model, never owner Mongo (INV-CQRS-001)."""
    row = await pool.fetchrow(
        "SELECT offer_id, sku_id, currency, price_minor, market_id, status"
        " FROM available_offer_view WHERE offer_id = $1",
        offer_id,
    )
    if row is None:
        return None
    return dict(row)


async def handle_quote(
    repo: MongoOrderRepository,
    pool: asyncpg.Pool,
    cart_id: str,
) -> Quote:
    """Price every cart line from the read model; quotes are immutable + TTL.

    Breakdown: subtotal - coupon discount + market tax = total. One currency
    and one market per cart (regional rules need a single jurisdiction).
    """
    from datetime import UTC, datetime

    cart = await repo.get_cart(CartId(cart_id))
    if not cart.items:
        raise domain.ValidationError(field="cart", reason="empty")
    lines: list[domain.QuoteLine] = []
    currency: str | None = None
    market: str | None = None
    for offer_id, quantity in cart.items.items():
        offer = await fetch_offer(pool, offer_id)
        if offer is None:
            raise domain.ValidationError(field="offer_id", reason=f"not available: {offer_id}")
        if currency is None:
            currency = str(offer["currency"])
        elif str(offer["currency"]) != currency:
            raise domain.ValidationError(field="currency", reason="mixed currencies")
        offer_market = str(offer.get("market_id", ""))
        if market is None:
            market = offer_market
        elif offer_market != market:
            raise domain.ValidationError(field="market_id", reason="mixed markets")
        lines.append(
            {
                "offer_id": offer_id,
                "sku_id": str(offer["sku_id"]),
                "quantity": quantity,
                "price_minor": int(offer["price_minor"]),  # type: ignore[arg-type]
            }
        )
    subtotal = sum(line["quantity"] * line["price_minor"] for line in lines)
    coupon = (
        await repo.get_coupon(cart.coupon_code) if cart.coupon_code else None
    )
    try:
        discount = pricing.validate_coupon(coupon, cart.coupon_code, subtotal, market or "")
    except pricing.CouponRejected as exc:
        raise domain.ValidationError(field="coupon_code", reason=str(exc)) from exc
    tax_rate, tax = pricing.tax_minor(market or "", subtotal - discount)
    expires = (datetime.now(UTC) + domain.QUOTE_TTL).isoformat()
    quote = Quote(
        id=QuoteId(f"q-{uuid.uuid4().hex[:12]}"),
        cart_id=cart.id,
        currency=currency or "",
        lines=lines,
        total_minor=subtotal - discount + tax,
        expires_at=expires,
        subtotal_minor=subtotal,
        discount_minor=discount,
        tax_minor=tax,
        tax_rate_bps=tax_rate,
        market_id=market or "",
        coupon_code=cart.coupon_code,
    )
    await repo.save_quote(quote)
    return quote


async def _pick_warehouse(
    http: httpx.AsyncClient, sku: str, qty: int
) -> str | None:
    """First configured warehouse whose stock hint covers the line.

    This is an availability HINT (INV-CQRS-001): the reservation itself
    revalidates atomically at the authoritative position.
    """
    for warehouse in _warehouses():
        try:
            response = await http.get(f"/positions/{warehouse}/{sku}")
        except httpx.HTTPError as exc:
            raise DownstreamError(f"inventory unreachable: {exc}") from exc
        if response.status_code == 404:
            continue  # no position in this warehouse
        if response.status_code != 200:
            raise DownstreamError(f"inventory position: {response.status_code}")
        body = response.json()
        assert isinstance(body, dict)
        if int(body.get("available", 0)) >= qty:  # type: ignore[arg-type]
            return warehouse
    return None


async def _reserve(
    http: httpx.AsyncClient, sku: str, qty: int, order: Order, correlation: str
) -> str:
    warehouse = await _pick_warehouse(http, sku, qty)
    if warehouse is None:
        raise StockShortage(sku)
    try:
        response = await http.post(
            "/reservations",
            json={
                "warehouse_id": warehouse,
                "sku_id": sku,
                "quantity": qty,
                "checkout_id": order.id,
                "idempotency_key": f"{order.idempotency_key}:{sku}",
                "correlation_id": correlation,
            },
        )
    except httpx.HTTPError as exc:
        raise DownstreamError(f"inventory unreachable: {exc}") from exc
    if response.status_code == 409:
        raise StockShortage(sku)
    if response.status_code != 201:
        raise DownstreamError(f"inventory reserve: {response.status_code}")
    body = response.json()
    assert isinstance(body, dict) and isinstance(body.get("id"), str)
    return body["id"]


async def _transition_reservation(
    http: httpx.AsyncClient, reservation_id: str, action: str, correlation: str
) -> None:
    """Confirm/release. 409 = our own previous attempt converged (sole writer)."""
    try:
        response = await http.post(
            f"/reservations/{reservation_id}/{action}",
            json={"correlation_id": correlation},
        )
    except httpx.HTTPError as exc:
        raise DownstreamError(f"inventory unreachable: {exc}") from exc
    if response.status_code in (200, 201, 409):
        return
    raise DownstreamError(f"inventory {action}: {response.status_code}")


async def _authorize(
    http: httpx.AsyncClient, order: Order, correlation: str
) -> dict[str, object]:
    try:
        response = await http.post(
            "/intents",
            json={
                "order_id": order.id,
                "customer_id": order.customer_id,
                "amount_minor": order.total_minor,
                "currency": order.currency,
                "card_last4": order.card_last4,
                "idempotency_key": f"{order.idempotency_key}:pay",
                "correlation_id": correlation,
            },
        )
    except httpx.HTTPError as exc:
        raise DownstreamError(f"payment unreachable: {exc}") from exc
    if response.status_code != 201:
        raise DownstreamError(f"payment authorize: {response.status_code}")
    body = response.json()
    assert isinstance(body, dict)
    return body


async def _payment_status(
    http: httpx.AsyncClient, intent_id: str, correlation: str
) -> dict[str, object]:
    try:
        response = await http.get(f"/intents/{intent_id}")
    except httpx.HTTPError as exc:
        raise DownstreamError(f"payment unreachable: {exc}") from exc
    if response.status_code == 404:
        return {"status": "UNKNOWN"}
    if response.status_code != 200:
        raise DownstreamError(f"payment status: {response.status_code}")
    body = response.json()
    assert isinstance(body, dict)
    _ = correlation
    return body


async def _release_all(
    http: httpx.AsyncClient, order: Order, correlation: str
) -> None:
    for reservation_id in order.reservation_ids:
        await _transition_reservation(http, reservation_id, "release", correlation)


async def _confirm_all(
    http: httpx.AsyncClient, order: Order, correlation: str
) -> None:
    for reservation_id in order.reservation_ids:
        await _transition_reservation(http, reservation_id, "confirm", correlation)


async def _drive(
    repo: MongoOrderRepository,
    http_inv: httpx.AsyncClient,
    http_pay: httpx.AsyncClient,
    order: Order,
    correlation: str,
) -> Order:
    """Advance one PENDING order. Terminal orders return untouched."""
    for _ in range(MAX_DRIVE_STEPS):
        if order.status != domain.PENDING:
            return order
        if not order.reservation_ids:
            try:
                held: list[str] = []
                for line in order.lines:
                    held.append(
                        await _reserve(http_inv, line["sku_id"], line["quantity"],
                                       order, correlation)
                    )
            except StockShortage as exc:
                order.reservation_ids = held
                try:
                    await _release_all(http_inv, order, correlation)
                except DownstreamError:
                    pass  # release retries on reconcile; reject stands
                order.reject(f"no stock: {exc}", _corr(correlation))
                return await repo.save_with_events(order)
            except DownstreamError:
                return order  # no markers moved: safe retry
            order.reservation_ids = held
            try:
                order = await repo.save_with_events(order)
            except domain.WriteConflict:
                order = await repo.get(order.id)
            continue
        if order.payment_intent_id is None:
            try:
                intent = await _authorize(http_pay, order, correlation)
            except DownstreamError:
                return order  # PENDING: reconcile drives payment later
            order.payment_intent_id = str(intent["id"])
            status = str(intent.get("status", ""))
            if status == "AUTHORIZED":
                await _confirm_all(http_inv, order, correlation)
                order.confirm(_corr(correlation))
            elif status == "DECLINED":
                try:
                    await _release_all(http_inv, order, correlation)
                except DownstreamError:
                    pass
                order.cancel("payment declined", _corr(correlation))
            # UNKNOWN: persist intent id, reconcile resolves (never re-charge).
            try:
                order = await repo.save_with_events(order)
            except domain.WriteConflict:
                order = await repo.get(order.id)
            return order
        return order
    raise domain.WriteConflict(order.idempotency_key)


async def handle_checkout(
    repo: MongoOrderRepository,
    cmd: CheckoutCommand,
    now_iso: str,
) -> tuple[Order, int]:
    """Consume the quote once, place idempotently, drive the saga.

    Returns (order, http_status): 201 CONFIRMED, 202 PENDING, 402 CANCELLED,
    409 REJECTED. Replays return the winner with its own final status.
    """
    from datetime import UTC, datetime

    # Pricing is snapshotted in the quote; checkout never re-reads prices.
    quote = await repo.get_quote(QuoteId(cmd.quote_id))
    now = now_iso or datetime.now(UTC).isoformat()
    if quote.expired(now):
        raise domain.ValidationError(field="quote_id", reason="expired")
    candidate = Order.place(
        OrderId(f"o-{uuid.uuid4().hex[:12]}"),
        quote,
        cmd.customer_id,
        cmd.card_last4,
        IdempotencyKey(cmd.idempotency_key),
        _corr(cmd.correlation_id),
    )
    try:
        order = await repo.place_with_quote(candidate, quote.id)
    except domain.WriteConflict:
        order = await repo.get_by_key(IdempotencyKey(cmd.idempotency_key))
    if order.status != domain.PENDING:
        return order, _status_for(order)
    async with (
        httpx.AsyncClient(base_url=_inventory_base(), timeout=15) as http_inv,
        httpx.AsyncClient(base_url=_payment_base(), timeout=30) as http_pay,
    ):
        try:
            order = await _drive(repo, http_inv, http_pay, order, cmd.correlation_id)
        except DownstreamError:
            order = await repo.get(order.id)  # persist what converged so far
    return order, _status_for(order)


async def handle_ship(
    repo: MongoOrderRepository, order_id: str, correlation_id: str
) -> Order:
    """CONFIRMED -> SHIPPED. Idempotent: SHIPPED returns untouched."""
    order = await repo.get(OrderId(order_id))
    if order.status == domain.SHIPPED:
        return order
    order.ship(_corr(correlation_id))
    return await repo.save_with_events(order)


async def handle_ops_cancel(
    repo: MongoOrderRepository, order_id: str, correlation_id: str
) -> Order:
    """Operational cancel (M4): PENDING only, reservations released.

    CONFIRMED cancellation is a money event (refund) — refused here until
    the refund flow lands (M6). Terminal orders return idempotently.
    """
    order = await repo.get(OrderId(order_id))
    if order.status in domain.TERMINAL:
        return order
    if order.status == domain.CONFIRMED:
        raise domain.InvalidTransition(status=order.status, event="ops cancel")
    async with httpx.AsyncClient(base_url=_inventory_base(), timeout=15) as http_inv:
        try:
            await _release_all(http_inv, order, correlation_id)
        except DownstreamError:
            return order  # reservations stay; retry
    order.cancel("cancelled by ops", _corr(correlation_id))
    return await repo.save_with_events(order)


async def handle_reconcile(
    repo: MongoOrderRepository,
    order_id: str,
    correlation_id: str,
) -> tuple[Order, int]:
    """PENDING resolves here: payment truth first, then the matching leg."""
    order = await repo.get(OrderId(order_id))
    if order.status != domain.PENDING:
        return order, _status_for(order)
    async with (
        httpx.AsyncClient(base_url=_inventory_base(), timeout=15) as http_inv,
        httpx.AsyncClient(base_url=_payment_base(), timeout=30) as http_pay,
    ):
        if order.payment_intent_id is None:
            try:
                order = await _drive(repo, http_inv, http_pay, order, correlation_id)
            except DownstreamError:
                pass
            return order, _status_for(order)
        try:
            intent = await _payment_status(
                http_pay, order.payment_intent_id, correlation_id)
        except DownstreamError:
            return order, _status_for(order)
        status = str(intent.get("status", "UNKNOWN"))
        if status == "AUTHORIZED":
            try:
                await _confirm_all(http_inv, order, correlation_id)
            except DownstreamError:
                return order, _status_for(order)
            order.confirm(_corr(correlation_id))
        elif status == "DECLINED":
            try:
                await _release_all(http_inv, order, correlation_id)
            except DownstreamError:
                return order, _status_for(order)
            order.cancel("payment declined", _corr(correlation_id))
        else:
            return order, _status_for(order)
        order = await repo.save_with_events(order)
        return order, _status_for(order)


def _status_for(order: Order) -> int:
    if order.status == domain.CONFIRMED:
        return 201
    if order.status == domain.CANCELLED:
        return 402
    if order.status == domain.REJECTED:
        return 409
    return 202


__all__ = ["Cart", "CheckoutCommand", "fetch_offer", "handle_checkout",
           "handle_quote", "handle_reconcile"]
