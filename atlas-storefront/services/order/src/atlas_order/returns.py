"""Returns/RMA (M6): customer requests, operator approves, money follows.

Lifecycle: REQUESTED -> APPROVED | REJECTED. Approval is the human gate:
the owner refunds the order's payment intent and restocks the returned
lines (inventory adjust +delta, reason 'rma'), then emits ReturnApproved
+ RefundRequested for the audit trail. INV-006: refund/restock append
ledger movements, never in-place edits.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, NewType, TypedDict

ReturnId = NewType("ReturnId", str)

REQUESTED: Final = "REQUESTED"
APPROVED: Final = "APPROVED"
REJECTED: Final = "REJECTED"


class ReturnLine(TypedDict):
    sku_id: str
    quantity: int
    price_minor: int


class ReturnError(Exception):
    """Base for returns failures (API maps to 422)."""


class AlreadyDecided(ReturnError):
    """The RMA is past REQUESTED; approval is single-shot (API maps to 409)."""


class NotRefundable(ReturnError):
    """Order state or payment state refuses the refund leg."""


@dataclass(slots=True)
class ReturnRequest:
    id: ReturnId
    version: int
    order_id: str
    status: str
    lines: list[ReturnLine]
    reason: str
    created_at: str
    decided_at: str | None = None

    def refund_total_minor(self) -> int:
        return sum(line["quantity"] * line["price_minor"] for line in self.lines)


def create_return(
    order_id: str, lines: list[ReturnLine], reason: str
) -> ReturnRequest:
    """Open a customer return request (no money moves here)."""
    if not lines:
        raise ReturnError("return needs at least one line")
    for line in lines:
        if line["quantity"] <= 0:
            raise ReturnError("quantity must be positive")
    return ReturnRequest(
        id=ReturnId(f"rma-{uuid.uuid4().hex[:12]}"),
        version=1,
        order_id=order_id,
        status=REQUESTED,
        lines=lines,
        reason=reason,
        created_at=datetime.now(UTC).isoformat(),
    )


def apply_approval(
    request: ReturnRequest, approved: bool, decided_at: str
) -> ReturnRequest:
    """REQUESTED -> APPROVED|REJECTED exactly once (idempotent replays out)."""
    if request.status != REQUESTED:
        raise AlreadyDecided(f"return already {request.status.lower()}")
    request.status = APPROVED if approved else REJECTED
    request.version += 1
    request.decided_at = decided_at
    return request
