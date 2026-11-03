"""Offer aggregate + pricing events (pure, no IO)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final, NewType, TypedDict

OfferId = NewType("OfferId", str)
SkuId = NewType("SkuId", str)
CorrelationId = NewType("CorrelationId", str)
IdempotencyKey = NewType("IdempotencyKey", str)

SCHEMA_VERSION: Final = 1
ACTIVE: Final = "ACTIVE"
INACTIVE: Final = "INACTIVE"


class OfferPayload(TypedDict, total=False):
    offer_id: str
    sku_id: str
    seller_id: str
    market_id: str
    channel: str
    currency: str
    price_minor: int
    status: str


Envelope = dict[str, str | int | OfferPayload | None]


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: str
    event_type: str
    aggregate_id: OfferId
    aggregate_version: int
    occurred_at: str
    schema_version: int
    correlation_id: CorrelationId
    causation_id: str | None
    payload: OfferPayload

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
    aggregate_id: OfferId,
    aggregate_version: int,
    correlation_id: CorrelationId,
    payload: OfferPayload,
    causation_id: str | None = None,
) -> DomainEvent:
    """Create a versioned pricing event for the outbox envelope (INV-010)."""
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


class DomainError(Exception):
    """Base for all pricing domain failures."""


@dataclass
class ValidationError(DomainError):
    field: str
    reason: str

    def __str__(self) -> str:
        return f"invalid {self.field}: {self.reason}"


@dataclass
class InvalidTransition(DomainError):
    status: str

    def __str__(self) -> str:
        return f"cannot transition from {self.status}"


@dataclass
class ConcurrencyError(DomainError):
    expected_version: int
    actual_version: int

    def __str__(self) -> str:
        return f"version conflict: expected={self.expected_version} actual={self.actual_version}"


@dataclass
class NotFound(DomainError):
    offer_id: OfferId

    def __str__(self) -> str:
        return f"offer not found: {self.offer_id}"


@dataclass
class OfferConflict(DomainError):
    """A second ACTIVE offer overlaps the same (sku, seller, market, channel)."""

    sku_id: SkuId

    def __str__(self) -> str:
        return f"overlapping active offer for sku: {self.sku_id}"


@dataclass
class WriteConflict(DomainError):
    """Idempotency race landed nowhere readable; safe to retry the command."""

    idempotency_key: IdempotencyKey

    def __str__(self) -> str:
        return f"idempotency write lost for key: {self.idempotency_key}"


@dataclass(slots=True)
class Offer:
    """Pricing aggregate. Only publish/update_price/deactivate mutate."""

    id: OfferId
    version: int
    status: str
    sku_id: SkuId
    seller_id: str
    market_id: str
    channel: str
    currency: str
    price_minor: int
    idempotency_key: IdempotencyKey
    events: list[DomainEvent] = field(default_factory=list, repr=False)

    @classmethod
    def publish(
        cls,
        offer_id: OfferId,
        sku_id: SkuId,
        seller_id: str,
        market_id: str,
        channel: str,
        currency: str,
        price_minor: int,
        idempotency_key: IdempotencyKey,
        correlation_id: CorrelationId,
    ) -> Offer:
        """Publish a new ACTIVE offer, emitting OfferPublished."""
        if price_minor <= 0:
            raise ValidationError(field="price_minor", reason="must be positive")
        if not currency.strip() or not market_id.strip():
            raise ValidationError(field="currency/market_id", reason="required")
        offer = cls(
            id=offer_id,
            version=1,
            status=ACTIVE,
            sku_id=sku_id,
            seller_id=seller_id,
            market_id=market_id,
            channel=channel,
            currency=currency,
            price_minor=price_minor,
            idempotency_key=idempotency_key,
        )
        offer.events.append(
            new_event(
                "OfferPublished",
                offer_id,
                1,
                correlation_id,
                {
                    "offer_id": offer_id,
                    "sku_id": sku_id,
                    "seller_id": seller_id,
                    "market_id": market_id,
                    "channel": channel,
                    "currency": currency,
                    "price_minor": price_minor,
                    "status": ACTIVE,
                },
            )
        )
        return offer

    def update_price(self, price_minor: int, correlation_id: CorrelationId) -> DomainEvent:
        """ACTIVE-only price change, emitting PriceChanged."""
        if self.status != ACTIVE:
            raise InvalidTransition(status=self.status)
        if price_minor <= 0:
            raise ValidationError(field="price_minor", reason="must be positive")
        self.price_minor = price_minor
        self.version += 1
        event = new_event(
            "PriceChanged",
            self.id,
            self.version,
            correlation_id,
            {
                "offer_id": self.id,
                "price_minor": price_minor,
                "status": self.status,
                "sku_id": self.sku_id,
                "market_id": self.market_id,
                "currency": self.currency,
            },
            causation_id=self.events[0].event_id if self.events else None,
        )
        self.events.append(event)
        return event

    def deactivate(self, correlation_id: CorrelationId) -> DomainEvent:
        """ACTIVE -> INACTIVE, emitting OfferDeactivated."""
        if self.status != ACTIVE:
            raise InvalidTransition(status=self.status)
        self.status = INACTIVE
        self.version += 1
        event = new_event(
            "OfferDeactivated",
            self.id,
            self.version,
            correlation_id,
            {"offer_id": self.id, "status": INACTIVE},
        )
        self.events.append(event)
        return event
