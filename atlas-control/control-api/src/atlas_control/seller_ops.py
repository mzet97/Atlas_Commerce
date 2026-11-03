"""seller_ops module: marketplace tenant registry (M10).

iam_admin registers sellers (tenants). Publishing 3P offers then requires
seller_operator + a (seller, id) scope grant — cross-tenant attempts are
403 + audited in pricing_ops. Zero tenant violation is the M10 gate.
"""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from .command_channel import allowed, gate

router = APIRouter(prefix="/ops/sellers")
IAM_ADMIN = "iam_admin"


class SellerIn(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    seller_id: str
    name: str
    correlation_id: str


def _pool(request: Request) -> asyncpg.Pool:
    pool = request.app.state.pool
    assert isinstance(pool, asyncpg.Pool)
    return pool


@router.post("", status_code=201)
async def register_seller(body: SellerIn, request: Request) -> JSONResponse:
    """iam_admin onboards a 3P tenant. Registry lives in the control DB."""
    token = await gate(
        request, "seller:register", body.seller_id, body.correlation_id,
        IAM_ADMIN, None,
    )
    row = await _pool(request).fetchrow(
        "INSERT INTO sellers (seller_id, name, created_by)"
        " VALUES ($1, $2, $3)"
        " ON CONFLICT (seller_id) DO UPDATE SET name = EXCLUDED.name"
        " RETURNING seller_id, name",
        body.seller_id,
        body.name,
        token.subject,
    )
    assert row is not None
    await allowed(request, token, "seller:register", body.seller_id, body.correlation_id)
    return JSONResponse({"seller_id": row["seller_id"], "name": row["name"]},
                        status_code=201)


@router.get("")
async def list_sellers(request: Request) -> JSONResponse:
    """Any authenticated operator reads the tenant registry."""
    from .command_channel import authenticate

    token = await authenticate(request)
    rows = await _pool(request).fetch(
        "SELECT seller_id, name, created_at FROM sellers ORDER BY created_at"
    )
    _ = token
    return JSONResponse([
        {"seller_id": r["seller_id"], "name": r["name"],
         "created_at": r["created_at"].isoformat()}
        for r in rows
    ])
