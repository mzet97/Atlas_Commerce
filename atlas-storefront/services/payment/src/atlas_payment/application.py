"""Application: intent commands, PSP calls, signed webhooks, reconciliation.

UNKNOWN resolves ONLY via reconcile (PSP status query), never by re-charge:
a retried charge after a timeout would double-pay. Webhooks move non-terminal
intents; terminal intents record the webhook as a no-op (out-of-order safe).
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
import uuid
from dataclasses import dataclass

import httpx

from . import domain
from .domain import CorrelationId, IdempotencyKey, IntentId, PaymentIntent
from .mongo_repo import MongoPaymentRepository

SIGNATURE_WINDOW_SECONDS = 300


class PSPError(Exception):
    """Transport failure talking to the PSP (timeout, 5xx without ref)."""


@dataclass(frozen=True, slots=True)
class CreateIntent:
    order_id: str
    customer_id: str
    amount_minor: int
    currency: str
    card_last4: str
    idempotency_key: str
    correlation_id: str


def verify_signature(secret: str, raw_body: bytes, timestamp: str, signature: str) -> bool:
    """HMAC-SHA256 over timestamp + '.' + raw body, ±5min window."""
    try:
        stamp = int(timestamp)
    except ValueError:
        return False
    if abs(time.time() - stamp) > SIGNATURE_WINDOW_SECONDS:
        return False
    expected = hmac.new(
        secret.encode(), f"{timestamp}.".encode() + raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _psp_base() -> str:
    return os.getenv("PSP_BASE_URL", "http://localhost:8190")


def _psp_timeout() -> float:
    return float(os.getenv("PSP_TIMEOUT_SECONDS", "10"))


async def psp_charge(
    order_id: str, amount_minor: int, currency: str, card_last4: str,
    idempotency_key: str, chaos: str = "",
) -> dict[str, object]:
    """Single charge attempt. Timeout raises PSPError (outcome stays UNKNOWN)."""
    headers = {"X-Chaos": chaos} if chaos else {}
    try:
        async with httpx.AsyncClient(timeout=_psp_timeout()) as http:
            response = await http.post(
                f"{_psp_base()}/charges",
                json={"order_id": order_id, "amount_minor": amount_minor,
                      "currency": currency, "card_last4": card_last4,
                      "idempotency_key": idempotency_key},
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise PSPError(f"psp timeout for key {idempotency_key}") from exc
    except httpx.HTTPError as exc:
        raise PSPError(f"psp unreachable: {exc}") from exc
    if response.status_code == 500:
        body = response.json()
        ref = body.get("provider_ref")
        return {"unknown": True, "provider_ref": ref if isinstance(ref, str) else None}
    body = response.json()
    return {"approved": bool(body.get("approved")), "provider_ref": body.get("provider_ref"),
            "decline_code": body.get("code")}


async def psp_status(provider_ref: str) -> str:
    """Reconciliation truth: the PSP owns the outcome of UNKNOWN charges."""
    try:
        async with httpx.AsyncClient(timeout=_psp_timeout()) as http:
            response = await http.get(f"{_psp_base()}/charges/{provider_ref}")
    except httpx.HTTPError as exc:
        raise PSPError(f"psp status unreachable: {exc}") from exc
    if response.status_code != 200:
        raise PSPError(f"psp unknown ref {provider_ref}")
    return str(response.json().get("status", ""))


async def psp_by_key(idempotency_key: str) -> dict[str, object]:
    """Find a charge the client timed out on (no ref seen). 404 -> {}."""
    try:
        async with httpx.AsyncClient(timeout=_psp_timeout()) as http:
            response = await http.get(f"{_psp_base()}/charges/by-key/{idempotency_key}")
    except httpx.HTTPError as exc:
        raise PSPError(f"psp lookup unreachable: {exc}") from exc
    if response.status_code != 200:
        return {}
    return dict(response.json())


async def handle_create(repo: MongoPaymentRepository, cmd: CreateIntent) -> PaymentIntent:
    """Initiate (idempotent) then drive one PSP attempt to a final outcome."""
    intent = await repo.initiate(
        PaymentIntent.initiate(
            IntentId(f"pi-{uuid.uuid4().hex[:12]}"),
            cmd.order_id,
            cmd.customer_id,
            cmd.amount_minor,
            cmd.currency,
            cmd.card_last4,
            IdempotencyKey(cmd.idempotency_key),
            CorrelationId(cmd.correlation_id),
        )
    )
    if intent.status != domain.INITIATED:
        return intent  # idempotent replay: the winner already drove an outcome
    correlation = CorrelationId(cmd.correlation_id)
    try:
        outcome = await psp_charge(
            cmd.order_id, cmd.amount_minor, cmd.currency,
            cmd.card_last4, cmd.idempotency_key,
        )
    except PSPError:
        intent.mark_unknown(None, correlation)
        return await repo.save_with_events(intent)
    if outcome.get("unknown"):
        ref = outcome.get("provider_ref")
        intent.mark_unknown(ref if isinstance(ref, str) else None, correlation)
        return await repo.save_with_events(intent)
    ref = outcome.get("provider_ref")
    provider_ref = ref if isinstance(ref, str) else ""
    if outcome.get("approved"):
        intent.authorize(provider_ref, correlation)
    else:
        code = outcome.get("decline_code")
        intent.decline(provider_ref or None,
                       code if isinstance(code, str) else "DECLINED", correlation)
    try:
        return await repo.save_with_events(intent)
    except domain.WriteConflict:
        # The PSP webhook (delivered before the charge response) already
        # applied the same outcome: converge on it instead of double-applying.
        current = await repo.get(intent.id)
        if current.status in domain.TERMINAL and current.provider_ref == provider_ref:
            return current
        raise


def _received_event(
    intent: PaymentIntent, event: str, correlation: CorrelationId
) -> domain.DomainEvent:
    """Traceability event: every first-seen webhook is observable downstream."""
    return domain.new_event(
        "PaymentWebhookReceived",
        intent.id,
        intent.version,
        correlation,
        {**intent._payload(), "event": event},
        causation_id=intent.events[0].event_id if intent.events else None,
    )


async def handle_webhook(
    repo: MongoPaymentRepository,
    provider_ref: str,
    event: str,
    order_id: str,
    correlation_id: str,
) -> PaymentIntent | None:
    """Apply a verified webhook. Replays and terminal intents are no-ops.

    Dedup record + transition + outbox commit atomically (repo.apply_webhook),
    so a crash mid-apply redelivers cleanly and converges.
    """
    intent = await repo.find_for_webhook(provider_ref, order_id)
    if intent is None:
        return None
    correlation = CorrelationId(correlation_id)
    if intent.status not in domain.TERMINAL and event in ("authorized", "declined"):
        if event == "authorized":
            intent.authorize(provider_ref, correlation)
        else:
            intent.decline(provider_ref, "DECLINED", correlation)
    # Terminal intents and unknown event names: record + trace, no transition.
    received = _received_event(intent, event, correlation)
    try:
        saved, _ = await repo.apply_webhook(
            intent, provider_ref, event, order_id, [received]
        )
    except domain.WriteConflict:
        # A concurrent reconcile won the race; its outcome stands.
        return await repo.get(intent.id)
    return saved


async def handle_reconcile(
    repo: MongoPaymentRepository, intent_id: IntentId, correlation_id: str
) -> PaymentIntent:
    """UNKNOWN -> AUTHORIZED/DECLINED via PSP truth. Terminal intents untouched."""
    intent = await repo.get(intent_id)
    if intent.status != domain.UNKNOWN:
        return intent
    correlation = CorrelationId(correlation_id)
    ref = intent.provider_ref
    if ref is None:
        found = await psp_by_key(str(intent.idempotency_key))
        maybe_ref = found.get("provider_ref")
        if not isinstance(maybe_ref, str):
            return intent  # PSP never saw it: stays UNKNOWN, retry reconcile later
        ref = maybe_ref
        intent.provider_ref = ref
    status = await psp_status(ref)
    if status == "approved":
        intent.authorize(ref, correlation)
    elif status == "declined":
        intent.decline(ref, "DECLINED", correlation)
    else:
        return intent
    reconciled = domain.new_event(
        "PaymentReconciled",
        intent.id,
        intent.version,
        correlation,
        {**intent._payload(), "outcome": status},
        causation_id=intent.events[0].event_id if intent.events else None,
    )
    return await repo.save_with_events(intent, [reconciled])
