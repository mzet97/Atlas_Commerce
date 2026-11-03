"""order_ops module: coupon rules + operational order commands (order owner).

Coupons require pricing_manager (market scope when scoped). Order cancel
requires fulfillment_operator; at or above the value threshold it takes
four eyes (a different finance_analyst checks), below it one operator
executes now. Control never stores canonical order state (ADR-0006).
"""

from __future__ import annotations

import uuid

import asyncpg
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from .audit import log_action
from .command_channel import (
    ScopeGrant,
    allowed,
    authenticate,
    forward,
    gate,
    json_out,
    threshold_minor,
)

router = APIRouter(prefix="/ops")
PRICING_MANAGER = "pricing_manager"
FULFILLMENT_OPERATOR = "fulfillment_operator"
CANCEL_ACTION = "order:cancel"


class CouponIn(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    code: str
    kind: str
    value: int
    market_id: str | None = None
    min_subtotal_minor: int = 0
    correlation_id: str


class DeactivateCouponIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    correlation_id: str


class OrderCommandIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    correlation_id: str


def _pool(request: Request) -> asyncpg.Pool:
    pool = request.app.state.pool
    assert isinstance(pool, asyncpg.Pool)
    return pool


def _scopes(market_id: str | None) -> list[ScopeGrant] | None:
    return [ScopeGrant(scope_type="market", scope_id=market_id)] if market_id else None


@router.post("/coupons", status_code=201)
async def upsert_coupon(body: CouponIn, request: Request) -> JSONResponse:
    """Pricing manager creates a coupon rule (optionally market-scoped)."""
    token = await gate(
        request,
        "coupon:manage",
        body.code,
        body.correlation_id,
        PRICING_MANAGER,
        _scopes(body.market_id),
    )
    status, coupon = await forward(
        request,
        "order_url",
        "POST",
        "/admin/coupons",
        {
            "code": body.code,
            "kind": body.kind,
            "value": body.value,
            "market_id": body.market_id,
            "min_subtotal_minor": body.min_subtotal_minor,
            "correlation_id": body.correlation_id,
        },
        token,
    )
    if status == 201:
        await allowed(request, token, "coupon:manage", body.code, body.correlation_id)
    return json_out(coupon, status)


@router.get("/coupons")
async def list_coupons(request: Request) -> JSONResponse:
    """Any pricing_manager reads the rules (authenticate-only gate)."""
    token = await authenticate(request)
    status, coupons = await forward(request, "order_url", "GET", "/admin/coupons", {}, token)
    return JSONResponse(coupons, status_code=status)


@router.post("/coupons/{code}/deactivate")
async def deactivate_coupon(
    code: str, body: DeactivateCouponIn, request: Request
) -> JSONResponse:
    """Pricing manager retires a coupon. Market scope re-checked when scoped."""
    market = await _coupon_market(request, code)
    token = await gate(
        request,
        "coupon:deactivate",
        code,
        body.correlation_id,
        PRICING_MANAGER,
        _scopes(market),
    )
    status, coupon = await forward(
        request,
        "order_url",
        "POST",
        f"/admin/coupons/{code}/deactivate",
        {"correlation_id": body.correlation_id},
        token,
    )
    if status == 200:
        await allowed(request, token, "coupon:deactivate", code, body.correlation_id)
    return json_out(coupon, status)


async def _coupon_market(request: Request, code: str) -> str | None:
    token = await authenticate(request)
    status, coupons = await forward(
        request, "order_url", "GET", "/admin/coupons", {}, token
    )
    if status != 200:
        return None
    for coupon in coupons:
        if coupon.get("code") == code:
            market = coupon.get("market_id")
            return str(market) if market else None
    return None


# -- operational order commands (M4) ------------------------------------


@router.post("/orders/{order_id}/cancel")
async def cancel_order(
    order_id: str, body: OrderCommandIn, request: Request
) -> JSONResponse:
    """Operator cancels an order; above the value threshold, four eyes.

    Below APPROVAL_THRESHOLD_MINOR the requesting operator executes now
    (audited); at or above it the request is FILED and a different
    finance_analyst approves before the owner command runs.
    """
    token = await gate(
        request, CANCEL_ACTION, order_id, body.correlation_id,
        FULFILLMENT_OPERATOR, None,
    )
    status, order = await forward(
        request, "order_url", "GET", f"/orders/{order_id}", {}, token
    )
    total = int(order.get("total_minor", 0)) if status == 200 else 0  # type: ignore[arg-type]
    if status == 200 and total < threshold_minor():
        status, cancelled = await forward(
            request,
            "order_url",
            "POST",
            f"/orders/{order_id}/cancel",
            {"correlation_id": body.correlation_id},
            token,
        )
        if status == 200:
            await allowed(
                request, token, CANCEL_ACTION, order_id, body.correlation_id
            )
        return json_out(cancelled, status)
    approval_id = f"apr-{uuid.uuid4().hex[:12]}"
    try:
        row = await _pool(request).fetchrow(
            "INSERT INTO finance_approvals"
            "(id, action, intent_id, requested_by, request_correlation_id,"
            " resource_type) VALUES ($1, $2, $3, $4, $5, 'order') RETURNING *",
            approval_id,
            CANCEL_ACTION,
            order_id,
            token.subject,
            body.correlation_id,
        )
    except asyncpg.UniqueViolationError:
        await log_action(
            _pool(request),
            actor_sub=token.subject,
            action=CANCEL_ACTION,
            resource_type="approval",
            resource_id=order_id,
            result="denied",
            correlation_id=body.correlation_id,
        )
        return JSONResponse({"detail": "cancel already pending"}, status_code=409)
    assert row is not None
    await allowed(request, token, CANCEL_ACTION, order_id, body.correlation_id)
    return JSONResponse(
        {
            "approval_id": row["id"],
            "action": row["action"],
            "resource_type": row["resource_type"],
            "status": row["status"],
            "requested_by": row["requested_by"],
        },
        status_code=202,
    )
