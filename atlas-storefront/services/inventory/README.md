# atlas-inventory — Stock authority (M2 slice)

Owns `StockPosition` per (warehouse, sku), the append-only `StockMovement`
ledger and `Reservation`s. `available = on_hand - reserved - safety_stock`
is enforced by conditional atomic updates; Redis/Postgres/Kafka never
decide availability (INV-001, INV-002).

Endpoints: `POST /positions/receive`, `POST /positions/adjust`,
`POST /reservations` (idempotent), `POST /reservations/{id}/confirm`,
`POST /reservations/{id}/release`, `GET /positions/{wh}/{sku}`.
Events: `StockAdjusted`, `StockReserved`, `ReservationConfirmed`,
`ReservationReleased`.
