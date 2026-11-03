"""Payment domain tests: pure transitions, no IO."""

from __future__ import annotations

import pytest

from atlas_payment import domain
from atlas_payment.domain import (
    CorrelationId,
    IdempotencyKey,
    IntentId,
    PaymentIntent,
)


def _intent(amount: int = 1999) -> PaymentIntent:
    return PaymentIntent.initiate(
        IntentId("pi-test"),
        "order-1",
        "cust-1",
        amount,
        "BRL",
        "4242",
        IdempotencyKey("key-1"),
        CorrelationId("corr-1"),
    )


class TestInitiate:
    def test_happy_path_emits_initiated(self) -> None:
        """Given valid data / When initiating / Then INITIATED + event."""
        intent = _intent()
        assert intent.status == domain.INITIATED
        assert intent.version == 1
        assert [e.event_type for e in intent.events] == ["PaymentInitiated"]

    def test_non_positive_amount_rejected(self) -> None:
        """Given amount 0 / When initiating / Then ValidationError."""
        with pytest.raises(domain.ValidationError):
            _intent(amount=0)


class TestTransitions:
    def test_authorize_from_initiated(self) -> None:
        """Given INITIATED / When PSP approves / Then AUTHORIZED v2."""
        intent = _intent()
        intent.authorize("psp-1", CorrelationId("c2"))
        assert intent.status == domain.AUTHORIZED
        assert intent.provider_ref == "psp-1"
        assert intent.version == 2

    def test_decline_from_initiated(self) -> None:
        """Given INITIATED / When PSP declines / Then DECLINED with code."""
        intent = _intent()
        intent.decline("psp-1", "DECLINED", CorrelationId("c2"))
        assert (intent.status, intent.decline_code) == ("DECLINED", "DECLINED")

    def test_unknown_then_authorize(self) -> None:
        """Given timeout / When reconciled approved / Then AUTHORIZED."""
        intent = _intent()
        intent.mark_unknown(None, CorrelationId("c2"))
        assert intent.status == domain.UNKNOWN
        intent.authorize("psp-9", CorrelationId("c3"))
        assert (intent.status, intent.provider_ref) == ("AUTHORIZED", "psp-9")

    def test_terminal_is_final(self) -> None:
        """Given AUTHORIZED / When any transition / Then InvalidTransition."""
        intent = _intent()
        intent.authorize("psp-1", CorrelationId("c2"))
        with pytest.raises(domain.InvalidTransition):
            intent.authorize("psp-2", CorrelationId("c3"))
        with pytest.raises(domain.InvalidTransition):
            intent.decline("psp-2", "X", CorrelationId("c3"))
        with pytest.raises(domain.InvalidTransition):
            intent.mark_unknown(None, CorrelationId("c3"))
