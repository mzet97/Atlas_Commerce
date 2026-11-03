"""Projection worker: Kafka offer events -> PostgreSQL read model.

Idempotent: (consumer_id, event_id) is the PK of processed_events, applied
in the SAME transaction as the projection row. Replays never duplicate.
"""

from __future__ import annotations

import asyncio
import json
import os

import asyncpg
from aiokafka import AIOKafkaConsumer
from pydantic import BaseModel, ConfigDict

CONSUMER_ID = "offer-projector-1"


class EventEnvelope(BaseModel):
    """Boundary parse of the versioned envelope (contracts N/N-1)."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_version: int
    correlation_id: str


async def apply_event(pool: asyncpg.Pool, raw: bytes) -> bool:
    """Apply one record. Returns True when applied, False when duplicate."""
    envelope = EventEnvelope.model_validate_json(raw.decode())
    payload = json.loads(raw.decode())["payload"]
    async with pool.acquire() as conn, conn.transaction():
        try:
            await conn.execute(
                "INSERT INTO processed_events"
                "(consumer_id, event_id, aggregate_id, aggregate_version)"
                " VALUES ($1, $2, $3, $4)",
                CONSUMER_ID,
                envelope.event_id,
                envelope.aggregate_id,
                envelope.aggregate_version,
            )
        except asyncpg.UniqueViolationError:
            return False
        if envelope.event_type in ("OfferPublished", "PriceChanged", "OfferDeactivated"):
            await conn.execute(
                "INSERT INTO available_offer_view"
                "(offer_id, sku_id, seller_id, market_id, currency, price_minor,"
                " status, projection_version)"
                " VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
                " ON CONFLICT (offer_id) DO UPDATE SET"
                " price_minor=EXCLUDED.price_minor, status=EXCLUDED.status,"
                " projection_version=EXCLUDED.projection_version"
                " WHERE available_offer_view.projection_version"
                " < EXCLUDED.projection_version",
                envelope.aggregate_id,
                payload.get("sku_id", ""),
                payload.get("seller_id", ""),
                payload.get("market_id", ""),
                payload.get("currency", ""),
                int(payload.get("price_minor", 0)),
                payload.get("status", ""),
                envelope.aggregate_version,
            )
        return True


async def run_forever() -> None:
    """Worker boundary: poison records are contained, the loop lives."""
    pool = await asyncpg.create_pool(os.environ["PG_DSN"], min_size=1, max_size=5)
    consumer = AIOKafkaConsumer(
        "atlas.offers.OfferPublished.v1",
        "atlas.offers.PriceChanged.v1",
        "atlas.offers.OfferDeactivated.v1",
        bootstrap_servers=os.environ["KAFKA_BOOTSTRAP"],
        group_id="offer-projector",
        enable_auto_commit=False,
    )
    await consumer.start()
    try:
        async for record in consumer:
            try:
                await apply_event(pool, bytes(record.value))
            except Exception as exc:  # worker boundary: contain, keep projecting
                print(f"projector record failed (continues): {type(exc).__name__}: {exc}")
            await consumer.commit()
    finally:
        await consumer.stop()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run_forever())
