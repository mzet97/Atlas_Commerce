"""Application layer: stock commands + handlers over repository ports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .domain import (
    CheckoutId,
    CorrelationId,
    IdempotencyKey,
    Reservation,
    ReservationId,
    StockPosition,
)


@dataclass(frozen=True, slots=True)
class ReceiveStock:
    warehouse_id: str
    sku_id: str
    quantity: int
    correlation_id: CorrelationId


@dataclass(frozen=True, slots=True)
class AdjustStock:
    warehouse_id: str
    sku_id: str
    delta: int
    reason: str
    actor: str
    correlation_id: CorrelationId


@dataclass(frozen=True, slots=True)
class ReserveStock:
    warehouse_id: str
    sku_id: str
    quantity: int
    checkout_id: CheckoutId
    idempotency_key: IdempotencyKey
    correlation_id: CorrelationId


@dataclass(frozen=True, slots=True)
class ConfirmReservation:
    reservation_id: ReservationId
    correlation_id: CorrelationId


@dataclass(frozen=True, slots=True)
class ReleaseReservation:
    reservation_id: ReservationId
    correlation_id: CorrelationId


class InventoryRepository(Protocol):
    async def receive(self, cmd: ReceiveStock) -> StockPosition:
        """Upsert position, ledger movement, outbox — ONE txn."""
        ...

    async def adjust(self, cmd: AdjustStock) -> StockPosition:
        """Adjust with reason+actor, ledger movement, outbox — ONE txn."""
        ...

    async def reserve(self, cmd: ReserveStock) -> Reservation:
        """INV-002: same key returns the same reservation, never double counts."""
        ...

    async def confirm(self, cmd: ConfirmReservation) -> Reservation: ...
    async def release(self, cmd: ReleaseReservation) -> Reservation: ...
    async def get(self, warehouse_id: str, sku_id: str) -> StockPosition: ...


async def handle_receive(cmd: ReceiveStock, repo: InventoryRepository) -> StockPosition:
    """Inbound stock intake."""
    return await repo.receive(cmd)


async def handle_adjust(cmd: AdjustStock, repo: InventoryRepository) -> StockPosition:
    """Manual adjustment with mandatory reason and actor."""
    return await repo.adjust(cmd)


async def handle_reserve(cmd: ReserveStock, repo: InventoryRepository) -> Reservation:
    """Idempotent conditional allocation, or InsufficientStock."""
    return await repo.reserve(cmd)


async def handle_confirm(cmd: ConfirmReservation, repo: InventoryRepository) -> Reservation:
    """Confirm an ACTIVE reservation into a shipped set."""
    return await repo.confirm(cmd)


async def handle_release(cmd: ReleaseReservation, repo: InventoryRepository) -> Reservation:
    """Release an ACTIVE reservation back to available."""
    return await repo.release(cmd)
