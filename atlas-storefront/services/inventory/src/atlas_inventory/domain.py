"""Inventory domain: positions, reservations, ledger (pure, no IO)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Final, NewType, TypedDict

ReservationId = NewType("ReservationId", str)
CheckoutId = NewType("CheckoutId", str)
CorrelationId = NewType("CorrelationId", str)
IdempotencyKey = NewType("IdempotencyKey", str)

SCHEMA_VERSION: Final = 1
RESERVE_TTL_SECONDS: Final = 900

ACTIVE: Final = "ACTIVE"
CONFIRMED: Final = "CONFIRMED"
RELEASED: Final = "RELEASED"


class StockPayload(TypedDict, total=False):
    warehouse_id: str
    sku_id: str
    on_hand: int
    reserved: int
    available: int
    reservation_id: str
    checkout_id: str
    quantity: int
    reason: str


Envelope = dict[str, str | int | StockPayload | None]


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_version: int
    occurred_at: str
    schema_version: int
    correlation_id: CorrelationId
    causation_id: str | None
    payload: StockPayload

    def envelope(self) -> Envelope:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "aggregate_version": self.aggregate_version,
            "occurred_at": self.occurred_at,
            "schema_version": self.schema_version,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "payload": self.payload,
        }


def new_event(
    event_type: str,
    aggregate_id: str,
    aggregate_version: int,
    correlation_id: CorrelationId,
    payload: StockPayload,
    causation_id: str | None = None,
) -> DomainEvent:
    """Create a versioned stock event for the outbox envelope (INV-010)."""
    return DomainEvent(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        occurred_at=datetime.now(UTC).isoformat(),
        schema_version=SCHEMA_VERSION,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=payload,
    )


class DomainError(Exception):
    """Base for all inventory domain failures."""


@dataclass
class ValidationError(DomainError):
    field: str
    reason: str

    def __str__(self) -> str:
        return f"invalid {self.field}: {self.reason}"


@dataclass
class InsufficientStock(DomainError):
    available: int
    requested: int

    def __str__(self) -> str:
        return f"insufficient stock: available={self.available} requested={self.requested}"


@dataclass
class InvalidTransition(DomainError):
    status: str

    def __str__(self) -> str:
        return f"cannot transition from {self.status}"


@dataclass
class ConcurrencyError(DomainError):
    expected_version: int
    actual_version: int

    def __str__(self) -> str:
        return f"version conflict: expected={self.expected_version} actual={self.actual_version}"


@dataclass
class NotFound(DomainError):
    resource: str

    def __str__(self) -> str:
        return f"not found: {self.resource}"


@dataclass
class WriteConflict(DomainError):
    """Idempotency race landed nowhere readable; safe to retry the command."""

    idempotency_key: IdempotencyKey

    def __str__(self) -> str:
        return f"idempotency write lost for key: {self.idempotency_key}"


@dataclass(slots=True)
class StockPosition:
    """Authoritative balance. Only receive/reserve/confirm/release/adjust mutate."""

    warehouse_id: str
    sku_id: str
    on_hand: int
    reserved: int
    safety_stock: int
    version: int
    events: list[DomainEvent] = field(default_factory=list, repr=False)

    def key(self) -> str:
        """Position identity: warehouse + sku (single owner, single writer)."""
        return f"{self.warehouse_id}:{self.sku_id}"

    def available(self) -> int:
        """INV-001: physical stock blocked below zero (no backorder here)."""
        return self.on_hand - self.reserved - self.safety_stock

    def _emit(
        self, event_type: str, correlation_id: CorrelationId, extra: StockPayload
    ) -> DomainEvent:
        base: StockPayload = {
            "warehouse_id": self.warehouse_id,
            "sku_id": self.sku_id,
            "on_hand": self.on_hand,
            "reserved": self.reserved,
            "available": self.available(),
        }
        base.update(extra)
        event = new_event(event_type, self.key(), self.version, correlation_id, base)
        self.events.append(event)
        return event

    def receive(self, quantity: int, correlation_id: CorrelationId) -> DomainEvent:
        """Inbound stock; always increases on_hand."""
        if quantity <= 0:
            raise ValidationError(field="quantity", reason="must be positive")
        self.on_hand += quantity
        self.version += 1
        return self._emit(
            "StockAdjusted", correlation_id, {"quantity": quantity, "reason": "receive"}
        )

    def adjust(self, delta: int, reason: str, correlation_id: CorrelationId) -> DomainEvent:
        """Manual adjustment with mandatory reason; never below zero."""
        if not reason.strip():
            raise ValidationError(field="reason", reason="mandatory")
        if self.on_hand + delta < 0:
            raise ValidationError(field="on_hand", reason="would go negative")
        self.on_hand += delta
        self.version += 1
        return self._emit("StockAdjusted", correlation_id, {"quantity": delta, "reason": reason})

    def reserve(
        self,
        quantity: int,
        reservation_id: ReservationId,
        checkout_id: CheckoutId,
        correlation_id: CorrelationId,
    ) -> DomainEvent:
        """INV-001: conditional allocation, or InsufficientStock."""
        if quantity <= 0:
            raise ValidationError(field="quantity", reason="must be positive")
        if self.available() < quantity:
            raise InsufficientStock(self.available(), quantity)
        self.reserved += quantity
        self.version += 1
        return self._emit(
            "StockReserved",
            correlation_id,
            {
                "reservation_id": reservation_id,
                "checkout_id": checkout_id,
                "quantity": quantity,
                "reason": "reserve",
            },
        )

    def confirm(self, quantity: int, correlation_id: CorrelationId) -> DomainEvent:
        """Reservation confirmed: leave reserved AND on_hand (shipped set)."""
        self.reserved -= quantity
        self.on_hand -= quantity
        self.version += 1
        return self._emit(
            "ReservationConfirmed", correlation_id, {"quantity": quantity, "reason": "confirm"}
        )

    def release(self, quantity: int, correlation_id: CorrelationId) -> DomainEvent:
        """Reservation released: back to available."""
        self.reserved -= quantity
        self.version += 1
        return self._emit(
            "ReservationReleased", correlation_id, {"quantity": quantity, "reason": "release"}
        )


@dataclass(slots=True)
class Reservation:
    """Temporary allocation bound to one checkout + idempotency key."""

    id: ReservationId
    checkout_id: CheckoutId
    warehouse_id: str
    sku_id: str
    quantity: int
    status: str
    expires_at: str
    idempotency_key: IdempotencyKey

    @classmethod
    def create(
        cls,
        reservation_id: ReservationId,
        checkout_id: CheckoutId,
        warehouse_id: str,
        sku_id: str,
        quantity: int,
        idempotency_key: IdempotencyKey,
    ) -> Reservation:
        """Create an ACTIVE reservation with TTL (TTL aids cleanup only)."""
        if quantity <= 0:
            raise ValidationError(field="quantity", reason="must be positive")
        expires = (datetime.now(UTC) + timedelta(seconds=RESERVE_TTL_SECONDS)).isoformat()
        return cls(
            id=reservation_id,
            checkout_id=checkout_id,
            warehouse_id=warehouse_id,
            sku_id=sku_id,
            quantity=quantity,
            status=ACTIVE,
            expires_at=expires,
            idempotency_key=idempotency_key,
        )

    def confirm(self) -> None:
        """ACTIVE -> CONFIRMED. A confirmed reservation never expires."""
        if self.status != ACTIVE:
            raise InvalidTransition(status=self.status)
        self.status = CONFIRMED

    def release(self) -> None:
        """ACTIVE -> RELEASED."""
        if self.status != ACTIVE:
            raise InvalidTransition(status=self.status)
        self.status = RELEASED
