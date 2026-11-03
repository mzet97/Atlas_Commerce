"""Order API tests: quote pricing, saga legs, compensation (downstream faked)."""

from __future__ import annotations

import pytest
from conftest import unique
from httpx import AsyncClient

from atlas_order import application

OFFER = {"offer_id": "o1", "sku_id": "s1", "currency": "BRL",
         "price_minor": 1999, "status": "PUBLISHED"}


async def _fake_offer(pool: object, offer_id: str) -> dict[str, object] | None:
    return dict(OFFER, offer_id=offer_id) if offer_id == "o1" else None


_RESULTS: dict[str, object] = {}


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Given: downstream legs faked, every call tracked."""
    calls: list[str] = []
    monkeypatch.setattr(application, "fetch_offer", _fake_offer)

    async def _reserve(http: object, sku: str, qty: int, order: object,
                       correlation: str) -> str:
        calls.append(f"reserve:{sku}")
        result = _RESULTS.get("reserve", "res-1")
        if isinstance(result, Exception):
            raise result
        assert isinstance(result, str)
        return result

    async def _leg(http: object, reservation_id: str, action: str,
                   correlation: str) -> None:
        calls.append(f"{action}:{reservation_id}")

    async def _authorize(http: object, order: object,
                         correlation: str) -> dict[str, object]:
        calls.append("authorize")
        result = _RESULTS.get("authorize", {"id": "pi-1", "status": "AUTHORIZED"})
        assert isinstance(result, dict)
        return result

    async def _status(http: object, intent_id: str,
                      correlation: str) -> dict[str, object]:
        calls.append(f"status:{intent_id}")
        result = _RESULTS.get("status", {"status": "UNKNOWN"})
        assert isinstance(result, dict)
        return result

    monkeypatch.setattr(application, "_reserve", _reserve)
    monkeypatch.setattr(application, "_transition_reservation", _leg)
    monkeypatch.setattr(application, "_authorize", _authorize)
    monkeypatch.setattr(application, "_payment_status", _status)
    _RESULTS.clear()
    return calls


async def _cart_with_item(api: AsyncClient) -> str:
    created = await api.post("/carts", json={
        "customer_id": unique("cust"), "correlation_id": unique("corr")})
    assert created.status_code == 201, created.text
    cart_id = created.json()["id"]
    added = await api.post(f"/carts/{cart_id}/items", json={
        "offer_id": "o1", "quantity": 2, "correlation_id": unique("corr")})
    assert added.status_code == 200, added.text
    return cart_id


async def _quote(api: AsyncClient) -> dict[str, object]:
    cart_id = await _cart_with_item(api)
    response = await api.post(f"/carts/{cart_id}/quote")
    assert response.status_code == 201, response.text
    parsed = response.json()
    assert isinstance(parsed, dict)
    return parsed


async def _checkout(api: AsyncClient, quote_id: str,
                    key: str | None = None) -> tuple[int, dict]:
    response = await api.post("/checkouts", json={
        "quote_id": quote_id, "customer_id": unique("cust"),
        "card_last4": "4242", "idempotency_key": key or unique("idem"),
        "correlation_id": unique("corr")})
    parsed = response.json()
    assert isinstance(parsed, dict)
    return response.status_code, parsed


class TestQuote:
    async def test_quote_prices_from_read_model(
        self, api: AsyncClient, fakes: list[str]
    ) -> None:
        """Given cart with 2x offer / When quoted / Then total = 2 * price."""
        quote = await _quote(api)
        assert quote["total_minor"] == 3998
        assert quote["currency"] == "BRL"

    async def test_unknown_offer_is_422(
        self, api: AsyncClient, fakes: list[str]
    ) -> None:
        """Given cart with missing offer / When quoted / Then 422."""
        cart_id = await _cart_with_item(api)
        await api.post(f"/carts/{cart_id}/items", json={
            "offer_id": "nope", "quantity": 1, "correlation_id": unique("corr")})
        response = await api.post(f"/carts/{cart_id}/quote")
        assert response.status_code == 422


class TestCheckout:
    async def test_happy_path_confirms(
        self, api: AsyncClient, fakes: list[str]
    ) -> None:
        """Given stock + approval / When checkout / Then 201 CONFIRMED."""
        quote = await _quote(api)
        status, order = await _checkout(api, str(quote["id"]))
        assert status == 201, order
        assert order["status"] == "CONFIRMED"
        assert order["reservation_ids"] == ["res-1"]
        assert order["payment_intent_id"] == "pi-1"
        assert "confirm:res-1" in fakes

    async def test_decline_compensates(
        self, api: AsyncClient, fakes: list[str]
    ) -> None:
        """Given decline / When checkout / Then 402 CANCELLED + released."""
        _RESULTS["authorize"] = {"id": "pi-2", "status": "DECLINED"}
        quote = await _quote(api)
        status, order = await _checkout(api, str(quote["id"]))
        assert status == 402, order
        assert order["status"] == "CANCELLED"
        assert "release:res-1" in fakes
        assert "confirm:res-1" not in fakes

    async def test_unknown_stays_pending(
        self, api: AsyncClient, fakes: list[str]
    ) -> None:
        """Given UNKNOWN / When checkout / Then 202 PENDING, resolved later."""
        _RESULTS["authorize"] = {"id": "pi-3", "status": "UNKNOWN"}
        quote = await _quote(api)
        status, order = await _checkout(api, str(quote["id"]))
        assert status == 202, order
        assert (order["status"], order["payment_intent_id"]) == ("PENDING", "pi-3")
        _RESULTS["status"] = {"status": "AUTHORIZED"}
        response = await api.post(f"/orders/{order['id']}/reconcile",
                                  json={"correlation_id": unique("corr")})
        assert response.json()["status"] == "CONFIRMED"

    async def test_shortage_rejects_without_charge(
        self, api: AsyncClient, fakes: list[str]
    ) -> None:
        """Given no stock / When checkout / Then 409 REJECTED, PSP untouched."""
        _RESULTS["reserve"] = application.StockShortage("s1")
        quote = await _quote(api)
        status, order = await _checkout(api, str(quote["id"]))
        assert status == 409, order
        assert order["status"] == "REJECTED"
        assert "authorize" not in fakes

    async def test_same_key_replays_winner(
        self, api: AsyncClient, fakes: list[str]
    ) -> None:
        """Given checkout / When same key again / Then same order, 1 of each."""
        quote = await _quote(api)
        key = unique("idem")
        first_status, first = await _checkout(api, str(quote["id"]), key)
        assert first_status == 201
        second_status, second = await _checkout(api, str(quote["id"]), key)
        assert (second_status, second["id"]) == (201, first["id"])
        assert fakes.count("authorize") == 1
        assert fakes.count("reserve:s1") == 1

    async def test_second_key_needs_fresh_quote(
        self, api: AsyncClient, fakes: list[str]
    ) -> None:
        """Given consumed quote / When new key reuses it / Then 422."""
        quote = await _quote(api)
        status, _ = await _checkout(api, str(quote["id"]))
        assert status == 201
        status2, body = await _checkout(api, str(quote["id"]), unique("idem"))
        assert status2 == 422, body

    async def test_ship_confirmed_order(
        self, api: AsyncClient, fakes: list[str]
    ) -> None:
        """Given CONFIRMED / When shipped twice / Then SHIPPED, idempotent."""
        quote = await _quote(api)
        _, order = await _checkout(api, str(quote["id"]))
        assert order["status"] == "CONFIRMED"
        first = await api.post(f"/orders/{order['id']}/ship",
                               json={"correlation_id": unique("corr")})
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "SHIPPED"
        second = await api.post(f"/orders/{order['id']}/ship",
                                json={"correlation_id": unique("corr")})
        assert second.json()["status"] == "SHIPPED"
        assert second.json()["version"] == first.json()["version"]

    async def test_ship_pending_is_409(
        self, api: AsyncClient, fakes: list[str]
    ) -> None:
        """Given PENDING / When shipped / Then 409, no transition."""
        _RESULTS["authorize"] = {"id": "pi-9", "status": "UNKNOWN"}
        quote = await _quote(api)
        status, order = await _checkout(api, str(quote["id"]))
        assert status == 202
        response = await api.post(f"/orders/{order['id']}/ship",
                                  json={"correlation_id": unique("corr")})
        assert response.status_code == 409

    async def test_expired_quote_rejected(
        self, api: AsyncClient, fakes: list[str]
    ) -> None:
        """Given expired quote / When checkout / Then 422, legs untouched."""
        from atlas_order.api import app as order_app

        quote = await _quote(api)
        repo = order_app.state.repo  # type: ignore[attr-defined]
        await repo.database.quotes.update_one(
            {"_id": quote["id"]}, {"$set": {"expires_at": "2000-01-01T00:00:00+00:00"}})
        status, body = await _checkout(api, str(quote["id"]))
        assert status == 422, body
        assert fakes == []
