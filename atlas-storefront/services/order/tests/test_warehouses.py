"""Multi-warehouse fulfillment: W-first hint picking, atomic revalidation."""

from __future__ import annotations

import json

import httpx
import pytest

from atlas_order import application


def _transport(positions: dict[str, int], reservations: list[str],
               shortage_warehouses: set[str] | None = None) -> httpx.MockTransport:
    """Inventory double: per-warehouse availability + reservation recorder."""
    shortage = shortage_warehouses or set()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path.startswith("/positions/"):
            _, _, warehouse, sku = path.split("/")
            available = positions.get(f"{warehouse}/{sku}", 0)
            if warehouse in shortage or available == 0:
                return httpx.Response(404)
            return httpx.Response(200, json={
                "warehouse_id": warehouse, "sku_id": sku,
                "on_hand": available, "reserved": 0,
                "safety_stock": 0, "available": available})
        if request.method == "POST" and path == "/reservations":
            body = json.loads(request.content.decode())
            reservations.append(f"{body['warehouse_id']}:{body['sku_id']}")
            return httpx.Response(201, json={"id": f"res-{len(reservations)}"})
        return httpx.Response(500)

    return httpx.MockTransport(handler)


class TestWarehousePicking:
    async def test_first_warehouse_with_stock_wins(self) -> None:
        """Given W1 empty + W2 stocked / When reserve / Then W2 picked."""
        reservations: list[str] = []
        async with httpx.AsyncClient(
            transport=_transport({"W2/sku-a": 5}, reservations),
            base_url="http://test",
        ) as http:
            class _OrderStub:
                id = "o-1"
                idempotency_key = "k-1"

            reservation_id = await application._reserve(
                http, "sku-a", 2, _OrderStub(), "corr")  # type: ignore[arg-type]
        assert reservation_id == "res-1"
        assert reservations == ["W2:sku-a"]

    async def test_first_configured_warehouse_preferred(self) -> None:
        """Given both stocked / When reserve / Then W1 (order) wins."""
        reservations: list[str] = []
        async with httpx.AsyncClient(
            transport=_transport({"W1/sku-a": 5, "W2/sku-a": 5}, reservations),
            base_url="http://test",
        ) as http:
            class _OrderStub:
                id = "o-1"
                idempotency_key = "k-1"

            await application._reserve(
                http, "sku-a", 2, _OrderStub(), "corr")  # type: ignore[arg-type]
        assert reservations == ["W1:sku-a"]

    async def test_no_warehouse_shortage(self) -> None:
        """Given no stock anywhere / When reserve / Then StockShortage."""
        async with httpx.AsyncClient(
            transport=_transport({}, []), base_url="http://test",
        ) as http:
            class _OrderStub:
                id = "o-1"
                idempotency_key = "k-1"

            with pytest.raises(application.StockShortage):
                await application._reserve(
                    http, "sku-x", 1, _OrderStub(), "corr")  # type: ignore[arg-type]

    async def test_hint_below_quantity_skipped(self) -> None:
        """Given W1 has 1 of 2 needed / When reserve / Then W2 picked."""
        reservations: list[str] = []
        async with httpx.AsyncClient(
            transport=_transport({"W1/sku-a": 1, "W2/sku-a": 9}, reservations),
            base_url="http://test",
        ) as http:
            class _OrderStub:
                id = "o-1"
                idempotency_key = "k-1"

            await application._reserve(
                http, "sku-a", 2, _OrderStub(), "corr")  # type: ignore[arg-type]
        assert reservations == ["W2:sku-a"]
