"""order_ops module: coupon pricing rules for the checkout (order owner).

Requires pricing_manager AND a market grant when the coupon is scoped to
a market. Coupons live in the order owner's Mongo; Control never stores
canonical pricing state (ADR-0006).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from .command_channel import (
    ScopeGrant,
    allowed,
    authenticate,
    forward,
    gate,
    json_out,
)

router = APIRouter(prefix="/ops/coupons")
PRICING_MANAGER = "pricing_manager"


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


def _scopes(market_id: str | None) -> list[ScopeGrant] | None:
    return [ScopeGrant(scope_type="market", scope_id=market_id)] if market_id else None


@router.post("", status_code=201)
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


@router.get("")
async def list_coupons(request: Request) -> JSONResponse:
    """Any pricing_manager reads the rules (authenticate-only gate)."""
    token = await authenticate(request)
    status, coupons = await forward(request, "order_url", "GET", "/admin/coupons", {}, token)
    return JSONResponse(coupons, status_code=status)


@router.post("/{code}/deactivate")
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
