"""Append-only audit log. Control owns this data (never owner aggregates)."""

from __future__ import annotations

import asyncpg


async def log_action(
    pool: asyncpg.Pool,
    *,
    actor_sub: str,
    action: str,
    resource_type: str,
    resource_id: str | None,
    result: str,
    correlation_id: str,
) -> None:
    """One row per attempt, allowed AND denied. No updates, no deletes."""
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO admin_actions"
            "(actor_sub, action, resource_type, resource_id, result, correlation_id)"
            " VALUES ($1, $2, $3, $4, $5, $6)",
            actor_sub,
            action,
            resource_type,
            resource_id,
            result,
            correlation_id,
        )
