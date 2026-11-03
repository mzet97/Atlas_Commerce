"""stock_ops module: inventory command channel to the Inventory owner.

Requires inventory_operator AND a warehouse grant for the position's
warehouse. Receive/adjust/reserve go through the owner; the Control
never touches positions, reservations or the ledger.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from .command_channel import ScopeGrant, allowed, forward, gate, json_out

router = APIRouter(prefix="/ops/stock")
INVENTORY_OPERATOR = "inventory_operator"


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
    correlation_id: str


class ReserveStockIn(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    warehouse_id: str
    sku_id: str
    quantity: int
    checkout_id: str
    idempotency_key: str
    correlation_id: str


def _warehouse_scope(warehouse_id: str) -> list[ScopeGrant]:
    return [ScopeGrant(scope_type="warehouse", scope_id=warehouse_id)]


@router.post("/receive", status_code=201)
async def receive_stock(body: ReceiveStockIn, request: Request) -> JSONResponse:
    """Inbound intake for a granted warehouse. Others 403 + audit."""
    token = await gate(
        request,
        "stock:receive",
        None,
        body.correlation_id,
        INVENTORY_OPERATOR,
        _warehouse_scope(body.warehouse_id),
    )
    status, position = await forward(
        request,
        "inventory_url",
        "POST",
        "/positions/receive",
        {
            "warehouse_id": body.warehouse_id,
            "sku_id": body.sku_id,
            "quantity": body.quantity,
            "correlation_id": body.correlation_id,
        },
        token,
    )
    if status == 201:
        await allowed(
            request,
            token,
            "stock:receive",
            f"{body.warehouse_id}:{body.sku_id}",
            body.correlation_id,
        )
    return json_out(position, status)


@router.post("/adjust")
async def adjust_stock(body: AdjustStockIn, request: Request) -> JSONResponse:
    """Manual adjustment with reason; actor is the verified subject."""
    token = await gate(
        request,
        "stock:adjust",
        None,
        body.correlation_id,
        INVENTORY_OPERATOR,
        _warehouse_scope(body.warehouse_id),
    )
    status, position = await forward(
        request,
        "inventory_url",
        "POST",
        "/positions/adjust",
        {
            "warehouse_id": body.warehouse_id,
            "sku_id": body.sku_id,
            "delta": body.delta,
            "reason": body.reason,
            "actor": token.subject,
            "correlation_id": body.correlation_id,
        },
        token,
    )
    if status == 200:
        await allowed(
            request,
            token,
            "stock:adjust",
            f"{body.warehouse_id}:{body.sku_id}",
            body.correlation_id,
        )
    return json_out(position, status)


@router.post("/reserve", status_code=201)
async def reserve_stock(body: ReserveStockIn, request: Request) -> JSONResponse:
    """Idempotent conditional allocation for a granted warehouse."""
    token = await gate(
        request,
        "stock:reserve",
        None,
        body.correlation_id,
        INVENTORY_OPERATOR,
        _warehouse_scope(body.warehouse_id),
    )
    status, reservation = await forward(
        request,
        "inventory_url",
        "POST",
        "/reservations",
        {
            "warehouse_id": body.warehouse_id,
            "sku_id": body.sku_id,
            "quantity": body.quantity,
            "checkout_id": body.checkout_id,
            "idempotency_key": body.idempotency_key,
            "correlation_id": body.correlation_id,
        },
        token,
    )
    if status == 201:
        await allowed(
            request, token, "stock:reserve", str(reservation.get("id", "")), body.correlation_id
        )
    return json_out(reservation, status)
