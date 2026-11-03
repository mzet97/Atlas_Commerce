"""HTTP boundary: intents, signed PSP webhooks, reconciliation."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict

from . import application, domain
from .application import CreateIntent
from .domain import IntentId
from .mongo_repo import MongoPaymentRepository


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the owner-side client per running loop; close on shutdown."""
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    repo = MongoPaymentRepository(client, os.getenv("PAYMENT_DB", "payment"))
    await repo.ensure_indexes()
    app.state.repo = repo
    try:
        yield
    finally:
        client.close()


app = FastAPI(title="atlas-payment", lifespan=lifespan)


def _repo(request: Request) -> MongoPaymentRepository:
    repo = request.app.state.repo
    assert isinstance(repo, MongoPaymentRepository)
    return repo


class CreateIntentRequest(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    order_id: str
    customer_id: str
    amount_minor: int
    currency: str
    card_last4: str
    idempotency_key: str
    correlation_id: str


class ReconcileRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    correlation_id: str


def _body(intent: domain.PaymentIntent) -> dict[str, object]:
    return {
        "id": intent.id,
        "status": intent.status,
        "version": intent.version,
        "order_id": intent.order_id,
        "amount_minor": intent.amount_minor,
        "currency": intent.currency,
        "provider_ref": intent.provider_ref,
        "decline_code": intent.decline_code,
        "refunded_minor": intent.refunded_minor,
    }


@app.exception_handler(domain.NotFound)
async def _not_found(_request: Request, exc: domain.NotFound) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=404)


@app.exception_handler(domain.ValidationError)
async def _validation(_request: Request, exc: domain.ValidationError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(domain.InvalidTransition)
async def _transition(_request: Request, exc: domain.InvalidTransition) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(domain.WriteConflict)
async def _conflict(_request: Request, exc: domain.WriteConflict) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(domain.DuplicatePayment)
async def _duplicate(_request: Request, exc: domain.DuplicatePayment) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(application.PSPError)
async def _psp_error(_request: Request, exc: application.PSPError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=502)


@app.post("/intents", status_code=201)
async def create_intent(body: CreateIntentRequest, request: Request) -> JSONResponse:
    """Initiate and drive one PSP attempt (200/402/202 semantics via status)."""
    intent = await application.handle_create(
        _repo(request),
        CreateIntent(
            order_id=body.order_id,
            customer_id=body.customer_id,
            amount_minor=body.amount_minor,
            currency=body.currency,
            card_last4=body.card_last4,
            idempotency_key=body.idempotency_key,
            correlation_id=body.correlation_id,
        ),
    )
    return JSONResponse(_body(intent), status_code=201)


@app.get("/intents/{intent_id}")
async def get_intent(intent_id: str, request: Request) -> JSONResponse:
    """Read a single intent (stale-read drill: projection may lag this view)."""
    intent = await _repo(request).get(IntentId(intent_id))
    return JSONResponse(_body(intent))


class RefundRequest(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    amount_minor: int | None = None
    reason: str = "refund"
    idempotency_key: str
    correlation_id: str


@app.post("/intents/{intent_id}/refunds", status_code=201)
async def refund_intent(
    intent_id: str, body: RefundRequest, request: Request
) -> JSONResponse:
    """Refund (full by default, partial by amount). PSP truth first.

    Reached from Control four-eyes (payments:refund — never an AI tool)
    and from RMA approvals. Replays converge on the stored refund.
    """
    intent = await application.handle_refund(
        _repo(request),
        application.RefundCommand(
            intent_id=intent_id,
            amount_minor=body.amount_minor,
            reason=body.reason,
            idempotency_key=body.idempotency_key,
            correlation_id=body.correlation_id,
        ),
    )
    return JSONResponse(_body(intent), status_code=201)


@app.post("/webhooks/psp")
async def psp_webhook(request: Request) -> JSONResponse:
    """Verified, deduplicated webhook entry. Bad signature -> 401, no state."""
    raw = await request.body()
    signature = request.headers.get("X-PSP-Signature", "")
    timestamp = request.headers.get("X-PSP-Timestamp", "")
    secret = os.getenv("PSP_WEBHOOK_SECRET", "psp-dev-secret")
    if not application.verify_signature(secret, raw, timestamp, signature):
        return JSONResponse({"detail": "bad signature"}, status_code=401)
    try:
        payload = json.loads(raw.decode())
    except ValueError:
        return JSONResponse({"detail": "bad json"}, status_code=400)
    event = payload.get("event")
    provider_ref = payload.get("provider_ref")
    order_id = payload.get("order_id", "")
    if not isinstance(event, str) or not isinstance(provider_ref, str):
        return JSONResponse({"detail": "bad event"}, status_code=400)
    correlation = request.headers.get("X-Correlation-Id", f"wh-{provider_ref}")
    intent = await application.handle_webhook(
        _repo(request), provider_ref, event, order_id, correlation
    )
    if intent is None:
        return JSONResponse({"detail": "intent not found"}, status_code=202)
    return JSONResponse(_body(intent))


@app.post("/intents/{intent_id}/reconcile")
async def reconcile(
    intent_id: str, body: ReconcileRequest, request: Request
) -> JSONResponse:
    """UNKNOWN resolves here via PSP truth; terminal intents return untouched."""
    intent = await application.handle_reconcile(
        _repo(request), IntentId(intent_id), body.correlation_id
    )
    return JSONResponse(_body(intent))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
