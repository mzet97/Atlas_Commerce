"""Motor repository: intent + webhooks + outbox in local transactions."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError, OperationFailure

from . import domain
from .domain import AUTHORIZED, IdempotencyKey, IntentId, PaymentIntent


class MongoPaymentRepository:
    """Owner-side writes. Reads here NEVER decide checkout/stock (INV-CQRS-001)."""

    def __init__(self, client: AsyncIOMotorClient, db_name: str = "payment") -> None:
        self._db = client[db_name]

    @property
    def database(self) -> AsyncIOMotorDatabase:
        """Test/ops seam: raw handle for assertions and the relay pass."""
        return self._db

    async def ensure_indexes(self) -> None:
        await self._db.intents.create_index("idempotency_key", unique=True)
        await self._db.intents.create_index(
            "provider_ref", unique=True, partialFilterExpression={"status": AUTHORIZED}
        )
        await self._db.webhooks.create_index(
            [("provider_ref", 1), ("event", 1)], unique=True
        )
        await self._db.refunds.create_index("idempotency_key", unique=True)
        await self._db.outbox.create_index("event_id", unique=True)
        await self._db.outbox.create_index("published")

    @staticmethod
    def _doc(i: PaymentIntent) -> dict[str, object]:
        return {
            "_id": i.id,
            "version": i.version,
            "status": i.status,
            "order_id": i.order_id,
            "customer_id": i.customer_id,
            "amount_minor": i.amount_minor,
            "currency": i.currency,
            "card_last4": i.card_last4,
            "idempotency_key": i.idempotency_key,
            "provider_ref": i.provider_ref,
            "decline_code": i.decline_code,
            "refunded_minor": i.refunded_minor,
            "authorized_at": i.authorized_at,
        }

    @staticmethod
    def _load(doc: dict[str, object]) -> PaymentIntent:
        assert isinstance(doc["_id"], str)
        assert isinstance(doc["version"], int)
        provider = doc.get("provider_ref")
        decline = doc.get("decline_code")
        return PaymentIntent(
            id=IntentId(doc["_id"]),
            version=doc["version"],
            status=str(doc["status"]),
            order_id=str(doc["order_id"]),
            customer_id=str(doc["customer_id"]),
            amount_minor=int(doc["amount_minor"]),  # type: ignore[arg-type]
            currency=str(doc["currency"]),
            card_last4=str(doc["card_last4"]),
            idempotency_key=IdempotencyKey(str(doc["idempotency_key"])),
            provider_ref=str(provider) if provider is not None else None,
            decline_code=str(decline) if decline is not None else None,
            refunded_minor=int(doc.get("refunded_minor", 0)),  # type: ignore[arg-type]
            authorized_at=(str(doc["authorized_at"]) if doc.get("authorized_at") else None),
        )

    async def initiate(self, intent: PaymentIntent) -> PaymentIntent:
        """Persist INITIATED + PaymentInitiated. Same key returns the winner."""
        for _ in range(3):
            try:
                async with (
                    await self._db.client.start_session() as session,
                    session.start_transaction(),
                ):
                    await self._db.intents.insert_one(self._doc(intent), session=session)
                    for event in intent.events:
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
                intent.events.clear()
                return intent
            existing = await self._db.intents.find_one(
                {"idempotency_key": intent.idempotency_key}
            )
            if existing is not None:
                return self._load(existing)
        raise domain.WriteConflict(intent.idempotency_key)

    async def get(self, intent_id: IntentId) -> PaymentIntent:
        doc = await self._db.intents.find_one({"_id": intent_id})
        if doc is None:
            raise domain.NotFound(intent_id)
        return self._load(doc)

    async def save_with_events(
        self, intent: PaymentIntent, extra: list[domain.DomainEvent] | None = None
    ) -> PaymentIntent:
        """Optimistic-concurrency transition + outbox in one transaction.

        The partial unique index on provider_ref/AUTHORIZED is the last
        line of defense for duplicate_paid_order=0; the pre-check below
        turns the common double-pay race into a typed DuplicatePayment.
        """
        events = list(intent.events)
        extra_events = list(extra or [])
        base_version = intent.version - len(events)
        if intent.status == AUTHORIZED and intent.provider_ref:
            paid = await self._db.intents.find_one(
                {"provider_ref": intent.provider_ref, "status": AUTHORIZED,
                 "_id": {"$ne": intent.id}}
            )
            if paid is not None:
                raise domain.DuplicatePayment(intent.provider_ref)
        for _ in range(3):
            try:
                async with (
                    await self._db.client.start_session() as session,
                    session.start_transaction(),
                ):
                    updated = await self._db.intents.find_one_and_update(
                        {"_id": intent.id, "version": base_version},
                        {"$set": self._doc(intent)},
                        session=session,
                    )
                    if updated is None:
                        raise domain.WriteConflict(intent.idempotency_key)
                    for event in [*events, *extra_events]:
                        await self._db.outbox.insert_one(
                            {**event.envelope(), "published": False}, session=session
                        )
            except DuplicateKeyError as exc:
                # Partial unique index fired: another intent got paid first.
                if intent.provider_ref:
                    raise domain.DuplicatePayment(intent.provider_ref) from exc
                raise
            except OperationFailure as exc:
                labels = exc.details.get("errorLabels", []) if exc.details else []
                if "TransientTransactionError" not in labels:
                    raise
            else:
                intent.events.clear()
                return intent
        raise domain.WriteConflict(intent.idempotency_key)

    async def find_for_webhook(
        self, provider_ref: str, order_id: str
    ) -> PaymentIntent | None:
        """Newest intent carrying the ref, else newest for the order."""
        doc = await self._db.intents.find_one(
            {"provider_ref": provider_ref}, sort=[("version", -1)]
        )
        if doc is None:
            doc = await self._db.intents.find_one(
                {"order_id": order_id}, sort=[("version", -1)]
            )
        return self._load(doc) if doc is not None else None

    async def find_refund(self, idempotency_key: str) -> dict[str, object] | None:
        doc = await self._db.refunds.find_one({"idempotency_key": idempotency_key})
        return dict(doc) if doc is not None else None

    async def count_authorized_since(self, customer_id: str, since_epoch: float) -> int:
        """Velocity antifraude counter (M10): authorized intents per customer
        inside the window. The `occurred_at` ISO timestamp of the last event
        is compared lexicographically via a stored authorized_at float."""
        from datetime import UTC, datetime

        cutoff = datetime.fromtimestamp(since_epoch, UTC).isoformat()
        return await self._db.intents.count_documents(
            {
                "customer_id": customer_id,
                "status": AUTHORIZED,
                "authorized_at": {"$gte": cutoff},
            }
        )

    async def refund_with_events(
        self,
        intent: PaymentIntent,
        refund_doc: dict[str, object],
    ) -> tuple[PaymentIntent, bool]:
        """Refund audit row + intent transition + outbox, one transaction.

        The refund row's unique idempotency key dedupes: a replay returns
        the stored row and does NOT transition again.
        """
        events = list(intent.events)
        base_version = intent.version - len(events)
        for _ in range(3):
            try:
                async with (
                    await self._db.client.start_session() as session,
                    session.start_transaction(),
                ):
                    await self._db.refunds.insert_one(refund_doc, session=session)
                    if events:
                        updated = await self._db.intents.find_one_and_update(
                            {"_id": intent.id, "version": base_version},
                            {"$set": self._doc(intent)},
                            session=session,
                        )
                        if updated is None:
                            raise domain.WriteConflict(intent.idempotency_key)
                    for event in events:
                        await self._db.outbox.insert_one(
                            {**event.envelope(), "published": False},
                            session=session,
                        )
            except DuplicateKeyError:
                stored = await self._db.refunds.find_one(
                    {"idempotency_key": refund_doc["idempotency_key"]}
                )
                reloaded = await self.get(intent.id)
                if stored is not None:
                    return reloaded, False
                raise
            except OperationFailure as exc:
                labels = exc.details.get("errorLabels", []) if exc.details else []
                if "TransientTransactionError" not in labels:
                    raise
            else:
                intent.events.clear()
                return intent, True
        raise domain.WriteConflict(intent.idempotency_key)

    async def apply_webhook(
        self,
        intent: PaymentIntent,
        provider_ref: str,
        event: str,
        order_id: str,
        extra: list[domain.DomainEvent],
    ) -> tuple[PaymentIntent, bool]:
        """Atomic webhook apply: dedup record + transition + outbox, one txn.

        Returns (intent, True) on first sight, (reloaded intent, False) on
        replay. A crash between dedup and transition is impossible: both
        commit or neither does, so redelivery always converges.
        """
        events = list(intent.events)
        base_version = intent.version - len(events)
        transitioned = len(events) > 0
        if intent.status == AUTHORIZED and intent.provider_ref:
            paid = await self._db.intents.find_one(
                {"provider_ref": intent.provider_ref, "status": AUTHORIZED,
                 "_id": {"$ne": intent.id}}
            )
            if paid is not None:
                raise domain.DuplicatePayment(intent.provider_ref)
        for _ in range(3):
            try:
                async with (
                    await self._db.client.start_session() as session,
                    session.start_transaction(),
                ):
                    await self._db.webhooks.insert_one(
                        {"provider_ref": provider_ref, "event": event,
                         "order_id": order_id},
                        session=session,
                    )
                    if transitioned:
                        updated = await self._db.intents.find_one_and_update(
                            {"_id": intent.id, "version": base_version},
                            {"$set": self._doc(intent)},
                            session=session,
                        )
                        if updated is None:
                            raise domain.WriteConflict(intent.idempotency_key)
                    for out_event in [*events, *extra]:
                        await self._db.outbox.insert_one(
                            {**out_event.envelope(), "published": False},
                            session=session,
                        )
            except DuplicateKeyError as exc:
                pattern = (exc.details or {}).get("keyPattern", {})
                if "provider_ref" in pattern and "event" not in pattern:
                    # Lost the double-pay race after the pre-check: typed out.
                    if intent.provider_ref:
                        raise domain.DuplicatePayment(intent.provider_ref) from exc
                    raise
                reloaded = await self._db.intents.find_one({"_id": intent.id})
                return (self._load(reloaded) if reloaded else intent), False
            except OperationFailure as exc:
                labels = exc.details.get("errorLabels", []) if exc.details else []
                if "TransientTransactionError" not in labels:
                    raise
            else:
                intent.events.clear()
                return intent, True
        raise domain.WriteConflict(intent.idempotency_key)
