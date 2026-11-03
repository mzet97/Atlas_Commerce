"""Application layer: pricing commands + handlers over repository ports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .domain import (
    CorrelationId,
    IdempotencyKey,
    Offer,
    OfferId,
    SkuId,
)


@dataclass(frozen=True, slots=True)
class PublishOffer:
    offer_id: OfferId
    sku_id: SkuId
    seller_id: str
    market_id: str
    channel: str
    currency: str
    price_minor: int
    idempotency_key: IdempotencyKey
    correlation_id: CorrelationId


@dataclass(frozen=True, slots=True)
class UpdatePrice:
    offer_id: OfferId
    expected_version: int
    price_minor: int
    correlation_id: CorrelationId


@dataclass(frozen=True, slots=True)
class DeactivateOffer:
    offer_id: OfferId
    expected_version: int
    correlation_id: CorrelationId


class OfferRepository(Protocol):
    async def publish(self, offer: Offer) -> Offer:
        """Insert ACTIVE offer + outbox in ONE txn; overlap -> OfferConflict."""
        ...

    async def get(self, offer_id: OfferId) -> Offer: ...

    async def update_price(
        self,
        offer_id: OfferId,
        expected_version: int,
        price_minor: int,
        correlation_id: CorrelationId,
    ) -> Offer: ...

    async def deactivate(
        self, offer_id: OfferId, expected_version: int, correlation_id: CorrelationId
    ) -> Offer: ...


async def handle_publish(cmd: PublishOffer, repo: OfferRepository) -> Offer:
    """Publish a new ACTIVE offer; idempotent on idempotency_key."""
    return await repo.publish(
        Offer.publish(
            cmd.offer_id,
            cmd.sku_id,
            cmd.seller_id,
            cmd.market_id,
            cmd.channel,
            cmd.currency,
            cmd.price_minor,
            cmd.idempotency_key,
            cmd.correlation_id,
        )
    )


async def handle_update_price(cmd: UpdatePrice, repo: OfferRepository) -> Offer:
    """Change price, or raise NotFound | ConcurrencyError | InvalidTransition."""
    return await repo.update_price(
        cmd.offer_id, cmd.expected_version, cmd.price_minor, cmd.correlation_id
    )


async def handle_deactivate(cmd: DeactivateOffer, repo: OfferRepository) -> Offer:
    """Deactivate, or raise NotFound | ConcurrencyError | InvalidTransition."""
    return await repo.deactivate(cmd.offer_id, cmd.expected_version, cmd.correlation_id)
