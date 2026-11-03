"""Shared command channel: authN + authZ + audit + owner forwarding.

One seam for every Control write path: verify the JWT, require the role,
require each scope grant (market/warehouse), audit denied attempts with the
VERIFIED subject, and forward the command untouched (owner codes pass through).
"""

from __future__ import annotations

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from .audit import log_action
from .auth import Forbidden, InvalidToken, TokenInfo, require_role, verify_bearer


class Unauthorized(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail


class ScopeGrant(BaseModel):
    """One ABAC grant checked server-side: type market|warehouse + id."""

    model_config = ConfigDict(frozen=True)

    scope_type: str
    scope_id: str


async def _has_grant(request: Request, actor_sub: str, grant: ScopeGrant) -> bool:
    row = await request.app.state.pool.fetchrow(
        "SELECT 1 FROM scope_grants WHERE actor_sub = $1 AND scope_type = $2 AND scope_id = $3",
        actor_sub,
        grant.scope_type,
        grant.scope_id,
    )
    return row is not None


async def _deny(
    request: Request, token: TokenInfo, action: str, resource_id: str | None, correlation_id: str
) -> None:
    await log_action(
        request.app.state.pool,
        actor_sub=token.subject,
        action=action,
        resource_type="command",
        resource_id=resource_id,
        result="denied",
        correlation_id=correlation_id,
    )


async def authenticate(request: Request) -> TokenInfo:
    """Any authenticated operator (no mutation rights implied)."""
    try:
        return verify_bearer(request, request.app.state.issuer)
    except InvalidToken as exc:
        raise Unauthorized(str(exc)) from exc


async def gate(
    request: Request,
    action: str,
    resource_id: str | None,
    correlation_id: str,
    role: str,
    scopes: list[ScopeGrant] | None = None,
) -> TokenInfo:
    """Authenticate, authorize (role + scopes), audit denials. Raise 401/403."""
    try:
        token = verify_bearer(request, request.app.state.issuer)
    except InvalidToken as exc:
        raise Unauthorized(str(exc)) from exc
    try:
        require_role(token, role, action)
        for grant in scopes or []:
            if not await _has_grant(request, token.subject, grant):
                raise Forbidden(f"{action} [{grant.scope_type}={grant.scope_id}]")
    except Forbidden:
        await _deny(request, token, action, resource_id, correlation_id)
        raise
    return token


async def forward(
    request: Request,
    base_url_attr: str,
    method: str,
    path: str,
    body: dict[str, object],
    token: TokenInfo,
) -> tuple[int, dict[str, object]]:
    """Forward the owner command; owner status codes pass through untouched."""
    async with httpx.AsyncClient(
        base_url=getattr(request.app.state, base_url_attr), timeout=15
    ) as http:
        response = await http.request(
            method,
            path,
            json=body,
            headers={
                "X-Actor-Sub": token.subject,
                "X-Correlation-Id": str(body.get("correlation_id", "")),
            },
        )
    parsed = response.json()
    assert isinstance(parsed, dict)
    return response.status_code, parsed


async def allowed(
    request: Request, token: TokenInfo, action: str, resource_id: str | None, correlation_id: str
) -> None:
    """Audit an allowed command. Fail-open never: write errors propagate."""
    await log_action(
        request.app.state.pool,
        actor_sub=token.subject,
        action=action,
        resource_type="command",
        resource_id=resource_id,
        result="allowed",
        correlation_id=correlation_id,
    )


def json_out(payload: dict[str, object], status: int) -> JSONResponse:
    """Owner payloads pass through byte-identical in shape."""
    return JSONResponse(payload, status_code=status)
