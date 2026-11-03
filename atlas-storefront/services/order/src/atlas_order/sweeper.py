"""PENDING expiration sweeper (M4): stale checkouts die with compensation.

Isolated module so the documented catch-all (a poison order must never
kill the sweeper) lives beside the only code that needs it.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta

import httpx

from . import domain
from .application import DownstreamError, _drive, _release_all
from .mongo_repo import MongoOrderRepository


def _pending_ttl_seconds() -> int:
    return int(os.getenv("ORDER_PENDING_TTL_SECONDS", "1800"))


async def expire_pending(repo: MongoOrderRepository) -> list[str]:
    """Cancel PENDING orders past TTL: payment truth attempt, then release.

    Returns cancelled order ids. One sweep pass; the loop calls it forever.
    """
    cutoff = (
        datetime.now(UTC) - timedelta(seconds=_pending_ttl_seconds())
    ).isoformat()
    cancelled: list[str] = []
    for order in await repo.list_pending_created_before(cutoff):
        if order.payment_intent_id is None:
            # Never authorized: drive once — the quote may still settle.
            try:
                async with (
                    httpx.AsyncClient(
                        base_url=os.getenv(
                            "INVENTORY_API_URL", "http://localhost:8104"
                        ),
                        timeout=15,
                    ) as http_inv,
                    httpx.AsyncClient(
                        base_url=os.getenv(
                            "PAYMENT_API_URL", "http://localhost:8105"
                        ),
                        timeout=30,
                    ) as http_pay,
                ):
                    order = await _drive(repo, http_inv, http_pay, order, "expiry")
            except DownstreamError:
                pass  # fall through to cancellation below if still PENDING
            if order.status != domain.PENDING:
                continue
        try:
            async with httpx.AsyncClient(
                base_url=os.getenv("INVENTORY_API_URL", "http://localhost:8104"),
                timeout=15,
            ) as http_inv:
                await _release_all(http_inv, order, "expiry")
        except DownstreamError:
            continue  # next sweep retries; never cancel without release
        order.cancel("pending expired", domain.CorrelationId(f"expiry-{order.id}"))
        try:
            await repo.save_with_events(order)
        except domain.WriteConflict:
            continue  # a concurrent drive won the order
        cancelled.append(order.id)
    return cancelled


async def expire_pending_loop(repo: MongoOrderRepository) -> None:
    """Background sweeper (lifespan task): cancel stale PENDINGs forever."""
    while True:
        await asyncio.sleep(30)
        try:
            await expire_pending(repo)
        except Exception:
            continue  # a poisoned sweep must never kill the sweeper
