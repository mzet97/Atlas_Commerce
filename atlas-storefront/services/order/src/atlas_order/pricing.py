"""Checkout pricing rules: coupons + regional taxes (pure, integer math).

Money is minor units only. Tax is floor-rounded per market rate (bps).
Coupon kinds: PERCENT (value = whole percent) and FIXED (value = minor
units off). Regional tax table is code-level and deterministic; a market
without a rule taxes at 0 (documented behavior, tested).
"""

from __future__ import annotations

from typing import Final

TAX_RATE_BPS: Final[dict[str, int]] = {"BR": 1550, "US": 875, "UE": 2100}


class CouponRejected(Exception):
    """Quote refuses the coupon; the API maps this to 422."""


def validate_coupon(
    coupon: dict[str, object] | None,
    code: str | None,
    subtotal_minor: int,
    market_id: str,
) -> int:
    """Discount the quote gets; 0 without a code, else validated rules."""
    if code is None:
        return 0
    if coupon is None or not bool(coupon.get("active", False)):
        raise CouponRejected("unknown or inactive coupon")
    kind = str(coupon.get("kind", ""))
    value = int(coupon.get("value", 0))  # type: ignore[arg-type]
    coupon_market = coupon.get("market_id")
    if coupon_market is not None and str(coupon_market) != market_id:
        raise CouponRejected("coupon not valid for this market")
    min_subtotal = int(coupon.get("min_subtotal_minor", 0))  # type: ignore[arg-type]
    if subtotal_minor < min_subtotal:
        raise CouponRejected("subtotal below coupon minimum")
    if kind == "PERCENT":
        if not 1 <= value <= 100:
            raise CouponRejected("percent value out of range")
        discount = subtotal_minor * value // 100
    elif kind == "FIXED":
        if value <= 0:
            raise CouponRejected("fixed value must be positive")
        discount = value
    else:
        raise CouponRejected("unknown coupon kind")
    return min(discount, subtotal_minor)


def tax_minor(market_id: str, taxable_minor: int) -> tuple[int, int]:
    """(rate_bps, tax_minor) for the market; floor rounding, never negative."""
    rate = TAX_RATE_BPS.get(market_id, 0)
    return rate, max(taxable_minor, 0) * rate // 10000
