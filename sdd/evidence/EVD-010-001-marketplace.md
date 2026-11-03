# EVD-010-001 — M10 marketplace 3P completo (2026-11-03)

Status: PASS (gates: zero violação de tenant, settlement correto,
regressão 1P verde).

## Tenancy (zero violação)
- Registro de tenants: `POST /ops/sellers` (iam_admin) → tabela `sellers`
  no DB control (migração 006); lista para operadores autenticados.
- Publish 3P: seller_operator + grants `(seller, seller-acme)` E
  `(market, BR)` — cross-tenant → **403 + linha auditada denied**
  (drill M03; test_cross_tenant_is_403_audited).
- 1P inalterado: `seller_id=atlas` continua no gate catalog_editor+market
  (regressão test_onep_regression_unaffected + drills).

## Oferta concorrente + buybox
- Unicidade por (sku, seller, market, channel) já no aggregate Offer —
  dois sellers ativos no MESMO SKU provados no drill (1P 1200 + 3P 790).
- Buybox na leitura: `ORDER BY price_minor ASC` na LATERAL do storefront —
  home exibiu R$ 7,90 (3P) sobre o 1P (drill M04).

## Split settlement
- `POST /ops/finance/settlements/{order_id}` (finance_analyst): lê
  projeções (orders_view+order_lines+available_offer_view), grava
  relatório auditável no DB control (migração 006): bruto 1580 /
  comissão 158 (10% bps env) / líquido 1422 por seller; replay
  idempotente (drill M05 + M05b). Owners mantêm estado canônico
  (ADR-0006); payouts fora de banda.

## Antifraude velocity
- >5 intents AUTHORIZED/cliente/60s → DECLINED `FRAUD_VELOCITY` sem
  tocar o PSP (test_velocity provado; `authorized_at` persistido).
- Evidência incidental ao vivo: os drills compartilhavam o customer
  "e2e" e a 6ª intent foi recusada por velocity na stack real — regra
  funcionando em produção-like (drill corrigido para customer único,
  como usuários reais).

## Provas executadas
- Drill `marketplace_e2e.py` → **ALL PASS (7 checks)** (M01..M05b).
- Suites: control **35 passed** (+4 marketplace), payment **27 passed**
  (+1 velocity); catálogo 14, offers 12, inventory 13, order 47,
  psp-fake 6, assistant 5 — regressão 1P 100% verde (ruff limpo).
- Drills de regressão: checkout 12/12, coupon 8/8, fulfill 5/5,
  refund 7/7 (seller_ids normalizados para 1P conforme o novo gate).
- SPEC-010: 9 artefatos em `specs/010-marketplace-3p/` (tasks 001-006
  PASS, com traceability REQ-MKT-001..005).
