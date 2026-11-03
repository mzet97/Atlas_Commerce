"""Shared fixtures: test DBs are the host-mapped stack (dev gate)."""

from __future__ import annotations

import os
import uuid

os.environ.setdefault(
    "MONGO_URL",
    "mongodb://localhost:27017/order_test?replicaSet=rs0&directConnection=true",
)
os.environ.setdefault("ORDER_DB", "order_test")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("INVENTORY_API_URL", "http://localhost:8104")
os.environ.setdefault("PAYMENT_API_URL", "http://localhost:8105")
os.environ.setdefault(
    "PG_DSN", "postgresql://postgres:atlas-pg-dev-only@localhost:5432/atlas"
)

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from atlas_order.api import app as order_app
from atlas_order.mongo_repo import MongoOrderRepository

PG_TEST_DSN = os.getenv(
    "PG_TEST_DSN", "postgresql://postgres:atlas-pg-dev-only@localhost:5432/atlas"
)


def unique(prefix: str) -> str:
    """Unique key per test: no ordering dependence, no teardown races."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def repo():
    """Given: a repository handle on the test database."""
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000)
    handle = MongoOrderRepository(client, os.environ["ORDER_DB"])
    await handle.ensure_indexes()
    yield handle
    client.close()


@pytest_asyncio.fixture
async def api():
    """Given: lifespan up (repo + pool per test loop)."""
    async with (
        order_app.router.lifespan_context(order_app),
        AsyncClient(transport=ASGITransport(app=order_app), base_url="http://test") as http,
    ):
        yield http
