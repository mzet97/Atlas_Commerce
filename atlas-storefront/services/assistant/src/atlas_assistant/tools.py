"""Tools the assistant MAY call (doc 08 allowlist). Nothing else exists.

Read-only, owner-served: search_catalog (catalog read model) and
check_inventory_hint (availability HINT — never checkout truth,
INV-CQRS-001). Forbidden tools (charge_card, issue_refund, set_price,
modify_stock) are not registered here at all — absence is the guarantee.
"""

from __future__ import annotations

import os

import httpx

TOOL_NAMES: tuple[str, ...] = ("search_catalog", "check_inventory_hint")

FORBIDDEN_TOOL_NAMES: tuple[str, ...] = (
    "charge_card",
    "issue_refund",
    "set_price",
    "modify_stock",
)


def _catalog_base() -> str:
    return os.getenv("CATALOG_API_URL", "http://localhost:8101")


def _inventory_base() -> str:
    return os.getenv("INVENTORY_API_URL", "http://localhost:8104")


async def search_catalog(query: str, limit: int = 5) -> list[dict[str, object]]:
    """PUBLISHED products with ACTIVE offer + availability hint."""
    async with httpx.AsyncClient(timeout=15) as http:
        response = await http.get(
            f"{_catalog_base()}/products", params={"q": query, "limit": limit}
        )
    if response.status_code != 200:
        return []
    rows = response.json()
    return [row for row in rows if isinstance(row, dict)]


async def check_inventory_hint(sku_id: str, warehouse_id: str = "W1") -> dict[str, object]:
    """Availability HINT for UI display; checkout revalidates at the owner."""
    async with httpx.AsyncClient(timeout=15) as http:
        response = await http.get(
            f"{_inventory_base()}/positions/{warehouse_id}/{sku_id}"
        )
    if response.status_code != 200:
        return {"sku_id": sku_id, "available": 0}
    body = response.json()
    assert isinstance(body, dict)
    return {"sku_id": sku_id, "available": int(body.get("available", 0))}
