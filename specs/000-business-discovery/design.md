# SPEC-000 design — modelos, ownership, ADRs, falhas

## Bounded contexts e owners (doc 02, diagrama 00)
Catalog, Offer/Pricing, Inventory, Search (read owner), Cart, Checkout/Saga,
Order, Payment, Fulfillment, Returns, Reviews, Customer, Communications,
AI Assistant, Control (approvals/audit/cases), Analytics (read models).

## Fronteiras de escrita
- Mongo por service DB: `catalog.products`, `offers.offers`,
  `inventory.positions/movements/reservations`, `orders.orders`,
  `payments.intents`, `checkout.sessions`, `control.approvals` (doc 04 §3).
- PostgreSQL: 10 projeções (`catalog_product_search`,
  `available_offer_view`, `customer_order_summary`, `order_detail_view`,
  `inventory_admin_view`, `payments_reconciliation_view`,
  `admin_audit_search`, `funnel_metrics_hourly`) + `projection_offsets` +
  `processed_events` (doc 04 §4).
- Pipeline: comando → validação/policy → Mongo+outbox (mesma transação,
  replica set obrigatório) → CDC → Kafka (chave por agregado) → workers
  idempotentes → PG → Redis cache-aside (diagrama 09).

## Checkout e compensações (docs 03–04, diagrama 10)
Reserva→Pedido(PENDING)→Autorização; ramos: autorizado (200 Confirmed),
recusado (402 + libera reserva), incerto (202 PENDING + reconciliação).
Saga persistida com idempotency key, retry com jitter, circuit breaker,
DLQ/quarentena, reconciliação periódica. Falhas: 2 compradores/1 unidade,
PSP timeout, reserva expirada pós-pagamento, consumer morto pós-commit PG,
outbox backlog, evento antigo após novo, cancelamento em fulfillment,
aprovação revogada.

## ADRs (todas PROPOSED)
ADR-001 microserviços vs monólito; ADR-002 CQRS Mongo/PG; ADR-003
Kafka+RabitMQ; ADR-004 outbox transacional; ADR-005 IA human-approved;
ADR-006 Control sem rewrite; ADR-007 (nova, OPEN-02/03) ordem da saga.

## Compatibilidade/migração
Envelope evento versionado (`event_id`, `aggregate_id/version`,
`occurred_at`, `schema_version`, `correlation/causation_id`,
`traceparent`); contratos N/N-1; rebuild de projeções por replay.
