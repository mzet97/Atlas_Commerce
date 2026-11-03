"""Inventory domain unit tests: balances and transitions, no IO."""

from __future__ import annotations

import pytest

from atlas_inventory.domain import (
    CheckoutId,
    CorrelationId,
    IdempotencyKey,
    InsufficientStock,
    InvalidTransition,
    Reservation,
    ReservationId,
    StockPosition,
    ValidationError,
)


def _position(on_hand: int = 10, reserved: int = 0, safety: int = 0) -> StockPosition:
    return StockPosition(
        warehouse_id="W1",
        sku_id="SKU-1",
        on_hand=on_hand,
        reserved=reserved,
        safety_stock=safety,
        version=1,
    )


class TestAvailable:
    def test_math_subtracts_reserved_and_safety(self) -> None:
        """Given balances / When available / Then on_hand-reserved-safety."""
        assert _position(10, 3, 2).available() == 5

    def test_reserve_beyond_available_is_rejected(self) -> None:
        """Given available 2 / When reserving 3 / Then InsufficientStock."""
        position = _position(10, 8, 0)
        with pytest.raises(InsufficientStock):
            position.reserve(3, ReservationId("r1"), CheckoutId("c1"), CorrelationId("corr"))
        assert (position.reserved, position.on_hand) == (8, 10)


class TestReceiveAdjust:
    def test_receive_increases_on_hand_and_emits(self) -> None:
        """Given empty / When receiving 5 / Then on_hand 5 + event."""
        position = _position(0)
        event = position.receive(5, CorrelationId("corr"))
        assert (position.on_hand, event.event_type) == (5, "StockAdjusted")

    def test_adjust_requires_reason(self) -> None:
        """Given blank reason / When adjusting / Then ValidationError."""
        with pytest.raises(ValidationError):
            _position(5).adjust(-1, " ", CorrelationId("corr"))

    def test_adjust_never_below_zero(self) -> None:
        """Given on_hand 2 / When adjusting -3 / Then ValidationError."""
        with pytest.raises(ValidationError):
            _position(2).adjust(-3, "count", CorrelationId("corr"))


class TestReservation:
    def test_confirm_and_release_are_exclusive(self) -> None:
        """Given ACTIVE / When confirmed then released / Then InvalidTransition."""
        reservation = Reservation.create(
            ReservationId("r1"), CheckoutId("c1"), "W1", "SKU-1", 1, IdempotencyKey("idem-1")
        )
        reservation.confirm()
        assert reservation.status == "CONFIRMED"
        with pytest.raises(InvalidTransition):
            reservation.release()
