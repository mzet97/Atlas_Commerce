"""fulfillment_ops module: audited shipment handoff (M6).

Requires fulfillment_operator. Control never touches stock or money: it
reads the order view and triggers the owner-side CONFIRMED -> SHIPPED
transition. Returns (no refund path) stay OPEN: no PSP refund exists.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from .command_channel import allowed, forward, gate, json_out

router = APIRouter(prefix="/ops/fulfillment")
FULFILLMENT_OPERATOR = "fulfillment_operator"


class ShipIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    correlation_id: str


async def _owner_get(request: Request, path: str) -> tuple[int, dict[str, object]]:
    async with httpx.AsyncClient(
        base_url=request.app.state.order_url, timeout=15
    ) as http:
        response = await http.get(path)
    parsed = response.json()
    assert isinstance(parsed, dict)
    return response.status_code, parsed


@router.get("/orders/{order_id}")
async def view_order(order_id: str, request: Request) -> JSONResponse:
    """Operator views an order before handing it to logistics. 403 + audit."""
    token = await gate(
        request, "order:view", order_id, f"view-{order_id}",
        FULFILLMENT_OPERATOR, None,
    )
    status, order = await _owner_get(request, f"/orders/{order_id}")
    if status == 200:
        await allowed(request, token, "order:view", order_id, f"view-{order_id}")
    return json_out(order, status)


@router.post("/orders/{order_id}/ship")
async def ship_order(order_id: str, body: ShipIn, request: Request) -> JSONResponse:
    """Operator ships a CONFIRMED order. Owner owns the transition."""
    token = await gate(
        request, "order:ship", order_id, body.correlation_id,
        FULFILLMENT_OPERATOR, None,
    )
    status, order = await forward(
        request,
        "order_url",
        "POST",
        f"/orders/{order_id}/ship",
        {"correlation_id": body.correlation_id},
        token,
    )
    if status == 200:
        await allowed(request, token, "order:ship", order_id, body.correlation_id)
    return json_out(order, status)
