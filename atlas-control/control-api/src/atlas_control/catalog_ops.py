"""catalog_ops module: authenticated command channel to the Catalog owner.

Control validates identity + role and writes its own audit row, then
forwards the command. It NEVER touches the owner's Mongo collections.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from .command_channel import allowed, authenticate, forward, gate, json_out

router = APIRouter(prefix="/ops")
CATALOG_EDITOR = "catalog_editor"


class CreateProductIn(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    title: dict[str, str]
    category_id: str | None = None
    idempotency_key: str
    correlation_id: str


class PublishProductIn(BaseModel):
    model_config = ConfigDict(frozen=True)

    expected_version: int
    correlation_id: str


@router.post("/products", status_code=201)
async def create_product(body: CreateProductIn, request: Request) -> JSONResponse:
    """Operator creates a DRAFT via the owner. Others get 403 + audit."""
    token = await gate(request, "catalog:create", None, body.correlation_id, CATALOG_EDITOR)
    status, created = await forward(
        request,
        "catalog_url",
        "POST",
        "/products",
        {
            "title": body.title,
            "category_id": body.category_id,
            "idempotency_key": body.idempotency_key,
            "correlation_id": body.correlation_id,
        },
        token,
    )
    if status == 201:
        await allowed(
            request, token, "catalog:create", str(created.get("id", "")), body.correlation_id
        )
    return json_out(created, status)


@router.post("/products/{product_id}/publish")
async def publish_product(
    product_id: str, body: PublishProductIn, request: Request
) -> JSONResponse:
    """Operator publishes via the owner. Others get 403 + audit."""
    token = await gate(request, "catalog:publish", product_id, body.correlation_id, CATALOG_EDITOR)
    status, result = await forward(
        request,
        "catalog_url",
        "POST",
        f"/products/{product_id}/publish",
        {"expected_version": body.expected_version, "correlation_id": body.correlation_id},
        token,
    )
    if status == 200:
        await allowed(request, token, "catalog:publish", product_id, body.correlation_id)
    return json_out(result, status)


@router.get("/products/{product_id}")
async def get_product(product_id: str, request: Request) -> JSONResponse:
    """Any authenticated operator may read the owner view (no mutation)."""
    token = await authenticate(request)
    status, result = await forward(
        request, "catalog_url", "GET", f"/products/{product_id}", {}, token
    )
    return json_out(result, status)
