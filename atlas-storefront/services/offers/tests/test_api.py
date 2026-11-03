"""Offers API integration tests: real HTTP surface + real Mongo."""

from __future__ import annotations

import pytest_asyncio
from conftest import unique
from httpx import ASGITransport, AsyncClient

from atlas_offers.api import app as offers_app


@pytest_asyncio.fixture
async def api():
    """Given: lifespan up (client per test loop), indexes ensured on boot."""
    async with (
        offers_app.router.lifespan_context(offers_app),
        AsyncClient(transport=ASGITransport(app=offers_app), base_url="http://test") as http,
    ):
        yield http


async def _publish(http: AsyncClient, key: str | None = None) -> dict[str, str | int]:
    body = {
        "sku_id": unique("sku"),
        "seller_id": "atlas",
        "market_id": "BR",
        "channel": "web",
        "currency": "BRL",
        "price_minor": 1999,
        "idempotency_key": key or unique("idem"),
        "correlation_id": unique("corr"),
    }
    response = await http.post("/offers", json=body)
    assert response.status_code == 201, response.text
    parsed = response.json()
    assert isinstance(parsed, dict)
    return parsed


class TestPublishOffer:
    async def test_happy_path_returns_active(self, api: AsyncClient) -> None:
        """Given valid pricing / When POST /offers / Then 201 ACTIVE v1."""
        created = await _publish(api)
        assert (created["status"], created["version"]) == ("ACTIVE", 1)

    async def test_same_key_returns_same_offer(self, api: AsyncClient) -> None:
        """Given published offer / When POST same key / Then same id."""
        key = unique("idem")
        first = await _publish(api, key)
        second = await _publish(api, key)
        assert first["id"] == second["id"]

    async def test_overlapping_active_offer_conflicts(self, api: AsyncClient) -> None:
        """Given ACTIVE offer / When overlapping publish / Then 409."""
        sku = unique("sku")
        body = {
            "sku_id": sku,
            "seller_id": "atlas",
            "market_id": "BR",
            "channel": "web",
            "currency": "BRL",
            "price_minor": 1999,
            "idempotency_key": unique("idem"),
            "correlation_id": unique("corr"),
        }
        first = await api.post("/offers", json=body)
        assert first.status_code == 201
        body["idempotency_key"] = unique("idem")
        body["correlation_id"] = unique("corr")
        second = await api.post("/offers", json=body)
        assert second.status_code == 409


class TestUpdatePrice:
    async def test_happy_path_reprices(self, api: AsyncClient) -> None:
        """Given ACTIVE v1 / When POST price v1 / Then 200 v2."""
        created = await _publish(api)
        response = await api.post(
            f"/offers/{created['id']}/price",
            json={"expected_version": 1, "price_minor": 2499, "correlation_id": unique("corr")},
        )
        assert response.status_code == 200, response.text
        assert (response.json()["price_minor"], response.json()["version"]) == (2499, 2)

    async def test_stale_version_conflicts(self, api: AsyncClient) -> None:
        """Given v2 / When POST price v1 / Then 409."""
        created = await _publish(api)
        await api.post(
            f"/offers/{created['id']}/price",
            json={"expected_version": 1, "price_minor": 2499, "correlation_id": unique("corr")},
        )
        response = await api.post(
            f"/offers/{created['id']}/price",
            json={"expected_version": 1, "price_minor": 2999, "correlation_id": unique("corr")},
        )
        assert response.status_code == 409

    async def test_unknown_offer_is_404(self, api: AsyncClient) -> None:
        """Given unknown id / When POST price / Then 404."""
        response = await api.post(
            "/offers/offer-missing/price",
            json={"expected_version": 1, "price_minor": 1, "correlation_id": unique("corr")},
        )
        assert response.status_code == 404
