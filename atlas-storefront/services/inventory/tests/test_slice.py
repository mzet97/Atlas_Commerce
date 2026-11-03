"""Inventory slice tests: last-unit race + exactly-once projection."""

from __future__ import annotations

import asyncio
import json
import os

import asyncpg
import pytest_asyncio
from aiokafka import AIOKafkaProducer
from conftest import KAFKA_TEST_BOOTSTRAP, PG_TEST_DSN, unique
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from atlas_inventory.api import app as inventory_app
from atlas_inventory.mongo_repo import MongoInventoryRepository
from atlas_inventory.projector import apply_event
from atlas_inventory.relay import publish_unpublished


@pytest_asyncio.fixture
async def stack():
    """Given: lifespan up (repo per test loop) + live producer and pool."""
    async with inventory_app.router.lifespan_context(inventory_app):
        client = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000)
        repo = MongoInventoryRepository(client, db_name="inventory_test")
        producer = AIOKafkaProducer(bootstrap_servers=KAFKA_TEST_BOOTSTRAP)
        await producer.start()
        pool = await asyncpg.create_pool(PG_TEST_DSN, min_size=1, max_size=2)
        assert pool is not None
        yield repo, producer, pool
        await producer.stop()
        await pool.close()
        client.close()


async def _receive(http: AsyncClient, sku: str, qty: int) -> None:
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


class TestLastUnitRace:
    async def test_exactly_one_winner_never_negative(
        self, stack: tuple[MongoInventoryRepository, AIOKafkaProducer, asyncpg.Pool]
    ) -> None:
        """Given 1 unit, 20 racers / When all reserve / Then 1 ACTIVE."""
        repo, _, _ = stack
        sku = unique("sku")
        async with AsyncClient(
            transport=ASGITransport(app=inventory_app), base_url="http://test"
        ) as http:
            await _receive(http, sku, 1)
            key = unique("race")
            responses = await asyncio.gather(
                *[
                    http.post(
                        "/reservations",
                        json={
                            "warehouse_id": "W1",
                            "sku_id": sku,
                            "quantity": 1,
                            "checkout_id": unique("checkout"),
                            "idempotency_key": f"{key}-{i}",
                            "correlation_id": unique("corr"),
                        },
                    )
                    for i in range(20)
                ]
            )
        won = [r for r in responses if r.status_code == 201]
        assert len(won) == 1
        assert all(r.status_code == 409 for r in responses if r not in won)
        count = await repo.database.reservations.count_documents(
            {"sku_id": sku, "status": "ACTIVE"}
        )
        assert count == 1
        position = await repo.get("W1", sku)
        assert position.available() == 0


class TestExactlyOnceProjection:
    async def test_duplicate_delivery_projects_once(
        self, stack: tuple[MongoInventoryRepository, AIOKafkaProducer, asyncpg.Pool]
    ) -> None:
        """Given relayed event / When applied twice / Then one row, one inbox."""
        repo, producer, pool = stack
        async with AsyncClient(
            transport=ASGITransport(app=inventory_app), base_url="http://test"
        ) as http:
            sku = unique("sku")
            await _receive(http, sku, 5)
        sent = await publish_unpublished(repo.database, producer)
        assert sent >= 1
        assert await publish_unpublished(repo.database, producer) == 0

        doc = await repo.database.outbox.find_one({"published": True}, sort=[("_id", -1)])
        assert doc is not None
        raw = json.dumps({k: v for k, v in doc.items() if k not in ("_id", "published")}).encode()
        assert await apply_event(pool, raw) is True
        assert await apply_event(pool, raw) is False
        row = await pool.fetchrow(
            "SELECT on_hand, reserved FROM inventory_availability_view"
            " WHERE warehouse_id = 'W1' AND sku_id = $1",
            doc["payload"]["sku_id"],
        )
        assert row is not None
        assert (row["on_hand"], row["reserved"]) == (5, 0)
