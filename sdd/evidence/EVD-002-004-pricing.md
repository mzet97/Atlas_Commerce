# EVD-002-004 — TASK-002-013: cupons, impostos por região e multi-armazém (2026-11-03)

Status: PASS (suites + drills verdes na stack viva).

## Cupons (regras de pricing no order owner)
- `order/src/atlas_order/pricing.py` (puro): PERCENT (1..100) e FIXED,
  escopo de mercado opcional (`market_id`), mínimo de subtotal, desconto
  nunca acima do subtotal; matemática inteira (minor units).
- Gestão: `POST/GET /admin/coupons`, `POST /admin/coupons/{code}/deactivate`
  no order; `POST/GET /ops/coupons`, `POST /ops/coupons/{code}/deactivate`
  no Control — role `pricing_manager` + grant `market` quando escopado;
  403 auditado para fora de escopo (padrão command_channel).
- Carrinho: `POST /carts/{id}/coupon` (set/clear; 422 se desconhecido/
  inativo). Validade completa aplica na quote.

## Impostos por região
- Tabela code-level determinística (bps): BR 1550, US 875, UE 2100;
  mercado desconhecido → 0 (documentado + testado). Arredondamento floor.
- Quote/pedido carregam breakdown completo: `subtotal_minor`,
  `discount_minor`, `tax_minor`, `tax_rate_bps`, `market_id`,
  `coupon_code`, `total_minor = subtotal - discount + tax`.
- Um mercado e uma moeda por carrinho (422 em mix) — regras regionais
  exigem jurisdição única.

## Multi-armazém
- Ordem de reserva consulta a disponibilidade por armazém
  (`GET /positions/{wh}/{sku}`) na lista `WAREHOUSES` (env; compose:
  `W1,W2`) e reserva no primeiro com hint suficiente (INV-CQRS-001:
  hint não autoriza — a reserva revalida atômica no owner).
- Sem estoque em nenhum armazém → REJECTED (409) sem cobrança.

## PSP fake: gatilhos migram de amount para cartão
O drill de cupom quebrou o C03 do `checkout_e2e.py`: os gatilhos de
timeout/unknown eram por VALOR (666/999) e o total agora carrega imposto.
Fix semântico no simulador: cartão `6666` = autorização lenta (12s),
cartão `9999` = nunca responde (reconciliação resolve), `0002` = decline.
Acoplamento documento-valor eliminado.

## Evidência executada (stack viva pós-rebuild determinístico)
- Suites: order **39 passed** (pricing 10, warehouses 4, api/projection/
  domain restantes), control **24 passed** (order_ops 3: pam cria cupom
  201; cara.catalog 403 + `admin_actions` denied; list/deactivate),
  psp-fake 6, payment 21, catalog 14, offers 12, inventory 13 —
  ruff limpo em todos.
- Drill `coupon_e2e.py` → **ALL PASS (8 checks)**: cupom via Control
  (pam.pricing), produto/oferta BR com estoque SOMENTE em W2, quote com
  breakdown 10000-1000+1395=10395, checkout CONFIRMED, intent cobrado
  10395, posição W2 comprometida (10→9), W1 intocado (404).
- Drill `checkout_e2e.py` → **ALL PASS (12 checks)** com totais
  tax-aware (C01 384, C03 769) e C03 via cartão 6666 (PENDING →
  reconciliação → CONFIRMED).
- `fulfill_e2e.py` → **ALL PASS (5 checks)** (regressão M6 intacta).
- Playwright → **8 passed** (regressão M5/M7 intacta).
