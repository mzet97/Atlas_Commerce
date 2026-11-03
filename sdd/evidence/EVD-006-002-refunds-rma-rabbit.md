# EVD-003-003 / EVD-006-002 — Refunds, RMA, dispatcher RabbitMQ (2026-11-03)

Status: PASS (suites + drill na stack viva; gates M3-refund e M6 fechados).

## Refunds (payment owner + PSP fake)
- PSP fake `POST /refunds`: idempotente por chave, limitado ao cobrado
  menos o já devolvido (parcial suportado); 409 em cobrança não aprovada.
- Payment owner: `POST /intents/{id}/refunds` — verdade do PSP PRIMEIRO,
  depois a transição auditável (`PaymentRefunded` no outbox; INV-006:
  registro append, nunca edit); `refunded_minor` acumula no intent e na
  projeção (migração 005). Replays convergem no resultado armazenado
  (curto-circuito antes do PSP). Refund em DECLINED → 409.
- Control `payments:refund` (finance_analyst): abaixo de
  APPROVAL_THRESHOLD_MINOR um analista executa (auditado); acima, filing
  202 com payload na aprovação (`resource_type`, JSONB 005) e um analista
  DIFERENTE aprova para executar; self-approve 403.

## Cancelamento de CONFIRMED com perna de dinheiro
- `cancel_confirmed` (domínio): CONFIRMED -> CANCELLED exige refund ANTES
  da transição; SHIPPED recusado (caminho do RMA). PENDING segue com
  release de reservas.

## Returns/RMA (order owner + Control)
- `POST /returns` (customer), aprovação operacional via
  `POST /ops/fulfillment/returns/{id}/approve` (fulfillment_operator,
  auditada): refund parcial (linhas da RMA) + restock via ledger
  (`/positions/adjust` +delta, reason rma); REQUESTED -> APPROVED único
  (replay 409); INV-006 respeitado (movimentos append).

## Dispatcher RabbitMQ real (ADR-0003 fechada na prática)
- `atlas_order.notifier`: lote `notification_queue` (FOR UPDATE SKIP
  LOCKED) -> fila quorum `atlas.notifications` (mensagens persistentes,
  default exchange) -> `SENT`. Compose: `rabbit` (rabbitmq:4.1-management,
  healthcheck) + `notification-dispatcher` (perfil m3).
- Evidência de drenagem: 45 QUEUED -> 45 SENT na PG; 45 mensagens na
  `atlas.notifications` (rabbitmqctl list_queues).
- Correções registradas: aio-pika publica na default exchange
  (`queue.publish` não existe); comando explícito do worker no compose
  (imagem sem CMD).

## Carrier (fake)
- `carrier.py`:`issue_label(order_id)` → `ATLAS-<order_id>` determinístico
  (ship idempotente mantém o código); vai no payload de `OrderShipped`.
  O adapter é a costura para integração real de transportadora.

## Evidência executada
- Suites: payment 26, order 47, control 31 — ruff limpo.
- Drill `refund_e2e.py` → **ALL PASS (7 checks)**: R01 refund direto
  (abaixo do threshold) com projeção; R02 cancel CONFIRMED via gina com
  refund prévio (intent refunded == total); R03 RMA aprovada via gina
  com refund parcial (900) + restock W1 (on_hand 5, ledger).
- Drills de regressão: checkout 12/12, coupon 8/8, fulfill 5/5.
