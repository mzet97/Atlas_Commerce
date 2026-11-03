"""HTTP boundary: parse untrusted JSON into typed commands (Pydantic v2)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict

from . import domain
from .application import (
    AdjustStock,
    ConfirmReservation,
    ReceiveStock,
    ReleaseReservation,
    ReserveStock,
    handle_adjust,
    handle_confirm,
    handle_receive,
    handle_release,
    handle_reserve,
)
from .domain import (
    CheckoutId,
    CorrelationId,
    IdempotencyKey,
    ReservationId,
)
from .mongo_repo import MongoInventoryRepository


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the owner-side client per running loop; close on shutdown."""
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    repo = MongoInventoryRepository(client, os.getenv("INVENTORY_DB", "inventory"))
    await repo.ensure_indexes()
    app.state.repo = repo
    try:
        yield
    finally:
        client.close()


app = FastAPI(title="atlas-inventory", lifespan=lifespan)


def _repo(request: Request) -> MongoInventoryRepository:
    # Boundary narrow: app.state is framework-untyped; parse once here.
    repo = request.app.state.repo
    assert isinstance(repo, MongoInventoryRepository)
    return repo


class ReceiveStockIn(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    warehouse_id: str
    sku_id: str
    quantity: int
    correlation_id: str


class AdjustStockIn(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    warehouse_id: str
    sku_id: str
    delta: int
    reason: str
    actor: str
    correlation_id: str


class ReserveStockIn(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    warehouse_id: str
    sku_id: str
    quantity: int
    checkout_id: str
    idempotency_key: str
    correlation_id: str


class TransitionIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    correlation_id: str


def _position_body(
    warehouse_id: str, sku_id: str, on_hand: int, reserved: int, available: int, version: int
) -> dict[str, str | int]:
    return {
        "warehouse_id": warehouse_id,
        "sku_id": sku_id,
        "on_hand": on_hand,
        "reserved": reserved,
        "available": available,
        "version": version,
    }


@app.exception_handler(domain.NotFound)
async def _not_found(_request: Request, exc: domain.NotFound) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=404)


@app.exception_handler(domain.ValidationError)
async def _invalid(_request: Request, exc: domain.ValidationError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(domain.InsufficientStock)
async def _no_stock(_request: Request, exc: domain.InsufficientStock) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(domain.ConcurrencyError)
async def _conflict(_request: Request, exc: domain.ConcurrencyError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(domain.InvalidTransition)
async def _transition(_request: Request, exc: domain.InvalidTransition) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(domain.WriteConflict)
async def _write_conflict(_request: Request, exc: domain.WriteConflict) -> JSONResponse:
    return JSONResponse({"detail": f"{exc} (safe to retry)"}, status_code=409)


@app.post("/positions/receive", status_code=201)
async def receive_stock(body: ReceiveStockIn, request: Request) -> dict[str, str | int]:
    """Inbound intake for a warehouse+sku."""
    position = await handle_receive(
        ReceiveStock(
            warehouse_id=body.warehouse_id,
            sku_id=body.sku_id,
            quantity=body.quantity,
            correlation_id=CorrelationId(body.correlation_id),
        ),
        _repo(request),
    )
    return _position_body(
        position.warehouse_id,
        position.sku_id,
        position.on_hand,
        position.reserved,
        position.available(),
        position.version,
    )


@app.post("/positions/adjust")
async def adjust_stock(body: AdjustStockIn, request: Request) -> dict[str, str | int]:
    """Manual adjustment with mandatory reason and actor (audited)."""
    position = await handle_adjust(
        AdjustStock(
            warehouse_id=body.warehouse_id,
            sku_id=body.sku_id,
            delta=body.delta,
            reason=body.reason,
            actor=body.actor,
            correlation_id=CorrelationId(body.correlation_id),
        ),
        _repo(request),
    )
    return _position_body(
        position.warehouse_id,
        position.sku_id,
        position.on_hand,
        position.reserved,
        position.available(),
        position.version,
    )


@app.post("/reservations", status_code=201)
async def reserve_stock(body: ReserveStockIn, request: Request) -> dict[str, str | int]:
    """Idempotent conditional allocation. No stock -> 409, never negative."""
    reservation = await handle_reserve(
        ReserveStock(
            warehouse_id=body.warehouse_id,
            sku_id=body.sku_id,
            quantity=body.quantity,
            checkout_id=CheckoutId(body.checkout_id),
            idempotency_key=IdempotencyKey(body.idempotency_key),
            correlation_id=CorrelationId(body.correlation_id),
        ),
        _repo(request),
    )
    return {"id": reservation.id, "status": reservation.status, "quantity": reservation.quantity}


@app.post("/reservations/{reservation_id}/confirm")
async def confirm_reservation(
    reservation_id: str, body: TransitionIn, request: Request
) -> dict[str, str | int]:
    """ACTIVE -> CONFIRMED: on_hand and reserved both decrease."""
    reservation = await handle_confirm(
        ConfirmReservation(
            reservation_id=ReservationId(reservation_id),
            correlation_id=CorrelationId(body.correlation_id),
        ),
        _repo(request),
    )
    return {"id": reservation.id, "status": reservation.status}


@app.post("/reservations/{reservation_id}/release")
async def release_reservation(
    reservation_id: str, body: TransitionIn, request: Request
) -> dict[str, str | int]:
    """ACTIVE -> RELEASED: quantity returns to available."""
    reservation = await handle_release(
        ReleaseReservation(
            reservation_id=ReservationId(reservation_id),
            correlation_id=CorrelationId(body.correlation_id),
        ),
        _repo(request),
    )
    return {"id": reservation.id, "status": reservation.status}


@app.get("/positions/{warehouse_id}/{sku_id}")
async def get_position(warehouse_id: str, sku_id: str, request: Request) -> dict[str, str | int]:
    """Owner-side read. NEVER authoritative for checkout (INV-CQRS-001)."""
    position = await _repo(request).get(warehouse_id, sku_id)
    return _position_body(
        position.warehouse_id,
        position.sku_id,
        position.on_hand,
        position.reserved,
        position.available(),
        position.version,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
