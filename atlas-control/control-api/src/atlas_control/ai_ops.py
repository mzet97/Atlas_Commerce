"""ai_ops module: merchandising curation for the AI recommender (M7).

Requires catalog_editor. The allowlist gates which ACTIVE offers the
storefront recommender may surface; it carries no PII and changes no
owner state. Reads stay on the projection.
"""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from .command_channel import allowed, gate

router = APIRouter(prefix="/ops/ai")
CATALOG_EDITOR = "catalog_editor"


class AllowIn(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    offer_id: str
    reason: str = ""
    correlation_id: str = ""
    weight: float = 1.0
    expires_at: str | None = None  # ISO-8601; null = curated until removed


def _pool(request: Request) -> asyncpg.Pool:
    """Curation writes land in the atlas read-model DB (next to the view)."""
    pool = request.app.state.atlas_pool
    assert isinstance(pool, asyncpg.Pool)
    return pool


@router.post("/allowlist", status_code=201)
async def allow_offer(body: AllowIn, request: Request) -> JSONResponse:
    """Curator allowlists an offer for AI surfacing. Idempotent re-add.

    weight feeds the storefront ranking; expires_at is the curation TTL
    (M7 gate): expired rows silently stop surfacing, no rewrite needed.
    """
    token = await gate(
        request, "ai:allow", body.offer_id, body.correlation_id,
        CATALOG_EDITOR, None,
    )
    row = await _pool(request).fetchrow(
        "INSERT INTO ai_allowlist (offer_id, reason, weight, expires_at)"
        " VALUES ($1, $2, $3, $4)"
        " ON CONFLICT (offer_id) DO UPDATE SET reason = EXCLUDED.reason,"
        " weight = EXCLUDED.weight, expires_at = EXCLUDED.expires_at"
        " RETURNING offer_id, reason, weight, expires_at",
        body.offer_id,
        body.reason,
        body.weight,
        body.expires_at,
    )
    assert row is not None
    await allowed(request, token, "ai:allow", body.offer_id, body.correlation_id)
    return JSONResponse(
        {
            "offer_id": row["offer_id"],
            "reason": row["reason"],
            "weight": float(row["weight"]),
            "expires_at": (
                row["expires_at"].isoformat() if row["expires_at"] else None
            ),
        },
        status_code=201,
    )


@router.delete("/allowlist/{offer_id}")
async def remove_offer(
    offer_id: str, request: Request, correlation_id: str = ""
) -> JSONResponse:
    """Curator removes an offer from AI surfacing. Missing is 404."""
    token = await gate(
        request, "ai:remove", offer_id, correlation_id, CATALOG_EDITOR, None
    )
    deleted = await _pool(request).execute(
        "DELETE FROM ai_allowlist WHERE offer_id = $1", offer_id
    )
    if deleted == "DELETE 0":
        return JSONResponse({"detail": "not allowlisted"}, status_code=404)
    await allowed(request, token, "ai:remove", offer_id, correlation_id)
    return JSONResponse({"offer_id": offer_id, "removed": True})


@router.get("/allowlist")
async def list_allowlist(request: Request) -> JSONResponse:
    """Curator/auditor reads the current allowlist."""
    await gate(request, "ai:view", None, "ai-list", CATALOG_EDITOR, None)
    rows = await _pool(request).fetch(
        "SELECT offer_id, reason, added_at FROM ai_allowlist ORDER BY added_at"
    )
    return JSONResponse([
        {"offer_id": r["offer_id"], "reason": r["reason"],
         "added_at": r["added_at"].isoformat()} for r in rows
    ])
