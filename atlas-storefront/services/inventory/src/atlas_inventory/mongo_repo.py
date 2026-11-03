"""Motor repository: position + ledger + reservation + outbox, ONE txn each."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorClientSession,
    AsyncIOMotorDatabase,
)
from pymongo.errors import DuplicateKeyError, OperationFailure

from . import domain
from .application import (
    AdjustStock,
    ConfirmReservation,
    ReceiveStock,
    ReleaseReservation,
    ReserveStock,
)
from .domain import (
    CheckoutId,
    CorrelationId,
    IdempotencyKey,
    Reservation,
    ReservationId,
    StockPosition,
)


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


class MongoInventoryRepository:
    """INV-001/INV-002 enforced here, atomically. Nothing else decides stock."""

    def __init__(self, client: AsyncIOMotorClient, db_name: str = "inventory") -> None:
        self._db = client[db_name]

    @property
    def database(self) -> AsyncIOMotorDatabase:
        """Test/ops seam: raw handle for assertions and the relay pass."""
        return self._db

    async def ensure_indexes(self) -> None:
        await self._db.positions.create_index([("warehouse_id", 1), ("sku_id", 1)], unique=True)
        await self._db.reservations.create_index("idempotency_key", unique=True)
        await self._db.reservations.create_index("checkout_id")
        await self._db.reservations.create_index("expires_at", expireAfterSeconds=0)
        await self._db.movements.create_index([("position_key", 1), ("at", 1)])
        await self._db.outbox.create_index("event_id", unique=True)
        await self._db.outbox.create_index("published")

    @staticmethod
    def _position_key(warehouse_id: str, sku_id: str) -> str:
        return f"{warehouse_id}:{sku_id}"

    @staticmethod
    def _position_doc(p: StockPosition) -> dict[str, str | int]:
        return {
            "_id": p.key(),
            "warehouse_id": p.warehouse_id,
            "sku_id": p.sku_id,
            "on_hand": p.on_hand,
            "reserved": p.reserved,
            "safety_stock": p.safety_stock,
            "version": p.version,
        }

    @staticmethod
    def _load_position(doc: dict[str, object]) -> StockPosition:
        assert isinstance(doc["_id"], str)
        assert isinstance(doc["warehouse_id"], str)
        assert isinstance(doc["sku_id"], str)
        assert isinstance(doc["on_hand"], int)
        assert isinstance(doc["reserved"], int)
        assert isinstance(doc["safety_stock"], int)
        assert isinstance(doc["version"], int)
        return StockPosition(
            warehouse_id=doc["warehouse_id"],
            sku_id=doc["sku_id"],
            on_hand=doc["on_hand"],
            reserved=doc["reserved"],
            safety_stock=doc["safety_stock"],
            version=doc["version"],
        )

    @staticmethod
    def _reservation_doc(r: Reservation) -> dict[str, str | int]:
        return {
            "_id": r.id,
            "checkout_id": r.checkout_id,
            "warehouse_id": r.warehouse_id,
            "sku_id": r.sku_id,
            "quantity": r.quantity,
            "status": r.status,
            "expires_at": r.expires_at,
            "idempotency_key": r.idempotency_key,
        }

    @staticmethod
    def _load_reservation(doc: dict[str, object]) -> Reservation:
        assert isinstance(doc["_id"], str)
        assert isinstance(doc["checkout_id"], str)
        assert isinstance(doc["warehouse_id"], str)
        assert isinstance(doc["sku_id"], str)
        assert isinstance(doc["quantity"], int)
        assert isinstance(doc["status"], str)
        assert isinstance(doc["expires_at"], str)
        assert isinstance(doc["idempotency_key"], str)
        return Reservation(
            id=ReservationId(doc["_id"]),
            checkout_id=CheckoutId(doc["checkout_id"]),
            warehouse_id=doc["warehouse_id"],
            sku_id=doc["sku_id"],
            quantity=doc["quantity"],
            status=doc["status"],
            expires_at=doc["expires_at"],
            idempotency_key=IdempotencyKey(doc["idempotency_key"]),
        )

    async def _movement(
        self,
        session: AsyncIOMotorClientSession,
        key: str,
        delta: int,
        reason: str,
        actor: str,
    ) -> None:
        await self._db.movements.insert_one(
            {
                "position_key": key,
                "delta": delta,
                "reason": reason,
                "actor": actor,
                "at": _utcnow(),
            },
            session=session,
        )

    async def _outbox(
        self,
        session: AsyncIOMotorClientSession,
        event: domain.DomainEvent,
    ) -> None:
        await self._db.outbox.insert_one({**event.envelope(), "published": False}, session=session)

    async def _get_or_create_position(
        self,
        session: AsyncIOMotorClientSession,
        warehouse_id: str,
        sku_id: str,
    ) -> StockPosition:
        key = self._position_key(warehouse_id, sku_id)
        doc = await self._db.positions.find_one({"_id": key}, session=session)
        if doc is not None:
            return self._load_position(doc)
        position = StockPosition(
            warehouse_id=warehouse_id,
            sku_id=sku_id,
            on_hand=0,
            reserved=0,
            safety_stock=0,
            version=1,
        )
        try:
            await self._db.positions.insert_one(self._position_doc(position), session=session)
        except DuplicateKeyError:
            doc = await self._db.positions.find_one({"_id": key}, session=session)
            assert doc is not None
            return self._load_position(doc)
        return position

    async def receive(self, cmd: ReceiveStock) -> StockPosition:
        """Inbound intake: upsert + ledger + event, atomically."""
        async with (
            await self._db.client.start_session() as session,
            session.start_transaction(),
        ):
            position = await self._get_or_create_position(session, cmd.warehouse_id, cmd.sku_id)
            event = position.receive(cmd.quantity, cmd.correlation_id)
            await self._db.positions.update_one(
                {"_id": position.key()},
                {"$set": {"on_hand": position.on_hand, "version": position.version}},
                session=session,
            )
            await self._movement(session, position.key(), cmd.quantity, "receive", "system")
            await self._outbox(session, event)
        position.events.clear()
        return position

    async def adjust(self, cmd: AdjustStock) -> StockPosition:
        """Manual adjustment with reason+actor, ledger movement, event."""
        async with (
            await self._db.client.start_session() as session,
            session.start_transaction(),
        ):
            position = await self._get_or_create_position(session, cmd.warehouse_id, cmd.sku_id)
            event = position.adjust(cmd.delta, cmd.reason, cmd.correlation_id)
            await self._db.positions.update_one(
                {"_id": position.key()},
                {"$set": {"on_hand": position.on_hand, "version": position.version}},
                session=session,
            )
            await self._movement(session, position.key(), cmd.delta, cmd.reason, cmd.actor)
            await self._outbox(session, event)
        position.events.clear()
        return position

    async def reserve(self, cmd: ReserveStock) -> Reservation:
        """INV-002: same key returns the same reservation, never double counts."""
        for _ in range(3):
            try:
                async with (
                    await self._db.client.start_session() as session,
                    session.start_transaction(),
                ):
                    position = await self._get_or_create_position(
                        session, cmd.warehouse_id, cmd.sku_id
                    )
                    reservation = Reservation.create(
                        ReservationId(f"res-{uuid.uuid4().hex[:12]}"),
                        cmd.checkout_id,
                        cmd.warehouse_id,
                        cmd.sku_id,
                        cmd.quantity,
                        cmd.idempotency_key,
                    )
                    event = position.reserve(
                        cmd.quantity,
                        reservation.id,
                        cmd.checkout_id,
                        cmd.correlation_id,
                    )
                    # INV-001: the version match is the atomic guard. A lost
                    # race modifies 0 docs -> ConcurrencyError -> retry, where
                    # the re-read sees the winner's reservation. NEVER skip
                    # this check: it is the oversell barrier.
                    updated = await self._db.positions.update_one(
                        {"_id": position.key(), "version": position.version - 1},
                        {"$set": {"reserved": position.reserved, "version": position.version}},
                        session=session,
                    )
                    if updated.modified_count != 1:
                        raise domain.ConcurrencyError(position.version - 1, position.version)
                    await self._db.reservations.insert_one(
                        self._reservation_doc(reservation), session=session
                    )
                    await self._outbox(session, event)
            # NOTE: DuplicateKeyError subclasses OperationFailure in pymongo,
            # so it MUST be checked first: a dup key is a committed winner
            # (INV-002), never a transient error. Reversing this check
            # re-raises the dup and breaks idempotency.
            except (DuplicateKeyError, OperationFailure, domain.ConcurrencyError) as exc:
                if isinstance(exc, DuplicateKeyError):
                    pass
                elif isinstance(exc, OperationFailure):
                    labels = exc.details.get("errorLabels", []) if exc.details else []
                    if "TransientTransactionError" not in labels:
                        raise
                # Lost race: re-read outside the aborted txn; the winner's
                # reservation is committed and visible (INV-002).
            else:
                position.events.clear()
                return reservation
            existing = await self._db.reservations.find_one(
                {"idempotency_key": cmd.idempotency_key}
            )
            if existing is not None:
                return self._load_reservation(existing)
        raise domain.WriteConflict(cmd.idempotency_key)

    async def _transition(
        self,
        reservation_id: ReservationId,
        correlation_id: CorrelationId,
        to: str,
    ) -> Reservation:
        for _ in range(3):
            try:
                async with (
                    await self._db.client.start_session() as session,
                    session.start_transaction(),
                ):
                    rdoc = await self._db.reservations.find_one(
                        {"_id": reservation_id}, session=session
                    )
                    if rdoc is None:
                        raise domain.NotFound(f"reservation:{reservation_id}")
                    reservation = self._load_reservation(rdoc)
                    position = await self._get_or_create_position(
                        session, reservation.warehouse_id, reservation.sku_id
                    )
                    if to == domain.CONFIRMED:
                        reservation.confirm()
                        event = position.confirm(reservation.quantity, correlation_id)
                    else:
                        reservation.release()
                        event = position.release(reservation.quantity, correlation_id)
                    updated = await self._db.positions.update_one(
                        {"_id": position.key(), "version": position.version - 1},
                        {
                            "$set": {
                                "on_hand": position.on_hand,
                                "reserved": position.reserved,
                                "version": position.version,
                            }
                        },
                        session=session,
                    )
                    if updated.modified_count != 1:
                        raise domain.ConcurrencyError(position.version - 1, position.version)
                    rupdated = await self._db.reservations.update_one(
                        {"_id": reservation_id, "status": domain.ACTIVE},
                        {"$set": {"status": reservation.status}},
                        session=session,
                    )
                    if rupdated.modified_count != 1:
                        raise domain.InvalidTransition(reservation.status)
                    if to == domain.CONFIRMED:
                        # Physical outflow only on confirm; release only
                        # frees the reservation (its doc is the audit trail).
                        await self._movement(
                            session, position.key(), -reservation.quantity, "confirm", "system"
                        )
                    await self._outbox(session, event)
            # NOTE: DuplicateKeyError subclasses OperationFailure in pymongo,
            # so most-specific first; ConcurrencyError re-reads below.
            except DuplicateKeyError:
                pass
            except OperationFailure as exc:
                labels = exc.details.get("errorLabels", []) if exc.details else []
                if "TransientTransactionError" not in labels:
                    raise
            except domain.ConcurrencyError:
                current = await self._db.reservations.find_one({"_id": reservation_id})
                if current is not None and current.get("status") != domain.ACTIVE:
                    return self._load_reservation(current)
                continue
            else:
                position.events.clear()
                return reservation
        raise domain.WriteConflict(IdempotencyKey(f"transition:{reservation_id}"))

    async def confirm(self, cmd: ConfirmReservation) -> Reservation:
        """ACTIVE -> CONFIRMED: on_hand and reserved both decrease."""
        return await self._transition(cmd.reservation_id, cmd.correlation_id, domain.CONFIRMED)

    async def release(self, cmd: ReleaseReservation) -> Reservation:
        """ACTIVE -> RELEASED: quantity returns to available."""
        return await self._transition(cmd.reservation_id, cmd.correlation_id, domain.RELEASED)

    async def get(self, warehouse_id: str, sku_id: str) -> StockPosition:
        doc = await self._db.positions.find_one({"_id": self._position_key(warehouse_id, sku_id)})
        if doc is None:
            raise domain.NotFound(f"position:{warehouse_id}:{sku_id}")
        return self._load_position(doc)
