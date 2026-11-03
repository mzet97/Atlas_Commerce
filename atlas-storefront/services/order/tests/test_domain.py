"""Order domain tests: pure transitions, no IO."""

from __future__ import annotations

import pytest

from atlas_order import domain
from atlas_order.domain import (
    Cart,
    CartId,
    CorrelationId,
    IdempotencyKey,
    Order,
    OrderId,
    Quote,
    QuoteId,
)


def _quote(consumed: str | None = None) -> Quote:
    return Quote(
        id=QuoteId("q-1"),
        cart_id=CartId("c-1"),
        currency="BRL",
        lines=[{"offer_id": "o1", "sku_id": "s1", "quantity": 2,
                "price_minor": 1999}],
        total_minor=3998,
        expires_at="2099-01-01T00:00:00+00:00",
        consumed_by=consumed,
    )


def _order() -> Order:
    return Order.place(
        OrderId("o-1"),
        _quote(),
        "cust-1",
        "4242",
        IdempotencyKey("k-1"),
        CorrelationId("c-1"),
    )


class TestCart:
    def test_add_accumulates(self) -> None:
        """Given cart / When adding twice / Then quantities sum."""
        cart = Cart(id=CartId("c-1"), customer_id="u")
        cart.add_item("o1", 1)
        cart.add_item("o1", 2)
        assert cart.items == {"o1": 3}

    def test_non_positive_rejected(self) -> None:
        """Given cart / When adding 0 / Then ValidationError."""
        with pytest.raises(domain.ValidationError):
            Cart(id=CartId("c-1"), customer_id="u").add_item("o1", 0)


class TestQuote:
    def test_expiry(self) -> None:
        """Given quote / When clock passes TTL / Then expired."""
        quote = _quote()
        assert quote.expired("2099-06-01T00:00:00+00:00") is True
        assert quote.expired("2026-01-01T00:00:00+00:00") is False


class TestOrder:
    def test_place_emits_placed(self) -> None:
        """Given live quote / When placing / Then PENDING + event."""
        order = _order()
        assert order.status == domain.PENDING
        assert [e.event_type for e in order.events] == ["OrderPlaced"]

    def test_place_does_not_gate_consumption(self) -> None:
        """Given consumed quote / When placing in memory / Then PENDING.

        Single-use is a repository concern (atomic claim); the aggregate
        stays gate-free so replays can reach the persisted winner.
        """
        order = Order.place(
            OrderId("o-2"), _quote(consumed="o-9"), "c", "4242",
            IdempotencyKey("k-2"), CorrelationId("c-2"))
        assert order.status == domain.PENDING

    def test_confirm_cancel_reject(self) -> None:
        """Given PENDING / When each terminal leg / Then status + event."""
        order = _order()
        order.confirm(CorrelationId("c2"))
        assert (order.status, order.version) == ("CONFIRMED", 2)
        order2 = _order()
        order2.cancel("declined", CorrelationId("c2"))
        assert (order2.status, order2.failure_reason) == ("CANCELLED", "declined")
        order3 = _order()
        order3.reject("no stock", CorrelationId("c2"))
        assert order3.status == "REJECTED"

    def test_terminal_is_final(self) -> None:
        """Given CONFIRMED / When any transition / Then InvalidTransition."""
        order = _order()
        order.confirm(CorrelationId("c2"))
        with pytest.raises(domain.InvalidTransition):
            order.cancel("x", CorrelationId("c3"))
        with pytest.raises(domain.InvalidTransition):
            order.reject("x", CorrelationId("c3"))

    def test_ship_from_confirmed(self) -> None:
        """Given CONFIRMED / When shipped / Then SHIPPED, replay invalid."""
        order = _order()
        order.confirm(CorrelationId("c2"))
        order.ship(CorrelationId("c3"))
        assert (order.status, order.version) == ("SHIPPED", 3)
        with pytest.raises(domain.InvalidTransition):
            order.ship(CorrelationId("c4"))
