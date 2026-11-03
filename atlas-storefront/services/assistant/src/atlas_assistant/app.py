"""HTTP boundary for the assistant (M7): one turn, one grounded reply."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from .graph import run_turn
from .tools import FORBIDDEN_TOOL_NAMES, TOOL_NAMES


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(title="atlas-assistant", lifespan=lifespan)


class ChatIn(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    message: str
    customer_id: str = "anon"


@app.post("/assistant/chat")
async def chat(body: ChatIn) -> JSONResponse:
    """Run the doc-08 graph; tools read-only, human gate at checkout."""
    result = await run_turn(body.message, body.customer_id)
    return JSONResponse(
        {
            "reply": result.get("reply", ""),
            "injection": result.get("injection", False),
            "proposals": result.get("proposals", []),
            "checkout_url": result.get("checkout_url"),
            "tools_available": list(TOOL_NAMES),
        }
    )


@app.get("/tools")
async def list_tools() -> JSONResponse:
    """Contract surface: only the read-only allowlist exists. Auditors can
    assert the forbidden set is absent (ADR-0005)."""
    return JSONResponse(
        {"allowed": list(TOOL_NAMES), "forbidden_absent": list(FORBIDDEN_TOOL_NAMES)}
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
