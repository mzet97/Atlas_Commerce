"""Velocity antifraude (M10): 6th authorized intent in the window declines."""

from __future__ import annotations

from atlas_payment import application, domain
from atlas_payment.domain import CorrelationId, IdempotencyKey, IntentId


async def test_velocity_declines_sixth_intent(repo, monkeypatch) -> None:
    """Given 5 AUTHORIZED in 60s / When 6th intent / Then FRAUD_VELOCITY."""
    from atlas_payment.mongo_repo import MongoPaymentRepository

    assert isinstance(repo, MongoPaymentRepository)
    customer = f"fraud-{IdempotencyKey('k') and __import__('uuid').uuid4().hex[:8]}"
    for i in range(5):
        intent = domain.PaymentIntent.initiate(
            IntentId(f"pi-{customer}-{i}"),
            f"o-{i}",
            customer,
            1000,
            "BRL",
            "4242",
            IdempotencyKey(f"vel-{customer}-{i}"),
            CorrelationId(f"c-{i}"),
        )
        intent.authorize(f"psp-{customer}-{i}", CorrelationId("c"))
        await repo.initiate(intent)
    count = await repo.count_authorized_since(customer, 0)
    assert count == 5

    psp_called: list[str] = []

    async def _no_charge(*args: object, **kwargs: object) -> dict[str, object]:
        psp_called.append("charge")
        return {"approved": True, "provider_ref": "psp-x"}

    monkeypatch.setattr(application, "psp_charge", _no_charge)
    flagged = await application.handle_create(
        repo,
        application.CreateIntent(
            order_id="o-6",
            customer_id=customer,
            amount_minor=1000,
            currency="BRL",
            card_last4="4242",
            idempotency_key=f"vel-{customer}-6",
            correlation_id="c-6",
        ),
    )
    assert flagged.status == domain.DECLINED
    assert flagged.decline_code == "FRAUD_VELOCITY"
    assert psp_called == []  # PSP never touched on a fraud reject
