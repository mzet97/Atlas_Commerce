"""Shared fixtures: test DBs are the host-mapped stack (dev gate)."""

from __future__ import annotations

import os
import uuid

os.environ.setdefault(
    "MONGO_URL",
    "mongodb://localhost:27017/payment_test?replicaSet=rs0&directConnection=true",
)
os.environ.setdefault("PAYMENT_DB", "payment_test")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("PSP_BASE_URL", "http://localhost:8190")
os.environ.setdefault("PSP_WEBHOOK_SECRET", "psp-dev-secret")
os.environ.setdefault("PSP_TIMEOUT_SECONDS", "10")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from atlas_payment.api import app as payment_app
from atlas_payment.mongo_repo import MongoPaymentRepository

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
    handle = MongoPaymentRepository(client, os.environ["PAYMENT_DB"])
    await handle.ensure_indexes()
    yield handle
    client.close()


@pytest_asyncio.fixture
async def api():
    """Given: lifespan up (client per test loop), indexes ensured on boot."""
    async with (
        payment_app.router.lifespan_context(payment_app),
        AsyncClient(transport=ASGITransport(app=payment_app), base_url="http://test") as http,
    ):
        yield http
