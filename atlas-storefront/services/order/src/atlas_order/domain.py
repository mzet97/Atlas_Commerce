"""Atlas Order domain: Cart + Quote + Order aggregates (pure, no IO).

Order saga states: PENDING -> CONFIRMED | CANCELLED | REJECTED.
PENDING + payment UNKNOWN resolves ONLY via reconcile (payment truth).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Final, NewType, TypedDict

CartId = NewType("CartId", str)
QuoteId = NewType("QuoteId", str)
OrderId = NewType("OrderId", str)
CorrelationId = NewType("CorrelationId", str)
IdempotencyKey = NewType("IdempotencyKey", str)

SCHEMA_VERSION: Final = 1
QUOTE_TTL: Final = timedelta(minutes=15)
PENDING: Final = "PENDING"
CONFIRMED: Final = "CONFIRMED"
SHIPPED: Final = "SHIPPED"
CANCELLED: Final = "CANCELLED"
REJECTED: Final = "REJECTED"
TERMINAL: Final = frozenset({SHIPPED, CANCELLED, REJECTED})


class QuoteLine(TypedDict):
    offer_id: str
    sku_id: str
    quantity: int
    price_minor: int


class OrderPayload(TypedDict, total=False):
    cart_id: str
    quote_id: str
    order_id: str
    customer_id: str
    lines: list[QuoteLine]
    subtotal_minor: int
    discount_minor: int
    tax_minor: int
    total_minor: int
    currency: str
    market_id: str
    coupon_code: str | None
    tax_rate_bps: int
    status: str
    payment_intent_id: str | None
    failure_reason: str | None
    tracking_code: str


Envelope = dict[str, str | int | OrderPayload | None]


class DomainError(Exception):
    """Base for all order domain failures."""


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
class NotFound(DomainError):
    resource: str

    def __str__(self) -> str:
        return f"not found: {self.resource}"


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_version: int
    occurred_at: str
    schema_version: int
    correlation_id: CorrelationId
    causation_id: str | None
    payload: OrderPayload

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
    aggregate_id: str,
    aggregate_version: int,
    correlation_id: CorrelationId,
    payload: OrderPayload,
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
class Cart:
    """Cart: customer-owned item bag. Quotes snapshot it; edits open a new quote."""

    id: CartId
    customer_id: str
    items: dict[str, int] = field(default_factory=dict)  # offer_id -> quantity
    coupon_code: str | None = None

    def add_item(self, offer_id: str, quantity: int) -> None:
        if quantity <= 0:
            raise ValidationError(field="quantity", reason="must be positive")
        self.items[offer_id] = self.items.get(offer_id, 0) + quantity


@dataclass(slots=True)
class Quote:
    """Quote: immutable priced snapshot with TTL. Checkout consumes it once.

    Breakdown: subtotal - discount + tax = total. Tax is floor-rounded by
    market rate (bps); coupon validated against the quote's single market.
    """

    id: QuoteId
    cart_id: CartId
    currency: str
    lines: list[QuoteLine]
    total_minor: int
    expires_at: str
    subtotal_minor: int = 0
    discount_minor: int = 0
    tax_minor: int = 0
    tax_rate_bps: int = 0
    market_id: str = ""
    coupon_code: str | None = None
    consumed_by: str | None = None

    def expired(self, now: str) -> bool:
        return now >= self.expires_at


@dataclass(slots=True)
class Order:
    """Checkout saga aggregate. Transitions append events for the outbox write."""

    id: OrderId
    version: int
    status: str
    quote_id: QuoteId
    customer_id: str
    lines: list[QuoteLine]
    total_minor: int
    currency: str
    card_last4: str
    idempotency_key: IdempotencyKey
    reservation_ids: list[str] = field(default_factory=list)
    payment_intent_id: str | None = None
    failure_reason: str | None = None
    subtotal_minor: int = 0
    discount_minor: int = 0
    tax_minor: int = 0
    tax_rate_bps: int = 0
    market_id: str = ""
    coupon_code: str | None = None
    created_at: str | None = None
    events: list[DomainEvent] = field(default_factory=list, repr=False)

    @classmethod
    def place(
        cls,
        order_id: OrderId,
        quote: Quote,
        customer_id: str,
        card_last4: str,
        idempotency_key: IdempotencyKey,
        correlation_id: CorrelationId,
    ) -> Order:
        """Create a PENDING order from a quote, emitting OrderPlaced.

        Single-use is enforced atomically by the repository (quote claim in
        the same transaction), so replays reach the winner instead of 422.
        """
        order = cls(
            id=order_id,
            version=1,
            status=PENDING,
            quote_id=quote.id,
            customer_id=customer_id,
            lines=list(quote.lines),
            total_minor=quote.total_minor,
            currency=quote.currency,
            card_last4=card_last4,
            idempotency_key=idempotency_key,
            subtotal_minor=quote.subtotal_minor,
            discount_minor=quote.discount_minor,
            tax_minor=quote.tax_minor,
            tax_rate_bps=quote.tax_rate_bps,
            market_id=quote.market_id,
            coupon_code=quote.coupon_code,
            created_at=datetime.now(UTC).isoformat(),
        )
        order.events.append(
            new_event("OrderPlaced", order_id, 1, correlation_id, order._payload())
        )
        return order

    def _payload(self) -> OrderPayload:
        return {
            "order_id": self.id,
            "quote_id": self.quote_id,
            "customer_id": self.customer_id,
            "lines": list(self.lines),
            "subtotal_minor": self.subtotal_minor,
            "discount_minor": self.discount_minor,
            "tax_minor": self.tax_minor,
            "total_minor": self.total_minor,
            "currency": self.currency,
            "market_id": self.market_id,
            "coupon_code": self.coupon_code,
            "tax_rate_bps": self.tax_rate_bps,
            "status": self.status,
            "payment_intent_id": self.payment_intent_id,
            "failure_reason": self.failure_reason,
        }

    def _transition(
        self, event_type: str, status: str, correlation_id: CorrelationId
    ) -> DomainEvent:
        if self.status != PENDING:
            raise InvalidTransition(status=self.status, event=event_type)
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

    def confirm(self, correlation_id: CorrelationId) -> DomainEvent:
        """PENDING -> CONFIRMED: stock confirmed, money authorized."""
        return self._transition("OrderConfirmed", CONFIRMED, correlation_id)

    def ship(self, correlation_id: CorrelationId) -> DomainEvent:
        """CONFIRMED -> SHIPPED: fulfillment hands to logistics (M6) with a
        deterministic fake-carrier label (carrier.py is the real seam)."""
        if self.status != CONFIRMED:
            raise InvalidTransition(status=self.status, event="OrderShipped")
        self.status = SHIPPED
        self.version += 1
        from .carrier import issue_label

        payload = self._payload()
        payload["tracking_code"] = issue_label(self.id)
        event = new_event(
            "OrderShipped",
            self.id,
            self.version,
            correlation_id,
            payload,
            causation_id=self.events[0].event_id if self.events else None,
        )
        self.events.append(event)
        return event

    def cancel(self, reason: str, correlation_id: CorrelationId) -> DomainEvent:
        """PENDING -> CANCELLED: payment declined, reservations released."""
        self.failure_reason = reason
        return self._transition("OrderCancelled", CANCELLED, correlation_id)

    def cancel_confirmed(
        self, reason: str, correlation_id: CorrelationId
    ) -> DomainEvent:
        """CONFIRMED -> CANCELLED (ops/RMA): the caller refunds BEFORE calling
        this — a cancelled confirmed order without its refund is a money bug."""
        if self.status != CONFIRMED:
            raise InvalidTransition(status=self.status, event="cancel confirmed")
        self.failure_reason = reason
        self.status = CANCELLED
        self.version += 1
        event = new_event(
            "OrderCancelled",
            self.id,
            self.version,
            correlation_id,
            self._payload(),
            causation_id=self.events[0].event_id if self.events else None,
        )
        self.events.append(event)
        return event

    def reject(self, reason: str, correlation_id: CorrelationId) -> DomainEvent:
        """PENDING -> REJECTED: no stock, nothing charged."""
        self.failure_reason = reason
        return self._transition("OrderRejected", REJECTED, correlation_id)
