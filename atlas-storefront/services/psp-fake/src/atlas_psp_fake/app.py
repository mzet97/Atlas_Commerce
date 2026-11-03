"""Deterministic fake PSP (DEV/TEST ONLY). No randomness, no PAN storage."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
import uuid

import httpx
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

app = FastAPI(title="atlas-psp-fake")

SECRET = os.getenv("PSP_WEBHOOK_SECRET", "psp-dev-secret")
CALLBACK_URL = os.getenv("PSP_CALLBACK_URL", "")
DECLINED_SUFFIX = "0002"
# Simulator knobs live on the CARD, never the amount: checkout totals now
# carry regional tax, so amount-matching would drift (found by the
# coupon/tax drill). 6666 = slow authorization; 9999 = never responds
# (only reconciliation truth resolves it).
TIMEOUT_SUFFIX = "6666"
UNKNOWN_SUFFIX = "9999"

_charges: dict[str, dict] = {}
_by_idem: dict[str, dict] = {}


def sign(body: bytes, timestamp: str) -> str:
    """HMAC-SHA256 over timestamp + '.' + raw body (payment webhooks)."""
    return hmac.new(SECRET.encode(), f"{timestamp}.".encode() + body,
                    hashlib.sha256).hexdigest()


class ChargeIn(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    amount_minor: int
    currency: str
    card_last4: str
    idempotency_key: str
    order_id: str


def _approved(ref: str, body: ChargeIn) -> dict:
    return {"approved": True, "provider_ref": ref,
            "amount_minor": body.amount_minor, "currency": body.currency}


async def _deliver_webhook(event: str, charge: dict, chaos: str) -> None:
    """Best-effort signed delivery; chaos modes drill dedup/ordering."""
    if not CALLBACK_URL:
        return
    payload = json.dumps({"event": event, "provider_ref": charge["provider_ref"],
                          "order_id": charge["order_id"],
                          "amount_minor": charge["amount_minor"]}).encode()
    stamp = str(int(time.time()))
    headers = {"X-PSP-Signature": sign(payload, stamp),
               "X-PSP-Timestamp": stamp,
               "Content-Type": "application/json"}
    sends = 2 if chaos == "duplicate" else 1
    delay = 0
    if chaos.startswith("delay:"):
        try:
            delay = int(chaos.split(":", 1)[1])
        except ValueError:
            delay = 0
    async with httpx.AsyncClient(timeout=10) as http:
        for _ in range(sends):
            if delay:
                await asyncio.sleep(delay)
            try:
                await http.post(CALLBACK_URL, content=payload, headers=headers)
            except httpx.HTTPError:
                pass  # simulator delivery is best-effort; status query is truth


@app.post("/charges")
async def charge(body: ChargeIn, x_chaos: str = Header(default="")) -> JSONResponse:
    """Authorize. Deterministic by card/amount; idempotent on key."""
    if body.idempotency_key in _by_idem:
        original, status = _by_idem[body.idempotency_key]
        return JSONResponse({**original, "duplicate": True}, status_code=status)
    ref = f"psp-{uuid.uuid4().hex[:12]}"
    record = {"provider_ref": ref, "order_id": body.order_id,
              "amount_minor": body.amount_minor, "currency": body.currency,
              "status": "approved", "attempts": 1}
    if body.card_last4.endswith(DECLINED_SUFFIX):
        record["status"] = "declined"
        _charges[ref] = record
        response = {"approved": False, "code": "DECLINED", "provider_ref": ref}
        _by_idem[body.idempotency_key] = (response, 200)
        await _deliver_webhook("declined", record, x_chaos)
        return JSONResponse(response)
    if body.card_last4.endswith(UNKNOWN_SUFFIX):
        record["status"] = "approved"
        _charges[ref] = record
        pending = {"provider_ref": ref, "pending": True,
                   "error": "acquirer timeout"}
        _by_idem[body.idempotency_key] = (pending, 500)
        return JSONResponse(pending, status_code=500)
    if body.card_last4.endswith(TIMEOUT_SUFFIX):
        await asyncio.sleep(12)
    _charges[ref] = record
    response = _approved(ref, body)
    _by_idem[body.idempotency_key] = (response, 200)
    await _deliver_webhook("authorized", record, x_chaos)
    return JSONResponse(response)


@app.get("/charges/by-key/{idempotency_key}")
async def charge_by_key(idempotency_key: str) -> JSONResponse:
    """Reconcile timeouts: find the charge when the client never saw a ref."""
    entry = _by_idem.get(idempotency_key)
    if entry is None:
        return JSONResponse({"error": "no charge for key"}, status_code=404)
    response, _status = entry
    return JSONResponse(response)


@app.get("/charges/{provider_ref}")
async def charge_status(provider_ref: str) -> JSONResponse:
    """Reconciliation truth: UNKNOWN outcomes resolve here, never by retry."""
    record = _charges.get(provider_ref)
    if record is None:
        return JSONResponse({"error": "unknown provider_ref"}, status_code=404)
    return JSONResponse({"provider_ref": provider_ref,
                         "status": record["status"]})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
