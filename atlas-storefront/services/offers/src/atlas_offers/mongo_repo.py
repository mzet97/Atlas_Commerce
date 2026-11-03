"""Motor repository: aggregate + outbox in a single local transaction."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorClientSession,
    AsyncIOMotorDatabase,
)
from pymongo.errors import DuplicateKeyError, OperationFailure

from . import domain
from .domain import CorrelationId, IdempotencyKey, Offer, OfferId, SkuId


class MongoOfferRepository:
    """Owner-side writes. Reads here NEVER decide checkout/stock (INV-CQRS-001)."""

    def __init__(self, client: AsyncIOMotorClient, db_name: str = "offers") -> None:
        self._db = client[db_name]

    @property
    def database(self) -> AsyncIOMotorDatabase:
        """Test/ops seam: raw handle for assertions and the relay pass."""
        return self._db

    async def ensure_indexes(self) -> None:
        await self._db.offers.create_index("idempotency_key", unique=True)
        await self._db.offers.create_index(
            [("sku_id", 1), ("seller_id", 1), ("market_id", 1), ("channel", 1), ("status", 1)]
        )
        await self._db.outbox.create_index("event_id", unique=True)
        await self._db.outbox.create_index("published")

    @staticmethod
    def _doc(o: Offer) -> dict[str, str | int | None]:
        return {
            "_id": o.id,
            "version": o.version,
            "status": o.status,
            "sku_id": o.sku_id,
            "seller_id": o.seller_id,
            "market_id": o.market_id,
            "channel": o.channel,
            "currency": o.currency,
            "price_minor": o.price_minor,
            "idempotency_key": o.idempotency_key,
        }

    @staticmethod
    def _load(doc: dict[str, object]) -> Offer:
        for key in (
            "_id",
            "version",
            "status",
            "sku_id",
            "seller_id",
            "market_id",
            "channel",
            "currency",
            "price_minor",
            "idempotency_key",
        ):
            assert key in doc, key
        assert isinstance(doc["_id"], str)
        assert isinstance(doc["version"], int)
        assert isinstance(doc["status"], str)
        assert isinstance(doc["sku_id"], str)
        assert isinstance(doc["seller_id"], str)
        assert isinstance(doc["market_id"], str)
        assert isinstance(doc["channel"], str)
        assert isinstance(doc["currency"], str)
        assert isinstance(doc["price_minor"], int)
        assert isinstance(doc["idempotency_key"], str)
        return Offer(
            id=OfferId(doc["_id"]),
            version=doc["version"],
            status=doc["status"],
            sku_id=SkuId(doc["sku_id"]),
            seller_id=doc["seller_id"],
            market_id=doc["market_id"],
            channel=doc["channel"],
            currency=doc["currency"],
            price_minor=doc["price_minor"],
            idempotency_key=IdempotencyKey(doc["idempotency_key"]),
        )

    async def _insert_with_outbox(
        self,
        session: AsyncIOMotorClientSession,
        offer: Offer,
        event: domain.DomainEvent,
    ) -> None:
        await self._db.offers.insert_one(self._doc(offer), session=session)
        await self._db.outbox.insert_one({**event.envelope(), "published": False}, session=session)

    async def publish(self, offer: Offer) -> Offer:
        """Insert ACTIVE offer unless an ACTIVE sibling overlaps (OfferConflict)."""
        for _ in range(3):
            try:
                async with (
                    await self._db.client.start_session() as session,
                    session.start_transaction(),
                ):
                    sibling = await self._db.offers.find_one(
                        {
                            "sku_id": offer.sku_id,
                            "seller_id": offer.seller_id,
                            "market_id": offer.market_id,
                            "channel": offer.channel,
                            "status": domain.ACTIVE,
                        },
                        session=session,
                    )
                    if sibling is not None and sibling["_id"] != offer.id:
                        raise domain.OfferConflict(offer.sku_id)
                    event = offer.events[0]
                    await self._insert_with_outbox(session, offer, event)
            except DuplicateKeyError:
                pass
            except OperationFailure as exc:
                labels = exc.details.get("errorLabels", []) if exc.details else []
                if "TransientTransactionError" not in labels:
                    raise
            else:
                offer.events.clear()
                return offer
            existing = await self._db.offers.find_one({"idempotency_key": offer.idempotency_key})
            if existing is not None:
                return self._load(existing)
        raise domain.WriteConflict(offer.idempotency_key)

    async def get(self, offer_id: OfferId) -> Offer:
        doc = await self._db.offers.find_one({"_id": offer_id})
        if doc is None:
            raise domain.NotFound(offer_id)
        return self._load(doc)

    async def _apply(
        self,
        offer_id: OfferId,
        expected_version: int,
        change: Callable[[Offer], domain.DomainEvent],
    ) -> Offer:
        # change is a typed domain transition (update_price/deactivate bound
        # by the caller); no stringly-typed dispatch.
        for _ in range(3):
            try:
                async with (
                    await self._db.client.start_session() as session,
                    session.start_transaction(),
                ):
                    doc = await self._db.offers.find_one({"_id": offer_id}, session=session)
                    if doc is None:
                        raise domain.NotFound(offer_id)
                    offer = self._load(doc)
                    if offer.version != expected_version:
                        raise domain.ConcurrencyError(expected_version, offer.version)
                    event = change(offer)
                    updated = await self._db.offers.update_one(
                        {"_id": offer_id, "version": expected_version},
                        {
                            "$set": {
                                "status": offer.status,
                                "version": offer.version,
                                "price_minor": offer.price_minor,
                            }
                        },
                        session=session,
                    )
                    if updated.modified_count != 1:
                        raise domain.ConcurrencyError(expected_version, offer.version)
                    await self._db.outbox.insert_one(
                        {**event.envelope(), "published": False}, session=session
                    )
            # NOTE: DuplicateKeyError subclasses OperationFailure in pymongo,
            # so it MUST be caught first (see inventory reserve).
            except DuplicateKeyError:
                pass
            except OperationFailure as exc:
                labels = exc.details.get("errorLabels", []) if exc.details else []
                if "TransientTransactionError" not in labels:
                    raise
            except domain.ConcurrencyError:
                # Lost race or stale client: re-read outside the aborted txn.
                conflict = await self._db.offers.find_one({"_id": offer_id})
                if conflict is not None:
                    current = self._load(conflict)
                    if current.version != expected_version:
                        raise domain.ConcurrencyError(
                            expected_version, current.version) from None
                # Same version visible: spurious loss, retry the transaction.
                continue
            else:
                offer.events.clear()
                return offer
        raise domain.WriteConflict(IdempotencyKey(f"mutate:{offer_id}"))

    async def update_price(
        self,
        offer_id: OfferId,
        expected_version: int,
        price_minor: int,
        correlation_id: CorrelationId,
    ) -> Offer:
        """Bump version + PriceChanged in ONE txn; stale version -> conflict."""
        return await self._apply(
            offer_id,
            expected_version,
            lambda offer: offer.update_price(price_minor, correlation_id),
        )

    async def deactivate(
        self, offer_id: OfferId, expected_version: int, correlation_id: CorrelationId
    ) -> Offer:
        """ACTIVE -> INACTIVE in ONE txn; stale version -> conflict."""
        return await self._apply(
            offer_id,
            expected_version,
            lambda offer: offer.deactivate(correlation_id),
        )

    @staticmethod
    def new_id() -> str:
        return f"offer-{uuid.uuid4().hex[:12]}"
