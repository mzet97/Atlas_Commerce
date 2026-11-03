"""Returns/RMA (M6): request -> approve -> refund + restock."""

from __future__ import annotations

import pytest
from conftest import unique
from httpx import AsyncClient

from atlas_order import application, domain
from atlas_order.domain import IdempotencyKey, Order, OrderId, QuoteId


def _confirmed_order(repo: object) -> Order:
    """Build + place a CONFIRMED order with a payment intent attached."""
    order = Order(
        id=OrderId(f"o-{unique('rma')}"),
        version=1,
        status=domain.CONFIRMED,
        quote_id=QuoteId("q-x"),
        customer_id="c",
        lines=[{"offer_id": "o1", "sku_id": f"sku-{unique('s')}",
                "quantity": 2, "price_minor": 1500}],
        total_minor=3000,
        currency="BRL",
        card_last4="4242",
        idempotency_key=IdempotencyKey(unique("idem")),
        payment_intent_id=f"pi-{unique('pi')}",
    )
    return order


@pytest.fixture
def money(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[str]]:
    """Given: refund + restock legs recorded, always succeeding."""
    calls: dict[str, list[str]] = {"refund": [], "restock": []}

    async def _refund(order: Order, rma_id: str, refund_total: int,
                      correlation: str) -> None:
        calls["refund"].append(f"{order.payment_intent_id}:{refund_total}")

    async def _restock(lines: list[dict[str, object]], correlation: str) -> None:
        calls["restock"].append(str([line["sku_id"] for line in lines]))

    monkeypatch.setattr(application, "rma_refund", _refund)
    monkeypatch.setattr(application, "rma_restock", _restock)
    return calls


class TestReturns:
    async def test_request_and_approve(
        self, api: AsyncClient, repo: object, money: dict[str, list[str]]
    ) -> None:
        """Given CONFIRMED order / When RMA approved / Then refund+restock."""
        from atlas_order.mongo_repo import MongoOrderRepository

        assert isinstance(repo, MongoOrderRepository)
        order = _confirmed_order(repo)
        await repo.place(order)
        created = await api.post("/returns", json={
            "order_id": order.id,
            "lines": [{"sku_id": order.lines[0]["sku_id"], "quantity": 1,
                       "price_minor": 1500}],
            "reason": "does not fit",
        })
        assert created.status_code == 201, created.text
        rma = created.json()
        assert rma["status"] == "REQUESTED"
        assert rma["refund_total_minor"] == 1500
        approved = await api.post(f"/returns/{rma['id']}/approve", json={
            "correlation_id": unique("corr")})
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "APPROVED"
        assert money["refund"] == [f"{order.payment_intent_id}:1500"]
        assert len(money["restock"]) == 1

    async def test_replay_is_409(
        self, api: AsyncClient, repo: object, money: dict[str, list[str]]
    ) -> None:
        """Given APPROVED / When approve again / Then 409, legs untouched."""
        from atlas_order.mongo_repo import MongoOrderRepository

        assert isinstance(repo, MongoOrderRepository)
        order = _confirmed_order(repo)
        await repo.place(order)
        created = await api.post("/returns", json={
            "order_id": order.id,
            "lines": [{"sku_id": "s1", "quantity": 1, "price_minor": 100}],
        })
        rma_id = created.json()["id"]
        first = await api.post(f"/returns/{rma_id}/approve", json={
            "correlation_id": unique("corr")})
        assert first.status_code == 200
        second = await api.post(f"/returns/{rma_id}/approve", json={
            "correlation_id": unique("corr")})
        assert second.status_code == 409
        assert len(money["refund"]) == 1

    async def test_pending_order_refused(
        self, api: AsyncClient, repo: object, money: dict[str, list[str]]
    ) -> None:
        """Given PENDING order / When RMA approve / Then 422, nothing moves."""
        from atlas_order.mongo_repo import MongoOrderRepository

        assert isinstance(repo, MongoOrderRepository)
        order = Order(
            id=OrderId(f"o-{unique('rma')}"),
            version=1,
            status=domain.PENDING,
            quote_id=QuoteId("q-x"),
            customer_id="c",
            lines=[{"offer_id": "o1", "sku_id": "s1", "quantity": 1,
                    "price_minor": 100}],
            total_minor=100,
            currency="BRL",
            card_last4="4242",
            idempotency_key=IdempotencyKey(unique("idem")),
        )
        await repo.place(order)
        created = await api.post("/returns", json={
            "order_id": order.id,
            "lines": [{"sku_id": "s1", "quantity": 1, "price_minor": 100}],
        })
        rma_id = created.json()["id"]
        approved = await api.post(f"/returns/{rma_id}/approve", json={
            "correlation_id": unique("corr")})
        assert approved.status_code == 422
        assert money["refund"] == []
