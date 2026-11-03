"""Ops cancel + PENDING expiration (M4): compensations and sweeper."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from conftest import unique
from httpx import AsyncClient

from atlas_order import application, domain
from atlas_order.domain import IdempotencyKey, Order, OrderId, QuoteId
from atlas_order.sweeper import expire_pending


def _order(status: str, created_seconds_ago: int = 0) -> Order:
    created = (
        datetime.now(UTC) - timedelta(seconds=created_seconds_ago)
    ).isoformat()
    return Order(
        id=OrderId(f"o-{unique('m4')}"),
        version=1,
        status=status,
        quote_id=QuoteId("q-x"),
        customer_id="c",
        lines=[],
        total_minor=1000,
        currency="BRL",
        card_last4="4242",
        idempotency_key=IdempotencyKey(unique("idem")),
        reservation_ids=["res-1"],
        created_at=created,
    )


@pytest.fixture
def releases(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Given: reservation transitions recorded, never hitting inventory."""
    calls: list[str] = []

    async def _leg(http: object, reservation_id: str, action: str,
                   correlation: str) -> None:
        calls.append(f"{action}:{reservation_id}")

    monkeypatch.setattr(application, "_transition_reservation", _leg)
    return calls


class TestOpsCancel:
    async def test_pending_cancel_releases(
        self, api: AsyncClient, repo: object, releases: list[str]
    ) -> None:
        """Given PENDING / When ops cancel / Then CANCELLED + released."""
        from atlas_order.mongo_repo import MongoOrderRepository

        assert isinstance(repo, MongoOrderRepository)
        order = await repo.place(_order(domain.PENDING))
        response = await api.post(f"/orders/{order.id}/cancel", json={
            "correlation_id": unique("corr")})
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "CANCELLED"
        assert response.json()["failure_reason"] == "cancelled by ops"
        assert releases == ["release:res-1"]

    async def test_terminal_replay_is_idempotent(
        self, api: AsyncClient, repo: object, releases: list[str]
    ) -> None:
        """Given CANCELLED / When cancel again / Then 200 untouched."""
        from atlas_order.mongo_repo import MongoOrderRepository

        assert isinstance(repo, MongoOrderRepository)
        order = _order(domain.PENDING)
        order.cancel("x", domain.CorrelationId("c"))
        await repo.place(order)
        response = await api.post(f"/orders/{order.id}/cancel", json={
            "correlation_id": unique("corr")})
        assert response.status_code == 200
        assert response.json()["version"] == 2
        assert releases == []  # nothing left to release

    async def test_confirmed_refused_until_refunds(
        self, api: AsyncClient, repo: object, releases: list[str]
    ) -> None:
        """Given CONFIRMED / When ops cancel / Then 409 (money event, M6)."""
        from atlas_order.mongo_repo import MongoOrderRepository

        assert isinstance(repo, MongoOrderRepository)
        order = await repo.place(_order(domain.PENDING))
        stored = await repo.get(order.id)
        stored.confirm(domain.CorrelationId("c"))
        await repo.save_with_events(stored)
        response = await api.post(f"/orders/{order.id}/cancel", json={
            "correlation_id": unique("corr")})
        assert response.status_code == 409


class TestPendingExpiration:
    async def test_stale_pending_cancelled_and_released(
        self, repo: object, releases: list[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Given PENDING past TTL / When sweep / Then CANCELLED + released.

        State-based assertions: prior suite runs may leave other stale
        PENDINGs the sweep also (correctly) cancels.
        """
        from atlas_order import sweeper
        from atlas_order.mongo_repo import MongoOrderRepository

        assert isinstance(repo, MongoOrderRepository)
        monkeypatch.setenv("ORDER_PENDING_TTL_SECONDS", "1")

        async def _no_drive(repo_arg: object, http_inv: object,
                            http_pay: object, order: Order,
                            correlation: str) -> Order:
            return order  # settle attempt finds nothing to drive

        monkeypatch.setattr(sweeper, "_drive", _no_drive)
        stale = await repo.place(_order(domain.PENDING, created_seconds_ago=30))
        fresh = await repo.place(_order(domain.PENDING, created_seconds_ago=0))
        await expire_pending(repo)
        stored = await repo.get(stale.id)
        assert stored.status == domain.CANCELLED
        assert stored.failure_reason == "pending expired"
        assert "release:res-1" in releases
        fresh_stored = await repo.get(fresh.id)
        assert fresh_stored.status == domain.PENDING

    async def test_authorized_pending_settles_before_cancel(
        self, repo: object, releases: list[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Given stale PENDING with no intent / When drive confirms / Then kept."""
        from atlas_order import sweeper
        from atlas_order.mongo_repo import MongoOrderRepository

        assert isinstance(repo, MongoOrderRepository)
        monkeypatch.setenv("ORDER_PENDING_TTL_SECONDS", "1")

        async def _confirm_drive(repo_arg: object, http_inv: object,
                                 http_pay: object, order: Order,
                                 correlation: str) -> Order:
            order.payment_intent_id = "pi-1"
            order.confirm(domain.CorrelationId(correlation))
            return await repo_arg.save_with_events(order)  # type: ignore[attr-defined]

        monkeypatch.setattr(sweeper, "_drive", _confirm_drive)
        stale = await repo.place(_order(domain.PENDING, created_seconds_ago=30))
        await expire_pending(repo)
        stored = await repo.get(stale.id)
        assert stored.status == domain.CONFIRMED
