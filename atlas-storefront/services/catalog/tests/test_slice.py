"""Slice tests: concurrency idempotency + exactly-once projection.

Needs the stack: Mongo (localhost:27017), Kafka (localhost:9092),
Postgres with migrations applied (localhost:5432/atlas).
"""

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

from atlas_catalog.api import app as catalog_app
from atlas_catalog.mongo_repo import MongoProductRepository
from atlas_catalog.projector import apply_event
from atlas_catalog.relay import publish_unpublished


@pytest_asyncio.fixture
async def stack():
    """Given: lifespan up (repo per test loop) + live producer and pool."""
    async with catalog_app.router.lifespan_context(catalog_app):
        client = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000)
        repo = MongoProductRepository(client, db_name="catalog_test")
        producer = AIOKafkaProducer(bootstrap_servers=KAFKA_TEST_BOOTSTRAP)
        await producer.start()
        pool = await asyncpg.create_pool(PG_TEST_DSN, min_size=1, max_size=2)
        assert pool is not None
        yield repo, producer, pool
        await producer.stop()
        await pool.close()
        client.close()


class TestConcurrentCreate:
    async def test_same_key_creates_exactly_one(
        self, stack: tuple[MongoProductRepository, AIOKafkaProducer, asyncpg.Pool]
    ) -> None:
        """Given 20 concurrent POSTs, one key / When raced / Then one product."""
        repo, _, _ = stack
        key = unique("idem")
        async with AsyncClient(
            transport=ASGITransport(app=catalog_app), base_url="http://test"
        ) as http:
            bodies = [
                {
                    "title": {"pt-BR": "Café"},
                    "idempotency_key": key,
                    "correlation_id": unique("corr"),
                }
                for _ in range(20)
            ]
            responses = await asyncio.gather(
                *(http.post("/products", json=body) for body in bodies)
            )
        assert all(r.status_code == 201 for r in responses)
        ids = {r.json()["id"] for r in responses}
        assert len(ids) == 1
        count = await repo.database.products.count_documents({"idempotency_key": key})
        assert count == 1


class TestExactlyOnceProjection:
    async def test_duplicate_delivery_projects_once(
        self, stack: tuple[MongoProductRepository, AIOKafkaProducer, asyncpg.Pool]
    ) -> None:
        """Given relayed event / When applied twice / Then one row, one inbox."""
        repo, producer, pool = stack
        async with AsyncClient(
            transport=ASGITransport(app=catalog_app), base_url="http://test"
        ) as http:
            body = {
                "title": {"pt-BR": "Café"},
                "idempotency_key": unique("idem"),
                "correlation_id": unique("corr"),
            }
            response = await http.post("/products", json=body)
            assert response.status_code == 201
        sent = await publish_unpublished(repo.database, producer)
        assert sent >= 1
        assert await publish_unpublished(repo.database, producer) == 0

        doc = await repo.database.outbox.find_one({"published": True}, sort=[("_id", -1)])
        assert doc is not None
        raw = json.dumps({k: v for k, v in doc.items() if k not in ("_id", "published")}).encode()
        assert await apply_event(pool, raw) is True
        assert await apply_event(pool, raw) is False
        row = await pool.fetchrow(
            "SELECT status, projection_version FROM catalog_product_search WHERE product_id = $1",
            doc["aggregate_id"],
        )
        assert row is not None
        assert (row["status"], row["projection_version"]) == ("DRAFT", 1)
        inbox = await pool.fetchval(
            "SELECT COUNT(*) FROM processed_events WHERE event_id = $1",
            doc["event_id"],
        )
        assert inbox == 1
