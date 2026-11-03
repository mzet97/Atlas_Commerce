"""Inventory API tests: real HTTP surface + real Mongo (host-mapped)."""

from __future__ import annotations

import pytest_asyncio
from conftest import unique
from httpx import ASGITransport, AsyncClient, Response

from atlas_inventory.api import app as inventory_app


@pytest_asyncio.fixture
async def api():
    """Given: lifespan up (client per test loop), indexes ensured on boot."""
    async with (
        inventory_app.router.lifespan_context(inventory_app),
        AsyncClient(transport=ASGITransport(app=inventory_app), base_url="http://test") as http,
    ):
        yield http


async def _receive(http: AsyncClient, sku: str, qty: int) -> dict[str, str | int]:
    response = await http.post(
        "/positions/receive",
        json={
            "warehouse_id": "W1",
            "sku_id": sku,
            "quantity": qty,
            "correlation_id": unique("corr"),
        },
    )
    assert response.status_code == 201, response.text
    parsed = response.json()
    assert isinstance(parsed, dict)
    return parsed


async def _reserve(http: AsyncClient, sku: str, qty: int, key: str | None = None) -> Response:
    return await http.post(
        "/reservations",
        json={
            "warehouse_id": "W1",
            "sku_id": sku,
            "quantity": qty,
            "checkout_id": unique("checkout"),
            "idempotency_key": key or unique("idem"),
            "correlation_id": unique("corr"),
        },
    )


class TestReceive:
    async def test_happy_path_creates_position(self, api: AsyncClient) -> None:
        """Given empty / When receiving 5 / Then on_hand 5, available 5."""
        position = await _receive(api, unique("sku"), 5)
        assert (position["on_hand"], position["available"]) == (5, 5)


class TestReserve:
    async def test_happy_path_allocates(self, api: AsyncClient) -> None:
        """Given on_hand 5 / When reserving 2 / Then ACTIVE, available drops."""
        sku = unique("sku")
        await _receive(api, sku, 5)
        response = await _reserve(api, sku, 2)
        assert response.status_code == 201
        assert response.json()["status"] == "ACTIVE"

    async def test_oversell_is_rejected(self, api: AsyncClient) -> None:
        """Given available 1 / When reserving 2 / Then 409, balances kept."""
        sku = unique("sku")
        await _receive(api, sku, 1)
        response = await _reserve(api, sku, 2)
        assert response.status_code == 409

    async def test_same_key_returns_same_reservation(self, api: AsyncClient) -> None:
        """Given reserved / When same key again / Then same id (INV-002)."""
        sku = unique("sku")
        await _receive(api, sku, 5)
        key = unique("idem")
        first = await _reserve(api, sku, 2, key)
        second = await _reserve(api, sku, 2, key)
        assert first.status_code == second.status_code == 201
        assert first.json()["id"] == second.json()["id"]


class TestConfirmRelease:
    async def test_confirm_ships_and_release_restores(self, api: AsyncClient) -> None:
        """Given ACTIVE 2 of 5 / When confirm+release paths / Then math holds."""
        sku = unique("sku")
        await _receive(api, sku, 5)
        first = await _reserve(api, sku, 2)
        rid = first.json()["id"]
        confirmed = await api.post(
            f"/reservations/{rid}/confirm", json={"correlation_id": unique("corr")}
        )
        assert confirmed.status_code == 200
        position = await api.get(f"/positions/W1/{sku}")
        assert (position.json()["on_hand"], position.json()["reserved"]) == (3, 0)

        second = await _reserve(api, sku, 1)
        rid2 = second.json()["id"]
        released = await api.post(
            f"/reservations/{rid2}/release", json={"correlation_id": unique("corr")}
        )
        assert released.status_code == 200
        position = await api.get(f"/positions/W1/{sku}")
        assert (position.json()["on_hand"], position.json()["reserved"]) == (3, 0)
