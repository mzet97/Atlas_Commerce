"""Motor repository: aggregate + outbox in a single local transaction."""

from __future__ import annotations

import uuid

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError, OperationFailure

from . import domain
from .domain import CorrelationId, IdempotencyKey, Product, ProductId


class MongoProductRepository:
    """Owner-side writes. Reads here NEVER decide checkout/stock (INV-CQRS-001)."""

    def __init__(self, client: AsyncIOMotorClient, db_name: str = "catalog") -> None:
        self._db = client[db_name]

    @property
    def database(self) -> AsyncIOMotorDatabase:
        """Test/ops seam: raw handle for assertions and the relay pass."""
        return self._db

    async def ensure_indexes(self) -> None:
        await self._db.products.create_index("idempotency_key", unique=True)
        await self._db.outbox.create_index("event_id", unique=True)
        await self._db.outbox.create_index("published")

    @staticmethod
    def _doc(p: Product) -> dict[str, str | int | dict[str, str] | None]:
        return {
            "_id": p.id,
            "version": p.version,
            "status": p.status,
            "title": p.title,
            "category_id": p.category_id,
            "idempotency_key": p.idempotency_key,
        }

    @staticmethod
    def _load(doc: dict[str, object]) -> Product:
        title = doc.get("title")
        category = doc.get("category_id")
        key = doc.get("idempotency_key")
        assert isinstance(doc["_id"], str)
        assert isinstance(doc["version"], int)
        assert isinstance(doc["status"], str)
        assert isinstance(title, dict)
        assert category is None or isinstance(category, str)
        assert isinstance(key, str)
        return Product(
            id=ProductId(doc["_id"]),
            version=doc["version"],
            status=doc["status"],
            title={str(k): str(v) for k, v in title.items()},
            category_id=category,
            idempotency_key=IdempotencyKey(key),
        )

    async def create(self, product: Product) -> Product:
        # Unique-index races surface twice: DuplicateKeyError on insert, or
        # WriteConflict/TransientTransactionError at commit. In both cases the
        # winner commits, so the fallback read below — outside any
        # transaction, since ours aborted — sees the surviving aggregate.
        for _ in range(3):
            try:
                async with (
                    await self._db.client.start_session() as session,
                    session.start_transaction(),
                ):
                    await self._db.products.insert_one(self._doc(product), session=session)
                    for event in product.events:
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
                product.events.clear()
                return product
            existing = await self._db.products.find_one(
                {"idempotency_key": product.idempotency_key}
            )
            if existing is not None:
                return self._load(existing)
        raise domain.WriteConflict(product.idempotency_key)

    async def get(self, product_id: ProductId) -> Product:
        doc = await self._db.products.find_one({"_id": product_id})
        if doc is None:
            raise domain.NotFound(product_id)
        return self._load(doc)

    async def publish(
        self, product_id: ProductId, expected_version: int, correlation_id: CorrelationId
    ) -> Product:
        async with (
            await self._db.client.start_session() as session,
            session.start_transaction(),
        ):
            doc = await self._db.products.find_one({"_id": product_id}, session=session)
            if doc is None:
                raise domain.NotFound(product_id)
            product = self._load(doc)
            if product.version != expected_version:
                raise domain.ConcurrencyError(expected_version, product.version)
            event = product.publish(correlation_id)
            updated = await self._db.products.update_one(
                {"_id": product_id, "version": expected_version},
                {"$set": {"status": product.status, "version": product.version}},
                session=session,
            )
            if updated.modified_count != 1:
                raise domain.ConcurrencyError(expected_version, product.version)
            await self._db.outbox.insert_one(
                {**event.envelope(), "published": False}, session=session
            )
        product.events.clear()
        return product

    @staticmethod
    def new_id() -> str:
        return f"product-{uuid.uuid4().hex[:12]}"
