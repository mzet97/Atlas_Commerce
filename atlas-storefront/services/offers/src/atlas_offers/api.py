"""HTTP boundary: parse untrusted JSON into typed commands (Pydantic v2)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict

from . import domain
from .application import (
    DeactivateOffer,
    PublishOffer,
    UpdatePrice,
    handle_deactivate,
    handle_publish,
    handle_update_price,
)
from .domain import CorrelationId, IdempotencyKey, OfferId, SkuId
from .mongo_repo import MongoOfferRepository


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create the owner-side client per running loop; close on shutdown."""
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    repo = MongoOfferRepository(client, os.getenv("OFFERS_DB", "offers"))
    await repo.ensure_indexes()
    app.state.repo = repo
    try:
        yield
    finally:
        client.close()


app = FastAPI(title="atlas-offers", lifespan=lifespan)


def _repo(request: Request) -> MongoOfferRepository:
    # Boundary narrow: app.state is framework-untyped; parse once here.
    repo = request.app.state.repo
    assert isinstance(repo, MongoOfferRepository)
    return repo


class PublishOfferIn(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    sku_id: str
    seller_id: str
    market_id: str
    channel: str
    currency: str
    price_minor: int
    idempotency_key: str
    correlation_id: str


class UpdatePriceIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_version: int
    price_minor: int
    correlation_id: str


class DeactivateOfferIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_version: int
    correlation_id: str


def _offer_body(
    offer_id: OfferId, status: str, version: int, price_minor: int
) -> dict[str, str | int]:
    return {"id": offer_id, "status": status, "version": version, "price_minor": price_minor}


@app.exception_handler(domain.NotFound)
async def _not_found(_request: Request, exc: domain.NotFound) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=404)


@app.exception_handler(domain.ValidationError)
async def _invalid(_request: Request, exc: domain.ValidationError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(domain.ConcurrencyError)
async def _conflict(_request: Request, exc: domain.ConcurrencyError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(domain.InvalidTransition)
async def _transition(_request: Request, exc: domain.InvalidTransition) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(domain.OfferConflict)
async def _overlap(_request: Request, exc: domain.OfferConflict) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(domain.WriteConflict)
async def _write_conflict(_request: Request, exc: domain.WriteConflict) -> JSONResponse:
    return JSONResponse({"detail": f"{exc} (safe to retry)"}, status_code=409)


@app.post("/offers", status_code=201)
async def publish_offer(body: PublishOfferIn, request: Request) -> dict[str, str | int]:
    """Publish a new ACTIVE offer. Overlap with an ACTIVE sibling -> 409."""
    offer = await handle_publish(
        PublishOffer(
            offer_id=OfferId(MongoOfferRepository.new_id()),
            sku_id=SkuId(body.sku_id),
            seller_id=body.seller_id,
            market_id=body.market_id,
            channel=body.channel,
            currency=body.currency,
            price_minor=body.price_minor,
            idempotency_key=IdempotencyKey(body.idempotency_key),
            correlation_id=CorrelationId(body.correlation_id),
        ),
        _repo(request),
    )
    return _offer_body(offer.id, offer.status, offer.version, offer.price_minor)


@app.post("/offers/{offer_id}/price")
async def update_price(
    offer_id: str, body: UpdatePriceIn, request: Request
) -> dict[str, str | int]:
    """ACTIVE-only price change. Stale version -> 409."""
    offer = await handle_update_price(
        UpdatePrice(
            offer_id=OfferId(offer_id),
            expected_version=body.expected_version,
            price_minor=body.price_minor,
            correlation_id=CorrelationId(body.correlation_id),
        ),
        _repo(request),
    )
    return _offer_body(offer.id, offer.status, offer.version, offer.price_minor)


@app.post("/offers/{offer_id}/deactivate")
async def deactivate_offer(
    offer_id: str, body: DeactivateOfferIn, request: Request
) -> dict[str, str | int]:
    """ACTIVE -> INACTIVE. Stale version or already inactive -> 409."""
    offer = await handle_deactivate(
        DeactivateOffer(
            offer_id=OfferId(offer_id),
            expected_version=body.expected_version,
            correlation_id=CorrelationId(body.correlation_id),
        ),
        _repo(request),
    )
    return _offer_body(offer.id, offer.status, offer.version, offer.price_minor)


@app.get("/offers/{offer_id}")
async def get_offer(offer_id: str, request: Request) -> dict[str, str | int | None]:
    """Owner-side read. NEVER authoritative for checkout (INV-CQRS-001)."""
    offer = await _repo(request).get(OfferId(offer_id))
    return {
        "id": offer.id,
        "status": offer.status,
        "version": offer.version,
        "sku_id": offer.sku_id,
        "seller_id": offer.seller_id,
        "market_id": offer.market_id,
        "channel": offer.channel,
        "currency": offer.currency,
        "price_minor": offer.price_minor,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
