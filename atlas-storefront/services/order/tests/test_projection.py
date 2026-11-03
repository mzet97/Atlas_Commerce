"""Relay + projector tests: outbox drains once, PG projection is idempotent."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import asyncpg
import pytest_asyncio
from conftest import PG_TEST_DSN, unique

from atlas_order import domain
from atlas_order.domain import CorrelationId, IdempotencyKey, OrderId, QuoteId
from atlas_order.projector import apply_event
from atlas_order.relay import publish_unpublished

MIGRATION = os.path.join(os.path.join(os.path.dirname(__file__), "..", "migrations",
                                      "003_order_projection.sql"))


@pytest_asyncio.fixture
async def pool():
    """Given: projection tables exist (idempotent migration)."""
    handle = await asyncpg.create_pool(PG_TEST_DSN, min_size=1, max_size=2)
    assert handle is not None
    sql = await asyncio.to_thread(Path(MIGRATION).read_text, encoding="utf-8")
    await handle.execute(sql)
    yield handle
    await handle.close()


class StubProducer:
    """Captures relay sends without a broker."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes]] = []

    async def send_and_wait(self, topic: str, value: bytes, key: bytes) -> None:
        self.sent.append((topic, value))


def _placed() -> domain.Order:
    quote = domain.Quote(
        id=QuoteId(unique("q")),
        cart_id=domain.CartId(unique("c")),
        currency="BRL",
        lines=[{"offer_id": "o1", "sku_id": "s1", "quantity": 1,
                "price_minor": 1999}],
        total_minor=1999,
        expires_at="2099-01-01T00:00:00+00:00",
    )
    return domain.Order.place(
        OrderId(unique("o")),
        quote,
        unique("cust"),
        "4242",
        IdempotencyKey(unique("idem")),
        CorrelationId(unique("corr")),
    )


class TestRelayDrain:
    async def test_outbox_marks_published(self, repo) -> None:
        """Given new order / When relay passes / Then sent + drain."""
        await repo.place(_placed())
        producer = StubProducer()
        sent = await publish_unpublished(repo.database, producer)  # type: ignore[arg-type]
        assert sent >= 1  # shared test DB may hold earlier rows
        topic, _raw = producer.sent[-1]
        assert topic == "atlas.order.OrderPlaced.v1"
        assert await publish_unpublished(repo.database, producer) == 0  # type: ignore[arg-type]

    async def test_envelope_feeds_projector(self, repo, pool) -> None:
        """Given relay envelope / When applied twice / Then True,False + rows."""
        await repo.place(_placed())
        producer = StubProducer()
        await publish_unpublished(repo.database, producer)  # type: ignore[arg-type]
        _, raw = producer.sent[-1]
        assert await apply_event(pool, raw) is True
        assert await apply_event(pool, raw) is False  # replay: no duplicate
        envelope = json.loads(raw.decode())
        row = await pool.fetchrow(
            "SELECT status, projection_version FROM orders_view WHERE order_id=$1",
            envelope["aggregate_id"],
        )
        assert (row["status"], row["projection_version"]) == ("PENDING", 1)
        lines = await pool.fetch(
            "SELECT offer_id, quantity FROM order_lines WHERE order_id=$1",
            envelope["aggregate_id"],
        )
        assert [(line["offer_id"], line["quantity"]) for line in lines] == [("o1", 1)]
