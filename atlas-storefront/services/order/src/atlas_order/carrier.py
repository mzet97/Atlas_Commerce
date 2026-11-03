"""Carrier adapter (M6, fake): deterministic shipping labels for drills.

A real carrier integration owns rates/pickups; this adapter is the seam.
Labels are deterministic per order (idempotent ship replays keep the same
tracking code) and carry no PII.
"""

from __future__ import annotations


def issue_label(order_id: str) -> str:
    """Fake tracking code for the order; stable across ship replays."""
    return f"ATLAS-{order_id}"
