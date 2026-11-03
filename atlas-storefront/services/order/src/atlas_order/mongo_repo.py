"""Motor repository: carts + quotes + orders with outbox in local transactions."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError, OperationFailure

from . import domain
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


class MongoOrderRepository:
    """Owner-side writes. Reads here NEVER decide checkout/stock (INV-CQRS-001)."""

    def __init__(self, client: AsyncIOMotorClient, db_name: str = "order") -> None:
        self._db = client[db_name]

    @property
    def database(self) -> AsyncIOMotorDatabase:
        """Test/ops seam: raw handle for assertions and the relay pass."""
        return self._db

    async def ensure_indexes(self) -> None:
        await self._db.carts.create_index("_id")
        await self._db.quotes.create_index("_id")
        await self._db.orders.create_index("idempotency_key", unique=True)
        await self._db.outbox.create_index("event_id", unique=True)
        await self._db.outbox.create_index("published")
        await self._db.coupons.create_index("_id")

    # -- coupons (pricing rules; managed via Control /ops/coupons) --------
    async def upsert_coupon(self, doc: dict[str, object]) -> None:
        await self._db.coupons.update_one(
            {"_id": str(doc["code"])}, {"$set": doc}, upsert=True
        )

    async def get_coupon(self, code: str) -> dict[str, object] | None:
        raw = await self._db.coupons.find_one({"_id": code})
        if raw is None:
            return None
        coupon = dict(raw)
        coupon.pop("_id", None)
        coupon["code"] = str(raw["_id"])
        return coupon

    async def list_coupons(self) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        async for raw in self._db.coupons.find():
            coupon = dict(raw)
            coupon["code"] = str(coupon.pop("_id", ""))
            out.append(coupon)
        return out

    # -- carts -----------------------------------------------------------
    async def save_cart(self, cart: Cart) -> None:
        await self._db.carts.update_one(
            {"_id": cart.id},
            {"$set": {"customer_id": cart.customer_id, "items": cart.items,
                      "coupon_code": cart.coupon_code}},
            upsert=True,
        )

    async def get_cart(self, cart_id: CartId) -> Cart:
        doc = await self._db.carts.find_one({"_id": cart_id})
        if doc is None:
            raise domain.NotFound(f"cart {cart_id}")
        items = doc.get("items") or {}
        coupon = doc.get("coupon_code")
        return Cart(id=cart_id, customer_id=str(doc.get("customer_id", "")),
                    items={str(k): int(v) for k, v in items.items()},
                    coupon_code=str(coupon) if coupon else None)

    # -- quotes ----------------------------------------------------------
    async def save_quote(self, quote: Quote) -> None:
        await self._db.quotes.insert_one(
            {
                "_id": quote.id,
                "cart_id": quote.cart_id,
                "currency": quote.currency,
                "lines": [dict(line) for line in quote.lines],
                "total_minor": quote.total_minor,
                "expires_at": quote.expires_at,
                "consumed_by": quote.consumed_by,
                "subtotal_minor": quote.subtotal_minor,
                "discount_minor": quote.discount_minor,
                "tax_minor": quote.tax_minor,
                "tax_rate_bps": quote.tax_rate_bps,
                "market_id": quote.market_id,
                "coupon_code": quote.coupon_code,
            }
        )

    async def get_quote(self, quote_id: QuoteId) -> Quote:
        doc = await self._db.quotes.find_one({"_id": quote_id})
        if doc is None:
            raise domain.NotFound(f"quote {quote_id}")
        consumed = doc.get("consumed_by")
        return Quote(
            id=quote_id,
            cart_id=CartId(str(doc["cart_id"])),
            currency=str(doc["currency"]),
            lines=[_line(line) for line in doc.get("lines") or []],
            total_minor=int(doc["total_minor"]),  # type: ignore[arg-type]
            expires_at=str(doc["expires_at"]),
            consumed_by=str(consumed) if consumed else None,
            subtotal_minor=int(doc.get("subtotal_minor", 0)),
            discount_minor=int(doc.get("discount_minor", 0)),
            tax_minor=int(doc.get("tax_minor", 0)),
            tax_rate_bps=int(doc.get("tax_rate_bps", 0)),
            market_id=str(doc.get("market_id", "")),
            coupon_code=(
                str(doc["coupon_code"]) if doc.get("coupon_code") else None
            ),
        )

    async def consume_quote(self, quote_id: QuoteId, order_id: OrderId) -> Quote:
        """Mark a quote consumed exactly once; second consumer gets the winner."""
        doc = await self._db.quotes.find_one_and_update(
            {"_id": quote_id, "consumed_by": None},
            {"$set": {"consumed_by": order_id}},
            return_document=True,
        )
        if doc is None:
            winner = await self._db.quotes.find_one({"_id": quote_id})
            if winner is None:
                raise domain.NotFound(f"quote {quote_id}")
            raise domain.ValidationError(
                field="quote_id",
                reason=f"already consumed by {winner.get('consumed_by')}",
            )
        return await self.get_quote(quote_id)

    # -- orders ----------------------------------------------------------
    @staticmethod
    def _doc(o: Order) -> dict[str, object]:
        return {
            "_id": o.id,
            "version": o.version,
            "status": o.status,
            "quote_id": o.quote_id,
            "customer_id": o.customer_id,
            "lines": [dict(line) for line in o.lines],
            "total_minor": o.total_minor,
            "currency": o.currency,
            "card_last4": o.card_last4,
            "idempotency_key": o.idempotency_key,
            "reservation_ids": list(o.reservation_ids),
            "payment_intent_id": o.payment_intent_id,
            "failure_reason": o.failure_reason,
            "subtotal_minor": o.subtotal_minor,
            "discount_minor": o.discount_minor,
            "tax_minor": o.tax_minor,
            "tax_rate_bps": o.tax_rate_bps,
            "market_id": o.market_id,
            "coupon_code": o.coupon_code,
            "created_at": o.created_at,
        }

    @staticmethod
    def _load(doc: dict[str, object]) -> Order:
        assert isinstance(doc["_id"], str)
        assert isinstance(doc["version"], int)
        payment = doc.get("payment_intent_id")
        failure = doc.get("failure_reason")
        coupon = doc.get("coupon_code")
        return Order(
            id=OrderId(doc["_id"]),
            version=doc["version"],
            status=str(doc["status"]),
            quote_id=QuoteId(str(doc["quote_id"])),
            customer_id=str(doc["customer_id"]),
            lines=[_line(line) for line in doc.get("lines") or []],  # type: ignore[union-attr]
            total_minor=int(doc["total_minor"]),  # type: ignore[arg-type]
            currency=str(doc["currency"]),
            card_last4=str(doc["card_last4"]),
            idempotency_key=IdempotencyKey(str(doc["idempotency_key"])),
            reservation_ids=[str(r) for r in doc.get("reservation_ids") or []],
            payment_intent_id=str(payment) if payment is not None else None,
            failure_reason=str(failure) if failure is not None else None,
            subtotal_minor=int(doc.get("subtotal_minor", 0)),  # type: ignore[arg-type]
            discount_minor=int(doc.get("discount_minor", 0)),  # type: ignore[arg-type]
            tax_minor=int(doc.get("tax_minor", 0)),  # type: ignore[arg-type]
            tax_rate_bps=int(doc.get("tax_rate_bps", 0)),  # type: ignore[arg-type]
            market_id=str(doc.get("market_id", "")),
            coupon_code=str(coupon) if coupon else None,
            created_at=(str(doc["created_at"]) if doc.get("created_at") else None),
        )

    async def list_pending_created_before(self, cutoff_iso: str) -> list[Order]:
        """PENDING orders placed before the cutoff (expiration sweeper).

        Orders predating `created_at` tracking (None) never expire — the
        sweeper only claims what it can age deterministically.
        """
        cursor = self._db.orders.find(
            {
                "status": domain.PENDING,
                "created_at": {"$lt": cutoff_iso, "$ne": None},
            }
        )
        return [self._load(doc) async for doc in cursor]

    async def place_with_quote(self, order: Order, quote_id: QuoteId) -> Order:
        """Consume the quote once AND persist PENDING + OrderPlaced, one txn.

        Same-key replay returns the winner. A quote consumed by another
        checkout raises ValidationError (client must re-quote).
        """
        for _ in range(3):
            try:
                async with (
                    await self._db.client.start_session() as session,
                    session.start_transaction(),
                ):
                    claimed = await self._db.quotes.find_one_and_update(
                        {"_id": quote_id, "consumed_by": None},
                        {"$set": {"consumed_by": order.id}},
                        session=session,
                    )
                    if claimed is None:
                        raise domain.ValidationError(
                            field="quote_id", reason="already consumed")
                    await self._db.orders.insert_one(self._doc(order), session=session)
                    for event in order.events:
                        await self._db.outbox.insert_one(
                            {**event.envelope(), "published": False}, session=session
                        )
            except domain.ValidationError:
                existing = await self._db.orders.find_one(
                    {"idempotency_key": order.idempotency_key}
                )
                if existing is not None:
                    return self._load(existing)
                raise
            except DuplicateKeyError:
                pass
            except OperationFailure as exc:
                labels = exc.details.get("errorLabels", []) if exc.details else []
                if "TransientTransactionError" not in labels:
                    raise
            else:
                order.events.clear()
                return order
            existing = await self._db.orders.find_one(
                {"idempotency_key": order.idempotency_key}
            )
            if existing is not None:
                return self._load(existing)
        raise domain.WriteConflict(order.idempotency_key)

    async def get_by_key(self, key: IdempotencyKey) -> Order:
        doc = await self._db.orders.find_one({"idempotency_key": key})
        if doc is None:
            raise domain.WriteConflict(key)
        return self._load(doc)

    async def place(self, order: Order) -> Order:
        """Persist PENDING + OrderPlaced. Same key returns the winner."""
        for _ in range(3):
            try:
                async with (
                    await self._db.client.start_session() as session,
                    session.start_transaction(),
                ):
                    await self._db.orders.insert_one(self._doc(order), session=session)
                    for event in order.events:
                        await self._db.outbox.insert_one(
                            {**event.envelope(), "published": False}, session=session
                        )
            except DuplicateKeyError:
                pass
            except OperationFailure as exc:
                labels = exc.details.get("errorLabels", []) if exc.details else []
                if "TransientTransactionError" not in labels:
                    raise
            else:
                order.events.clear()
                return order
            existing = await self._db.orders.find_one(
                {"idempotency_key": order.idempotency_key}
            )
            if existing is not None:
                return self._load(existing)
        raise domain.WriteConflict(order.idempotency_key)

    async def get(self, order_id: OrderId) -> Order:
        doc = await self._db.orders.find_one({"_id": order_id})
        if doc is None:
            raise domain.NotFound(f"order {order_id}")
        return self._load(doc)

    async def save_with_events(self, order: Order) -> Order:
        """Optimistic-concurrency transition + outbox in one transaction."""
        events = list(order.events)
        base_version = order.version - len(events)
        for _ in range(3):
            try:
                async with (
                    await self._db.client.start_session() as session,
                    session.start_transaction(),
                ):
                    updated = await self._db.orders.find_one_and_update(
                        {"_id": order.id, "version": base_version},
                        {"$set": self._doc(order)},
                        session=session,
                    )
                    if updated is None:
                        raise domain.WriteConflict(order.idempotency_key)
                    for event in events:
                        await self._db.outbox.insert_one(
                            {**event.envelope(), "published": False}, session=session
                        )
            except OperationFailure as exc:
                labels = exc.details.get("errorLabels", []) if exc.details else []
                if "TransientTransactionError" not in labels:
                    raise
            else:
                order.events.clear()
                return order
        raise domain.WriteConflict(order.idempotency_key)


def _line(raw: object) -> domain.QuoteLine:
    assert isinstance(raw, dict)
    return {
        "offer_id": str(raw["offer_id"]),
        "sku_id": str(raw["sku_id"]),
        "quantity": int(raw["quantity"]),  # type: ignore[arg-type]
        "price_minor": int(raw["price_minor"]),  # type: ignore[arg-type]
    }


__all__ = ["CorrelationId", "MongoOrderRepository"]
