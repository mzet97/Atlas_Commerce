"""pricing_ops module: priced command channel to the Offer owner.

Requires catalog_editor AND a market grant for the offer's market.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from .command_channel import ScopeGrant, allowed, forward, gate, json_out

router = APIRouter(prefix="/ops/offers")
CATALOG_EDITOR = "catalog_editor"
SELLER_OPERATOR = "seller_operator"


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


def _market_scope(market_id: str) -> list[ScopeGrant]:
    return [ScopeGrant(scope_type="market", scope_id=market_id)]


@router.post("", status_code=201)
async def publish_offer(body: PublishOfferIn, request: Request) -> JSONResponse:
    """Operator publishes an offer. Others 403 + audit.

    M10 tenancy: 1P (seller_id == atlas) keeps the catalog_editor+market
    gate; a 3P seller_id requires seller_operator + a (seller, id) grant —
    publishing for a foreign tenant is 403 + audited (zero violation).
    """
    if body.seller_id == "atlas":
        token = await gate(
            request,
            "offer:publish",
            None,
            body.correlation_id,
            CATALOG_EDITOR,
            _market_scope(body.market_id),
        )
    else:
        token = await gate(
            request,
            "offer:publish",
            None,
            body.correlation_id,
            SELLER_OPERATOR,
            [ScopeGrant(scope_type="seller", scope_id=body.seller_id),
             ScopeGrant(scope_type="market", scope_id=body.market_id)],
        )
    status, offer = await forward(
        request,
        "offers_url",
        "POST",
        "/offers",
        {
            "sku_id": body.sku_id,
            "seller_id": body.seller_id,
            "market_id": body.market_id,
            "channel": body.channel,
            "currency": body.currency,
            "price_minor": body.price_minor,
            "idempotency_key": body.idempotency_key,
            "correlation_id": body.correlation_id,
        },
        token,
    )
    if status == 201:
        await allowed(
            request, token, "offer:publish", str(offer.get("id", "")), body.correlation_id
        )
    return json_out(offer, status)


@router.post("/{offer_id}/price")
async def update_price(offer_id: str, body: UpdatePriceIn, request: Request) -> JSONResponse:
    """Operator reprices. Market scope re-checked on every mutation."""
    market = await _offer_market(request, offer_id)
    token = await gate(
        request, "offer:price", offer_id, body.correlation_id, CATALOG_EDITOR, _market_scope(market)
    )
    status, offer = await forward(
        request,
        "offers_url",
        "POST",
        f"/offers/{offer_id}/price",
        {
            "expected_version": body.expected_version,
            "price_minor": body.price_minor,
            "correlation_id": body.correlation_id,
        },
        token,
    )
    if status == 200:
        await allowed(request, token, "offer:price", offer_id, body.correlation_id)
    return json_out(offer, status)


async def _offer_market(request: Request, offer_id: str) -> str:
    """Read the owner view to learn the market before authorizing the write."""
    from .command_channel import authenticate

    token = await authenticate(request)
    status, offer = await forward(request, "offers_url", "GET", f"/offers/{offer_id}", {}, token)
    if status != 200 or not isinstance(offer.get("market_id"), str):
        return "__unknown__"
    return offer["market_id"]


@router.post("/{offer_id}/deactivate")
async def deactivate_offer(
    offer_id: str, body: DeactivateOfferIn, request: Request
) -> JSONResponse:
    """Operator deactivates. Market scope re-checked on every mutation."""
    market = await _offer_market(request, offer_id)
    token = await gate(
        request,
        "offer:deactivate",
        offer_id,
        body.correlation_id,
        CATALOG_EDITOR,
        _market_scope(market),
    )
    status, offer = await forward(
        request,
        "offers_url",
        "POST",
        f"/offers/{offer_id}/deactivate",
        {"expected_version": body.expected_version, "correlation_id": body.correlation_id},
        token,
    )
    if status == 200:
        await allowed(request, token, "offer:deactivate", offer_id, body.correlation_id)
    return json_out(offer, status)
