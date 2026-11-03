# EVD-003-002 — M3 increment-2: checkout saga (Order owner)

Status: PASS (observed outputs only; commands + results below).

## Scope
Order owner (`:8106`): Cart → Quote (TTL, breakdown) → Checkout saga
Reserve → Order(PENDING) → Authorize → CONFIRMED, com compensação
(ADR-0007). Sem ACID global; legs idempotentes por construção.

## Serviços (profile `m3`, 26 containers Up)
- `atlas-base-order-api-1` Up `:8106`, relay + projector Up
- `GET /health` → `{"status":"ok"}`
- Migração `003_order_projection.sql` aplicada via `psql`
  (`orders_view`, `order_lines`, `processed_events`)

## Suites (observado)
- `services/order`: `ruff` clean + `18 passed`
  (domínio 7, API 9, projeção 2)
- Sem regressão: payment 21, psp-fake 6, control 12 (inalterados após
  o increment-1; fonte única de verdade reaproveitada, sem reedição)

## Drill E2E `services/order/e2e/checkout_e2e.py` (stdlib, ao vivo)
Setup real via Control (`cara.catalog`): produto → publish → oferta
333 (`offer-d6c59180a5a3`) → 20 un. W1 → quote converge da read model.
- `ALL PASS (12 checks)`: C01 approve → 201 CONFIRMED, estoque 20→19,
  intent AUTHORIZED; C02 `10002` → 402 CANCELLED, estoque de volta a 19;
  C03 qty2 = 666 (timeout 12s > client) → 202 PENDING → reconcile →
  CONFIRMED; C04 mesma chave → mesmo pedido + mesmo intent (1 charge);
  C05 mesma quote, outra chave → 422 `already consumed`.

## Invariantes (observado no banco)
- Owner mongo `order.orders`: 4 pedidos (3 CONFIRMED + 1 CANCELLED),
  zero PENDING preso.
- PG `orders_view`: 3 CONFIRMED + 1 CANCELLED, `order_lines`: 4 —
  converge exato com o owner após relay ao vivo.
- Nota honesta: 3 fileiras PENDING residuais dos testes unitários
  (mesma PG `atlas` compartilhada) foram removidas por `order_id`
  antes da contagem final; mesmo padrão documentado em EVD-003-001.

## Decisões registradas
- Single-use da quote é gate atômico do repositório (`place_with_quote`:
  claim + insert + outbox na mesma txn), não do agregado — replay com
  a mesma chave alcança o vencedor em vez de 422.
- A saga é a única transicionadora das próprias reservas: 409 em
  confirm/release = convergência de tentativa anterior, nunca erro.
- Preço vem de `available_offer_view` (CQRS); checkout nunca relê preço.

## Fora do escopo (OPEN, sem ornamento)
- Cart/quote sem auth (mesmo padrão das slices M2; hardening é M4),
  múltiplos armazéns, frete/imposto, estorno, L0-L4 (`NOT_MEASURED`),
  remotes/commits (3 repos seguem uncommitted, aguardando revisão).
