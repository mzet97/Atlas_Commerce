"""Atlas Payment domain: PaymentIntent aggregate + versioned events (pure, no IO).

Statuses: INITIATED -> AUTHORIZED | DECLINED | UNKNOWN -> AUTHORIZED | DECLINED.
UNKNOWN resolves ONLY via reconcile (PSP status query), never by re-charge.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final, NewType, TypedDict

IntentId = NewType("IntentId", str)
CorrelationId = NewType("CorrelationId", str)
IdempotencyKey = NewType("IdempotencyKey", str)

SCHEMA_VERSION: Final = 1
INITIATED: Final = "INITIATED"
AUTHORIZED: Final = "AUTHORIZED"
DECLINED: Final = "DECLINED"
UNKNOWN: Final = "UNKNOWN"
TERMINAL: Final = frozenset({AUTHORIZED, DECLINED})


class IntentPayload(TypedDict, total=False):
    intent_id: str
    order_id: str
    customer_id: str
    amount_minor: int
    currency: str
    status: str
    provider_ref: str | None
    decline_code: str | None
    event: str
    outcome: str


Envelope = dict[str, str | int | IntentPayload | None]


class DomainError(Exception):
    """Base for all payment domain failures."""


@dataclass
class ValidationError(DomainError):
    field: str
    reason: str

    def __str__(self) -> str:
        return f"invalid {self.field}: {self.reason}"


@dataclass
class InvalidTransition(DomainError):
    status: str
    event: str

    def __str__(self) -> str:
        return f"cannot {self.event} from {self.status}"


@dataclass
class WriteConflict(DomainError):
    """Idempotency race landed nowhere readable; safe to retry the command."""

    idempotency_key: IdempotencyKey

    def __str__(self) -> str:
        return f"idempotency write lost for key: {self.idempotency_key}"


@dataclass
class DuplicatePayment(DomainError):
    """One provider_ref already backs an AUTHORIZED intent (duplicate_paid_order)."""

    provider_ref: str

    def __str__(self) -> str:
        return f"provider_ref already paid: {self.provider_ref}"


@dataclass
class NotFound(DomainError):
    intent_id: IntentId

    def __str__(self) -> str:
        return f"intent not found: {self.intent_id}"


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: str
    event_type: str
    aggregate_id: IntentId
    aggregate_version: int
    occurred_at: str
    schema_version: int
    correlation_id: CorrelationId
    causation_id: str | None
    payload: IntentPayload

    def envelope(self) -> Envelope:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "aggregate_version": self.aggregate_version,
            "occurred_at": self.occurred_at,
            "schema_version": self.schema_version,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "payload": self.payload,
        }


def new_event(
    event_type: str,
    aggregate_id: IntentId,
    aggregate_version: int,
    correlation_id: CorrelationId,
    payload: IntentPayload,
    causation_id: str | None = None,
) -> DomainEvent:
    """Create a versioned domain event for the outbox envelope (INV-010)."""
    return DomainEvent(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_version=aggregate_version,
        occurred_at=datetime.now(UTC).isoformat(),
        schema_version=SCHEMA_VERSION,
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload=payload,
    )


@dataclass(slots=True)
class PaymentIntent:
    """Payment aggregate. Transitions append events for the outbox write."""

    id: IntentId
    version: int
    status: str
    order_id: str
    customer_id: str
    amount_minor: int
    currency: str
    card_last4: str
    idempotency_key: IdempotencyKey
    provider_ref: str | None = None
    decline_code: str | None = None
    refunded_minor: int = 0
    events: list[DomainEvent] = field(default_factory=list, repr=False)

    @classmethod
    def initiate(
        cls,
        intent_id: IntentId,
        order_id: str,
        customer_id: str,
        amount_minor: int,
        currency: str,
        card_last4: str,
        idempotency_key: IdempotencyKey,
        correlation_id: CorrelationId,
    ) -> PaymentIntent:
        """Create an INITIATED intent, emitting PaymentInitiated for the outbox."""
        if amount_minor <= 0:
            raise ValidationError(field="amount_minor", reason="must be positive")
        if not currency.strip():
            raise ValidationError(field="currency", reason="required")
        intent = cls(
            id=intent_id,
            version=1,
            status=INITIATED,
            order_id=order_id,
            customer_id=customer_id,
            amount_minor=amount_minor,
            currency=currency,
            card_last4=card_last4,
            idempotency_key=idempotency_key,
        )
        intent.events.append(
            new_event(
                "PaymentInitiated",
                intent_id,
                1,
                correlation_id,
                intent._payload(),
            )
        )
        return intent

    def _payload(self) -> IntentPayload:
        return {
            "intent_id": self.id,
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "amount_minor": self.amount_minor,
            "currency": self.currency,
            "status": self.status,
            "provider_ref": self.provider_ref,
            "decline_code": self.decline_code,
            "refunded_minor": self.refunded_minor,
        }

    def _transition(
        self, event_type: str, status: str, correlation_id: CorrelationId
    ) -> DomainEvent:
        self.status = status
        self.version += 1
        event = new_event(
            event_type,
            self.id,
            self.version,
            correlation_id,
            self._payload(),
            causation_id=self.events[0].event_id if self.events else None,
        )
        self.events.append(event)
        return event

    def authorize(
        self, provider_ref: str, correlation_id: CorrelationId
    ) -> DomainEvent:
        """INITIATED/UNKNOWN -> AUTHORIZED (charge approved or reconciled)."""
        if self.status not in (INITIATED, UNKNOWN):
            raise InvalidTransition(status=self.status, event="authorize")
        self.provider_ref = provider_ref
        return self._transition("PaymentAuthorized", AUTHORIZED, correlation_id)

    def decline(
        self, provider_ref: str | None, code: str, correlation_id: CorrelationId
    ) -> DomainEvent:
        """INITIATED/UNKNOWN -> DECLINED (business decline or reconciled)."""
        if self.status not in (INITIATED, UNKNOWN):
            raise InvalidTransition(status=self.status, event="decline")
        self.provider_ref = provider_ref
        self.decline_code = code
        return self._transition("PaymentDeclined", DECLINED, correlation_id)

    def mark_unknown(
        self, provider_ref: str | None, correlation_id: CorrelationId
    ) -> DomainEvent:
        """INITIATED -> UNKNOWN (timeout/5xx: outcome known only to the PSP)."""
        if self.status != INITIATED:
            raise InvalidTransition(status=self.status, event="mark_unknown")
        self.provider_ref = provider_ref
        return self._transition("PaymentUnknown", UNKNOWN, correlation_id)

    def refundable_minor(self) -> int:
        """What may still go back: charged minus already refunded."""
        return self.amount_minor - self.refunded_minor

    def refund(
        self, amount_minor: int, correlation_id: CorrelationId
    ) -> DomainEvent:
        """AUTHORIZED -> AUTHORIZED with refunded_minor grown (INV-006: refund
        appends an auditable event, never an in-place edit)."""
        if self.status != AUTHORIZED:
            raise InvalidTransition(status=self.status, event="refund")
        if amount_minor <= 0 or amount_minor > self.refundable_minor():
            raise ValidationError(field="amount_minor", reason="exceeds refundable")
        self.refunded_minor += amount_minor
        return self._transition("PaymentRefunded", AUTHORIZED, correlation_id)
