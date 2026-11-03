"""Offer domain unit tests: pure pricing rules, no IO, milliseconds each."""

from __future__ import annotations

import pytest

from atlas_offers.domain import (
    CorrelationId,
    IdempotencyKey,
    InvalidTransition,
    Offer,
    OfferConflict,
    OfferId,
    SkuId,
    ValidationError,
)


def _publish(price: int = 1999) -> Offer:
    return Offer.publish(
        offer_id=OfferId("offer-1"),
        sku_id=SkuId("sku-1"),
        seller_id="atlas",
        market_id="BR",
        channel="web",
        currency="BRL",
        price_minor=price,
        idempotency_key=IdempotencyKey("idem-1"),
        correlation_id=CorrelationId("corr-1"),
    )


class TestPublish:
    def test_happy_path_starts_active_v1(self) -> None:
        """Given valid pricing / When published / Then ACTIVE v1 + event."""
        offer = _publish()
        assert (offer.status, offer.version) == ("ACTIVE", 1)
        assert [e.event_type for e in offer.events] == ["OfferPublished"]

    def test_zero_price_is_rejected(self) -> None:
        """Given price 0 / When published / Then ValidationError."""
        with pytest.raises(ValidationError):
            _publish(price=0)


class TestUpdatePrice:
    def test_happy_path_bumps_version_with_event(self) -> None:
        """Given ACTIVE v1 / When price changes / Then v2 + PriceChanged."""
        offer = _publish()
        event = offer.update_price(2499, CorrelationId("corr-2"))
        assert (offer.price_minor, offer.version) == (2499, 2)
        assert event.event_type == "PriceChanged"

    def test_inactive_offer_rejects_price_change(self) -> None:
        """Given INACTIVE / When price changes / Then InvalidTransition."""
        offer = _publish()
        offer.deactivate(CorrelationId("corr-2"))
        with pytest.raises(InvalidTransition):
            offer.update_price(2499, CorrelationId("corr-3"))

    def test_conflict_error_carries_sku(self) -> None:
        """Given overlap data / When raised / Then typed sku preserved."""
        err = OfferConflict(SkuId("sku-9"))
        assert err.sku_id == "sku-9"
        assert "sku-9" in str(err)
