"""API integration tests: real HTTP surface + real Mongo (host-mapped).

Each test uses unique keys: no ordering dependence, no teardown races.
"""

from __future__ import annotations

import pytest_asyncio
from conftest import unique
from httpx import ASGITransport, AsyncClient

from atlas_catalog.api import app as catalog_app


@pytest_asyncio.fixture
async def api():
    """Given: lifespan up (client per test loop), indexes ensured on boot."""
    async with (
        catalog_app.router.lifespan_context(catalog_app),
        AsyncClient(transport=ASGITransport(app=catalog_app), base_url="http://test") as http,
    ):
        yield http


async def _create(http: AsyncClient, key: str | None = None) -> dict[str, str | int]:
    body = {
        "title": {"pt-BR": "Café"},
        "category_id": None,
        "idempotency_key": key or unique("idem"),
        "correlation_id": unique("corr"),
    }
    response = await http.post("/products", json=body)
    assert response.status_code == 201, response.text
    parsed = response.json()
    assert isinstance(parsed, dict)
    return parsed


class TestCreateProduct:
    async def test_happy_path_returns_draft(self, api: AsyncClient) -> None:
        """Given valid body / When POST /products / Then 201 DRAFT v1."""
        created = await _create(api)
        assert created["status"] == "DRAFT"
        assert created["version"] == 1

    async def test_same_idempotency_key_returns_same_product(self, api: AsyncClient) -> None:
        """Given created product / When POST same key / Then same id, no dup."""
        key = unique("idem")
        first = await _create(api, key)
        second = await _create(api, key)
        assert first["id"] == second["id"]

    async def test_missing_locale_is_422(self, api: AsyncClient) -> None:
        """Given title without pt-BR / When POST / Then 422, nothing stored."""
        response = await api.post(
            "/products",
            json={
                "title": {"en-US": "Coffee"},
                "idempotency_key": unique("idem"),
                "correlation_id": unique("corr"),
            },
        )
        assert response.status_code == 422


class TestPublishProduct:
    async def test_happy_path_publishes(self, api: AsyncClient) -> None:
        """Given DRAFT v1 / When publish v1 / Then 200 PUBLISHED v2."""
        created = await _create(api)
        response = await api.post(
            f"/products/{created['id']}/publish",
            json={"expected_version": 1, "correlation_id": unique("corr")},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "PUBLISHED"
        assert response.json()["version"] == 2

    async def test_stale_version_conflicts(self, api: AsyncClient) -> None:
        """Given PUBLISHED v2 / When publish v1 / Then 409."""
        created = await _create(api)
        await api.post(
            f"/products/{created['id']}/publish",
            json={"expected_version": 1, "correlation_id": unique("corr")},
        )
        response = await api.post(
            f"/products/{created['id']}/publish",
            json={"expected_version": 1, "correlation_id": unique("corr")},
        )
        assert response.status_code == 409

    async def test_unknown_product_is_404(self, api: AsyncClient) -> None:
        """Given unknown id / When publish / Then 404."""
        response = await api.post(
            "/products/product-missing/publish",
            json={"expected_version": 1, "correlation_id": unique("corr")},
        )
        assert response.status_code == 404
