"""Atlas Catalog domain: Product aggregate + versioned events (pure, no IO).

Mutation is intentional and narrow: only `Product.publish` mutates, and it
appends the resulting event to `Product.events` for the outbox write.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final, NewType, TypedDict

ProductId = NewType("ProductId", str)
CorrelationId = NewType("CorrelationId", str)
IdempotencyKey = NewType("IdempotencyKey", str)

SCHEMA_VERSION: Final = 1
DRAFT: Final = "DRAFT"
PUBLISHED: Final = "PUBLISHED"
DEFAULT_LOCALE: Final = "pt-BR"


class ProductPayload(TypedDict, total=False):
    product_id: str
    status: str
    title: dict[str, str]
    category_id: str | None


Envelope = dict[str, str | int | ProductPayload | None]


class DomainError(Exception):
    """Base for all catalog domain failures."""


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
        return f"cannot publish from {self.status}"


@dataclass
class ConcurrencyError(DomainError):
    expected_version: int
    actual_version: int

    def __str__(self) -> str:
        return f"version conflict: expected={self.expected_version} actual={self.actual_version}"


@dataclass
class WriteConflict(DomainError):
    """Idempotency race landed nowhere readable; safe to retry the command."""

    idempotency_key: IdempotencyKey

    def __str__(self) -> str:
        return f"idempotency write lost for key: {self.idempotency_key}"


@dataclass
class NotFound(DomainError):
    product_id: ProductId

    def __str__(self) -> str:
        return f"product not found: {self.product_id}"


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_id: str
    event_type: str
    aggregate_id: ProductId
    aggregate_version: int
    occurred_at: str
    schema_version: int
    correlation_id: CorrelationId
    causation_id: str | None
    payload: ProductPayload

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
    aggregate_id: ProductId,
    aggregate_version: int,
    correlation_id: CorrelationId,
    payload: ProductPayload,
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
class Product:
    """Catalog aggregate. Only `publish` mutates, by documented design."""

    id: ProductId
    version: int
    status: str
    title: dict[str, str]
    category_id: str | None
    idempotency_key: IdempotencyKey
    events: list[DomainEvent] = field(default_factory=list, repr=False)

    @classmethod
    def create(
        cls,
        product_id: ProductId,
        title: dict[str, str],
        category_id: str | None,
        idempotency_key: IdempotencyKey,
        correlation_id: CorrelationId,
    ) -> Product:
        """Create a DRAFT product, emitting ProductCreated for the outbox."""
        if not (title or {}).get(DEFAULT_LOCALE, "").strip():
            raise ValidationError(field=f"title[{DEFAULT_LOCALE}]", reason="required")
        product = cls(
            id=product_id,
            version=1,
            status=DRAFT,
            title=dict(title),
            category_id=category_id,
            idempotency_key=idempotency_key,
        )
        product.events.append(
            new_event(
                "ProductCreated",
                product_id,
                1,
                correlation_id,
                {
                    "product_id": product_id,
                    "status": DRAFT,
                    "title": dict(title),
                    "category_id": category_id,
                },
            )
        )
        return product

    def publish(self, correlation_id: CorrelationId) -> DomainEvent:
        """Move DRAFT -> PUBLISHED, emitting ProductPublished for the outbox."""
        if self.status != DRAFT:
            raise InvalidTransition(status=self.status)
        self.status = PUBLISHED
        self.version += 1
        event = new_event(
            "ProductPublished",
            self.id,
            self.version,
            correlation_id,
            {"product_id": self.id, "status": PUBLISHED, "title": dict(self.title)},
            causation_id=self.events[0].event_id if self.events else None,
        )
        self.events.append(event)
        return event
