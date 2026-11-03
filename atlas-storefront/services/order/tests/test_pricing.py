"""Checkout pricing rules: coupons + regional taxes (TASK-002-013)."""

from __future__ import annotations

import pytest
from conftest import unique
from httpx import AsyncClient

from atlas_order import application, pricing

OFFER_BR = {"offer_id": "o1", "sku_id": "s1", "currency": "BRL",
            "price_minor": 10000, "market_id": "BR", "status": "PUBLISHED"}


class TestCouponRules:
    def test_no_code_means_no_discount(self) -> None:
        assert pricing.validate_coupon(None, None, 10000, "BR") == 0

    def test_unknown_or_inactive_is_rejected(self) -> None:
        with pytest.raises(pricing.CouponRejected):
            pricing.validate_coupon(None, "X", 10000, "BR")
        inactive = {"code": "X", "kind": "PERCENT", "value": 10, "active": False}
        with pytest.raises(pricing.CouponRejected):
            pricing.validate_coupon(inactive, "X", 10000, "BR")

    def test_percent_discount_floor(self) -> None:
        coupon = {"code": "P10", "kind": "PERCENT", "value": 10, "active": True}
        assert pricing.validate_coupon(coupon, "P10", 999, "BR") == 99

    def test_fixed_discount_capped_at_subtotal(self) -> None:
        coupon = {"code": "F500", "kind": "FIXED", "value": 500, "active": True}
        assert pricing.validate_coupon(coupon, "F500", 300, "BR") == 300

    def test_minimum_subtotal_enforced(self) -> None:
        coupon = {"code": "M", "kind": "FIXED", "value": 100,
                  "min_subtotal_minor": 1000, "active": True}
        with pytest.raises(pricing.CouponRejected):
            pricing.validate_coupon(coupon, "M", 999, "BR")
        assert pricing.validate_coupon(coupon, "M", 1000, "BR") == 100

    def test_market_scoped_coupon(self) -> None:
        coupon = {"code": "BR", "kind": "PERCENT", "value": 10,
                  "market_id": "BR", "active": True}
        assert pricing.validate_coupon(coupon, "BR", 1000, "BR") == 100
        with pytest.raises(pricing.CouponRejected):
            pricing.validate_coupon(coupon, "BR", 1000, "US")


class TestTaxRules:
    def test_known_markets(self) -> None:
        assert pricing.tax_minor("BR", 10000) == (1550, 1550)
        assert pricing.tax_minor("US", 10000) == (875, 875)
        assert pricing.tax_minor("UE", 10000) == (2100, 2100)

    def test_floor_rounding(self) -> None:
        rate, tax = pricing.tax_minor("BR", 101)
        assert rate == 1550 and tax == 15  # 101*0.155 = 15.655 -> 15

    def test_unknown_market_taxes_zero(self) -> None:
        assert pricing.tax_minor("XX", 10000) == (0, 0)


@pytest.fixture
def br_offer(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_offer(pool: object, offer_id: str) -> dict[str, object] | None:
        return dict(OFFER_BR, offer_id=offer_id) if offer_id == "o1" else None

    monkeypatch.setattr(application, "fetch_offer", _fake_offer)


class TestQuoteBreakdown:
    async def test_br_quote_adds_tax(self, api: AsyncClient, br_offer: None,
                                     repo: object) -> None:
        """Given BR offer 100.00 / When quoted / Then tax 15.5%, total 115.50."""
        cart_id = await _cart(api, qty=1)
        quote = await _quote(api, cart_id)
        assert quote["subtotal_minor"] == 10000
        assert quote["tax_minor"] == 1550
        assert quote["discount_minor"] == 0
        assert quote["total_minor"] == 11550
        assert quote["tax_rate_bps"] == 1550
        assert quote["market_id"] == "BR"

    async def test_coupon_discount_applies_before_tax(
        self, api: AsyncClient, br_offer: None, repo: object
    ) -> None:
        """Given P10 coupon / When quoted / Then 10000-1000+1395 = 10395."""
        from atlas_order.mongo_repo import MongoOrderRepository

        assert isinstance(repo, MongoOrderRepository)
        await repo.upsert_coupon(
            {"code": "P10", "kind": "PERCENT", "value": 10, "active": True}
        )
        cart_id = await _cart(api, qty=1)
        set_coupon = await api.post(f"/carts/{cart_id}/coupon", json={
            "code": "P10", "correlation_id": unique("corr")})
        assert set_coupon.status_code == 200, set_coupon.text
        quote = await _quote(api, cart_id)
        assert quote["discount_minor"] == 1000
        assert quote["tax_minor"] == 1395  # 15.5% on 9000 taxable (BR bps)
        assert quote["total_minor"] == 10395
        assert quote["coupon_code"] == "P10"

    async def test_unknown_coupon_code_rejected_on_set(
        self, api: AsyncClient, br_offer: None, repo: object
    ) -> None:
        cart_id = await _cart(api, qty=1)
        response = await api.post(f"/carts/{cart_id}/coupon", json={
            "code": "NOPE", "correlation_id": unique("corr")})
        assert response.status_code == 422

    async def test_market_scoped_coupon_refused_for_other_market(
        self, api: AsyncClient, br_offer: None, repo: object
    ) -> None:
        """Given US-scoped coupon / When BR cart quotes / Then 422."""
        from atlas_order.mongo_repo import MongoOrderRepository

        assert isinstance(repo, MongoOrderRepository)
        await repo.upsert_coupon(
            {"code": "US10", "kind": "PERCENT", "value": 10,
             "market_id": "US", "active": True}
        )
        cart_id = await _cart(api, qty=1)
        set_coupon = await api.post(f"/carts/{cart_id}/coupon", json={
            "code": "US10", "correlation_id": unique("corr")})
        assert set_coupon.status_code == 200
        response = await api.post(f"/carts/{cart_id}/quote")
        assert response.status_code == 422

    async def test_admin_upsert_and_deactivate(
        self, api: AsyncClient, br_offer: None, repo: object
    ) -> None:
        """Given admin endpoint / When upsert+deactivate / Then rules persist."""
        created = await api.post("/admin/coupons", json={
            "code": "F200", "kind": "FIXED", "value": 200,
            "min_subtotal_minor": 500, "correlation_id": unique("corr")})
        assert created.status_code == 201, created.text
        assert created.json()["active"] is True
        listed = await api.get("/admin/coupons")
        assert "F200" in [c["code"] for c in listed.json()]
        retired = await api.post("/admin/coupons/F200/deactivate", json={
            "correlation_id": unique("corr")})
        assert retired.status_code == 200
        assert retired.json()["active"] is False


async def _cart(api: AsyncClient, qty: int) -> str:
    created = await api.post("/carts", json={
        "customer_id": unique("cust"), "correlation_id": unique("corr")})
    assert created.status_code == 201, created.text
    cart_id = created.json()["id"]
    added = await api.post(f"/carts/{cart_id}/items", json={
        "offer_id": "o1", "quantity": qty, "correlation_id": unique("corr")})
    assert added.status_code == 200, added.text
    return str(cart_id)


async def _quote(api: AsyncClient, cart_id: str) -> dict[str, object]:
    response = await api.post(f"/carts/{cart_id}/quote")
    assert response.status_code == 201, response.text
    parsed = response.json()
    assert isinstance(parsed, dict)
    return parsed
