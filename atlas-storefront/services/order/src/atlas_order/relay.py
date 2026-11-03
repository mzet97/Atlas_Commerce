"""Outbox relay: Mongo outbox -> Kafka. Single pass is testable; loop runs it."""

from __future__ import annotations

import asyncio
import json
import os

from aiokafka import AIOKafkaProducer
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

POLL_SECONDS: float = 2.0
BATCH_SIZE: int = 100


def topic_for(event_type: str) -> str:
    """Topic per event type, versioned (contracts N/N-1)."""
    return f"atlas.order.{event_type}.v1"


async def publish_unpublished(db: AsyncIOMotorDatabase, producer: AIOKafkaProducer) -> int:
    """Publish one batch of unpublished outbox docs. Returns count sent."""
    docs = await db.outbox.find({"published": False}).limit(BATCH_SIZE).to_list(BATCH_SIZE)
    sent = 0
    for doc in docs:
        envelope = {k: v for k, v in doc.items() if k not in ("_id", "published")}
        await producer.send_and_wait(
            topic_for(str(doc["event_type"])),
            json.dumps(envelope).encode(),
            key=str(doc["aggregate_id"]).encode(),
        )
        await db.outbox.update_one({"_id": doc["_id"]}, {"$set": {"published": True}})
        sent += 1
    return sent


async def run_forever() -> None:
    """Worker boundary: a poison batch must not kill the relay silently."""
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    producer = AIOKafkaProducer(bootstrap_servers=os.environ["KAFKA_BOOTSTRAP"])
    await producer.start()
    try:
        while True:
            try:
                await publish_unpublished(client.order, producer)
            except Exception as exc:  # worker boundary: contain poison batch, keep relaying
                print(f"relay batch failed (continues): {type(exc).__name__}: {exc}")
            await asyncio.sleep(POLL_SECONDS)
    finally:
        await producer.stop()
        client.close()


if __name__ == "__main__":
    asyncio.run(run_forever())
