# atlas-order — M3 checkout saga owner (ADR-0007)

Cart → Quote (versioned, TTL, breakdown) → Checkout saga:

`Reserve → Order(PENDING) → Authorize → CONFIRMED`,
with compensation on every failing leg. No global ACID.

## Legs and compensation

1. **Reserve** (inventory): one reservation per quote line, idempotent on
   `order_id + sku`. Shortage → order REJECTED, held legs released.
2. **Order(PENDING)**: persisted before money moves; idempotent on checkout
   key (replay returns the winner, never re-drives the saga).
3. **Authorize** (payment): APPROVED → confirm reservations + CONFIRMED;
   DECLINED → release reservations + CANCELLED (HTTP 402);
   UNKNOWN/timeout → order stays PENDING, resolved ONLY by
   `POST /orders/{id}/reconcile` (payment truth, never a re-charge).

Prices come from the `available_offer_view` read model (CQRS: owner Mongo
is never the price authority). Money in minor units, no PAN/CVV.
