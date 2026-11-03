"""finance_ops module: audited finance reads + maker-checker money movement.

Requires finance_analyst. Control never touches PSP credentials or owner
Mongo: it reads the owner view and triggers owner-side reconciliation or
refunds. Reads execute directly; RECONCILE and REFUND below the value
threshold execute with a single audited analyst, at or above it they take
four eyes (M4): one analyst requests, a DIFFERENT analyst approves, and
only the approval executes (payload travels with the request).
"""

from __future__ import annotations

import json
import uuid

import asyncpg
import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from .audit import log_action
from .auth import Forbidden
from .command_channel import allowed, forward, gate, json_out, threshold_minor

router = APIRouter(prefix="/ops/finance")
FINANCE_ANALYST = "finance_analyst"
RECONCILE_ACTION = "payment:reconcile"
REFUND_ACTION = "payment:refund"


class ReconcileIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    correlation_id: str


class RefundIn(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    amount_minor: int | None = None
    reason: str = "refund"
    correlation_id: str


class DecideIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    correlation_id: str


async def _owner_get(request: Request, path: str) -> tuple[int, dict[str, object]]:
    """Authenticated read of the owner view (no body on GET)."""
    async with httpx.AsyncClient(
        base_url=request.app.state.payment_url, timeout=15
    ) as http:
        response = await http.get(path)
    parsed = response.json()
    assert isinstance(parsed, dict)
    return response.status_code, parsed


def _pool(request: Request) -> asyncpg.Pool:
    pool = request.app.state.pool
    assert isinstance(pool, asyncpg.Pool)
    return pool


def _approval_body(row: asyncpg.Record) -> dict[str, object]:
    return {
        "approval_id": row["id"],
        "action": row["action"],
        "resource_type": row["resource_type"],
        "intent_id": row["intent_id"],
        "status": row["status"],
        "requested_by": row["requested_by"],
        "decided_by": row["decided_by"],
        "execution_status": row["execution_status"],
    }


def _approval_full(row: asyncpg.Record) -> dict[str, object]:
    body = _approval_body(row)
    payload = row["payload"]
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            payload = {}
    body["payload"] = payload
    return body


@router.get("/payments/{intent_id}")
async def view_payment(intent_id: str, request: Request) -> JSONResponse:
    """Analyst views a payment intent. Others 403 + audit."""
    token = await gate(
        request, "payment:view", intent_id, f"view-{intent_id}", FINANCE_ANALYST, None
    )
    status, intent = await _owner_get(request, f"/intents/{intent_id}")
    if status == 200:
        await allowed(request, token, "payment:view", intent_id, f"view-{intent_id}")
    return json_out(intent, status)


@router.post("/payments/{intent_id}/reconcile")
async def request_reconcile(
    intent_id: str, body: ReconcileIn, request: Request
) -> JSONResponse:
    """Maker files a reconcile; below threshold ONE analyst executes now.

    Value threshold (APPROVAL_THRESHOLD_MINOR): intents under it may be
    reconciled by the requesting analyst directly (still audited); at or
    above it, nothing moves until a DIFFERENT analyst approves.
    """
    token = await gate(
        request, RECONCILE_ACTION, intent_id, body.correlation_id, FINANCE_ANALYST, None
    )
    status, intent = await _owner_get(request, f"/intents/{intent_id}")
    amount = int(intent.get("amount_minor", 0)) if status == 200 else 0  # type: ignore[arg-type]
    if amount < threshold_minor():
        status, intent = await forward(
            request,
            "payment_url",
            "POST",
            f"/intents/{intent_id}/reconcile",
            {"correlation_id": body.correlation_id},
            token,
        )
        if status == 200:
            await allowed(
                request, token, RECONCILE_ACTION, intent_id, body.correlation_id
            )
        return json_out(intent, status)
    approval_id = f"apr-{uuid.uuid4().hex[:12]}"
    try:
        row = await _pool(request).fetchrow(
            "INSERT INTO finance_approvals"
            "(id, action, intent_id, requested_by, request_correlation_id)"
            " VALUES ($1, $2, $3, $4, $5) RETURNING *",
            approval_id,
            RECONCILE_ACTION,
            intent_id,
            token.subject,
            body.correlation_id,
        )
    except asyncpg.UniqueViolationError:
        await log_action(
            _pool(request),
            actor_sub=token.subject,
            action=RECONCILE_ACTION,
            resource_type="approval",
            resource_id=intent_id,
            result="denied",
            correlation_id=body.correlation_id,
        )
        return JSONResponse({"detail": "reconcile already pending"}, status_code=409)
    assert row is not None
    await allowed(request, token, RECONCILE_ACTION, intent_id, body.correlation_id)
    return JSONResponse(_approval_body(row), status_code=202)


@router.post("/payments/{intent_id}/refund")
async def refund_payment(
    intent_id: str, body: RefundIn, request: Request
) -> JSONResponse:
    """Refund (payments:refund — never an AI tool, ADR-0005).

    Below the value threshold ONE analyst executes now; at or above it the
    request is FILED with its payload and a DIFFERENT analyst approves.
    """
    token = await gate(
        request, REFUND_ACTION, intent_id, body.correlation_id, FINANCE_ANALYST, None
    )
    status, intent = await _owner_get(request, f"/intents/{intent_id}")
    amount = int(intent.get("amount_minor", 0)) if status == 200 else 0  # type: ignore[arg-type]
    idem = f"refund-{intent_id}-{body.correlation_id[:24]}"
    payload: dict[str, object] = {
        "amount_minor": body.amount_minor,
        "reason": body.reason,
        "idempotency_key": idem,
    }
    if amount < threshold_minor():
        status, refunded = await forward(
            request,
            "payment_url",
            "POST",
            f"/intents/{intent_id}/refunds",
            {
                "amount_minor": body.amount_minor,
                "reason": body.reason,
                "idempotency_key": idem,
                "correlation_id": body.correlation_id,
            },
            token,
        )
        if status in (200, 201):
            await allowed(request, token, REFUND_ACTION, intent_id, body.correlation_id)
        return json_out(refunded, status)
    approval_id = f"apr-{uuid.uuid4().hex[:12]}"
    try:
        row = await _pool(request).fetchrow(
            "INSERT INTO finance_approvals"
            "(id, action, intent_id, requested_by, request_correlation_id,"
            " resource_type, payload)"
            " VALUES ($1, $2, $3, $4, $5, 'payment_intent', $6) RETURNING *",
            approval_id,
            REFUND_ACTION,
            intent_id,
            token.subject,
            body.correlation_id,
            json.dumps(payload),
        )
    except asyncpg.UniqueViolationError:
        await log_action(
            _pool(request),
            actor_sub=token.subject,
            action=REFUND_ACTION,
            resource_type="approval",
            resource_id=intent_id,
            result="denied",
            correlation_id=body.correlation_id,
        )
        return JSONResponse({"detail": "refund already pending"}, status_code=409)
    assert row is not None
    await allowed(request, token, REFUND_ACTION, intent_id, body.correlation_id)
    return JSONResponse(_approval_full(row), status_code=202)


@router.get("/approvals/pending")
async def list_pending(request: Request) -> JSONResponse:
    """Checker queue: every PENDING request awaiting a second pair of eyes."""
    await gate(request, "approval:list", None, "list", FINANCE_ANALYST, None)
    rows = await _pool(request).fetch(
        "SELECT * FROM finance_approvals WHERE status = 'PENDING'"
        " ORDER BY requested_at",
    )
    return JSONResponse([_approval_body(row) for row in rows])


@router.post("/approvals/{approval_id}/approve")
async def approve(
    approval_id: str, body: DecideIn, request: Request
) -> JSONResponse:
    """Checker: a DIFFERENT analyst approves and the command executes."""
    token = await gate(
        request, "approval:decide", approval_id, body.correlation_id,
        FINANCE_ANALYST, None,
    )
    pool = _pool(request)
    row = await pool.fetchrow(
        "SELECT * FROM finance_approvals WHERE id = $1", approval_id
    )
    if row is None:
        return JSONResponse({"detail": "approval not found"}, status_code=404)
    if row["status"] != "PENDING":
        return JSONResponse(
            {"detail": f"already {row['status']}".lower()}, status_code=409)
    if row["requested_by"] == token.subject:
        await log_action(
            pool,
            actor_sub=token.subject,
            action="approval:decide",
            resource_type="approval",
            resource_id=approval_id,
            result="denied",
            correlation_id=body.correlation_id,
        )
        raise Forbidden("maker cannot check its own request")
    if row["action"] == "order:cancel":
        status, target = await forward(
            request,
            "order_url",
            "POST",
            f"/orders/{row['intent_id']}/cancel",
            {"correlation_id": body.correlation_id},
            token,
        )
    elif row["action"] == REFUND_ACTION:
        filed = row["payload"]
        if isinstance(filed, str):
            try:
                filed = json.loads(filed)
            except ValueError:
                filed = {}
        filed = filed if isinstance(filed, dict) else {}
        status, target = await forward(
            request,
            "payment_url",
            "POST",
            f"/intents/{row['intent_id']}/refunds",
            {
                "amount_minor": filed.get("amount_minor"),
                "reason": filed.get("reason", "refund"),
                "idempotency_key": filed.get(
                    "idempotency_key", f"refund-{approval_id}"
                ),
                "correlation_id": body.correlation_id,
            },
            token,
        )
    else:
        status, target = await forward(
            request,
            "payment_url",
            "POST",
            f"/intents/{row['intent_id']}/reconcile",
            {"correlation_id": body.correlation_id},
            token,
        )
    if status in (200, 201):
        result, exec_status = "EXECUTED", status
    else:
        result, exec_status = "FAILED", status
    updated = await pool.fetchrow(
        "UPDATE finance_approvals SET status = $1, decided_by = $2,"
        " decided_at = now(), execution_status = $3 WHERE id = $4 RETURNING *",
        result,
        token.subject,
        exec_status,
        approval_id,
    )
    assert updated is not None
    await allowed(
        request, token, "approval:decide", approval_id, body.correlation_id
    )
    return json_out({**_approval_body(updated), "target": target}, status)


@router.post("/approvals/{approval_id}/reject")
async def reject(approval_id: str, body: DecideIn, request: Request) -> JSONResponse:
    """Checker declines the request. A fresh request may be filed later."""
    token = await gate(
        request, "approval:decide", approval_id, body.correlation_id,
        FINANCE_ANALYST, None,
    )
    pool = _pool(request)
    row = await pool.fetchrow(
        "SELECT * FROM finance_approvals WHERE id = $1", approval_id
    )
    if row is None:
        return JSONResponse({"detail": "approval not found"}, status_code=404)
    if row["status"] != "PENDING":
        return JSONResponse(
            {"detail": f"already {row['status']}".lower()}, status_code=409)
    if row["requested_by"] == token.subject:
        await log_action(
            pool,
            actor_sub=token.subject,
            action="approval:decide",
            resource_type="approval",
            resource_id=approval_id,
            result="denied",
            correlation_id=body.correlation_id,
        )
        raise Forbidden("maker cannot check its own request")
    updated = await pool.fetchrow(
        "UPDATE finance_approvals SET status = 'REJECTED', decided_by = $1,"
        " decided_at = now() WHERE id = $2 RETURNING *",
        token.subject,
        approval_id,
    )
    assert updated is not None
    await allowed(
        request, token, "approval:decide", approval_id, body.correlation_id
    )
    return JSONResponse(_approval_body(updated))
