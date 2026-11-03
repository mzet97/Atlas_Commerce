"""Refunds (M6): PSP truth first, then the auditable local transition."""

from __future__ import annotations

import pytest
from conftest import unique

from atlas_payment import application, domain
from atlas_payment.domain import CorrelationId, IdempotencyKey, IntentId


async def _authorized_intent(repo: object, amount: int = 5000) -> domain.PaymentIntent:
    """Given: an AUTHORIZED intent with a provider ref."""
    from atlas_payment.mongo_repo import MongoPaymentRepository

    assert isinstance(repo, MongoPaymentRepository)
    intent = domain.PaymentIntent.initiate(
        IntentId(f"pi-{unique('ref')}"),
        f"o-{unique('ord')}",
        unique("cust"),
        amount,
        "BRL",
        "4242",
        IdempotencyKey(unique("idem")),
        CorrelationId(unique("corr")),
    )
    intent.authorize(f"psp-{unique('ref2')}", CorrelationId("c"))
    return await repo.initiate(intent)


@pytest.fixture
def psp(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Given: the PSP refund leg recorded and always successful."""
    calls: list[str] = []

    async def _refund(provider_ref: str, amount_minor: int,
                      idempotency_key: str) -> dict[str, object]:
        calls.append(f"{provider_ref}:{amount_minor}")
        return {"refund_id": f"psp-ref-{len(calls)}", "provider_ref": provider_ref,
                "amount_minor": amount_minor, "refunded_minor": amount_minor}

    monkeypatch.setattr(application, "psp_refund", _refund)
    return calls


class TestRefunds:
    async def test_full_refund_default_amount(
        self, repo: object, psp: list[str]
    ) -> None:
        """Given AUTHORIZED 5000 / When refund without amount / Then 5000 back."""
        intent = await _authorized_intent(repo)
        saved = await application.handle_refund(
            repo,
            application.RefundCommand(
                intent_id=intent.id, amount_minor=None, reason="ops cancel",
                idempotency_key=unique("idem"), correlation_id=unique("corr"),
            ),
        )
        assert saved.refunded_minor == 5000
        assert saved.status == domain.AUTHORIZED
        assert saved.refundable_minor() == 0
        assert psp and f"{intent.provider_ref}:5000" in psp[0]

    async def test_partial_refund_keeps_rest(
        self, repo: object, psp: list[str]
    ) -> None:
        """Given 5000 / When refund 2000 / Then refunded 2000, 3000 left."""
        intent = await _authorized_intent(repo)
        saved = await application.handle_refund(
            repo,
            application.RefundCommand(
                intent_id=intent.id, amount_minor=2000, reason="partial",
                idempotency_key=unique("idem"), correlation_id=unique("corr"),
            ),
        )
        assert saved.refunded_minor == 2000
        assert saved.refundable_minor() == 3000

    async def test_over_refund_rejected_before_psp(
        self, repo: object, psp: list[str]
    ) -> None:
        """Given 5000 / When refund 6000 / Then 422, PSP never called."""
        intent = await _authorized_intent(repo)
        with pytest.raises(domain.ValidationError):
            await application.handle_refund(
                repo,
                application.RefundCommand(
                    intent_id=intent.id, amount_minor=6000, reason="x",
                    idempotency_key=unique("idem"), correlation_id=unique("corr"),
                ),
            )
        assert psp == []

    async def test_declined_intent_refuses(self, repo: object, psp: list[str]) -> None:
        """Given DECLINED / When refund / Then 409 invalid transition."""
        from atlas_payment.mongo_repo import MongoPaymentRepository

        assert isinstance(repo, MongoPaymentRepository)
        intent = domain.PaymentIntent.initiate(
            IntentId(f"pi-{unique('ref')}"),
            f"o-{unique('ord')}",
            unique("cust"),
            5000,
            "BRL",
            "4242",
            IdempotencyKey(unique("idem")),
            CorrelationId(unique("corr")),
        )
        intent.decline(None, "DECLINED", CorrelationId("c"))
        await repo.initiate(intent)
        with pytest.raises(domain.InvalidTransition):
            await application.handle_refund(
                repo,
                application.RefundCommand(
                    intent_id=intent.id, amount_minor=None, reason="x",
                    idempotency_key=unique("idem"), correlation_id=unique("corr"),
                ),
            )

    async def test_replay_same_key_converges(self, repo: object, psp: list[str]) -> None:
        """Given refunded / When same idem key / Then stored outcome, no double."""
        intent = await _authorized_intent(repo)
        key = unique("idem")
        first = await application.handle_refund(
            repo,
            application.RefundCommand(
                intent_id=intent.id, amount_minor=None, reason="x",
                idempotency_key=key, correlation_id=unique("corr"),
            ),
        )
        second = await application.handle_refund(
            repo,
            application.RefundCommand(
                intent_id=intent.id, amount_minor=None, reason="x",
                idempotency_key=key, correlation_id=unique("corr"),
            ),
        )
        assert second.refunded_minor == first.refunded_minor == 5000
        assert second.version == first.version  # no second transition
        assert len(psp) == 1  # replay short-circuits before the PSP leg
