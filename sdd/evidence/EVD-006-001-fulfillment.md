# EVD-006-001 — M6 increment-1: fulfillment + fila de notificações

Status: PASS (observed outputs only; commands + results below).

## Escopo
`CONFIRMED -> SHIPPED` no owner via `POST /orders/{id}/ship`
(idempotente), comandado pelo Control (`fulfillment_operator`,
usuária `gina.fulfillment`). Fila `notification_queue` (PG) como
contrato de conteúdo: transporte RabbitMQ segue diferido.

## Prova (observado)
- order: `ruff` clean + `21 passed` (ship domínio + API: replay estável,
  PENDING → 409).
- control-api: `ruff` clean + `18 passed` (incl. `test_fulfillment.py`:
  customer → 403 + auditoria, operadora → SHIPPED via owner real).
- Migração `004_notification_queue.sql` aplicada.
- Drill `services/order/e2e/fulfill_e2e.py`: `ALL PASS (5 checks)` —
  setup próprio (produto→oferta→estoque→CONFIRMED), ship 200,
  replay mesma versão, customer 403, view SHIPPED.
- PG (observado): `orders_view` → `SHIPPED`; `notification_queue` →
  `OrderConfirmed|QUEUED` + `OrderShipped|QUEUED` p/ o pedido.

## Decisões registradas
- Ship é transição do owner; Control só comanda + audita (mesmo padrão
  das slices M2/M3). Replays retornam o estado sem republicar evento.
- `notification_queue` tem PK (order_id, event): redelivery do projetor
  nunca duplica conteúdo; `status` (QUEUED→SENT) pertence ao futuro
  dispatcher, não ao projetor.

## Fora do escopo (OPEN, sem ornamento)
- Devoluções/estorno (sem PSP refund), transportadora/rastreio,
  dispatcher RabbitMQ, expiração de PENDING, L0-L4 (`NOT_MEASURED`),
  remotes/commits (aguardando revisão do usuário).
