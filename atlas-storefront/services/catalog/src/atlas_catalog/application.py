"""Application layer: commands + handlers over repository ports."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .domain import ConcurrencyError, CorrelationId, IdempotencyKey, NotFound, Product, ProductId


@dataclass(frozen=True, slots=True)
class CreateProduct:
    product_id: ProductId
    title: dict[str, str]
    category_id: str | None
    idempotency_key: IdempotencyKey
    correlation_id: CorrelationId


@dataclass(frozen=True, slots=True)
class PublishProduct:
    product_id: ProductId
    expected_version: int
    correlation_id: CorrelationId


class ProductRepository(Protocol):
    async def create(self, product: Product) -> Product:
        """Insert aggregate + outbox in ONE local transaction.

        Same idempotency_key returns the existing aggregate (no duplicate).
        """
        ...

    async def get(self, product_id: ProductId) -> Product: ...

    async def publish(
        self, product_id: ProductId, expected_version: int, correlation_id: CorrelationId
    ) -> Product:
        """Conditional version bump + outbox in ONE local transaction."""
        ...


async def handle_create(cmd: CreateProduct, repo: ProductRepository) -> Product:
    """Create a DRAFT product; idempotent on idempotency_key."""
    return await repo.create(
        Product.create(
            cmd.product_id,
            cmd.title,
            cmd.category_id,
            cmd.idempotency_key,
            cmd.correlation_id,
        )
    )


async def handle_publish(cmd: PublishProduct, repo: ProductRepository) -> Product:
    """Publish, or raise NotFound | ConcurrencyError | InvalidTransition."""
    return await repo.publish(cmd.product_id, cmd.expected_version, cmd.correlation_id)


__all__ = [
    "ConcurrencyError",
    "CorrelationId",
    "CreateProduct",
    "IdempotencyKey",
    "NotFound",
    "ProductRepository",
    "PublishProduct",
    "handle_create",
    "handle_publish",
]
